# Models

Two exports remain. Both take the same 61 inputs from a pair of accelerometers on one limb.

## What runs

`paired-synchronized-offline/{L,R}` is the deployed model. `scripts/tally_paired_stream.py` loads it:

- `realtime_model.npz` — `quality_coef` (1, 61), `quality_intercept`, `exercise_coef` (3, 61),
  `exercise_intercept`, `exercise_classes`. Coefficients are pre-scaled, so feed raw features.
- `realtime_model.h` — the same weights as C, for the firmware route.
- `metadata.json`, `results.json`, `predictions.csv` — the contract, the measured scores, the per-series predictions.

| side | series | cycles | quality | exercise | parameters |
|---|---:|---:|---:|---:|---:|
| L | 301 | 5,190 | 91.03 % | 98.01 % | 992 bytes |
| R | 306 | 5,265 | 88.89 % | 96.41 % | 992 bytes |

Scores are series-level, subject-held-out (LOSO), over 30 volunteers. Chance is about 50 % for quality
and about 35 % for exercise. Cycle labels are pseudo-labels derived from the series labels, so no
per-repetition correctness is claimed.

## What else is here

`paired-synchronized-causal/{L,R}` is the same model trained on causal cycle boundaries. It scores
92.36 % (L) and 89.87 % (R), but only when the cycles come from the causal detector, so the Python
script does not use it. It is kept because `scripts/measure_feedback_target.py`,
`scripts/measure_tally_target.py`, `scripts/round2_summary.py` and `scripts/test_paired_runtime.py`
run against it.

`streaming/` holds the C runtime those scripts compile: `paired_stream.c` and `paired_runtime.c`.

## Input contract

61 float32 values per repetition, in this order:

1. `duration_s`
2. upper arm: `mean, std, min, max, range, rms, skew, kurtosis, energy, zcr`, each for x, y, z
3. forearm: the same ten statistics in the same order

Accelerations in g, gravity included, ±3 g range, 100 Hz, both sensors on the same limb and read on
one clock.

## Scoring

`p_wrong = sigmoid(quality_intercept + quality_coef · x)`, then average `p_wrong` over the repetitions
of the set and call the set wrong at 0.5 or above. The exercise head is a three-way softmax over
`exercise_coef · x + exercise_intercept`.

## Removed in the 2026-11 cleanup

`small` (single mount), `realtime-linear` and its three variants, `rnn-experiment`, `application`,
`feedback`, `paired-causal` and `paired-offline` (invalid clock alignment), and `placement-controls`
(single-sensor ablations that were never a deployment candidate). All of them live in git history at
commit `f7fb8ac`. Historical reports under `docs/` still cite them by name.
