# Tally modelling continuation — 2026-11-07

## 1. Research memo

Read [the research memo](MODELLING-RESEARCH-MEMO.md), [opened-source audit](MODELLING-LITERATURE-NOTES.md)
and [embedded feasibility notes](EMBEDDED-FEASIBILITY-NOTES.md). The recommendation is two small
linear classifiers over accelerometer features, with an explicit unavailable error explanation.
Weak temporal supervision can produce instance scores, but does not establish individual
repetition correctness. No reviewed source establishes an error head trained without error labels.
Recent skeleton, quaternion and wearable benchmarks use different targets and split protocols;
their headline scores are not comparable to this recording-level accelerometer LOSO experiment.

## 2. Plan and position

[The one-page plan](MODELLING-PLAN.md) was recorded before training. Its alternatives, confidence
marks, label sources and pre-training memory arithmetic remain the decision record.

Use the **known left-upper-arm, ±3 g linear export** as the starting prototype candidate. Placement
and preprocessing follow the intended sensor contract. This is not a patient-facing validated
monitor. The all-placement model preserves the comparison with existing results; it processes one
three-axis recording at a time and does not fuse four sensors or use gyro/magnetometer channels.

Exercise identity comes from filenames. Quality training propagates the whole-series label to
each detected repetition and gives each recording equal total training weight. It is a weak
pseudo-label baseline, not an end-to-end bag-loss MIL model. Predictions are averaged as probabilities
for the **completed recording**, the only quality level with ground truth. Error output always says
`not enough evidence to say`.

**Confidence:** high that these coefficients fit the target; medium for generalization to held-out
PHYTMO volunteers; low/unproven for a different accelerometer rig, older patients, causal segmentation,
individual repetition correctness and error explanations.

## 3. Built, commands and actual output

All commands below ran from `/home/peter/work/198-Project`. Logs and JSON are in [runs/](runs/).
The numerical environment was Python 3.12.14, NumPy 2.3.4, SciPy 1.16.3 and scikit-learn 1.7.2.
`scripts/requirements-modelling.txt` pins the three scientific dependencies. Installation used:

```bash
uv venv --python /usr/bin/python3.12 /tmp/tally-modelling-venv
UV_CACHE_DIR=/tmp/tally-uv-cache uv pip install --python /tmp/tally-modelling-venv/bin/python numpy==2.3.4 scipy==1.16.3 scikit-learn==1.7.2
```

The repository preflight found `docs/`, `training-data/`, both existing models, and required commit
`c8a09e1 research: commit the training matrices and the model comparison`. Work is on
`codex/embedded-modelling`. No firmware change was required.

### Saved training data

The full upper-limb subset is saved persistently at
`/home/peter/work/198-Project/data/phytmo/inertial/upper/`. These are original CSVs, including the
accelerometer channels, so future training can reuse them. `/data/` is ignored by Git. The original
and ±3 g derived accelerometer feature matrices are also retained in the new model folders and
committed; they can be reused with `--features-root`.

The ordinary full-archive transfer stopped incomplete. The successful targeted download used:

```bash
set -o pipefail; /tmp/tally-modelling-venv/bin/python scripts/fetch_upper_range.py --out data/phytmo/inertial/upper 2>&1 | tee -a docs/runs/fetch-upper.log
```

Actual successful output:

```text
verified 1484 files; transferred 204,759,173 bytes in 25 range blocks
```

[Inventory](runs/raw-inventory.json): **1,484 files, 624,034,102 uncompressed bytes**. Each member
was checked against its ZIP CRC during extraction and rechecked after final placement. The local
completion manifest is `data/phytmo/inertial/fetch-upper-manifest.json`. No archive or raw dataset
was committed. The download log retains an initial initialization failure; its fix and a path
normalization were followed by the complete CRC recheck.

### One training entry point

`scripts/realtime_pipeline.py` accepts a dataset root, rebuilds accelerometer features from raw
files, trains, runs fixed-seed LOSO and ablations, prints tables with floors, and exports C/NPZ plus
metadata, fold results and out-of-fold predictions. All fitting/scaling uses training subjects only.
No hyperparameters were selected on test folds. Benchmark mode requires all 30 volunteers;
sample-sized runs require `--smoke-test` and are explicitly excluded from benchmark conclusions.

Exact full raw control and clipped commands:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-modelling-venv/bin/python scripts/realtime_pipeline.py data/phytmo/inertial/upper --unclipped --out model/realtime-linear
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-modelling-venv/bin/python scripts/realtime_pipeline.py data/phytmo/inertial/upper --clip-g 3 --out model/realtime-linear-clipped
```

These were piped through `tee docs/runs/realtime-raw-control.log` and
`tee docs/runs/realtime-clipped.log`, respectively, with `set -o pipefail`. Actual output excerpts:

```text
raw timestamps: duplicates=179, maximum gap=0.120773792 s; nominal 100 Hz, no resampling
status=full-dataset protocol; source=raw CSV without clipping; series=1368 repetitions=24632 subjects=30; sensor=all; seed=0
| Quality / weighted linear | 0.869883 | 0.500000 | 0.497076 |
| Quality / original unweighted linear | 0.864766 | 0.500000 | 0.497076 |
| Quality / duration only | 0.548977 | 0.500000 | 0.497076 |
| Exercise / weighted linear | 0.945906 | 0.345029 | 0.333333 |
status=full-dataset protocol; source=raw CSV clipped at ±3 g before offline segmentation; series=1368 repetitions=24634 subjects=30; sensor=all; seed=0
| Quality / weighted linear | 0.866959 | 0.500000 | 0.497076 |
| Exercise / weighted linear | 0.946637 | 0.345029 | 0.333333 |
```

The nominal sample rate preserves the existing feature contract. Timestamp jitter, duplicates
and gaps are exposed rather than resampled silently. The full unclipped rebuild exactly matches
**all 1,368 original feature bags**; cohort keys, labels and exercises match in both range arms.
Clipping changes detected repetition counts in four recordings. Those counts are detector output,
not hand-validated repetition ground truth. See [data comparison](runs/data-comparison.log).

Known-placement commands:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-modelling-venv/bin/python scripts/realtime_pipeline.py training-data --features-root --sensor Larm --out model/realtime-linear-larm
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-modelling-venv/bin/python scripts/realtime_pipeline.py model/realtime-linear-clipped --features-root --sensor Larm --out model/realtime-linear-larm-clipped
```

Their complete printed tables are [unclipped](runs/realtime-larm.log) and
[clipped](runs/realtime-larm-clipped.log). Cached clipping cannot be reconstructed; the latter
uses the matrix already clipped **before** detection and feature extraction in the raw run.

### Learning curve and ablation

Each outer fold holds out one volunteer. Only the remaining volunteers are randomly ordered
using seed 0, with nested prefixes for the curve. Rows below aggregate held-out recording counts;
the final model still trains on the complete outer training fold, without choosing a curve point.

| Training volunteers per fold | Unclipped quality accuracy | ±3 g quality accuracy | Majority-class floor |
| --- | ---: | ---: | ---: |
| 10 | 85.4532% | 85.8918% | 50.0% |
| 20 | 86.8421% | 86.9883% | 50.0% |
| 29 | 86.9883% | 86.6959% | 50.0% |

Duration alone reaches **54.8977% (floor 50.0%)**, versus **86.9883% (floor 50.0%)** with the full
features. Subject exclusion and this ablation support a signal beyond duration/person-specific
memorization, but do not prove freedom from dataset or sensor-placement biases. The clipped curve
is not monotonic; do not use it to tune on held-out people. The existing unweighted logistic result
reproduces at **86.4766% (floor 50.0%)**.

### Export verification and target cost

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-modelling-venv/bin/python scripts/test_realtime_pipeline.py
PYTHONDONTWRITEBYTECODE=1 /tmp/tally-modelling-venv/bin/python scripts/fetch_upper_range.py --self-check
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-modelling-venv/bin/python scripts/verify_linear_export.py model/realtime-linear-clipped --features-root model/realtime-linear-clipped --arm-object --report docs/runs/realtime-clipped-verification.json
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-modelling-venv/bin/python scripts/verify_linear_export.py model/realtime-linear-larm-clipped --features-root model/realtime-linear-clipped --sensor Larm --arm-object --report docs/runs/realtime-larm-clipped-verification.json
```

Assertions pass: real sample feature/cache equality, statistic-major feature ordering, pooled C
probability parity and invalid C input rejection. Raw-to-cached smoke-test round trips also pass.
All exports were checked against fresh Python fits. In the all-placement clipped arm, max
exercise probability error is **8.52e-7**, max quality error **7.33e-7**; coefficient differences
are zero and all implementation decision differences are zero. This compares implementations,
not predictions against repetition-quality truth.

The clipped export has **512 B float32 parameters**, a **3,001 B C header** and **1,617 B NPZ**;
the known-placement clipped header is **2,984 B**, also **512 B parameters / 1,617 B NPZ**.
[Verification JSON](runs/realtime-clipped-verification.json) records the exact host and Cortex-M4
compile commands and section listing. Target code is **336 B**, coefficient sections **508 B**
(the remaining bias is embedded in code), plus the error string and unwind sections. `expf` is
unresolved. These are **unlinked object sections**, excluding Arduino core, board startup, linked
libm, full firmware and runtime memory. No board was attached.

Pre-training targets remain **8 KiB added flash / 12 KiB added RAM**. Arithmetic: four outputs ×
(31 weights + bias) × 4 B = 512 B; 124 MACs plus four `expf` calls per candidate segment.
The illustrative 10,000-cycle MAC/logit allowance / 48 MHz = **0.208 ms estimate**, excluding
softmax/sigmoid normalization and divisions, unmeasured exponentials, features, detection,
acquisition and display. There is no measured total
latency. The proposed feature buffer and causal detector are not implemented in the export.

## 4. Final comparison

Accuracy unit is a completed **sensor recording**, with micro-averaging. All rows use outer LOSO
over **30 volunteers**; all streams from the test person are excluded from fitting. All-placement
rows contain 1,368 recordings; Larm rows contain 342. Repetitions and simultaneous limb streams
are not independent subjects. Sizes below are measured parameter bytes, shared by both exported
heads; they are not full firmware flash use.

| Approach / task | Accuracy | Split | Majority-class floor | Exported parameters |
| --- | ---: | --- | ---: | ---: |
| Original unweighted linear / quality | 86.48% | LOSO-30, all placements | 50.00% | Not exported |
| Duration-only ablation / quality | 54.90% | LOSO-30, all placements | 50.00% | Not exported |
| Weighted linear, original range / quality | 86.99% | LOSO-30, all placements | 50.00% | 512 B shared |
| Weighted linear, original range / exercise | 94.59% | LOSO-30, all placements | 34.50% | 512 B shared |
| Weighted linear, ±3 g / quality | 86.70% | LOSO-30, all placements | 50.00% | 512 B shared |
| Weighted linear, ±3 g / exercise | 94.66% | LOSO-30, all placements | 34.50% | 512 B shared |
| Weighted linear, Larm original range / quality | 89.18% | LOSO-30, Larm only | 50.00% | 512 B shared |
| Weighted linear, Larm ±3 g / quality | 88.89% | LOSO-30, Larm only | 50.00% | 512 B shared |
| Weighted linear, Larm ±3 g / exercise | 94.74% | LOSO-30, Larm only | 34.50% | 512 B shared |
| Repetition correctness / error category | Not measurable | No labels | Not defined | No error classifier |

Class floors use the observed overall class counts for descriptive comparison. Logs additionally
show a stricter predictor: choose the majority class on **training** subjects, then evaluate on
the held-out person. It scores 49.7076% for quality and 33.3333% for exercise. It can fall below the
global class floor because missing recordings change fold distributions. No test labels choose
the fitted models or predictor classes. Earlier logs call this predictor a train-majority floor;
the full raw logs distinguish it from the descriptive class floor.

Clipping's all-placement quality change is **−0.2924 percentage points**, four fewer correct
recordings, with no cohort change. Both training and test data are clipped in that arm: this is
retraining for the target range, not deploying an unchanged unclipped classifier. Exercise
recognition changes by **+0.0731 points**. The reproduced saturation check still finds **12.0%**
of recordings above 3 g (**19.4% EAH**). The small benchmark delta weakens the earlier assumption
that clipping necessarily causes a large accuracy loss; it does not measure physical ADXL335
noise, filtering, calibration, mounting or ADC behavior.

The saturation recheck command was:

```bash
PYTHONDONTWRITEBYTECODE=1 /tmp/tally-modelling-venv/bin/python - <<'PY'
import sys
sys.path.insert(0,'scripts')
import saturation
saturation.ROOT='data/phytmo/inertial/upper'
saturation.main()
PY
```

## 5. Unproven and the next experiment

No accuracy can be claimed for individual repetition correctness or any error category. The
series label cannot say which repetition was wrong, and confidence is not evidence of a cause.
The existing detector sees future samples and whole-series statistics. A successful classifier
call is not a real-time detection result. The proposed five-second buffer would exclude **297 of
24,632** existing segments; their maximum duration is **22.12 s**. A port must define abstention
or a different bounded algorithm and measure its latency and RAM. The physical ADC pin shortage
and four-sensor acquisition remain unresolved. No clinical or home-patient validation was run.

**One next experiment:** the owner-approved, synchronized video/sensor pilot in the plan:
**six volunteers × three exercises × ten repetitions = 180 repetitions**, with two independent
raters marking boundaries, correctness and observable causes or “not observable.” Use only
clinician-approved safe variants. Measure agreement and Cohen's kappa before treating error labels
as learnable. Run a causal detector on the same recordings, record post-completion latency and
abstention, and keep held-out people separate. This is an annotation/feasibility pilot, not proof
of clinical effectiveness.

## 6. Decisions for the owner

- Decide the sensor/interface and exact mounting; all four analog sensors still need acquisition
  hardware beyond the six available ADC inputs. The clipping ablation alone does not decide the BOM.
- Approve patient-facing terminology and the allowed clinical scope; provisional scores must not
  be presented as validated diagnoses or explanations.
- Decide whether to run the annotation pilot and which error categories are actually observable.
  “Effort” is not directly established by the available acceleration signals.

The raw-data download and local retention were explicitly authorized and completed. Existing
forests, their metadata, `docs/RESULTS.md` and the hardware sketch remain unchanged. No push,
pull request or repository comment was made.

Commits before this final report: research `b335245`, pre-training plan `4fa63ab`, persistent data
tooling `19b8b00`, modelling implementation/exports/results `63a5759`. Git author identity was
unset, so these commits use `Codex <codex@openai.com>` without changing global configuration.

### Supplementary measurement command

The following command produced [the final fact log](runs/final-facts.log), including the saved-data
inventory, duration-buffer limit and clipping deltas. These are measurements or arithmetic on
recorded results, not additional training runs.

```bash
PYTHONDONTWRITEBYTECODE=1 /tmp/tally-modelling-venv/bin/python - <<'PY'
import json
from pathlib import Path
import numpy as np
m=json.loads(Path('data/phytmo/inertial/fetch-upper-manifest.json').read_text())
print('saved files, bytes, transfer bytes:',m['verified_file_count'],m['verified_uncompressed_bytes'],m['http_range_bytes_transferred'])
z=np.load('training-data/reps_features_acc.npz',allow_pickle=True)
d=np.concatenate([np.asarray(b,dtype=float)[:,0] for b in z['bags']])
print('segments over 5 s, total, maximum s:',int(np.sum(d>5)),len(d),float(d.max()))
a=json.loads(Path('model/realtime-linear/results.json').read_text())
b=json.loads(Path('model/realtime-linear-clipped/results.json').read_text())
print('quality delta percentage points:',100*(b['quality_loso_accuracy']-a['quality_loso_accuracy']))
print('exercise delta percentage points:',100*(b['exercise_loso_accuracy']-a['exercise_loso_accuracy']))
PY
```
