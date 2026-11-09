"""Compile C99 and compare exported probabilities with sklearn on real feature rows."""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import tempfile
from pathlib import Path

import joblib
import numpy as np

from train_small import CACHE, REPO, ROOT, load_data


def compile_library(directory, temp):
    library = Path(temp)/'small.so'
    command = ['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-pedantic', '-shared', '-fPIC', '-O2',
               str(directory/'form_rep.c'), str(directory/'form_window.c'), '-lm', '-o', str(library)]
    subprocess.run(command, check=True)
    return ctypes.CDLL(str(library)), command


def c_probabilities(lib, name, rows):
    predict = getattr(lib, name+'_predict')
    predict.argtypes = [ctypes.POINTER(ctypes.c_float)]
    predict.restype = ctypes.c_float
    rows = np.ascontiguousarray(rows, dtype=np.float32)
    return np.array([predict(row.ctypes.data_as(ctypes.POINTER(ctypes.c_float))) for row in rows])


def verify(directory, data, n=0):
    reports = {}
    with tempfile.TemporaryDirectory(prefix='verify-small-') as temp:
        lib, command = compile_library(directory, temp)
        for kind in ('rep', 'window'):
            rows = data[kind+'_X']
            indices = np.arange(len(rows)) if n == 0 or n >= len(rows) else np.linspace(0, len(rows)-1, n, dtype=int)
            rows = rows[indices].astype(np.float32)
            model = joblib.load(directory/f'form_{kind}.joblib')
            expected = model.predict_proba(rows)[:, 1]
            actual = c_probabilities(lib, 'form_'+kind, rows)
            deviation = float(np.max(np.abs(actual-expected)))
            agreement = float(np.mean((actual >= .5) == (expected >= .5)))
            report = {'real_rows': len(rows), 'max_absolute_probability_deviation': deviation,
                      'predicted_label_agreement': agreement, 'quantisation_step': None,
                      'storage': 'float32 thresholds and leaf values; thresholds rounded downward',
                      'reference_input': 'real extracted rows cast to the deployment float32 contract for both sklearn and C'}
            if kind == 'rep' and len(indices) == len(data['rep_X']):
                starts = data['rep_starts']
                pa = np.add.reduceat(actual, starts[:-1])/np.diff(starts)
                pe = np.add.reduceat(expected, starts[:-1])/np.diff(starts)
                report['series_predicted_label_agreement'] = float(np.mean((pa >= .5) == (pe >= .5)))
            assert deviation <= .001, report
            assert agreement == 1., report
            if 'series_predicted_label_agreement' in report:
                assert report['series_predicted_label_agreement'] == 1., report
            for invalid in (np.nan, np.inf, -np.inf):
                row = np.zeros((1, rows.shape[1])); row[0, 0] = invalid
                assert c_probabilities(lib, 'form_'+kind, row)[0] == -1.
            reports[kind] = report
    return {'models': reports, 'host_compile_command': command,
            'interpretation': 'Implementation parity only: per-repetition ground truth does not exist.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model-dir', type=Path, default=REPO/'model/small')
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--cache', type=Path, default=CACHE)
    ap.add_argument('--rows', type=int, default=0, help='0 means all real rows; otherwise evenly spaced N rows per model')
    ap.add_argument('--report', type=Path)
    args = ap.parse_args()
    if args.rows < 0:
        ap.error('--rows must be nonnegative')
    report = verify(args.model_dir, load_data(args.root, args.cache), args.rows)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
