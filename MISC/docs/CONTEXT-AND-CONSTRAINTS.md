# Context and constraints

Everything a new reader needs before trusting any number in this folder, and the constraints that
produced the decisions. Written 2026-11-06.

## The course and the brief

ECE 198 Design Project, University of Waterloo, Fall 2026. First-year design course; the team
builds a working device and defends the design.

The client problem: CCCARE (Centre for Community, Clinical and Applied Research Excellence) runs
supervised exercise programmes for older adults at the university. One instructor supervises up to
30 participants per session. When a participant goes home, nobody measures the exercises. Patients
drift, do half-repetitions, and stop.

Our answer: four accelerometers on one pair of limbs — two on the upper arm, two on the forearm —
so the pair can measure the angle between those two segments. A board reads them, counts
repetitions, and shows the count and pace on a screen. A separate program scores the recorded
session and writes one summary for the instructor.

Status: the repository is a scaffold. No part of the system runs on hardware yet.

## Design targets (from the team's report, not measurements)

| Measure | Target |
| --- | --- |
| Counting error | at most 1 error per 10 repetitions |
| Samples recorded | 95% or more of the session |
| Continuous run | 60 minutes without a reset |

None of those has been measured. No hardware has been built or tested.

## Hard constraints that shaped the modelling work

**Sensing.** Four ADXL335 accelerometers, analog, ±3 g. Twelve analog channels against six ADC pins
(A0–A5) on the Arduino UNO R4 Minima. This is a hardware decision, not a software one: an external
analogue multiplexer, or digital IMUs on I2C/SPI.

**Sensor range.** The public research data was recorded at ±16 g. Measured on 1,368 recorded
series: **12.0% peak above 3 g**, and 19.4% for arms-overhead. A ±3 g part would clip those, and a
clipped repetition is indistinguishable from a badly performed one — the exact thing the model is
supposed to judge.

**Compute.** UNO R4 Minima: Renesas RA4M1, 48 MHz Cortex-M4F, 256 kB flash, 32 kB RAM. Measured by
compiling: an empty sketch is 39 kB flash / 3.9 kB RAM; TensorFlow Lite Micro (after patching its
board gate, which refuses the R4 outright) costs 38.5 kB flash / 3.5 kB RAM. About 180 kB flash and
25 kB RAM are left. `AllOpsResolver` overflows flash by 32 kB. The core ships no CMSIS-DSP, so any
FFT must be vendored.

**Labels.** The reference dataset labels a whole series correct or incorrect. There is **no
per-repetition label and no error-type label**. Any claim about "which repetition was bad" or "what
the patient did wrong" is unsupported by this data, whatever the model architecture.

**Data volume.** 1,368 labelled upper-limb series from 30 volunteers, 24,632 repetitions. Small. Any
model with hundreds of thousands of parameters is over-parameterised for it.

**Validation.** Every reported accuracy is leave-one-subject-out over all 30 volunteers, and every
table prints the majority-class floor next to it (50.0–50.1%). Splitting by file would leak the
same person into train and test.

## Decisions taken, with the reason

| Decision | Why |
| --- | --- |
| Score repetitions, not sliding windows | +5.6 points on the same data with no new labels (86.5% vs 80.9%). |
| Average per-repetition scores rather than max-pool | Max pooling assumes one bad rep spoils the set; these labels describe how the whole set was performed. Max pooling lost 5.4 points. |
| Accept accelerometer-only | Adding the gyroscope was worth about 2 points (83.2% vs 80.9%). The sensor's range is a bigger risk than its missing axis. |
| Drop the RBF SVM from the sweep | Minutes per fit at 94k windows × 30 folds for no added insight once logistic regression and forests had bracketed the problem. |
| Use `scipy.signal.find_peaks` for repetition detection | The hand-rolled peak picker under-counted two of three exercises by roughly half. Validated against an independent autocorrelation period estimate. |
| Do not claim a sequence model yet | No RNN or 1D CNN has been trained. A raw-sample dense net scored *worse* than summary features, which is evidence about capacity at this data size, not evidence about sequence models. |

## Rejected, and why

- **Max-pooling MIL** for the series verdict: lost to plain averaging.
- **Raw samples into a dense net**: 75.2% against 80.5% for summary features; reordering the samples
  changed the result by 0.3 points, so the net was not using sequence anyway.
- **Self-supervised IMU pretraining**: needs a large heterogeneous unlabelled corpus; this dataset is
  30 subjects on one sensor rig.

## Open questions for the next session

1. Train a real 1D CNN on the raw window and get a sixth row in the results table. This is the only
   honest way to answer the "should be an RNN" note from the collaborator who supplied the paper.
2. Decide the sensor question before the bill of materials is ordered: keep the ±3 g ADXL335 and
   document the clipping risk, or move to a digital ±8/±16 g IMU, which also removes the 12-pin
   problem.
3. Per-repetition ground truth does not exist. If the team wants to claim "which rep was bad",
   someone has to hand-label a few hundred repetitions. Until then, report series-level accuracy.
4. Bench-test saturation on real hardware. The 12% figure is from a different sensor rig, at ±16 g.

## Where the data and the code live

The dataset is 3.4 GB and is **not** in this repository. It lives on the hub machine at
`~/work/phytmo/`, extracted to `data/inertial/upper/` (598 MB, 1,484 CSVs).

```bash
# source data
wget -c -O PHYTMO.zip "https://zenodo.org/api/records/6319979/files/PHYTMO.zip/content"
unzip -o -q PHYTMO.zip 'inertial/upper/*' -d data
```

Dataset: PHYTMO, García-de-Villa et al., *Scientific Data* 9:266 (2022),
doi 10.1038/s41597-022-01387-2, Zenodo doi 10.5281/zenodo.6319979, CC-BY-4.0.

## Provenance of every number

| Kind | Where it came from | Trust |
| --- | --- | --- |
| Accuracies | `scripts/*.py` runs, logs kept beside them | measured, reproducible |
| Repetition counts | same, `run_mil2.log` | measured |
| Saturation percentages | `scripts/saturation.py` over all 1,368 series | measured |
| Flash / RAM figures | `arduino-cli compile` for `arduino:renesas_uno:minima`, no board attached | compile-time, not runtime |
| Battery, thermal, latency on hardware | — | **not measured** |
| Paper's own results | their published tables, arXiv 2401.12857 | quoted, not reproduced |

## Known weak points in the current work

- Dense-net arms stopped at 80 iterations without converging, so their accuracies are indicative.
- Training rows were capped at 12,000 per fold for the expensive arms.
- The repetition detector is validated against a period estimate, not against hand-counted reps.
- All figures are accelerometer-only, upper-limb, three exercises. Nothing here covers the lower
  limb or gait.
