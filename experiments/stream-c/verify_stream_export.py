"""Replay every PHYTMO upper-body CSV through the C streaming segmenter.

Run from the repository root with the pinned environment:
    .venv/bin/python scripts/verify_stream_export.py
"""
from __future__ import annotations

import argparse
import ctypes
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import joblib
import numpy as np

from harness import parse_name, read_inertial, window_features
from reps import ACC, FS, find_peaks
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from train_small import FEATURES, REPO, ROOT


WRAPPER = r'''
#include "form_stream.h"
#include "form_rep.h"
#include <math.h>
#include <stddef.h>
static form_stream state;
size_t bridge_state_size(void) { return sizeof(state); }
void bridge_init(void) { form_stream_init(&state); }
float bridge_peak(void) { return state.peak_ema; }
int bridge_peak_initialized(void) { return state.peak_initialized; }
void bridge_set_peak(float peak, int initialized) {
    state.peak_ema = peak;
    state.peak_initialized = initialized != 0;
}
void bridge_push(float x, float y, float z) { form_stream_push(&state, x, y, z); }
int bridge_poll(float *x, float *p) { return form_stream_poll(&state, x, p); }
int bridge_active(void) { return state.active; }
int bridge_pending(void) { return state.pending; }
int bridge_error(void) { return state.error; }
int bridge_segment_length(void) { return state.segment_length; }
int bridge_max_segment_length(void) { return state.max_segment_length; }
int bridge_baseline_count(void) { return state.baseline_count; }
int bridge_sample_index(void) { return state.sample_index; }
int bridge_pending_start(void) { return state.pending_start; }
int bridge_pending_end(void) { return state.pending_end; }
int bridge_pending_forced(void) { return state.pending_forced; }
float bridge_predict(const float *x) { return form_rep_predict(x); }
'''


def compile_bridge(temp: Path, model_dir: Path):
    src = temp / 'stream_bridge.c'
    libpath = temp / 'stream_bridge.so'
    src.write_text(WRAPPER)
    command = ['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-pedantic', '-O2', '-fPIC', '-shared',
               '-I', str(model_dir), str(model_dir/'form_stream.c'), str(model_dir/'form_rep.c'),
               str(model_dir/'form_window.c'), str(src), '-lm', '-o', str(libpath)]
    subprocess.run(command, check=True)
    lib = ctypes.CDLL(str(libpath))
    for name in ('bridge_state_size', 'bridge_peak', 'bridge_peak_initialized', 'bridge_active',
                 'bridge_pending', 'bridge_error', 'bridge_segment_length', 'bridge_max_segment_length',
                 'bridge_baseline_count', 'bridge_sample_index', 'bridge_pending_start',
                 'bridge_pending_end', 'bridge_pending_forced'):
        getattr(lib, name).restype = ctypes.c_size_t if name == 'bridge_state_size' else ctypes.c_int
    lib.bridge_peak.restype = ctypes.c_float
    lib.bridge_set_peak.argtypes = [ctypes.c_float, ctypes.c_int]
    lib.bridge_push.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
    lib.bridge_poll.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
    lib.bridge_poll.restype = ctypes.c_int
    lib.bridge_predict.argtypes = [ctypes.POINTER(ctypes.c_float)]
    lib.bridge_predict.restype = ctypes.c_float
    return lib, command


def _poll(lib):
    row = (ctypes.c_float * 31)()
    p = ctypes.c_float()
    status = lib.bridge_poll(row, ctypes.byref(p))
    if status == 1:
        start, end = int(lib.bridge_pending_start()), int(lib.bridge_pending_end())
        return {'start': start, 'end': end, 'forced': bool(lib.bridge_pending_forced()),
                'features': np.frombuffer(row, dtype=np.float32).copy(), 'probability': float(p.value)}
    if status == -1:
        raise RuntimeError('C stream entered a sticky error state')
    return None


def replay(lib, sig: np.ndarray):
    """Push every row in order; don't append samples to close an active tail."""
    results = []
    samples = np.asarray(sig[:, ACC], dtype=np.float32)
    for row in samples:
        lib.bridge_push(float(row[0]), float(row[1]), float(row[2]))
        item = _poll(lib)
        if item is not None:
            results.append(item)
        if lib.bridge_error():
            raise RuntimeError('C stream entered a sticky error state')
    return results


def py_boundaries(sig: np.ndarray):
    peaks = find_peaks(sig)
    if len(peaks) < 2:
        return []
    bounds = np.r_[0, (peaks[1:] + peaks[:-1]) // 2, len(sig)].astype(int)
    return [{'start': int(a), 'end': int(b), 'features': np.r_[(b-a)/FS,
             window_features(sig[a:b, ACC][None, :, :])[0]].astype(np.float32)}
            for a, b in zip(bounds[:-1], bounds[1:]) if b-a >= 10]


def match_segments(reference, streamed, tolerance=50):
    """Greedy nearest-start matching, stable on equal-distance ties."""
    candidates = sorted((abs(a['start']-b['start']), i, j)
                        for i, a in enumerate(reference) for j, b in enumerate(streamed)
                        if abs(a['start']-b['start']) <= tolerance)
    used_ref, used_stream, pairs = set(), set(), []
    for offset, i, j in candidates:
        if i not in used_ref and j not in used_stream:
            used_ref.add(i); used_stream.add(j)
            pairs.append((i, j, offset))
    return sorted(pairs)


def all_csvs(root: Path, limit: int):
    paths = sorted(root.rglob('*.csv'))
    if limit and len(paths) > limit:
        if limit < 200:
            raise ValueError('--limit must be 0 or at least 200')
        paths = [paths[i] for i in np.linspace(0, len(paths)-1, limit, dtype=int)]
    return paths


def c_self_checks(lib):
    checks = {}
    lib.bridge_init()
    lib.bridge_push(float('nan'), 0.0, 0.0)
    checks['nonfinite_input_errors'] = bool(lib.bridge_error() and lib.bridge_poll(None, None) == -1)
    assert checks['nonfinite_input_errors']
    lib.bridge_init()
    for _ in range(650):
        lib.bridge_push(0.0, 0.0, 1.0)
        assert _poll(lib) is None
    checks['constant_signal_no_segments'] = not bool(lib.bridge_error())
    assert checks['constant_signal_no_segments']
    # Invalid model features must preserve the classifier's sentinel contract.
    invalid = (ctypes.c_float * 31)(); invalid[0] = float('inf')
    checks['model_nonfinite_sentinel'] = lib.bridge_predict(invalid) == -1.0
    assert checks['model_nonfinite_sentinel']
    # A brief pulse closes below the 120-sample minimum and produces no pending feature.
    lib.bridge_init()
    for v in ([1.0]*220 + [1.4]*8 + [1.0]*240):
        lib.bridge_push(0.0, 0.0, float(v)); _poll(lib)
    checks['minimum_length_discard'] = (int(lib.bridge_max_segment_length()) < 120 and
                                        not bool(lib.bridge_pending()) and not bool(lib.bridge_error()))
    assert checks['minimum_length_discard']
    # A long ramp followed by a plateau closes after the below-threshold deadband.
    lib.bridge_init()
    closed = None
    for v in [1.0+i*.01 for i in range(250)] + [3.49]*500:
        lib.bridge_push(0.0, 0.0, float(v))
        closed = _poll(lib)
        if closed: break
    checks['deadband_close'] = bool(closed and not closed['forced'] and closed['end']-closed['start'] >= 120)
    assert checks['deadband_close']
    # Sustained motion exercises the hard 500-sample cap and forced close.
    lib.bridge_init()
    closed = None
    for i in range(800):
        v = 1.0 + i*.01
        lib.bridge_push(0.0, 0.0, v)
        closed = _poll(lib)
        if closed:
            break
    checks['segment_cap_observed'] = bool(closed and closed['forced'] and closed['end']-closed['start'] == 500)
    assert checks['segment_cap_observed']
    # Leave a cap result unpolled, then the opposite ramp forces a second result.
    lib.bridge_init()
    lib.bridge_set_peak(0.0, 1)
    vals = [1.0+i*.01 for i in range(800)] + [8.99-i*.01 for i in range(800)]
    for v in vals:
        lib.bridge_push(0.0, 0.0, float(v))
        if lib.bridge_error(): break
    checks['unconsumed_result_errors'] = bool(lib.bridge_error())
    assert checks['unconsumed_result_errors']
    return checks


def verify(model_dir=REPO/'model/small', root=ROOT, limit=0):
    started = time.perf_counter()
    model_dir, root = Path(model_dir), Path(root)
    paths = all_csvs(root, limit)
    if not paths:
        raise ValueError(f'no CSV files under {root}')
    per_subject_peak = {}
    file_rows, all_offsets_start, all_offsets_end = [], [], []
    matched_features, same_boundary_features = [], []
    matched_python_rows, matched_stream_probabilities = [], []
    same_boundary_within_tolerance = []
    numerical_outliers = []
    valid_reference = valid_stream = matched = unfinished = 0
    max_occupancy = 0
    with tempfile.TemporaryDirectory(prefix='verify-stream-') as name:
        lib, command = compile_bridge(Path(name), model_dir)
        checks = c_self_checks(lib)
        sizeof_state = int(lib.bridge_state_size())
        for file_index, path in enumerate(paths, 1):
            rel = path.relative_to(root).as_posix()
            meta = parse_name(str(path))
            subject_match = re.match(r'^([A-E]\d{2})', path.name)
            subject = meta[0] if meta else (subject_match.group(1) if subject_match else path.parent.name)
            sig = read_inertial(str(path))
            if subject in per_subject_peak:
                peak, initialized = per_subject_peak[subject]
                lib.bridge_init()
                lib.bridge_set_peak(peak, initialized)
            else:
                lib.bridge_init()
            streamed = replay(lib, sig)
            per_subject_peak[subject] = (float(lib.bridge_peak()), int(lib.bridge_peak_initialized()))
            unfinished_file = bool(lib.bridge_active() and lib.bridge_segment_length())
            unfinished += int(unfinished_file)
            reference = py_boundaries(sig)
            valid_reference += len(reference)
            valid_stream += len(streamed)
            pairs = match_segments(reference, streamed)
            matched += len(pairs)
            offsets_s, offsets_e = [], []
            py_rows, c_rows = [], []
            for out in streamed:
                ref_same = np.r_[(out['end']-out['start'])/FS,
                    window_features(sig[out['start']:out['end'], ACC][None, :, :])[0]].astype(np.float32)
                deltas = np.abs(ref_same-out['features'])
                within = np.isclose(ref_same, out['features'], rtol=1e-3, atol=1e-3)
                same_boundary_features.extend(deltas)
                same_boundary_within_tolerance.extend(within)
                for slot in np.flatnonzero(~within):
                    numerical_outliers.append({'file': rel, 'start': out['start'], 'end': out['end'],
                        'feature': (['duration_s']+FEATURES)[slot], 'python': float(ref_same[slot]),
                        'c': float(out['features'][slot]), 'absolute_delta': float(deltas[slot])})
            for i, j, offset in pairs:
                ref, out = reference[i], streamed[j]
                offsets_s.append(out['start']-ref['start'])
                offsets_e.append(out['end']-ref['end'])
                all_offsets_start.append(out['start']-ref['start'])
                all_offsets_end.append(out['end']-ref['end'])
                py_rows.append(ref['features']); c_rows.append(out['features'])
                # Same Python interval features are the sklearn input for this C decision.
                matched_python_rows.append(ref['features'])
                matched_stream_probabilities.append(out['probability'])
            if py_rows:
                py_mat, c_mat = np.vstack(py_rows), np.vstack(c_rows)
                matched_features.extend(np.abs(py_mat-c_mat).ravel())
            max_occupancy = max(max_occupancy, int(lib.bridge_max_segment_length()))
            used_ref = {i for i, _, _ in pairs}
            used_stream = {j for _, j, _ in pairs}
            file_rows.append({'file': rel, 'subject': subject, 'calibration_file': meta is None,
                                  'exercise': meta[1] if meta else None, 'label': meta[3] if meta else None,
                                  'python_segments': len(reference), 'stream_segments': len(streamed),
                                  'matched': len(pairs), 'unfinished_at_eof': unfinished_file,
                                  'start_offsets_samples': offsets_s, 'end_offsets_samples': offsets_e,
                                  'forced_closures': sum(s['forced'] for s in streamed),
                                  'unmatched_python_bounds': [[r['start'], r['end']] for i, r in enumerate(reference) if i not in used_ref],
                                  'unmatched_stream_bounds': [[r['start'], r['end']] for j, r in enumerate(streamed) if j not in used_stream]})
            if file_index % 100 == 0:
                print(f'processed {file_index}/{len(paths)} CSV files', file=sys.stderr, flush=True)
        offline_model = joblib.load(model_dir/'form_rep.joblib')
        matched_probability_deltas, matched_verdict_agreements = [], []
        if matched_python_rows:
            x = np.ascontiguousarray(np.vstack(matched_python_rows), dtype=np.float32)
            offline_probs = offline_model.predict_proba(x)[:, 1]
            paired_c_probs = np.asarray(matched_stream_probabilities)
            matched_probability_deltas = np.abs(paired_c_probs-offline_probs)
            matched_verdict_agreements = (paired_c_probs >= .5) == (offline_probs >= .5)
        # Regression gate for both untouched classifiers and the existing deployed artifacts.
        from verify_small_export import verify as verify_golden_models
        with np.load(model_dir/'golden.npz', allow_pickle=False) as golden:
            golden_data = {'rep_X': golden['rep_X'], 'rep_starts': np.arange(len(golden['rep_X'])+1),
                           'window_X': golden['window_X']}
        golden_models = verify_golden_models(model_dir, golden_data)
        same_boundary_features = np.asarray(same_boundary_features, dtype=float)
        report = {
            'root': str(root.resolve()), 'csv_count': len(paths), 'all_csv_count': len(list(root.rglob('*.csv'))),
            'calibration_files': sum(r['calibration_file'] for r in file_rows),
            'labelled_files': sum(not r['calibration_file'] for r in file_rows),
            'limit': limit, 'elapsed_seconds': time.perf_counter()-started, 'compile_command': command,
            'protocol': {'python_reference': 'train_small.load_data boundary/feature formulas: >=2 scipy peaks; [0, integer midpoints, len]; retain length >=10. Replay includes calibration and <3-row recordings that training excludes.',
                         'stream': '100 Hz float32 accel samples; all CSVs sorted; per-subject peak EMA retained across files; segment state reset per recording',
                         'matching': 'greedy one-to-one nearest start, |delta start| <= 50 samples; ties by Python tuple order',
                         'EOF': 'no synthetic flush samples; active tail reported unfinished'},
            'segmentation': {'python_segments': valid_reference, 'stream_segments': valid_stream, 'matched': matched,
                             'python_match_rate': matched/valid_reference if valid_reference else None,
                             'stream_match_rate': matched/valid_stream if valid_stream else None,
                             'agreement': matched/max(valid_reference, valid_stream, 1),
                             'start_offset_samples': _summary(all_offsets_start), 'end_offset_samples': _summary(all_offsets_end),
                             'pooled_offset_samples': _summary(all_offsets_start+all_offsets_end),
                             'unmatched_python': valid_reference-matched, 'unmatched_stream': valid_stream-matched,
                             'forced_closures': sum(r['forced_closures'] for r in file_rows),
                             'unfinished_at_eof_files': unfinished},
            'calibration': {'files': sum(r['calibration_file'] for r in file_rows),
                            'python_segments': sum(r['python_segments'] for r in file_rows if r['calibration_file']),
                            'stream_segments': sum(r['stream_segments'] for r in file_rows if r['calibration_file']),
                            'included_in_adaptive_subject_replay': True, 'excluded_from_train_small_label_metrics': True},
            'same_boundary_feature_parity': {'segments': valid_stream,
                'stream_segments': valid_stream, 'rtol': 1e-3, 'atol': 1e-3,
                'max_abs_feature_delta': float(np.max(same_boundary_features)) if same_boundary_features.size else None,
                'mean_abs_feature_delta': float(np.mean(same_boundary_features)) if same_boundary_features.size else None,
                'median_abs_feature_delta': float(np.median(same_boundary_features)) if same_boundary_features.size else None,
                'within_tolerance_fraction': float(np.mean(same_boundary_within_tolerance)) if same_boundary_within_tolerance else None,
                'outside_tolerance_count': len(numerical_outliers), 'outliers': numerical_outliers,
                'matched_different_boundary_feature_delta_mean_abs': float(np.mean(matched_features)) if matched_features else None,
                'matched_different_boundary_feature_delta_median_abs': float(np.median(matched_features)) if matched_features else None,
                'matched_different_boundary_feature_delta_max_abs': float(np.max(matched_features)) if matched_features else None,
                'matched_different_boundary_feature_delta_count': len(matched_features),
                'note': 'same-boundary feature check recomputes Python features over each exact C [start,end) interval; detector disagreement is reported separately'},
            'matched_verdicts': {'matched_pairs': matched,
                'agreement_at_0_5': float(np.mean(matched_verdict_agreements)) if len(matched_verdict_agreements) else None,
                'mean_abs_probability_delta_joblib_vs_stream': float(np.mean(matched_probability_deltas)) if len(matched_probability_deltas) else None,
                'max_abs_probability_delta_joblib_vs_stream': float(np.max(matched_probability_deltas)) if len(matched_probability_deltas) else None},
            'memory': {'sizeof_form_stream_bytes': sizeof_state,
                       'peak_reserved_state_bytes': sizeof_state,
                       'peak_state_plus_output_bytes': sizeof_state + 32*ctypes.sizeof(ctypes.c_float),
                       'sample_storage_bytes': 500*3*ctypes.sizeof(ctypes.c_float),
                       'baseline_storage_bytes': 201*ctypes.sizeof(ctypes.c_float),
                       'pending_feature_bytes': 31*ctypes.sizeof(ctypes.c_float), 'fixed_state_includes_all_fields': True,
                       'max_segment_samples_observed': max_occupancy,
                       'scope': 'fixed allocation equals peak reserved state; plus-output includes out_x[31] and p_wrong. Stack/library/interrupt high-water and model flash excluded.'},
            'self_checks': checks, 'golden_model_regression': golden_models, 'files': file_rows,
        }
        return report


def _summary(values):
    a = np.asarray(values, dtype=float)
    if not len(a):
        return {'count': 0, 'mean': None, 'mean_abs': None, 'median': None, 'median_abs': None, 'p90_abs': None, 'p95_abs': None, 'max_abs': None}
    return {'count': len(a), 'mean': float(a.mean()), 'mean_abs': float(np.abs(a).mean()),
            'median': float(np.median(a)), 'median_abs': float(np.median(np.abs(a))), 'p90_abs': float(np.percentile(np.abs(a), 90)),
            'p95_abs': float(np.percentile(np.abs(a), 95)),
            'max_abs': float(np.abs(a).max())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--model-dir', type=Path, default=REPO/'model/small')
    ap.add_argument('--limit', type=int, default=0, help='0=all; otherwise evenly spaced fixed subset (>=200)')
    ap.add_argument('--report', type=Path, help='write complete JSON report here')
    args = ap.parse_args()
    if args.limit < 0 or 0 < args.limit < 200:
        ap.error('--limit must be 0 or at least 200')
    report = verify(args.model_dir, args.root, args.limit)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    seg = report['segmentation']; feat = report['same_boundary_feature_parity']; verdict = report['matched_verdicts']
    print('| Measure | Result |\n|---|---:|')
    print(f"| CSV files | {report['csv_count']} |")
    print(f"| Python / streamed segments | {seg['python_segments']} / {seg['stream_segments']} |")
    print(f"| One-to-one matches (50-sample start tolerance) | {seg['matched']} ({seg['agreement']:.3f}) |")
    print(f"| Unmatched Python / stream segments | {seg['unmatched_python']} / {seg['unmatched_stream']} |")
    for name in ('start', 'end', 'pooled'):
        v = seg[f'{name}_offset_samples']
        print(f"| {name.title()} boundary offset median / p90 absolute | {v['median_abs']} / {v['p90_abs']} samples |")
    print(f"| Same-boundary feature mean / median / max absolute delta | {feat['mean_abs_feature_delta']} / {feat['median_abs_feature_delta']} / {feat['max_abs_feature_delta']} |")
    print(f"| Same-boundary features within rtol=1e-3, atol=1e-3 | {feat['within_tolerance_fraction']} |")
    print(f"| Matched different-boundary feature mean / median / max abs delta | {feat['matched_different_boundary_feature_delta_mean_abs']} / {feat['matched_different_boundary_feature_delta_median_abs']} / {feat['matched_different_boundary_feature_delta_max_abs']} |")
    print(f"| Matched segment verdict agreement (Python joblib vs C stream) | {verdict['agreement_at_0_5']} |")
    print(f"| Matched mean absolute probability delta (joblib vs C) | {verdict['mean_abs_probability_delta_joblib_vs_stream']} |")
    print(f"| Unfinished EOF tails | {seg['unfinished_at_eof_files']} |")
    print(f"| sizeof(form_stream); maximum samples observed | {report['memory']['sizeof_form_stream_bytes']} bytes; {report['memory']['max_segment_samples_observed']} |")
    print(f"| Peak reserved state / state + output bytes (stack excluded) | {report['memory']['peak_reserved_state_bytes']} / {report['memory']['peak_state_plus_output_bytes']} |")
    print(f"| Elapsed seconds | {report['elapsed_seconds']:.3f} |")
    print('\n'+json.dumps({k: report[k] for k in ('self_checks', 'memory')}, indent=2))


if __name__ == '__main__':
    main()
