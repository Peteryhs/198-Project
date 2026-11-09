"""Reproduce compact HGB candidates; all training rows, subject-held-out folds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path('tmp/small-data.npz'))
    parser.add_argument('--leaves', type=int, default=7)
    parser.add_argument('--iterations', type=int, nargs='+', default=[50, 100, 200])
    parser.add_argument('--learning-rate', type=float, default=.15)
    parser.add_argument('--l2', type=float, default=0.)
    parser.add_argument('--kinds', nargs='+', default=['rep', 'window'])
    parser.add_argument('--features', type=int, nargs='+', help='predeclared input feature subset')
    parser.add_argument('--float32', action='store_true', help='fit and evaluate the deployment input precision')
    parser.add_argument('--out', type=Path, default=Path('tmp/boost-results.json'))
    args = parser.parse_args()
    data = dict(np.load(args.cache, allow_pickle=False))
    iterations = sorted(set(args.iterations))
    results = []
    all_predictions = {}
    for kind in args.kinds:
        X, row_y, row_subject = (data[f'{kind}_{key}'] for key in ('X', 'y', 'subject'))
        if args.features is not None:
            X = X[:, args.features]
        if args.float32:
            X = X.astype(np.float32)
        if kind == 'rep':
            y, subject, exercise = (data[f'series_{key}'] for key in ('y', 'subject', 'exercise'))
        else:
            y, subject, exercise = (data[f'window_{key}'] for key in ('y', 'subject', 'exercise'))
        predictions = {n: np.zeros(len(y), dtype=np.int8) for n in iterations}
        for s in np.unique(subject):
            test = subject == s
            train_rows = row_subject != s
            test_rows = row_subject == s
            clf = HistGradientBoostingClassifier(
                max_iter=iterations[0], max_leaf_nodes=args.leaves,
                learning_rate=args.learning_rate, l2_regularization=args.l2,
                early_stopping=False, random_state=0, warm_start=True)
            for n in iterations:
                clf.set_params(max_iter=n)
                clf.fit(X[train_rows], row_y[train_rows])
                p = clf.predict_proba(X[test_rows])[:, 1]
                if kind == 'rep':
                    lengths = np.diff(data['rep_starts'])[test]
                    starts = np.r_[0, np.cumsum(lengths)[:-1]]
                    p = np.add.reduceat(p, starts) / lengths
                predictions[n][test] = p >= .5
            print(kind, s, ' '.join(f'{n}:{np.mean(predictions[n][test] == y[test]):.4f}' for n in iterations), flush=True)
        for n in iterations:
            clf = HistGradientBoostingClassifier(
                max_iter=n, max_leaf_nodes=args.leaves,
                learning_rate=args.learning_rate, l2_regularization=args.l2,
                early_stopping=False, random_state=0)
            clf.fit(X, row_y)
            name = f'{kind}-hgb-l{args.leaves}-n{n}-lr{args.learning_rate}-l2{args.l2}'
            if args.features is not None:
                name += f'-f{len(args.features)}'
            if args.float32:
                name += '-float32'
            result = {
                'name': name, 'kind': kind,
                'params': {k: clf.get_params()[k] for k in ('max_iter', 'max_leaf_nodes', 'learning_rate', 'l2_regularization', 'early_stopping', 'random_state')},
                'accuracy': float(np.mean(predictions[n] == y)),
                'correct': int(np.sum(predictions[n] == y)), 'n': len(y),
                'per_exercise': {str(ex): {'accuracy': float(np.mean(predictions[n][exercise == ex] == y[exercise == ex])), 'n': int(np.sum(exercise == ex))} for ex in np.unique(exercise)},
                'nodes': int(sum(len(stage[0].nodes) for stage in clf._predictors)),
                'features': args.features,
                'input_precision': 'float32' if args.float32 else 'float64',
                'subjects': len(np.unique(subject)),
            }
            results.append(result)
            all_predictions[name] = predictions[n]
            args.out.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(clf, args.out.parent / (name + '.joblib'))
            args.out.write_text(json.dumps(results, indent=2) + '\n')
            np.savez_compressed(args.out.with_suffix('.npz'), **all_predictions)
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
