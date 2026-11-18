# Tally modelling phase three — 2026-11-07

The host-side work is implemented and checked. The result is a reusable measurement-augmentation
pipeline, an optical-board replay with four explicit placement hypotheses, a working local
inspection tool, and a gated duration-feedback module. **No convincing quality benefit from the
tested augmentation, validated physical placement ranking, or patient feedback accuracy is established.**

Start state was `57aa2b6` on `codex/simulation-placement`, as anticipated in the brief. Work is on
`codex/modelling-augmentation-feedback`. Existing untracked `output/` and `tmp/`, raw recordings,
accepted models, historical results, exact coefficient assertions and the firmware sketch are
preserved. No push, PR or repository comment was made. GPT-6 Luna subagents with high reasoning
handled independent simulation, augmentation, feedback/research and cross-review; the primary
agent integrated the work and independently checked saved results and the rendered UI.

## 1. Research and decisions

[The pre-implementation memo](PHASE3-DECISIONS.md) records decisions, rejected alternatives and
confidence. [Feedback literature notes](FEEDBACK-PHASE3.md) give publication years, primary links,
opened methods/evaluation sections, access failures, modality/label limitations and a smaller pilot.
The manufacturer ADXL335 specifications/applications, PHYTMO methods/data descriptor and official
MuJoCo sensor contract were checked before implementation.

The choices were to reuse the fixed paired C feature path and linear heads; generate sensor
variation rather than invented movement-quality labels; prefer measured board motion while refusing
an uncalibrated optical reference; and keep observable duration feedback separate from classifier
confidence. Large biomechanics/learning frameworks, timestamp-only speed changes, acceleration-only
translations, confidence-as-an-error-explanation and a weighted placement score were rejected.

## 2. Simulator audit and validation

[Full audit](SIMULATOR-AUDIT-PHASE3.md), [per-record results](runs/phase3/simulation-placement.json).
The original MuJoCo static/pendulum tests still pass; its **0/84 empirical distribution-gate result
is unchanged**. Fixed planar harmonics, amplitudes and nominal periods produce overly concentrated,
often over-energetic signals. Neither geometry nor the sensor transfer was calibrated. A gravity
sign fix was not supported by the independent physics tests.

New replay differentiates measured optical board poses at translated/circumferential virtual sites,
with explicit local/world frames, Y-up gravity, missing-span preservation and spectra from contiguous
spans. Tests cover static gravity, known translation, centripetal site acceleration, irregular timing,
invalid geometry and gaps. It improves the mechanical experiment without claiming exercise realism.

The calibration/validation split was specified as A–D versus E before replay. A common optical/IMU
clock and chip-origin transform could not be identified from the supplied metadata; consequently
no calibration was fitted and no held-out calibrated reference claim was made. One-sample (10 ms)
clock precision was an engineering prerequisite, not a relaxation of the old signal-distribution
gate. The old ratio/distance thresholds remain intact. Per-file lag fitting on the evaluation
person was rejected. Optical differentiation/filtering and unknown extrinsics remain limitations.

The deterministic optical subset has 30 files from **five people**, A01–E01, with three exercises
and both series conditions. It is not a 30-volunteer placement benchmark. It produced 1,440 virtual
segment/stress rows, with no optical-file rejection. Matched raw inertial distributions are available
for 52/60 upper and 58/60 forearm comparisons; the remaining ten have duplicate/nonmonotonic clocks.
Per-axis distributions, dynamic envelopes, dominant frequency, HF energy, clipping and coverage are
retained. Similar unaligned aggregate envelopes do not prove waveform fidelity. Optical/IMU temporal
correlation and anatomical cycle timing remain unavailable without alignment/annotation.

## 3. Four mounting candidates

These are four alternatives for **two sensors on one limb**, not eight simultaneous sensors.
Definitions live in [placements.json](../simulation/placements.json). Fractions run from acromion
toward lateral epicondyle for upper arm, and lateral epicondyle toward ulnar styloid for forearm.
Nominal lengths are 0.30/0.25 m and radii 0.045/0.035 m; geometry stresses are ±20%, with ±15° surface
variation. These are assumptions, not measured anthropometry. Reference board local X is assumed
distal; proposed chip +X points proximally, +Y follows the circumferential tangent and +Z points
outward. Surface changes rotate that axis convention with the band. Straps need orientation marks;
actual board-to-anatomy registration must be measured.

All quantities below are **exploratory virtual replay**, with no validated sensor transfer. RMS is
the pooled dynamic acceleration RMS in g; the stress ranges describe aggregate medians under the
coupled geometry/surface variations, not confidence intervals. Rail fractions count virtual axis
samples at/beyond ±3 g before a hardware transfer model; all candidate median rail fractions are zero.

| Candidate and definition (upper / forearm) | Evidence and classification | Nominal RMS U / F; stressed median ranges (g) | p90 rail fraction U / F | Practical tradeoff | Coverage / confidence |
| --- | --- | --- | --- | --- | --- |
| Exterior-lateral midpoint hypothesis: 50% / 50%, lateral 0° / 0°; nominal 15 / 12.5 cm from proximal landmarks | PHYTMO supports lateral surfaces only. Exact distances unrecorded; site-specific accuracy unavailable | 0.297 / 0.405; 0.283–0.297 / 0.401–0.406 | 0.016% / 0.015% | Central band clearance; soft-tissue movement and self-placement need measurement | Same 30 files / 5 people / both sides; low physical confidence, gate failed |
| Proximal lateral: 30% / 30%, 0° / 0°; 9 / 7.5 cm | Geometric hypothesis; no independent site measurements or classification result | 0.293 / 0.403; 0.285–0.298 / 0.402–0.404 | 0.0008% / 0.071% | Shorter lever arm; shoulder clothing and proximal forearm muscle/band movement may complicate mounting | Same subset; low physical confidence, gate failed |
| Distal lateral: 72% / 72%, 0° / 0°; 21.6 / 18 cm | Geometric hypothesis; no independent site measurements or classification result | 0.306 / 0.415; 0.302–0.308 / 0.413–0.417 | 0.186% / 0.169% | More distal leverage; check joint clearance, strap migration and contact during exercise | Same subset; low physical confidence, gate failed |
| Proximal anterolateral/anterior: 30% / 30%, 45° / 90°; 9 / 7.5 cm | Changes actual surface position and axes, not just vector rotation; no site-specific accuracy | 0.296 / 0.399; 0.292–0.300 / 0.397–0.406 | 0.079% / 0.108% | Different contact surface may affect comfort, muscle deformation and self-application; none measured | Same subset; low physical confidence, gate failed |

Finite sample coverage in these interpolated optical replay rows is 100%; this is not a measurement
of original optical visibility or real mounting success. Descriptive E01 rows are retained separately
by person in the JSON, but the failed calibration gate prevents calling them validation. The raw
paired classifier results below concern recorded lateral sites of unknown exact distance; they
cannot be assigned to one of these hypotheses. There is **no credible ranking or physical optimum**.

## 4. Reusable augmentation

[Implementation, commands and provenance contract](AUGMENTATION-PHASE3.md).
The small [example config](../configs/augmentation-example.json) controls per-sensor rotation, bias,
gain, noise, causal bandwidth approximation, ADC step, clipping, seed and count. Originals remain
intact. Each NPZ/manifest identifies volunteer, source and counterpart, raw/aligned hashes, exact
sampled rotations/parameters, seed, label origin, transformed status, validation status and
dataset/config/pipeline versions. Source relatives stay in their volunteer fold.

Measurement variation retains the source whole-series label because it represents the same
movement under a changed measurement process, conditional on the stated assumptions. Changed
tempo/excursion/interruption synthesis is refused: there is no defensible target/label, and a
timestamp-only warp misses acceleration changes. Unobserved site translation is also refused in
this acceleration-only path. The separate optical site configuration remains exploratory.

Implementation tests pass. Physical fidelity is **unvalidated**: the post-run, non-tuning diagnostic
checks all 607 matched signals and reports per-axis distributions, spectra, rail fractions and
within-pair magnitude correlation. For example, left-forearm median envelope changes 0.738→0.733 g
and HF fraction 0.0322→0.0270. That expected filtering effect and similar aggregate distributions
do not reproduce physical ADXL335 response. [Diagnostic](runs/phase3/augmentation-fidelity.json).

## 5. Matched untouched-real evaluation

Each side uses all 30 volunteer LOSO folds, 29 training volunteers, fixed `C=1` and the existing
61-feature C detector/extractor. Each training recording contributes total weight one, shared by
its original and one augmented copy. Test inputs are untouched measured recordings under the
existing ±3 g preprocessing contract. No configuration/threshold was chosen on these scores.

| Recorded side | Retained / available | Quality real → augmented; majority floor | Quality difference, subject-bootstrap 95% | Exercise real → augmented; majority floor |
| --- | --- | --- | --- | --- |
| L | 301 / 342 (88.01%); 41 rejects | 92.36% → 92.36%; 50.17% | 0.00 pp, [-1.31, +1.32] pp | 98.01% → 98.67%; 34.55% |
| R | 306 / 342 (89.47%); 36 rejects | 89.87% → 90.20%; 50.65% | +0.33 pp, [-0.67, +1.62] pp | 97.06% → 97.06%; 33.99% |

Training-fold-majority predictors score quality/exercise 46.84%/33.22% for L and 50.65%/30.39% for R.
Exercise difference intervals are [0.00, +1.64] pp for L and [0.00, 0.00] pp for R. These are 2,000
volunteer-block bootstrap draws, not independent-repetition intervals. Both quality intervals include
no change; no convincing quality benefit is established. Side cohorts differ; this is not a side
ranking. There were zero rejected transformed feature bags in this configuration. All source
rejections, per-person retention, folds and lineage are in the committed side reports.

The independent saved-result audit recomputed both tasks' scores, exactly matched real-only
decisions to accepted causal predictions, checked every fold/source hash, and regenerated sampled
NPZs bit for bit. [Audit output](runs/phase3/results-audit.log). No accepted model was replaced or
new augmented model exported. The fixed architecture would still have 992 B of float32 coefficients;
adding host training examples does not add on-device parameters. Series labels establish neither
repetition correctness nor error categories.

## 6. Local visualization

[Open the running workbench](http://127.0.0.1:8765); [instructions and example](INSPECTION-PHASE3.md).
It uses ordinary HTML/canvas and a loopback Python server. The default source/config works locally.
It shows two links/mounts, all four arrangements, play/pause/scrub/reset, six shared-axis g traces,
clipping, C detector events, unavailable states and exact provenance. Settings call the same Python
augmentation implementation. JSON export also records the selected visual arrangement/view/time.

The default loop is illustrative. Optional measured optical-board replay uses measured positions/
quaternions with assumed anatomy/geometry and a separate recording-start clock. It explicitly does
not establish synchronization with the acceleration. Neither view implies validated biomechanics.
Desktop and mobile screenshots were opened and inspected; browser interaction, export, error recovery
and layout checks pass. Screenshots/example download remain ignored under `data/phase3-inspection/`.

## 7. Feedback groundwork and target cost

[Evidence, API, pilot and footprint](FEEDBACK-PHASE3.md). The portable C layer takes exercise,
prescribed duration/bounds, measured duration, validity and boundary-evidence provenance. It returns
cue, measurement, target/bounds, applicability, reason and fixed descriptive message. It operates
independently of the quality classifier, so a “correct” prediction cannot suppress a measured
deviation. A “wrong” prediction cannot invent a cause. Current detector events are unvalidated
anatomical boundaries and therefore **abstain**. Five test groups and replay fixtures pass; fixtures
are synthetic test evidence, not measured feedback accuracy. ROM/posture/effort/grip remain unavailable.

Before implementation the scalar function was budgeted at zero persistent state, no sample buffer,
O(1) comparisons and <300 B added target text. Actual Cortex-M4F unity-object measurement is
**+581 B text/rodata/exidx, zero module BSS, 16 B compiler frame**. Complete causal baseline is
2,546 B text/rodata/exidx + 14,488 B BSS; with feedback 3,127 + 14,488 B. Config/measurement/result
records are 28/28/48 B (104 B if retained together, plus caller-owned strings). With prior explicit
stack/core/display/interrupt reserves, the provisional one-pair total is 24,832/32,768 B, leaving
7,936 B. Two float-buffered pair states plus core alone are 33,040 B, already over RAM.

These are unlinked objects and arithmetic reserves, not linked firmware flash, RAM high-water or
hardware timing. They include detector, features, classifier and pooling, but libm/compiler helpers,
Arduino acquisition/core/display linking remain unmeasured. No Arduino CLI/GNU ARM linker is
installed here; Clang target compilation succeeded. Four ADXL335s need 12 analog channels versus
six available; one pair consumes six. No firmware edit or board execution was necessary or performed.

A later small learned error head would need independently observed, exercise-specific, multi-label
deviations per repetition, reliable boundaries, uncertain/unobservable fields, prescription versions,
subjects/remount lineage and held-out-person false-cue/coverage evaluation. Begin only after rater
reliability is measured. A separate logistic output per supported deviation could reuse existing
features (arithmetic: 62×4 = 248 coefficient bytes/output, plus one sigmoid/output and validation
logic), but its usefulness is unknown. Do not force simultaneous faults into one class. Dynamic ROM
needs independently calibrated kinematics/reference; trunk posture needs a view/sensor of the trunk;
grip/load/effort claims need separately defined force/load or physiological outcomes. Additional
sensing has its own acquisition and resource cost. No such model was trained in this phase.

## 8. Reproduction, actual outputs and commits

Run from `/home/peter/work/198-Project`. The environment is Python 3.12.14, NumPy 2.3.4, SciPy 1.16.3,
scikit-learn 1.7.2, with MuJoCo 3.3.7 for historical simulation tests. Use the locked setup in
[MODELLING-ENVIRONMENT.md](MODELLING-ENVIRONMENT.md); this session used the existing
`/tmp/tally-round2-env/bin/python`. All numerical runs used:

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/tmp/tally-round2-env/bin/python scripts/placement_replay.py --out docs/runs/phase3/simulation-placement.json
/tmp/tally-round2-env/bin/python scripts/augmentation_pipeline.py data/phytmo/inertial/upper --config configs/augmentation-example.json --out data/phase3-augmentation
/tmp/tally-round2-env/bin/python scripts/verify_phase3_results.py
/tmp/tally-round2-env/bin/python scripts/augmentation_fidelity.py
/tmp/tally-round2-env/bin/python scripts/feedback_replay.py
/tmp/tally-round2-env/bin/python scripts/measure_feedback_target.py
/tmp/tally-round2-env/bin/python -u scripts/verify_round2.py
/tmp/tally-round2-env/bin/python scripts/inspection_server.py --port 8765
```

Generate without fitting by adding `--generate-only` and choosing another output directory; the
documentation's example uses `data/phase3-generation`. Unit scripts are `test_augmentation_pipeline`,
`test_augmentation_fidelity`, `test_placement_replay`, `test_feedback` and `test_inspection_server`.
The inspection HTTP tests require permission to bind loopback in this sandbox; they passed when run
with that permission. Browser-QA exact module/browser paths are recorded in [the tool guide](INSPECTION-PHASE3.md).

Actual notable output (full stdout files are under [runs/phase3](runs/phase3/)):

```text
Optical pose replay: 1440 rows, 24 group summaries
Measured-site calibration gate: False (clock and board-to-chip extrinsics unidentified)
L: scores independently recomputed; 301 matched baseline sources, 41 rejected, 30 disjoint folds; 301 variants retain volunteer/labels/hashes/version; four-task saved decisions checked; sampled NPZ replay bit-identical
R: scores independently recomputed; 306 matched baseline sources, 36 rejected, 30 disjoint folds; 306 variants retain volunteer/labels/hashes/version; four-task saved decisions checked; sampled NPZ replay bit-identical
All 10 valid models: exact saved coefficients, C probability parity and every LOSO series decision verified.
```

The nine original regression scripts also pass; [regression log](runs/phase3/regression-tests.log).
The [delivery verification](runs/phase3/delivery-verification.log) records tool versions, available
target tools, unchanged protected artifacts and the absence of physical/linked-image measurements.
The reported causal coefficient drift did not recur. Assertions were not weakened, exports were not
refreshed, and every accepted coefficient refit error is exactly zero. Logs separately report small
C/Python probability errors under the existing assertion, with zero decision differences.

| Completed item | Commit |
| --- | --- |
| Research/decision memo before implementation | `7f155d1` |
| Augmentation, matched results, fidelity and independent artifact audit | `26833bc` |
| Simulator audit, four mounts and optical replay | `08045ac` |
| Feedback research, C groundwork, tests and target measurements | `1db7d23` |
| Local workbench, API checks and desktop/mobile verification | `e22c7d1` |
| Final optical reference cohort correction and pose-timing hardening | `e244b0c` |

Generated examples/manifests/predictions occupy about 133 MB locally under ignored
`data/phase3-augmentation/augmentation-example/{L,R}/`; no raw dataset, archive or file over 50 MB
was committed. Each folder contains `generated/*.npz`, `augmentation-manifest.jsonl`, `example.json`,
`results.json` and `predictions.csv`. The final delivery commit adds this report, index links and
the verification record; its hash is reported in the chat and is available from `git log`.

## 9. Uncertainties, decisions and the next experiment

Unresolved: actual ADXL335 bias/gain/bandwidth/noise/aliasing/saturation recovery; sample simultaneity;
clock and chip/anatomy origins; self-remount and patient transfer; anatomical boundaries and error
labels; prescription applicability; false feedback/abstention; complete linked resource usage and
on-device acquisition/feature/display latency. A plausible animation and host replay prove none of
these. Bench work still needs ADC calibration/cadence, channel skew, saturation/filter response,
RAM high-water/stack, computation latency and repetition-end-to-display timing.

Owner decisions: one-limb prototype versus two-limb acquisition/memory redesign; actual prescribed
targets and allowed wording; indexed strap instructions and joint clearance; supervised pilot,
raters/video handling; whether calibrated optical replay is worth further collection. No universal
placement preference or clinical target was fabricated for those decisions.

**Single most useful next experiment:** the staged, intended-ADXL335 paired-sensor timing/remount
pilot in [FEEDBACK-PHASE3.md](FEEDBACK-PHASE3.md): three volunteers, three exercises, four approved
timing conditions, four repetitions and before/after self-remount blocks (288 planned repetitions).
Record a visible/logged sync event, source geometry/orientation, acquisition cadence and actual
prescription; have two independent raters annotate observed boundaries/deviations, blinded to
instructions and model output. Add measured chip/marker origins if optical replay is pursued.
This is a feasibility budget, not a guaranteed sample size. It addresses the evidence that currently
blocks physical augmentation, timing feedback and useful remount evaluation before a larger study.
