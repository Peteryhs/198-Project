# Model

Two trained models, exported so the team does not have to re-derive them. Both answer one question
about one series: was it performed correctly?

| File | Size | Pipeline | Leave-one-subject-out accuracy |
| --- | --- | --- | --- |
| `small/form_rep.joblib` | 72 KB | per-repetition features, averaged over the repetitions | **89.3%** |
| `small/form_window.joblib` | 104 KB | 3 s sliding window, 30 summary features | 81.1% |
| `small/form_rep.c`, `small/form_window.c` | 13 KB + 26 KB of arrays | the same models as C99 for the board | — |
| `metadata.json` | 2 KB | input contract, hyperparameters, provenance | — |

The 2.5 MB and 2.7 MB random forests that used to sit here were never able to run on the
UNO R4 (107,528 and 114,860 nodes against a 10,000-node budget). They are gone from the working
tree and remain readable in git history at `ae8ea7f` if the comparison is ever needed.

Chance is 50%, because the classes are balanced by construction. Both are
`sklearn.ensemble.RandomForestClassifier`, 80 trees, `min_samples_leaf=8`, `max_depth=14`.

**Read the accuracy column carefully.** Those are leave-one-subject-out numbers, measured on
volunteers the model had never seen. The shipped `.joblib` files are then refitted on **all 30
volunteers** so they are usable. Their training accuracy is around 92% and that number is
meaningless — do not quote it.

## Using the repetition model

`joblib.load` unpickles the file, which runs code inside it. Only load a `.joblib` that came from
this repository; never one a stranger sent you.

```python
import joblib, numpy as np

model = joblib.load("model/small/form_rep.joblib")

# one series -> repetitions -> features -> verdict
probs = []
for rep in repetitions_of(series):          # each rep: (n_samples, 3) accel in g
    feats = rep_features(rep)               # 31 values, order defined below
    probs.append(model.predict_proba(feats[None, :])[0, 1])
verdict = "wrong" if np.mean(probs) >= 0.5 else "correct"
```

`repetitions_of` and `rep_features` are the two functions in `../scripts/reps.py` and
`../scripts/train_export.py`. Repetition boundaries are the midpoints between detected peaks;
`find_peaks` uses `scipy.signal.find_peaks` on the detrended accelerometer magnitude with a 1.2 s
minimum distance and a prominence floor at 0.35 × the signal's 90th percentile.

## Input contract

100 Hz, three accelerometer axes in g. Ten statistics, each containing x/y/z values, in this statistic-major order:

```
mean, std, min, max, range, rms, skew, kurtosis, energy, zero-crossing rate
```

For the repetition model a leading feature `duration_s` comes first, so the vector is
`[duration_s] + 30 axis/statistic values = 31 values`. The window model takes the 30 statistics only.

## Why the repetition model differs from the 86.5% in the docs

86.5% was logistic regression on the same per-repetition features; 88.3% is a random forest on them.
Same features, same split, same pooling, better classifier. Both rows are in `../docs/RESULTS.md`.

## Getting this onto the board

`small/form_rep.c/.h` and `small/form_window.c/.h` now contain allocation-free C99 boosted
forests, with float32 thresholds/scores and a libm `expf` sigmoid. Their companion joblibs are
full-cohort sklearn references for export verification; the existing large joblibs are unchanged.

| Small model | All-subject LOSO | EAH / EFE / SQZ | Nodes | Cortex-M4F text / rodata |
| --- | ---: | --- | ---: | ---: |
| Repetition HGB, 50 iterations / 15 leaves | 89.3275% | 92.8879 / 88.8889 / 86.2288% | 1,450 | 212 / 13,150 B |
| Window HGB, 100 iterations / 15 leaves | 81.0786% | 84.0349 / 81.5410 / 76.6963% | 2,900 | 212 / 26,300 B |

Combined code/arrays/exception indices occupy 39,890 B of the enforced 120,000 B model ceiling.
Those are object sizes, not linked flash. A real UNO R4 Minima resource probe links the actual
existing app, feedback, Serial, paired runtime/model, both new models, feature extraction and an
extra three-second single-sensor ring: **96,164 B flash / 22,824 B static RAM**. A provisional
4,096 B stack/interrupt reserve leaves 5,848 B RAM. This proves resource co-residency; production
paired firmware is unchanged and physical execution/stack high-water remain unmeasured.

Use `form_rep_predict(features)` or `form_window_predict(features)` for P(wrong); a nonfinite
input returns -1. Keep the series verdict as the **mean of repetition probabilities**, thresholded
at `>= 0.5`. There is no per-repetition ground truth. Small-model feature order is explicitly
statistic-major: `[mean_x, mean_y, mean_z, std_x, ...]`, with `duration_s` prepended for repetitions.
All small-model LOSO fits use this finite float32 input contract, matching C.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .venv/bin/python scripts/train_small.py --fit
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .venv/bin/python scripts/verify_small_export.py --rows 0
.venv/bin/python scripts/measure_small_target.py
.venv/bin/python -m pytest scripts/test_small_export.py -q
```

Training gates combined node/object-byte budgets and accuracy, then checks C parity before writing
exports. Golden rows live in `small/golden.npz`. See [the measured report](../docs/runs/small-model/REPORT.md)
for baseline reruns, exact per-exercise losses, rejected candidates, reproduction commands and limitations.
The overall tolerance is unused; window SQZ nevertheless regresses by 1.2792 percentage points.
