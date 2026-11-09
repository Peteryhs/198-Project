"""Compact tree-family LOSO sweep on train_small's reproducible feature cache."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier


CANDIDATES = {
    "rf12d6": ("rf", 12, 6),
    "rf24d6": ("rf", 24, 6),
    "rf12d7": ("rf", 12, 7),
    "rf24d7": ("rf", 24, 7),
    "rf12d8": ("rf", 12, 8),
    "rf16d8": ("rf", 16, 8),
    "rf24d8": ("rf", 24, 8),
    "rf8d9": ("rf", 8, 9),
    "rf12d9": ("rf", 12, 9),
    "rf8d10": ("rf", 8, 10),
    "et24d7": ("et", 24, 7),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=Path("tmp/small-data.npz"))
    ap.add_argument("--output", type=Path, default=Path("tmp/forest-results.json"))
    ap.add_argument("--candidates", nargs="+", choices=CANDIDATES, default=list(CANDIDATES))
    ap.add_argument("--modes", nargs="+", choices=("rep", "window"), default=["rep", "window"])
    ap.add_argument("--features", choices=("all", "no_redundant"), default="all",
                    help="no_redundant removes range/rms/energy, retaining the public feature indices")
    ap.add_argument("--compare-probabilities", type=Path,
                    help="compare a stored repetition prediction archive against the rerun logistic baseline")
    ap.add_argument("--baselines", type=Path, default=Path("docs/runs/small-model/baselines.npz"))
    args = ap.parse_args()
    if args.compare_probabilities:
        from scipy.stats import binomtest
        with np.load(args.compare_probabilities, allow_pickle=False) as predictions:
            y, probability = predictions["y"], predictions["probability"]
        with np.load(args.baselines, allow_pickle=False) as baselines:
            baseline = baselines["rep_logreg"] >= .5
        forest = probability >= .5
        assert len(forest) == len(baseline) == len(y)
        a = int(np.sum((forest == y) & (baseline != y)))
        b = int(np.sum((forest != y) & (baseline == y)))
        result = dict(forest_accuracy=float(np.mean(forest == y)),
                      logreg_accuracy=float(np.mean(baseline == y)),
                      accuracy_edge_points=float(np.mean(forest == y)-np.mean(baseline == y))*100,
                      forest_only_correct=a, logreg_only_correct=b,
                      mcnemar_exact_p=float(binomtest(a, a+b).pvalue) if a+b else 1.)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return
    z = np.load(args.cache, allow_pickle=False)
    results = json.loads(args.output.read_text()) if args.output.exists() else {}
    for mode in args.modes:
        X = z[f"{mode}_X"]
        selected = np.arange(X.shape[1])
        if args.features == "no_redundant":
            offset = int(mode == "rep")
            selected = np.r_[np.arange(offset), np.arange(12) + offset,
                             np.arange(18, 24) + offset, np.arange(27, 30) + offset]
            X = X[:, selected]
        y = z[f"{mode}_y"]
        subjects = z[f"{mode}_subject"]
        assert len(np.unique(subjects)) == 30
        ey = z["series_y"] if mode == "rep" else y
        esub = z["series_subject"] if mode == "rep" else subjects
        ex = z["series_exercise"] if mode == "rep" else z["window_exercise"]
        for name in args.candidates:
            start = time.monotonic()
            kind, n, depth = CANDIDATES[name]
            cls = RandomForestClassifier if kind == "rf" else ExtraTreesClassifier
            params = dict(n_estimators=n, max_depth=depth, min_samples_leaf=8,
                          n_jobs=3, random_state=0)
            p = np.empty(len(ey))
            folds = []
            for s in np.unique(subjects):
                te = subjects == s
                model = cls(**params).fit(X[~te], y[~te])
                prob = model.predict_proba(X[te])[:, 1]
                if mode == "rep":
                    lengths = np.diff(z["rep_starts"])[esub == s]
                    offsets = np.r_[0, np.cumsum(lengths)]
                    assert offsets[-1] == len(prob)
                    prob = np.add.reduceat(prob, offsets[:-1]) / lengths
                p[esub == s] = prob
                folds.append(sum(t.tree_.node_count for t in model.estimators_))
            model = cls(**params).fit(X, y)
            pred = p >= .5
            report = {"family": cls.__name__, "params": params, "feature_indices": selected.tolist(),
                      "accuracy": float(np.mean(pred == ey)),
                      "per_exercise": {e: float(np.mean(pred[ex == e] == ey[ex == e])) for e in np.unique(ex)},
                      "correct": int(np.sum(pred == ey)), "n": len(ey),
                      "subjects": len(np.unique(subjects)),
                      "full_fit_nodes": sum(t.tree_.node_count for t in model.estimators_),
                      "max_fold_nodes": max(folds), "seconds": time.monotonic() - start}
            key = f"{mode}_{name}"
            results[key] = report
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2) + "\n")
            np.savez_compressed(args.output.with_name(args.output.stem + "_" + key + ".npz"),
                                probability=p, y=ey, subject=esub, exercise=ex)
            print(key, json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
