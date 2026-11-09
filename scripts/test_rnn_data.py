"""Causal cycle capture and phase 6 source parity checks."""
import csv
import json
import sys
from pathlib import Path

import numpy as np

from rnn_data import _Capture, _cache_read, _downsample, load_side
from streaming_pipeline import StreamExtractor
from paired_pipeline import aligned_pair
import paired_pipeline as pp

ROOT = Path(__file__).resolve().parents[1]


def main():
    cycle = np.arange(30, dtype=np.float32).reshape(5, 6)
    reduced = _downsample(cycle)
    assert np.array_equal(reduced, np.stack([cycle[:4].mean(0), cycle[4:].mean(0)]))
    t = np.arange(500) / 100
    signal = np.zeros((500, 10)); signal[:, 0] = t
    gap = signal.copy(); gap[250:, 0] += .2
    try:
        aligned_pair(gap, signal)
    except ValueError:
        pass
    else:
        raise AssertionError('timestamp gap was accepted')

    t = np.arange(2400) / 100
    x = np.tile((1 + .4 * np.sin(2 * np.pi * t / 2))[:, None], (1, 6)).astype(np.float32)
    with _Capture() as capture, StreamExtractor() as reference:
        seq, f = capture(x)
        expected = reference(x)
        assert len(seq) == len(f) == len(expected) == len(reference.ends)
        assert np.allclose(f, expected, atol=1e-6)
        assert all(len(c) == round(float(row[0]) * 100) for c, row in zip(seq, f))
        prefix = 1550
        short_seq, short_f = capture(x[:prefix])
        keep = reference.ends <= prefix
        assert np.array_equal(short_f, f[keep])
        assert len(short_seq) == keep.sum()
        assert all(np.array_equal(a, b) for a, b in zip(short_seq, [c for c, k in zip(seq, keep) if k]))
        assert len(capture(np.ones((2000, 6), np.float32))[1]) == 0
        assert capture.overflows > 0
        for bad in (np.zeros(6), np.zeros((2, 5)), np.full((2, 6), np.nan)):
            try:
                capture(bad)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid C input was accepted')

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data/phytmo/inertial/upper'
    for side in 'LR':
        data = load_side(root, side)
        cache = ROOT / 'data/phase6-rnn-cache' / f'{side}-{data["cache_key"]}.npz'
        cached = load_side(root, side, cache_path=cache)
        assert np.array_equal(cached['features'], data['features'])
        try:
            _cache_read(cache, side, data['raw_hashes'], data['pipeline_hashes'], 'stale-key')
        except ValueError:
            pass
        else:
            raise AssertionError('stale cache lineage was accepted')
        with (ROOT / 'model/paired-synchronized-causal' / side / 'predictions.csv').open() as f:
            accepted = list(csv.DictReader(f))
        assert data['names'] == [row['source'] for row in accepted]
        assert data['subs'].tolist() == [row['subject'] for row in accepted]
        assert data['exs'].tolist() == [row['exercise'] for row in accepted]
        assert data['y'].tolist() == [int(row['quality']) for row in accepted]
        assert sum(map(len, data['sequences'])) == len(data['features'])
        assert np.array_equal(data['durations'], data['features'][:, 0])
        report = json.loads((ROOT / 'model/paired-synchronized-causal' / side / 'results.json').read_text())
        assert len(data['names']) == report['series']
        assert len(data['features']) == report['cycles']
        with StreamExtractor() as extractor:
            bags, _, _, _, sources, _ = pp.collect(root, side, extractor)
        assert sources == data['names']
        assert [len(bag) for bag in bags] == [len(series) for series in data['sequences']]
        assert np.array_equal(np.concatenate(bags), data['features'])
        print(f'{side}: {len(data["names"])} sources, {len(data["features"])} cycles, '
              f'{sum(len(c) for s in data["sequences"] for c in s)} 25 Hz steps')
    print('C cycle capture, feature parity, partial-group retention and source parity passed')


if __name__ == '__main__':
    main()
