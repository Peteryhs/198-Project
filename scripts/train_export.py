"""Train and export the two models behind the results table.

Exports two artefacts, both trained on all 30 volunteers (the deployable fit, not the
leave-one-subject-out evaluation):

  form-window-rf.joblib   series verdict from a 3 s sliding window's summary features
  form-rep-rf.joblib      series verdict from per-repetition features, averaged over the repetitions

The accuracies quoted in metadata.json are the LOSO numbers measured elsewhere; the shipped fit is
trained on everybody, so its own training accuracy is optimistic. Both numbers are recorded so no
one has to guess which is which.

Run: uv run --locked python train_export.py
"""

from __future__ import annotations

import json
import os

import numpy as np

from harness import CHANNEL_SETS, COLS, parse_name, read_inertial, window_features, windows
from reps import FS, find_peaks

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "data/inertial/upper")
OUT = os.path.join(HERE, "repo-docs/model")
ACC = [COLS.index(c) for c in CHANNEL_SETS["acc"]]

WINDOW = 300          # 3 s
OVERLAP = 0.5
REP_STATS = ["mean", "std", "min", "max", "range", "rms", "skew", "kurtosis", "energy", "zcr"]


def load_windows() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X, y, sub = [], [], []
    for dirpath, _, files in os.walk(ROOT):
        for f in sorted(files):
            if not f.endswith(".csv"):
                continue
            path = os.path.join(dirpath, f)
            meta = parse_name(path)
            if meta is None:
                continue
            subject, _ex, _side, label, _series = meta
            w = windows(read_inertial(path)[:, ACC], WINDOW, OVERLAP)
            if len(w) == 0:
                continue
            X.append(window_features(w))
            y.append(np.full(len(w), label))
            sub.append(np.full(len(w), subject))
    return np.vstack(X), np.concatenate(y), np.concatenate(sub)


def load_reps() -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
    bags, y, sub = [], [], []
    for dirpath, _, files in os.walk(ROOT):
        for f in sorted(files):
            if not f.endswith(".csv"):
                continue
            path = os.path.join(dirpath, f)
            meta = parse_name(path)
            if meta is None:
                continue
            subject, _ex, _side, label, _series = meta
            sig = read_inertial(path)
            peaks = find_peaks(sig)
            if len(peaks) < 2:
                continue
            bounds = [0] + list((peaks[1:] + peaks[:-1]) // 2) + [len(sig)]
            rows = []
            for a, b in zip(bounds[:-1], bounds[1:]):
                seg = sig[a:b, ACC]
                if len(seg) < 10:
                    continue
                rows.append(np.concatenate([[len(seg) / FS], window_features(seg[None, :, :])[0]]))
            if len(rows) < 3:
                continue
            bags.append(np.vstack(rows))
            y.append(label)
            sub.append(subject)
    return bags, np.asarray(y), np.asarray(sub)


def fit_rf(n: int, leaf: int, depth: int):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_estimators=n, min_samples_leaf=leaf, max_depth=depth,
                                  n_jobs=-1, random_state=0)


def main() -> None:
    import joblib
    from sklearn.metrics import accuracy_score

    os.makedirs(OUT, exist_ok=True)

    # ---- window model ----
    Xw, yw, subw = load_windows()
    clf_w = fit_rf(80, 8, 14).fit(Xw, yw)
    print(f"window: {len(Xw)} rows, train acc {(clf_w.predict(Xw) == yw).mean():.3f}")

    # ---- repetition model ----
    bags, yr, subr = load_reps()
    Xr = np.vstack(bags)
    lens = np.array([len(b) for b in bags])
    rep_y = np.repeat(yr, lens)
    clf_r = fit_rf(80, 8, 14).fit(Xr, rep_y)
    print(f"reps: {len(Xr)} rows, {len(bags)} series")

    # honest LOSO for the repetition model, mean pooling over the bag
    pred = np.empty(len(bags), dtype=int)
    starts = np.concatenate([[0], np.cumsum(lens)])
    for s in sorted(set(subr)):
        te = subr == s
        tr = ~te
        tr_rows = np.concatenate([np.arange(starts[i], starts[i + 1]) for i in np.where(tr)[0]])
        m = fit_rf(80, 8, 14).fit(Xr[tr_rows], rep_y[tr_rows])
        for i in np.where(te)[0]:
            p = m.predict_proba(Xr[starts[i]:starts[i + 1]])[:, 1]
            pred[i] = int(p.mean() >= 0.5)
    loso_rep = float(accuracy_score(yr, pred))
    print(f"repetition model LOSO accuracy: {loso_rep:.3f}")

    joblib.dump(clf_w, os.path.join(OUT, "form-window-rf.joblib"), compress=3)
    joblib.dump(clf_r, os.path.join(OUT, "form-rep-rf.joblib"), compress=3)

    meta = {
        "created": "2026-11-06",
        "library": "scikit-learn RandomForestClassifier",
        "hyperparameters": {"n_estimators": 80, "min_samples_leaf": 8, "max_depth": 14,
                            "random_state": 0},
        "input_contract": {
            "sampling_hz": 100,
            "sensor_channels": ["accel_x", "accel_y", "accel_z"],
            "units": "g",
            "window_model": {
                "file": "form-window-rf.joblib",
                "window_samples": WINDOW,
                "overlap": OVERLAP,
                "features_per_axis": REP_STATS,
                "n_features": int(Xw.shape[1]),
                "labels": {"0": "correct", "1": "wrong"},
            },
            "rep_model": {
                "file": "form-rep-rf.joblib",
                "features_per_axis": REP_STATS,
                "n_features": int(Xr.shape[1] - 1) + 1,
                "feature_0": "repetition duration in seconds",
                "pooling": "mean of per-repetition probabilities gives the series verdict",
                "labels": {"0": "correct", "1": "wrong"},
            },
        },
        "evaluation": {
            "protocol": "leave-one-subject-out over 30 volunteers",
            "chance_floor": 0.500,
            "window_model_loso_accuracy": 0.809,
            "rep_model_loso_accuracy": round(loso_rep, 3),
            "note": "the shipped fits are trained on all 30 subjects, so their training accuracy "
                    "is optimistic; quote the LOSO numbers, not the training fit",
        },
        "provenance": {
            "dataset": "PHYTMO, Zenodo doi 10.5281/zenodo.6319979, CC-BY-4.0",
            "thresholds": "repetitions detected with scipy.signal.find_peaks, 1.2 s minimum "
                          "distance, prominence 0.35 x 90th percentile of the detrended magnitude",
        },
    }
    with open(os.path.join(OUT, "metadata.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

    for fn in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, fn)
        print(f"  {fn:26s} {os.path.getsize(p):>10,} B")


if __name__ == "__main__":
    main()
