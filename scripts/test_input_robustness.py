"""Does the shipped model survive degraded sensor input?

Freezes the two exported models (`model/small/*.joblib`), degrades only the measurement, and
scores each severity tier against the clean arm. Reports accuracy, the change against clean, the
rank correlation between clean and degraded P(wrong), and AUC against the true labels.

The models are the shipped all-subject fits, so absolute accuracy here is higher than the
leave-one-subject-out numbers in docs/RESULTS.md. The claim being tested is the *difference*
between arms on the same series, not the absolute level.

Run from the repository root:

    .venv/bin/python scripts/test_input_robustness.py

Writes docs/runs/small-model/figures/robustness.csv
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import joblib
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from augmentation_pipeline import transform
from harness import CHANNEL_SETS, COLS, parse_name, read_inertial, window_features, windows
from reps import FS, find_peaks

ROOT = Path("data/phytmo/inertial/upper")
MODELS = Path("model/small")
OUT = Path("docs/runs/small-model/figures/robustness.csv")
SEED = 20261110
ACC = [COLS.index(c) for c in CHANNEL_SETS["acc"]]

BASE = {
    "version": 1,
    "seed": SEED,
    "sample_rate_hz": 100.0,
    "clip_g": 3.0,
    "quantization_step_g": 0.001017,
}

TIERS = {
    "clean": None,
    "mild": dict(BASE, noise_std_g=0.005, bias_g=[0.01, -0.01, 0.01], gain=[1.01, 1.01, 1.01],
                 lowpass_hz=40.0, orientation={"max_degrees": 3.0}),
    "moderate": dict(BASE, noise_std_g=0.02, bias_g=[0.03, -0.03, 0.03], gain=[1.03, 1.03, 1.03],
                     lowpass_hz=25.0, orientation={"max_degrees": 8.0}),
    "severe": dict(BASE, noise_std_g=0.06, bias_g=[0.08, -0.08, 0.08], gain=[1.08, 1.08, 1.08],
                   lowpass_hz=15.0, orientation={"max_degrees": 15.0},
                   quantization_step_g=0.01),
}


def series_features(sig: np.ndarray):
    """Window rows and repetition rows for one series, using the shipped contracts."""
    w = windows(sig[:, ACC], 300, 0.5)
    wf = window_features(w) if len(w) else np.empty((0, 30))
    peaks = find_peaks(sig)
    rep = np.empty((0, 31))
    if len(peaks) >= 2:
        bounds = [0] + list((peaks[1:] + peaks[:-1]) // 2) + [len(sig)]
        rows = [np.r_[[(b - a) / FS], window_features(sig[a:b, ACC][None, :, :])[0]]
                for a, b in zip(bounds[:-1], bounds[1:]) if b - a >= 10]
        if len(rows) >= 3:
            rep = np.vstack(rows)
    return wf, rep


def main() -> None:
    # joblib.load unpickles, so these two files are trusted only as committed artefacts of this
    # repository (model/small/, produced by scripts/train_small.py).
    rep_model = joblib.load(MODELS / "form_rep.joblib")
    window_model = joblib.load(MODELS / "form_window.joblib")

    paths = [p for p in sorted(ROOT.rglob("*.csv")) if parse_name(str(p)) is not None]
    print(f"{len(paths)} labelled series")

    # Per tier: list of (series_label, exercise, subject, series_prob, window_probs, window_labels)
    arms: dict[str, list] = {t: [] for t in TIERS}
    for i, path in enumerate(paths):
        meta = parse_name(str(path))
        subject, exercise, _side, label, _series = meta
        raw = read_inertial(str(path))
        for tier, cfg in TIERS.items():
            sig = raw if cfg is None else raw.copy()
            if cfg is not None:
                sig[:, ACC] = transform(raw[:, ACC].astype(np.float64), cfg, SEED)
            wf, rep = series_features(sig)
            series_p = (float(rep_model.predict_proba(rep)[:, 1].mean())
                        if len(rep) else np.nan)
            w_p = window_model.predict_proba(wf)[:, 1] if len(wf) else np.empty(0)
            arms[tier].append((label, exercise, subject, series_p, w_p))
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(paths)}", flush=True)

    def summarise(model: str, prob_index: int, unit: str) -> list[dict]:
        clean_probs = np.concatenate([np.atleast_1d(a[prob_index]) for a in arms["clean"]])
        rows = []
        clean_auc = None
        for tier in TIERS:
            probs, labels = [], []
            for a in arms[tier]:
                p = np.atleast_1d(a[prob_index])
                n = len(p)
                probs.append(p)
                if model == "rep":
                    labels.append(np.full(1, a[0]))
                else:
                    labels.append(np.full(n, a[0]))
            probs = np.concatenate(probs)
            labels = np.concatenate(labels)
            ok = np.isfinite(probs)
            probs, labels = probs[ok], labels[ok]
            acc = float(((probs >= 0.5).astype(int) == labels).mean())
            auc = float(roc_auc_score(labels, probs))
            if tier == "clean":
                clean_auc = auc
                base_acc = acc
                rho = 1.0
            else:
                cc = clean_probs[np.isfinite(clean_probs)]
                rho = float(spearmanr(cc, probs)[0]) if len(cc) == len(probs) else float("nan")
            rows.append(dict(model=model, unit=unit, tier=tier, seed=SEED, n_units=int(len(probs)),
                             accuracy_pct=round(acc * 100, 3),
                             delta_pp_vs_clean=round((acc - base_acc) * 100, 3),
                             spearman_vs_clean=round(rho, 4),
                             auc_pct=round(auc * 100, 3),
                             clean_auc_pct=round(clean_auc * 100, 3)))
        return rows

    rows = summarise("rep", 3, "series") + summarise("window", 4, "window")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
