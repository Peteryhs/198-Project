"""Does keeping the raw samples in order actually help?

Three arms, identical windows, identical leave-one-subject-out split:

  features  the 30 summary numbers our harness uses      (order destroyed on purpose)
  raw       the 900 raw samples of the window, flattened  (order preserved: every sample
                                                           gets its own weight)
  shuffled  the same 900 samples, randomly reordered      (control: same information,
                                                           no order)

If raw beats shuffled, order is carrying signal. If raw only matches features, the summaries were
already enough and the extra machinery is not worth it on a microcontroller.

No torch here: this is a dense network, not a CNN. Labelled as such in the write-up.

Run: uv run --locked python raw_vs_features.py
"""

from __future__ import annotations

import os

import numpy as np

from harness import CHANNEL_SETS, COLS, parse_name, read_inertial, window_features, windows

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "data/inertial/upper")
ACC = [COLS.index(c) for c in CHANNEL_SETS["acc"]]
SIZE = 300  # 3 s, the best window from the earlier sweep
CACHE = os.path.join(HERE, "cache/raw_arm_300.npz")


def build() -> dict:
    if os.path.exists(CACHE):
        z = np.load(CACHE)
        return {k: z[k] for k in z.files}
    raw, feats, y, sub = [], [], [], []
    for dirpath, _, files in os.walk(ROOT):
        for f in sorted(files):
            if not f.endswith(".csv"):
                continue
            path = os.path.join(dirpath, f)
            meta = parse_name(path)
            if meta is None:
                continue
            subject, _ex, _side, label, _series = meta
            sig = read_inertial(path)[:, ACC]
            w = windows(sig, SIZE, 0.5)
            if len(w) == 0:
                continue
            raw.append(w.astype(np.float32))                      # (n, 300, 3)
            feats.append(window_features(w).astype(np.float32))
            y.append(np.full(len(w), label, dtype=np.int64))
            sub.append(np.full(len(w), subject))
    out = {
        "raw": np.vstack(raw).reshape(-1, SIZE * len(ACC)),
        "feat": np.vstack(feats),
        "y": np.concatenate(y),
        "sub": np.concatenate(sub),
    }
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    np.savez_compressed(CACHE, **out)
    return out


def run(X: np.ndarray, y: np.ndarray, sub: np.ndarray, kind: str,
        max_train: int = 12000) -> tuple[float, np.ndarray]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(0)
    pred = np.empty_like(y)
    for s in sorted(set(sub)):
        te = sub == s
        tr = ~te
        Xtr, ytr = X[tr], y[tr]
        if len(Xtr) > max_train:
            idx = rng.choice(len(Xtr), max_train, replace=False)
            Xtr, ytr = Xtr[idx], ytr[idx]
        if kind == "logreg":
            clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1))
        else:
            clf = make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=(128,), alpha=1e-3, max_iter=80,
                              random_state=0, early_stopping=False),
            )
        clf.fit(Xtr, ytr)
        pred[te] = clf.predict(X[te])
    return float((pred == y).mean()), pred


def main() -> None:
    d = build()
    X_raw, X_feat, y, sub = d["raw"], d["feat"], d["y"], d["sub"]
    print(f"{len(y)} windows, {len(set(sub))} subjects, floor {max(y.mean(), 1 - y.mean()):.3f}",
          flush=True)

    shuf = np.empty_like(X_raw)
    order = np.random.default_rng(1).permutation(X_raw.shape[1])
    shuf[:] = X_raw[:, order]  # same multiset of values per window, order destroyed

    for name, X, kind in [
        ("features + logreg", X_feat, "logreg"),
        ("features + mlp", X_feat, "mlp"),
        ("raw (in order) + mlp", X_raw, "mlp"),
        ("raw (shuffled) + mlp", shuf, "mlp"),
        ("raw (in order) + logreg", X_raw, "logreg"),
    ]:
        acc, _ = run(X, y, sub, kind)
        print(f"  {name:26s} {acc * 100:5.1f}%", flush=True)


if __name__ == "__main__":
    main()
