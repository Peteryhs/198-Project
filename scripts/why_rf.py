"""Why does the random forest beat the logistic regression on the same repetition features?

Two things to answer with evidence rather than opinion:

1. Which features the forest actually leans on (importances from the exported model).
2. Whether the 1.8-point gap is real or noise: same folds, same features, per-series predictions,
   compared with an exact McNemar test on the discordant pairs.

Run: uv run --locked python why_rf.py
"""

from __future__ import annotations

import json
import os

from modelling_environment import check_environment
check_environment()

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache/reps_acc.npz")
MODEL = os.path.join(HERE, "repo-docs/model/form-rep-rf.joblib")


def load_bags():
    z = np.load(CACHE, allow_pickle=True)
    return list(z["bags"]), z["y"], z["subject"]


def main() -> None:
    import joblib
    from scipy.stats import binomtest
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    bags, y, sub = load_bags()
    lens = np.array([len(b) for b in bags])
    X = np.vstack(bags).astype(np.float64)
    rep_y = np.repeat(y, lens)
    starts = np.concatenate([[0], np.cumsum(lens)])

    # ---- 1. what the exported forest relies on ----
    model = joblib.load(MODEL)
    names = (["duration_s"] + [f"{a}_{s}" for a in ("x", "y", "z")
                               for s in ("mean", "std", "min", "max", "range", "rms",
                                         "skew", "kurt", "energy", "zcr")])
    imp = np.asarray(model.feature_importances_)
    order = np.argsort(imp)[::-1]
    print("feature importances, exported forest (top 8):")
    for i in order[:8]:
        print(f"  {names[i]:16s} {imp[i]:.3f}")
    print(f"  ... {len(names) - 8} more, total {imp.sum():.3f}")

    # ---- 2. are the two models actually different? ----
    pred_rf = np.empty(len(bags), dtype=int)
    pred_lr = np.empty(len(bags), dtype=int)
    for s in sorted(set(sub)):
        te = sub == s
        tr = ~te
        tr_rows = np.concatenate([np.arange(starts[i], starts[i + 1]) for i in np.where(tr)[0]])
        rf = RandomForestClassifier(n_estimators=80, min_samples_leaf=8, max_depth=14,
                                    n_jobs=-1, random_state=0).fit(X[tr_rows], rep_y[tr_rows])
        lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0))
        lr.fit(X[tr_rows], rep_y[tr_rows])
        for i in np.where(te)[0]:
            sl = slice(starts[i], starts[i + 1])
            pred_rf[i] = int(rf.predict_proba(X[sl])[:, 1].mean() >= 0.5)
            pred_lr[i] = int(lr.predict_proba(X[sl])[:, 1].mean() >= 0.5)

    acc_rf = float((pred_rf == y).mean())
    acc_lr = float((pred_lr == y).mean())
    rf_only = int(((pred_rf == y) & (pred_lr != y)).sum())
    lr_only = int(((pred_lr == y) & (pred_rf != y)).sum())
    print(f"\nLOSO accuracy: forest {acc_rf:.3f}  logreg {acc_lr:.3f}  (n={len(y)} series)")
    print(f"discordant pairs: forest right / logreg wrong {rf_only}, "
          f"logreg right / forest wrong {lr_only}")
    if rf_only + lr_only:
        p = binomtest(rf_only, rf_only + lr_only, 0.5).pvalue
        print(f"exact McNemar p = {p:.4f}")

    json.dump({"accuracy_forest": acc_rf, "accuracy_logreg": acc_lr,
               "forest_only_correct": rf_only, "logreg_only_correct": lr_only,
               "mcnemar_p": float(p) if rf_only + lr_only else None,
               "top_features": {names[i]: float(imp[i]) for i in order[:8]}},
              open(os.path.join(HERE, "why_rf.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
