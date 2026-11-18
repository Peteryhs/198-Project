"""Per-repetition scoring from per-file labels.

PHYTMO labels a whole series correct/incorrect; there is no per-repetition ground truth. This
trains on repetitions with the series label as a bag label and compares three things:

  window   the existing 3 s sliding-window baseline (harness.py), for reference
  reps     naive label propagation: every repetition inherits its file's label
  mil      multiple-instance learning: a linear scorer over repetition features, bag logit is
           the max over its repetitions, so only the most incriminating rep gets gradient

Bag-level accuracy is what we can measure honestly. Rep-level correctness needs hand-labelled
repetitions, which do not exist yet - so this reports bag accuracy only, plus how often the MIL
model's top-scoring repetition is the one that disagrees with its siblings (a sanity signal, not
a metric).

Run: python mil.py
"""

from __future__ import annotations

import os

import numpy as np

from harness import CHANNEL_SETS, COLS, parse_name, read_inertial, window_features, windows
from reps import FS, find_peaks

ROOT = "data/inertial/upper"
ACC = [COLS.index(c) for c in CHANNEL_SETS["acc"]]
CACHE = "cache/reps_acc.npz"


def rep_features(sig: np.ndarray) -> np.ndarray:
    """One feature row per repetition, cut at the midpoint between neighbouring peaks."""
    peaks = find_peaks(sig)
    if len(peaks) < 2:
        return np.empty((0, 31))
    bounds = [0] + list((peaks[1:] + peaks[:-1]) // 2) + [len(sig)]
    rows = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = sig[a:b, ACC]
        if len(seg) < 10:
            continue
        f = window_features(seg[None, :, :])[0]
        rows.append(np.concatenate([[len(seg) / FS], f]))
    return np.vstack(rows) if rows else np.empty((0, 31))


def build_bags() -> tuple[list[np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    if os.path.exists(CACHE):
        # allow_pickle is needed for a ragged array of per-series bags; this file is written
        # by build_bags() in this same script from local CSVs and never leaves the machine.
        z = np.load(CACHE, allow_pickle=True)
        return list(z["bags"]), z["y"], z["subject"], z["exercise"]
    bags, ys, subs, exs = [], [], [], []
    for dirpath, _, files in os.walk(ROOT):
        for f in sorted(files):
            if not f.endswith(".csv"):
                continue
            path = os.path.join(dirpath, f)
            meta = parse_name(path)
            if meta is None:
                continue
            subject, ex, _side, label, _series = meta
            sig = read_inertial(path)
            rows = rep_features(sig)
            if len(rows) < 3:
                continue
            bags.append(rows.astype(np.float32))
            ys.append(label)
            subs.append(subject)
            exs.append(ex)
    y = np.asarray(ys, dtype=np.int64)
    os.makedirs("cache", exist_ok=True)
    np.savez_compressed(CACHE, bags=np.array(bags, dtype=object), y=y,
                        subject=np.asarray(subs), exercise=np.asarray(exs))
    return bags, y, np.asarray(subs), np.asarray(exs)


def pool_max(scores: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """Max over each bag's slice of a flat score array."""
    return np.maximum.reduceat(scores, offsets[:-1])


def train_mil(X: np.ndarray, offsets: np.ndarray, y: np.ndarray,
              epochs: int = 300, lr: float = 0.5, l2: float = 1e-3) -> np.ndarray:
    """Numpy MIL: bag logit = max over reps of (w.x + b), trained with BCE."""
    w = np.zeros(X.shape[1], dtype=np.float64)
    b = 0.0
    starts = offsets[:-1]
    for _ in range(epochs):
        logits = X @ w + b
        bag = np.maximum.reduceat(logits, starts)
        p = 1.0 / (1.0 + np.exp(-bag))
        g_bag = (p - y) / len(y)
        # Route the gradient to each bag's argmax repetition only.
        gw = np.zeros_like(w)
        gb = 0.0
        for k, s in enumerate(starts):
            e = offsets[k + 1]
            j = s + int(np.argmax(logits[s:e]))
            gw += g_bag[k] * X[j]
            gb += g_bag[k]
        w -= lr * (gw + l2 * w)
        b -= lr * gb
    return np.concatenate([w, [b]])


def predict_mil(X: np.ndarray, offsets: np.ndarray, theta: np.ndarray) -> np.ndarray:
    logits = X @ theta[:-1] + theta[-1]
    bag = np.maximum.reduceat(logits, offsets[:-1])
    return (1.0 / (1.0 + np.exp(-bag))) >= 0.5


def main() -> None:
    bags, y, subjects, exercises = build_bags()
    print(f"{len(bags)} series, {sum(len(b) for b in bags)} repetitions, "
          f"{len(set(subjects))} subjects, positive rate {y.mean():.2f}")

    # Standardise on the pooled repetition features, using train-fold statistics only.
    lens = np.array([len(b) for b in bags])
    print(f"reps per series: median {np.median(lens):.0f}, min {lens.min()}, max {lens.max()}")
    subs = sorted(set(subjects))
    acc_prop = np.empty(len(bags), dtype=np.int64)
    acc_mil = np.empty(len(bags), dtype=np.int64)

    for s in subs:
        te = subjects == s
        tr = ~te
        Xtr = np.vstack([bags[i] for i in np.where(tr)[0]])
        mu, sd = Xtr.mean(0), Xtr.std(0)
        sd = np.where(sd == 0, 1.0, sd)

        def prep(feats):
            return (feats - mu) / sd

        # naive propagation: every rep carries the bag label
        ytr_rep = np.concatenate([np.full(len(bags[i]), y[i]) for i in np.where(tr)[0]])
        from sklearn.linear_model import LogisticRegression
        clf = LogisticRegression(max_iter=3000, C=1.0).fit(prep(Xtr), ytr_rep)

        # MIL
        lens_tr = np.concatenate([[len(bags[i])] for i in np.where(tr)[0]])
        offsets_tr = np.concatenate([[0], np.cumsum(lens_tr)])
        theta = train_mil(prep(Xtr).astype(np.float64), offsets_tr, y[tr].astype(np.float64))

        for i in np.where(te)[0]:
            p = clf.predict_proba(prep(bags[i]))[:, 1]
            acc_prop[i] = int(p.mean() >= 0.5)
            Xte = prep(bags[i]).astype(np.float64)
            off = np.array([0, len(Xte)])
            acc_mil[i] = int(predict_mil(Xte, off, theta)[0])

    floor = max(y.mean(), 1 - y.mean())
    print(f"\nbag-level accuracy, leave-one-subject-out (floor {floor:.3f}):")
    print(f"  naive rep propagation : {(acc_prop == y).mean():.3f}")
    print(f"  MIL (max pooling)     : {(acc_mil == y).mean():.3f}")
    for ex in sorted(set(exercises)):
        m = exercises == ex
        print(f"    {ex}: propagation {(acc_prop[m] == y[m]).mean():.3f}  "
              f"MIL {(acc_mil[m] == y[m]).mean():.3f}")


if __name__ == "__main__":
    main()
