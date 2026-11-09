# Research and supporting material

Work done on the exercise-scoring model, kept beside the firmware so the numbers can be checked
rather than taken on trust.

Latest: [Basic feedback application and replay](BASIC-FEEDBACK.md) — one-pair lifecycle,
Serial scaffold, host tests and full-path object budget. Real timing cues remain gated on
independently validated boundaries.

[Tiny GRU real-data experiment](TINY-RNN-REPORT.md) — all 30 volunteers on both sides.
The tested RNN did not beat the existing classifier; specific error labels remain unavailable.
Simulation development remains parked.

[Phase 5 reconstruction and reporting audit](PHASE5-REPORT.md) and the
[complete continuation prompt](TALLY-CONTINUATION-PROMPT.md). A fit/scoring interpolation defect
is fixed and all folds rerun; validation still fails. The new anatomy/timing checks and the
proposed user-calibration alternative are documented for continuation.

[Phase 4 calibrated replay and virtual sensor search](PHASE4-REPORT.md) retains the historical
30-volunteer, 81-position evidence; those maps are diagnostics, not real-placement accuracy.

Start here, in this order:

1. **[CONTEXT-AND-CONSTRAINTS.md](CONTEXT-AND-CONSTRAINTS.md)** — the course context, the hardware
   and data constraints, every decision and why, what was rejected, what is still open, and where
   each number came from. Read this first; the rest will not make sense without it.
2. **[RESEARCH-FINDINGS.md](RESEARCH-FINDINGS.md)** — the reference paper's method, our baseline,
   what we tested, and what the tests showed.
3. **[RESULTS.md](RESULTS.md)** — every result as a table, generated from the run logs.
4. **[brand/BRAND.md](brand/BRAND.md)** — name, mark, colours with hex, type, tagline, and the
   rejected alternatives.

## Headline numbers

Accelerometer only, leave-one-subject-out over 30 volunteers, chance is 50%.

| Approach | Accuracy |
| --- | --- |
| 3 s sliding windows, summary features, random forest | 80.9% |
| Per-repetition scoring, averaged, logistic regression | 86.5% |
| **Per-repetition scoring, averaged, random forest (exported)** | **88.3%** |
| Per-repetition scoring, max pooling | 81.1% |
| Same windows with the gyroscope added | 83.2% |

The repetition-level win is the useful one: +7.4 points over windows with the exported forest, no
new labels, nothing new to buy. Both trained models are in [`../model/`](../model/).

## What is not proven

- No model of any kind has run on the Arduino. Every microcontroller figure in these documents is a
  compile-time size, not a runtime measurement.
- Per-repetition correctness has no ground truth. Only the series-level verdict is measured.
- No sequence model (RNN, 1D CNN) has been trained yet. That is the first open question in
  CONTEXT-AND-CONSTRAINTS.md.
- 12% of the reference recordings peak above 3 g, which the current sensor would clip.

## Figures

- `figures/fig1_window_accuracy.png` — accuracy against window length, with and without the gyroscope
- `figures/fig2_methods.png` — windows versus per-repetition scoring, per exercise
- `figures/fig3_saturation.png` — how much of the data exceeds the sensor's range
- `figures/lesson-ours-vs-rnn.png` — why summary features cannot see movement shape

## Scripts

`scripts/` regenerates everything. The dataset is not in this repository; fetch it with the commands
in CONTEXT-AND-CONSTRAINTS.md, then:

```bash
uv run --locked python scripts/harness.py --windows 100 200 300
uv run --locked python scripts/mil.py
uv run --locked python scripts/raw_vs_features.py
uv run --locked python scripts/saturation.py
uv run --locked python scripts/genfigs.py
```

## Modelling continuation

- [Research memo](MODELLING-RESEARCH-MEMO.md) and [full source audit](MODELLING-LITERATURE-NOTES.md)
- [Pre-training decision and budget](MODELLING-PLAN.md)
- [New experiments, exact commands and limitations](MODELLING-REPORT.md)
- [Persistent local raw-data location](../training-data/README.md#persistent-local-raw-data)

The new linear C exports are separate from the existing forests. Their repetition scores are
provisional; error explanations and embedded real-time performance remain unvalidated.

Numerical versions are enforced; see [environment setup](MODELLING-ENVIRONMENT.md).

Round two: [complete report](ROUND2-REPORT.md), [research](ROUND2-RESEARCH.md), [positions](ROUND2-PLAN.md), [error annotation protocol](ROUND2-ERROR-PROTOCOL.md).

Phase three: [complete handoff](PHASE3-REPORT.md), [research decisions](PHASE3-DECISIONS.md),
[simulator audit and four exploratory mounts](SIMULATOR-AUDIT-PHASE3.md),
[augmentation and matched real-data results](AUGMENTATION-PHASE3.md),
[local signal inspection](INSPECTION-PHASE3.md), [gated timing feedback](FEEDBACK-PHASE3.md).
