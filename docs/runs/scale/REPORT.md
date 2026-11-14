# Paired model capacity experiment

Recommendation: **keep the existing affine deployment models**.

No selected variant establishes a quality gain beyond subject-fold noise: every exploratory subject-block interval includes zero or favors the baseline.

All scores are series-level subject-held-out LOSO on the baseline's retained recordings within each side/mode and the same 61 float32 features. Cycle labels remain inherited pseudo-labels. Pairing, boundaries, clipping, features, equal total series weights, probability pooling, and folds are unchanged. Fresh affine refits reproduced every stored decision for both heads in all four cohorts (see `results.json` audits). Left/right cohorts differ, so this is not a matched side comparison.

| Baseline | Side | Series | Cycles | Quality % | Exercise % | Parameter B |
|---|---|---:|---:|---:|---:|---:|
| synchronized-causal | L | 301 | 6998 | 92.36 | 98.01 | 992 |
| synchronized-causal | R | 306 | 7169 | 89.87 | 97.06 | 992 |
| synchronized-offline | L | 301 | 5190 | 91.03 | 98.01 | 992 |
| synchronized-offline | R | 306 | 5265 | 88.89 | 96.41 | 992 |

Capacity grid fixed before reading scores: HGB leaves 15/31/63 × iterations 50/200, learning rate 0.1, no early stopping; MLP ReLU hidden layers 64, 128–64, 256–128, Adam, alpha=0.0001, max_iter=300, no validation split, training-fold weighted standardisation; ExtraTrees 32 trees/head, max_leaf_nodes=256. Seed 0 for every estimator. Other estimator defaults are scikit-learn 1.7.2. Full settings and convergence warnings are in the per-variant JSON files.

| Cohort | Side | Variant | Quality % | Δ pp | Exercise % | Δ pp | State B | LOSO train s | Full fit s | NumPy batch µs/cycle | NumPy single µs |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| causal | L | hgb-leaves15-iter50 | 91.36 | -1.00 | 97.67 | -0.33 | 169134 | 18.23 | 0.67 | 62.54 | 8045.71 |
| causal | L | hgb-leaves15-iter200 | 92.03 | -0.33 | 97.67 | -0.33 | 676134 | 61.48 | 2.05 | 242.72 | 31301.64 |
| causal | L | hgb-leaves31-iter50 | 91.36 | -1.00 | 97.34 | -0.66 | 354734 | 28.49 | 0.95 | 88.61 | 11991.80 |
| causal | L | hgb-leaves31-iter200 | 92.69 | +0.33 | 97.34 | -0.66 | 1418534 | 105.37 | 3.40 | 354.62 | 45339.02 |
| causal | L | hgb-leaves63-iter50 | 92.36 | +0.00 | 97.34 | -0.66 | 725934 | 44.45 | 1.44 | 111.69 | 14000.53 |
| causal | L | hgb-leaves63-iter200 | 91.69 | -0.66 | 97.34 | -0.66 | 2223458 | 135.09 | 4.45 | 405.88 | 50064.17 |
| causal | L | mlp-64 | 88.37 | -3.99 | 97.67 | -0.33 | 67590 | 132.32 | 4.47 | 0.57 | 33.58 |
| causal | L | mlp-128-64 | 89.04 | -3.32 | 97.67 | -0.33 | 263174 | 145.44 | 4.80 | 1.72 | 67.77 |
| causal | L | mlp-256-128 | 89.70 | -2.66 | 97.67 | -0.33 | 786438 | 209.55 | 7.66 | 3.37 | 51.19 |
| causal | L | extratrees-32-leaves256 | 91.36 | -1.00 | 98.01 | +0.00 | 1341190 | 5.87 | 0.20 | 45.60 | 5302.53 |
| causal | R | hgb-leaves15-iter50 | 90.20 | +0.33 | 96.73 | -0.33 | 169134 | 18.24 | 0.61 | 62.45 | 9366.60 |
| causal | R | hgb-leaves15-iter200 | 89.54 | -0.33 | 96.41 | -0.65 | 676134 | 61.68 | 2.04 | 239.02 | 31447.73 |
| causal | R | hgb-leaves31-iter50 | 89.87 | +0.00 | 95.75 | -1.31 | 354734 | 28.98 | 0.94 | 89.56 | 13395.59 |
| causal | R | hgb-leaves31-iter200 | 89.54 | -0.33 | 96.08 | -0.98 | 1418534 | 106.84 | 3.47 | 352.55 | 48609.87 |
| causal | R | hgb-leaves63-iter50 | 89.54 | -0.33 | 96.08 | -0.98 | 725934 | 45.01 | 1.44 | 113.68 | 17400.80 |
| causal | R | hgb-leaves63-iter200 | 89.54 | -0.33 | 97.06 | +0.00 | 2232216 | 136.15 | 4.51 | 414.14 | 57287.86 |
| causal | R | mlp-64 | 88.89 | -0.98 | 96.41 | -0.65 | 67590 | 136.67 | 4.57 | 0.58 | 31.82 |
| causal | R | mlp-128-64 | 88.89 | -0.98 | 97.06 | +0.00 | 263174 | 144.41 | 5.36 | 1.54 | 42.53 |
| causal | R | mlp-256-128 | 88.24 | -1.63 | 97.39 | +0.33 | 786438 | 209.41 | 7.15 | 3.40 | 52.45 |
| causal | R | extratrees-32-leaves256 | 88.89 | -0.98 | 97.39 | +0.33 | 1341190 | 5.86 | 0.20 | 45.68 | 5684.99 |
| offline | L | hgb-leaves15-iter50 | 91.36 | +0.33 | 98.34 | +0.33 | 169134 | 16.16 | 0.53 | 66.01 | 9984.60 |
| offline | L | hgb-leaves15-iter200 | 91.69 | +0.66 | 98.67 | +0.66 | 676134 | 56.28 | 1.86 | 253.60 | 35626.12 |
| offline | L | hgb-leaves31-iter50 | 90.37 | -0.66 | 97.67 | -0.33 | 354734 | 25.68 | 0.84 | 89.09 | 12481.61 |
| offline | L | hgb-leaves31-iter200 | 91.69 | +0.66 | 98.01 | +0.00 | 1285772 | 86.04 | 2.87 | 340.77 | 44686.93 |
| offline | L | hgb-leaves63-iter50 | 91.36 | +0.33 | 98.01 | +0.00 | 725934 | 39.13 | 1.26 | 113.49 | 15185.78 |
| offline | L | hgb-leaves63-iter200 | 91.69 | +0.66 | 98.01 | +0.00 | 1956832 | 112.60 | 3.55 | 377.97 | 50119.48 |
| offline | L | mlp-64 | 91.69 | +0.66 | 97.67 | -0.33 | 67590 | 98.34 | 3.35 | 0.59 | 34.75 |
| offline | L | mlp-128-64 | 90.70 | -0.33 | 97.67 | -0.33 | 263174 | 109.51 | 3.54 | 1.53 | 42.07 |
| offline | L | mlp-256-128 | 90.70 | -0.33 | 97.34 | -0.66 | 786438 | 161.22 | 5.55 | 3.38 | 52.15 |
| offline | L | extratrees-32-leaves256 | 91.36 | +0.33 | 97.67 | -0.33 | 1341190 | 4.61 | 0.16 | 45.40 | 4958.71 |
| offline | R | hgb-leaves15-iter50 | 91.50 | +2.61 | 96.41 | +0.00 | 169134 | 16.24 | 0.53 | 64.55 | 9118.93 |
| offline | R | hgb-leaves15-iter200 | 90.52 | +1.63 | 97.06 | +0.65 | 676134 | 56.47 | 1.86 | 251.25 | 33404.34 |
| offline | R | hgb-leaves31-iter50 | 90.52 | +1.63 | 96.73 | +0.33 | 354734 | 25.68 | 0.83 | 89.09 | 12487.36 |
| offline | R | hgb-leaves31-iter200 | 90.52 | +1.63 | 96.73 | +0.33 | 1279450 | 87.24 | 2.85 | 342.33 | 45981.42 |
| offline | R | hgb-leaves63-iter50 | 91.50 | +2.61 | 96.41 | +0.00 | 725934 | 39.48 | 1.26 | 109.15 | 14322.63 |
| offline | R | hgb-leaves63-iter200 | 90.20 | +1.31 | 96.73 | +0.33 | 1945812 | 111.02 | 3.58 | 365.84 | 49104.48 |
| offline | R | mlp-64 | 91.18 | +2.29 | 96.41 | +0.00 | 67590 | 101.64 | 3.39 | 0.56 | 33.30 |
| offline | R | mlp-128-64 | 89.87 | +0.98 | 97.06 | +0.65 | 263174 | 102.55 | 3.08 | 1.53 | 43.04 |
| offline | R | mlp-256-128 | 90.20 | +1.31 | 97.06 | +0.65 | 786438 | 146.50 | 5.16 | 3.40 | 51.62 |
| offline | R | extratrees-32-leaves256 | 89.87 | +0.98 | 97.39 | +0.98 | 1341190 | 4.70 | 0.16 | 45.25 | 4788.28 |

Measured ExtraTrees full-model nodes (both heads): causal/L 32704; causal/R 32704; offline/L 32704; offline/R 32704.

Training costs are measured host wall time for both heads: LOSO sums the held-out fits; full fit trains on all retained data. Sweep workers may contend for CPU; full fits and inference benchmarks run sequentially with one library thread. Inference is the exported NumPy loader, median of five warm runs on 256 cycles (batch) or one cycle (single), excluding feature extraction, loading, and pooling. State bytes are the uncompressed NPZ array payload including scaling, topology and classes, not Python process RAM; compressed file bytes and actual ensemble node counts are in JSON. The affine baseline's 992 B counts float32 coefficients/intercepts; larger exports use float64 values and int32 indices and count their full array state. These are x86 host measurements, not AR9331 estimates; CPU/compiler details are in `host.json`.

Some MLP fits reached the fixed iteration limit without convergence. Their scores describe that fixed training budget; no extra iterations or hyperparameter tuning were selected from these folds.

**causal/L best: hgb-leaves31-iter200.** Fold quality range 71.43–100.00%; subjects won/tied/lost 10/13/7. Paired series gains/losses 12/11; exact two-sided McNemar p=1. Subject-block bootstrap 95% interval for the aggregate quality change: [-3.30, +3.67] pp.

Retain the affine model on this side.

Changed subject folds: A01 100.0→90.9% (-1/11); A03 100.0→91.7% (-1/12); A05 100.0→81.8% (-2/11); A06 85.7→100.0% (+1/7); A07 100.0→83.3% (-1/6); A09 100.0→77.8% (-2/9); B01 100.0→71.4% (-2/7); C02 81.8→100.0% (+2/11); C03 90.0→100.0% (+1/10); C04 72.7→81.8% (+1/11); C05 81.8→90.9% (+1/11); D01 81.8→90.9% (+1/11); D02 88.9→100.0% (+1/9); D03 90.9→100.0% (+1/11); E01 100.0→90.0% (-1/10); E03 66.7→75.0% (+1/12); E05 90.0→100.0% (+1/10).

This candidate regresses on the listed losing subjects, including when its aggregate mean rises.

**causal/R best: hgb-leaves15-iter50.** Fold quality range 70.00–100.00%; subjects won/tied/lost 4/24/2. Paired series gains/losses 4/3; exact two-sided McNemar p=1. Subject-block bootstrap 95% interval for the aggregate quality change: [-1.68, +2.08] pp.

Retain the affine model on this side.

Changed subject folds: A07 83.3→100.0% (+1/6); B01 80.0→70.0% (-1/10); C04 75.0→83.3% (+1/12); D02 83.3→91.7% (+1/12); D04 100.0→81.8% (-2/11); E04 90.0→100.0% (+1/10).

This candidate regresses on the listed losing subjects, including when its aggregate mean rises.

**offline/L best: mlp-64.** Fold quality range 71.43–100.00%; subjects won/tied/lost 8/15/7. Paired series gains/losses 11/9; exact two-sided McNemar p=0.823803. Subject-block bootstrap 95% interval for the aggregate quality change: [-2.43, +3.82] pp.

Offline segmentation control only.

Changed subject folds: A01 100.0→90.9% (-1/11); A02 100.0→85.7% (-1/7); A03 100.0→91.7% (-1/12); A04 90.0→100.0% (+1/10); A05 90.9→72.7% (-2/11); A09 100.0→88.9% (-1/9); B01 100.0→85.7% (-1/7); B04 100.0→91.7% (-1/12); C04 72.7→81.8% (+1/11); C05 81.8→90.9% (+1/11); D01 81.8→100.0% (+2/11); D02 88.9→100.0% (+1/9); D03 72.7→81.8% (+1/11); E02 91.7→100.0% (+1/12); E03 66.7→83.3% (+2/12).

This candidate regresses on the listed losing subjects, including when its aggregate mean rises.

**offline/R best: hgb-leaves15-iter50.** Fold quality range 75.00–100.00%; subjects won/tied/lost 11/17/2. Paired series gains/losses 11/3; exact two-sided McNemar p=0.057373. Subject-block bootstrap 95% interval for the aggregate quality change: [+0.00, +4.79] pp.

Offline segmentation control only.

Changed subject folds: A03 90.9→100.0% (+1/11); A05 80.0→90.0% (+1/10); B01 70.0→80.0% (+1/10); B04 88.9→77.8% (-1/9); C03 91.7→100.0% (+1/12); C04 75.0→83.3% (+1/12); C05 81.8→90.9% (+1/11); D01 72.7→81.8% (+1/11); D02 91.7→100.0% (+1/12); D03 90.9→100.0% (+1/11); D04 100.0→81.8% (-2/11); E03 75.0→83.3% (+1/12); E05 91.7→100.0% (+1/12).

This candidate regresses on the listed losing subjects, including when its aggregate mean rises.

Variants were selected on these same folds: McNemar p-values and bootstrap intervals are **descriptive, not confirmatory**. McNemar treats series as paired units despite within-subject dependence; the subject-block interval better reflects fold spread, but remains exploratory after selection. No gain is established beyond fold noise when its interval includes zero.

Deployment gate: positive lower subject-bootstrap bound, no losing subject, and no exercise-accuracy regression; causal candidates only. Offline models are segmentation controls. A failed gate retains affine deployment and produces no `model/paired-scaled/{L,R}` artifact. Full numeric candidate states remain in ignored `output/scale/models/`; load with `load_numeric(path)` and `predict_numpy(state, 'quality' or 'exercise', X)` from `scripts/scale_paired_models.py`. Exports were checked against scikit-learn on every rebuilt cycle, including pooled decisions; no pickle or C header is needed. The deployment gate is conservative; failure is not proof that all larger models are inferior.

Reproduce: `.venv/bin/python scripts/scale_paired_model.py --rebuild --jobs 4`. Checkpoints resume completed variants; delete only `docs/runs/scale/{causal,offline}-{L,R}/` and ignored `output/scale/` to force a fresh sweep. Feature audits include input and matrix hashes. `commands.log` records the executed commands.

Not tested: no board, no live sampling, no patient data, no anatomical repetition labels, no new features/detectors, no remount robustness, no named error mechanisms, no nested selection or independent confirmatory cohort, no AR9331 Python/package/RAM/latency integration. Volunteer series labels do not validate per-repetition correctness or patient safety.
