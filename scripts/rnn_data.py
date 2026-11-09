"""Extract causal C detector cycles and their matching six-channel sequences."""
from __future__ import annotations

import ctypes
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import paired_pipeline as pp

ROOT = Path(__file__).resolve().parents[1]


class _Capture:
    """Run the accepted C detector and copy each ready cycle before it resets n."""
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        tmp = Path(self.temp.name)
        wrapper = tmp / 'capture.c'
        wrapper.write_text(
            '#include "paired_stream.h"\n'
            'int replay(const float *x,unsigned n,float *features,float *seq,unsigned *lens,unsigned *overflow){\n'
            ' PairStream s={0}; unsigned ready=0; float f[61];\n'
            ' for(unsigned i=0;i<n;i++){unsigned before=s.n;\n'
            '  int r=stream_push(&s,i*10,x+i*6,f);\n'
            '  if(r==1){unsigned m=before==STREAM_CAP?1:before+1;\n'
            '   for(unsigned k=0;k<61;k++)features[ready*61+k]=f[k];\n'
            '   for(unsigned j=0;j<m*6;j++)seq[ready*STREAM_CAP*6+j]=((float*)s.samples)[j];\n'
            '   lens[ready++]=m;}} *overflow=s.overflows; return ready;}\n')
        so = tmp / 'capture.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-I', str(ROOT / 'model/streaming'),
                        str(wrapper), str(ROOT / 'model/streaming/paired_stream.c'),
                        '-lm', '-o', str(so)], check=True)
        self.lib = ctypes.CDLL(str(so))
        self.ptr = ctypes.POINTER(ctypes.c_float)
        self.uptr = ctypes.POINTER(ctypes.c_uint)
        self.lib.replay.argtypes = [self.ptr, ctypes.c_uint, self.ptr, self.ptr, self.uptr, self.uptr]
        self.lib.replay.restype = ctypes.c_int

    def __call__(self, x):
        x = np.asarray(x, dtype=np.float32)
        if x.ndim != 2 or x.shape[1] != 6 or not np.isfinite(x).all():
            raise ValueError('C capture expects a finite N×6 matrix')
        x = np.ascontiguousarray(np.clip(x, -3, 3))
        cap = len(x) // 120 + 2
        f = np.empty((cap, 61), np.float32)
        seq = np.empty((cap, 600, 6), np.float32)
        lens = np.empty(cap, np.uint32)
        overflow = ctypes.c_uint()
        n = self.lib.replay(x.ctypes.data_as(self.ptr), len(x), f.ctypes.data_as(self.ptr),
                            seq.ctypes.data_as(self.ptr), lens.ctypes.data_as(self.uptr),
                            ctypes.byref(overflow))
        self.overflows = overflow.value
        return [seq[i, :int(m)].copy() for i, m in enumerate(lens[:n])], f[:n].copy()

    def close(self):
        self.temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _downsample(cycle):
    # Non-overlapping causal four-sample means; retain the final partial group.
    return np.asarray([cycle[i:i + 4].mean(axis=0) for i in range(0, len(cycle), 4)],
                      dtype=np.float32)


def _pack(sequences):
    cycle_offsets = [0]
    flat = []
    for series in sequences:
        for cycle in series:
            flat.append(cycle)
            cycle_offsets.append(cycle_offsets[-1] + len(cycle))
    series_offsets = np.cumsum([0] + [len(x) for x in sequences], dtype=np.int64)
    packed = np.concatenate(flat) if flat else np.empty((0, 6), np.float32)
    return packed, np.asarray(cycle_offsets), series_offsets


def _unpack(packed, cycle_offsets, series_offsets):
    cycles = [packed[a:b].copy() for a, b in zip(cycle_offsets[:-1], cycle_offsets[1:])]
    return [[cycles[i] for i in range(a, b)] for a, b in zip(series_offsets[:-1], series_offsets[1:])]


def _pipeline_digests():
    files = [Path(__file__), ROOT / 'scripts/paired_pipeline.py',
             ROOT / 'model/streaming/paired_stream.c', ROOT / 'model/streaming/paired_stream.h']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def _cache_read(path, side, raw_hashes, pipeline_hashes, cache_key):
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z['meta']))
        if (meta.get('side') != side or meta.get('raw_hashes') != raw_hashes or
                meta.get('pipeline_hashes') != pipeline_hashes or meta.get('cache_key') != cache_key):
            raise ValueError(f'stale or mismatched RNN cache: {path}')
        return dict(sequences=_unpack(z['samples'], z['cycle_offsets'], z['series_offsets']),
                    features=z['features'].copy(), durations=z['durations'].copy(),
                    y=z['y'].copy(), subs=z['subs'].copy(), exs=z['exs'].copy(),
                    names=meta['names'], rejected=meta['rejected'], raw_hashes=raw_hashes,
                    pipeline_hashes=pipeline_hashes, cache_key=cache_key, side=side)


def _write_manifest(data):
    path = ROOT / 'docs/runs/phase6-rnn' / f'data-{data["side"]}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {k: data[k] for k in ('side', 'names', 'rejected', 'raw_hashes',
                                      'pipeline_hashes', 'cache_key')}
    manifest.update(series=len(data['names']), cycles=len(data['features']),
                    cache='data/phase6-rnn-cache',
                    sequence='causal non-overlapping four-sample means; final partial group retained')
    path.write_text(json.dumps(manifest, indent=2) + '\n')


def load_side(root, side, cache_path=None):
    """Return series bags, matching C features, labels, source names, rejects and hashes."""
    root = Path(root)
    if side not in {'L', 'R'}:
        raise ValueError("side must be 'L' or 'R'")
    rows = list(pp.records(root, side))
    digests = {}
    for p, _, _, _ in rows:
        q = p.parent.parent / f'{side}forearm' / p.name
        digests[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        if q.exists():
            digests[q.relative_to(root).as_posix()] = hashlib.sha256(q.read_bytes()).hexdigest()
    pipeline_hashes = _pipeline_digests()
    lineage = dict(raw_hashes=digests, pipeline_hashes=pipeline_hashes, side=side)
    cache_key = hashlib.sha256(json.dumps(lineage, sort_keys=True).encode()).hexdigest()
    if cache_path is None:
        cache_path = ROOT / 'data/phase6-rnn-cache' / f'{side}-{cache_key}.npz'
    else:
        cache_path = Path(cache_path)
    if cache_path.exists():
        result = _cache_read(cache_path, side, digests, pipeline_hashes, cache_key)
        _write_manifest(result)
        return result

    sequences, features, durations, y, subs, exs, names, rejected = [], [], [], [], [], [], [], []
    capture = _Capture()
    try:
        for p, meta, x, error in rows:
            name = p.relative_to(root).as_posix()
            if error:
                rejected.append({'source': name, 'reason': error})
                continue
            cycles, f = capture(np.clip(x, -3, 3))
            if len(f) < 3:
                rejected.append({'source': name, 'reason': 'fewer than 3 detected cycles'})
                continue
            sequences.append([_downsample(c) for c in cycles])
            features.append(f)
            durations.append(f[:, 0].copy())
            y.append(meta[3]); subs.append(meta[0]); exs.append(meta[1]); names.append(name)
    finally:
        capture.close()
    if len(set(subs)) != 30:
        raise ValueError(f'LOSO requires 30 subjects, got {len(set(subs))}')
    result = dict(sequences=sequences, features=np.concatenate(features),
                  durations=np.concatenate(durations), y=np.asarray(y), subs=np.asarray(subs),
                  exs=np.asarray(exs), names=names, rejected=rejected,
                  raw_hashes=digests, pipeline_hashes=pipeline_hashes,
                  cache_key=cache_key, side=side)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    packed, cycle_offsets, series_offsets = _pack(sequences)
    np.savez_compressed(cache_path, samples=packed, cycle_offsets=cycle_offsets,
                        series_offsets=series_offsets, features=result['features'],
                        durations=result['durations'], y=result['y'], subs=result['subs'],
                        exs=result['exs'], meta=json.dumps(dict(names=names, rejected=rejected,
                                                                raw_hashes=digests,
                                                                pipeline_hashes=pipeline_hashes,
                                                                cache_key=cache_key, side=side)))
    _write_manifest(result)
    return result
