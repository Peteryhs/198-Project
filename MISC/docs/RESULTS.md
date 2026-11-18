# PHYTMO baseline results

All numbers produced by the scripts in this folder. Task: decide whether a recorded series of an
upper-limb exercise was performed correctly or incorrectly. Split: leave-one-subject-out over all
30 volunteers. Random floor: 50.0% (the two classes are balanced by construction).

Data: PHYTMO (`doi:10.5281/zenodo.6319979`, CC-BY-4.0), `inertial/upper` only — 1,368 labelled
series across EAH (arms over head), EFE (elbow flex) and SQZ (squeeze).

## 1. Sliding-window sweep, accelerometer only

| Window | Model | Accuracy | EAH | EFE | SQZ |
| --- | --- | --- | --- | --- | --- |
| 1 s | hgb | 75.9% | 78.7% | 75.0% | 73.2% |
| 1 s | logreg | 70.2% | 73.3% | 67.8% | 68.4% |
| 1 s | rf | 76.2% | 78.6% | 75.1% | 74.1% |
| 2 s | hgb | 79.5% | 83.1% | 78.8% | 75.4% |
| 2 s | logreg | 75.4% | 78.6% | 75.0% | 71.6% |
| 2 s | rf | 79.4% | 82.4% | 77.8% | 77.3% |
| 3 s | hgb | 80.7% | 83.9% | 81.1% | 75.9% |
| 3 s | logreg | 78.4% | 81.3% | 79.2% | 73.8% |
| 3 s | rf | 80.9% | 84.0% | 79.8% | 77.9% |

## 2. Sliding-window sweep, accelerometer + gyroscope

| Window | Model | Accuracy | EAH | EFE | SQZ |
| --- | --- | --- | --- | --- | --- |
| 2 s | hgb | 81.4% | 85.1% | 81.3% | 76.8% |
| 2 s | logreg | 77.7% | 81.8% | 77.7% | 72.4% |
| 2 s | rf | 80.9% | 84.0% | 81.0% | 76.8% |
| 3 s | hgb | 83.2% | 86.8% | 84.0% | 77.8% |
| 3 s | logreg | 81.3% | 86.2% | 82.1% | 73.8% |
| 3 s | rf | 82.9% | 86.1% | 83.4% | 78.0% |

Best accelerometer-only: **80.9%** at 3 s
(rf).
Best with gyroscope: **83.2%** at 3 s
(hgb). The gyroscope arm was not run at 1 s.

## 3. Per-repetition scoring versus windows

Series are cut into repetitions at the midpoint between detected peaks; the per-repetition
predictions are then combined into one verdict for the series.

| Method | All three | EAH | EFE | SQZ |
| --- | --- | --- | --- | --- |
| 3 s windows, rf | 80.9% | 84.0% | 79.8% | 77.9% |
| Repetitions, mean over reps (logistic regression) | 86.5% | 89.0% | 88.7% | 82.0% |
| Repetitions, mean over reps (random forest, exported) | 88.3% | n/a | n/a | n/a |
| Repetitions, max pooling (MIL) | 81.1% | 83.4% | 87.5% | 72.9% |

1,368 series were segmented into 24,632 repetitions
(median 16 per series).

## 4. Repetitions detected per exercise

| Exercise | Series | Median reps | Min | Max |
| --- | --- | --- | --- | --- |
| EAH | 464 | 20 | 7 | 45 |
| EFE | 432 | 15 | 6 | 46 |
| SQZ | 472 | 15 | 6 | 36 |

## 5. Peak acceleration per series versus sensor range

Capture was recorded at ±16 g. The build's ADXL335 clips at ±3 g, so the "over 3.0 g" column is
the share of each exercise's recorded series that a ±3 g part would saturate.

| Exercise | Series | Median peak | p90 | Over 1.5 g | Over 2.0 g | Over 3.0 g | Over 6.0 g |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EAH | 464 | 1.79 g | 4.12 g | 71.8% | 37.3% | 19.4% | 3.7% |
| EFE | 432 | 1.49 g | 3.61 g | 49.3% | 27.8% | 13.9% | 2.5% |
| SQZ | 472 | 1.33 g | 2.08 g | 34.1% | 10.8% | 3.0% | 0.4% |
| All | 1368 | 1.52 g | 3.27 g | 51.7% | 25.1% | 12.0% | 2.2% |

## 6. Hardware budget, measured by compiling

`arduino-cli` against `arduino:renesas_uno` 1.6.0 for `arduino:renesas_uno:minima`:

| Item | Flash | RAM |
| --- | --- | --- |
| Empty Serial sketch | 38,984 B | 3,940 B |
| TensorFlow Lite Micro, sine model, patched | 77,540 B | 7,444 B |
| Net cost of TFLM | ~38,556 B | ~3,504 B |
| Available on the board | 262,144 B | 32,768 B |
| Left after TFLM | ~184,604 B | ~25,324 B |

`tflite::AllOpsResolver` overflows flash by 32,116 B, so only a selective
`MicroMutableOpResolver` links. No board was attached, so nothing here is a runtime measurement.

## 7. Reproduce

```bash
cd ~/work/phytmo
unzip -o -q PHYTMO.zip 'inertial/upper/*' -d data
uv run --no-project --with numpy --with scikit-learn python harness.py --windows 100 200 300
uv run --no-project --with numpy --with scikit-learn python harness.py \
  --channels accgyro --windows 200 300
uv run --no-project --with numpy --with scipy --with scikit-learn python mil.py
uv run --no-project --with numpy python saturation.py
uv run --no-project --with numpy python genfigs.py
uv run --no-project --with numpy python build_results.py
```

## 8. What is not measured

- Per-repetition correctness: the dataset labels whole series, so only series-level accuracy has
  ground truth. Voice that plainly rather than implying per-rep scoring is validated.
- The repetition detector is validated against an independent period estimate, not against
  hand-counted reps.
- No Arduino has run any of this. All hardware numbers are compile-time sizes.

## Round two — paired and causal experiments

Added without replacing accepted history. See [round-two report](ROUND2-REPORT.md) for every command,
majority floors, coverage, common-cohort comparisons, simulation rejection and resource costs.
Among the new full-cohort paired exports, only `model/paired-synchronized-*` are valid; the first paired exports are retained as
invalid device-uptime alignment history. Simulation scores are not real-data performance.

| Source / configuration | series | quality accuracy / majority floor | exercise accuracy / majority floor |
| --- | ---: | ---: | ---: |
| REAL recordings / L paired offline | 301 | 91.03% / 50.17% | 98.01% / 34.55% |
| REAL recordings / R paired offline | 306 | 88.89% / 50.65% | 96.41% / 33.99% |
| REAL recordings / L paired causal | 301 | 92.36% / 50.17% | 98.01% / 34.55% |
| REAL recordings / R paired causal | 306 | 89.87% / 50.65% | 97.06% / 33.99% |
