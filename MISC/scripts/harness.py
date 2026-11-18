"""PHYTMO -> per-window exercise-quality classifier.

Reads the inertial CSVs, cuts sliding windows, extracts features, and scores
correct vs wrong executions with leave-one-subject-out cross validation.

Usage:
    python harness.py --root data/inertial/upper --exercises EAH EFE SQZ --channels acc
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass

from modelling_environment import check_environment
check_environment()

import numpy as np

FILE_RE = re.compile(r"^([A-E])(\d{2})([A-Z]{3})([LR]?)([01])_([12])\.csv$")

# Column order in every PHYTMO inertial CSV, verified against real files.
COLS = [
    "time",
    "gx", "gy", "gz",
    "ax", "ay", "az",
    "mx", "my", "mz",
]
CHANNEL_SETS = {
    "acc": ["ax", "ay", "az"],
    "accgyro": ["ax", "ay", "az", "gx", "gy", "gz"],
}


def read_inertial(path: str) -> np.ndarray:
    """Return an (n_samples, 10) array. Header is text, body is floats."""
    return np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)


def parse_name(path: str):
    """(subject, exercise, side, label, series) or None for Calib files."""
    m = FILE_RE.match(os.path.basename(path))
    if not m:
        return None
    group, num, ex, side, label, series = m.groups()
    return f"{group}{num}", ex, side, int(label), int(series)


def windows(sig: np.ndarray, size: int, overlap: float = 0.5) -> np.ndarray:
    """(n_windows, size, n_channels) view over the sliding windows."""
    shift = max(1, int(size * (1.0 - overlap)))
    if len(sig) < size:
        return np.empty((0, size, sig.shape[1]))
    n = (len(sig) - size) // shift + 1
    idx = np.arange(size)[None, :] + shift * np.arange(n)[:, None]
    return sig[idx]


def _kurtosis(x: np.ndarray, axis: int) -> np.ndarray:
    m = x.mean(axis=axis, keepdims=True)
    s = x.std(axis=axis, keepdims=True)
    s = np.where(s == 0, 1.0, s)
    return (((x - m) / s) ** 4).mean(axis=axis) - 3.0


def _skew(x: np.ndarray, axis: int) -> np.ndarray:
    m = x.mean(axis=axis, keepdims=True)
    s = x.std(axis=axis, keepdims=True)
    s = np.where(s == 0, 1.0, s)
    return (((x - m) / s) ** 3).mean(axis=axis)


def window_features(w: np.ndarray) -> np.ndarray:
    """w: (n_windows, size, n_channels) -> (n_windows, n_channels * 10)."""
    mean = w.mean(axis=1)
    std = w.std(axis=1)
    mn = w.min(axis=1)
    mx = w.max(axis=1)
    rng = mx - mn
    rms = np.sqrt((w ** 2).mean(axis=1))
    skew = _skew(w, 1)
    kurt = _kurtosis(w, 1)
    energy = (w ** 2).sum(axis=1) / w.shape[1]
    zcr = (np.diff(np.sign(w - mean[:, None, :]), axis=1) != 0).sum(axis=1) / w.shape[1]
    return np.concatenate(
        [mean, std, mn, mx, rng, rms, skew, kurt, energy, zcr], axis=1
    )


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    subject: np.ndarray
    exercise: np.ndarray
    source: np.ndarray


def build(root: str, exercises: set[str] | None, channels: str,
          size: int, overlap: float, cache: str = "cache") -> Dataset:
    cols = CHANNEL_SETS[channels]
    idx = [COLS.index(c) for c in cols]
    tag = "-".join(sorted(exercises)) if exercises else "all"
    key = os.path.join(cache, f"{channels}_{tag}_{size}_{overlap}.npz")
    if os.path.exists(key):
        z = np.load(key, allow_pickle=False)
        return Dataset(z["X"], z["y"], z["subject"], z["exercise"], z["source"])
    feats, labels, subjects, exs, srcs = [], [], [], [], []
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith(".csv"):
                continue
            path = os.path.join(dirpath, f)
            meta = parse_name(path)
            if meta is None:
                continue
            subject, ex, _side, label, _series = meta
            if exercises and ex not in exercises:
                continue
            sig = read_inertial(path)[:, idx]
            wins = windows(sig, size, overlap)
            if len(wins) == 0:
                continue
            feats.append(window_features(wins))
            labels.append(np.full(len(wins), label, dtype=np.int64))
            subjects.append(np.full(len(wins), subject))
            exs.append(np.full(len(wins), ex))
            srcs.append(np.full(len(wins), f))
    if not feats:
        raise SystemExit(f"no usable CSVs under {root}")
    ds = Dataset(
        X=np.vstack(feats),
        y=np.concatenate(labels),
        subject=np.concatenate(subjects),
        exercise=np.concatenate(exs),
        source=np.concatenate(srcs),
    )
    os.makedirs(cache, exist_ok=True)
    np.savez_compressed(key, X=ds.X, y=ds.y, subject=ds.subject,
                        exercise=ds.exercise, source=ds.source)
    return ds


def loso(ds: Dataset, channels: str, size: int, max_train: int = 20000) -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    rng = np.random.default_rng(0)

    def sub(X, y):
        """Cap the training rows: RBF SVM is O(n^2)+ and 94k rows x 30 folds is hours."""
        if len(X) <= max_train:
            return X, y
        idx = rng.choice(len(X), max_train, replace=False)
        return X[idx], y[idx]

    models = {
        "logreg": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, C=1.0)
        ),
        "rf": lambda: RandomForestClassifier(n_estimators=200, min_samples_leaf=5, n_jobs=-1,
                                            random_state=0),
        "hgb": lambda: HistGradientBoostingClassifier(max_iter=300, random_state=0),
    }
    # RBF SVM dropped: with C=10 it needs minutes per fit here, and 30 folds x 3 window
    # sizes is hours for a baseline that logreg/rf already bracket.
    capped = {"rf", "hgb"}

    subs = sorted(set(ds.subject))
    print(f"\n{size}-sample windows ({size/100:.0f} s), channels={channels}, "
          f"{len(ds.X)} windows, {len(subs)} subjects, "
          f"{len(set(ds.y))} classes, positive rate {ds.y.mean():.2f}", flush=True)

    for name, make in models.items():
        pred = np.empty_like(ds.y)
        for s in subs:
            te = ds.subject == s
            tr = ~te
            if len(set(ds.y[tr])) < 2 or len(set(ds.y[te])) < 2:
                pred[te] = ds.y[tr].mean() >= 0.5
                continue
            Xtr, ytr = sub(ds.X[tr], ds.y[tr]) if name in capped else (ds.X[tr], ds.y[tr])
            clf = make().fit(Xtr, ytr)
            pred[te] = clf.predict(ds.X[te])
        acc = accuracy_score(ds.y, pred)
        f1 = f1_score(ds.y, pred, zero_division=0)
        per_ex = "  ".join(
            f"{ex}:{accuracy_score(ds.y[ds.exercise == ex], pred[ds.exercise == ex]):.3f}"
            for ex in sorted(set(ds.exercise))
        )
        # A trivial "always the majority class" floor, per subject fold.
        floor = max(ds.y.mean(), 1 - ds.y.mean())
        print(f"  {name:8s} acc={acc:.3f}  f1={f1:.3f}  floor={floor:.3f}   {per_ex}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/inertial/upper")
    ap.add_argument("--exercises", nargs="*", default=["EAH", "EFE", "SQZ"])
    ap.add_argument("--channels", default="acc", choices=sorted(CHANNEL_SETS))
    ap.add_argument("--windows", nargs="*", type=int, default=[100, 200, 300])
    ap.add_argument("--overlap", type=float, default=0.5)
    args = ap.parse_args()

    exs = set(args.exercises) if args.exercises else None
    for size in args.windows:
        ds = build(args.root, exs, args.channels, size, args.overlap)
        loso(ds, args.channels, size)


if __name__ == "__main__":
    main()
