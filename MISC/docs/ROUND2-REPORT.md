# Simulation, placement and evidence — round two, 2026-11-07

The requested experiments are complete. Pair fusion and a bounded causal C pipeline now exist;
the numerical environment is enforced. The evidence supports a paired prototype, **not a validated
patient error coach**. The constructed limb simulator failed its empirical gate. No error mechanisms
or hardware latency are claimed. Accepted round-one models, coefficients, benchmark history,
fetcher and firmware are unchanged.

**Repository delivery constraint:** this session mounts the original `.git` read-only. A normal
`git add` failed with `Unable to create .git/index.lock: Read-only file system`. Commits were made
on `codex/simulation-placement` in the writable metadata copy `/tmp/tally-round2.git`, using this
same working tree. The original branch reference cannot be advanced from this session. The
incremental bundle `output/round2-commits.bundle` contains the commits; `output/round2-commits.txt`
lists every hash. Nothing was pushed, and no PR or repository comment was made. Existing untracked
`output/` and `tmp/` contents were left intact.

## Fixes and commits

| Requirement | Commit(s) | Proof |
| --- | --- | --- |
| Fuse two sensors into one decision | `7cd731e`, corrected by `068b08a` | `timing-checks.log`: exact fresh-fit coefficients and zero C/Python series-decision differences for both sides; pairing/clock/gap tests |
| Causal detector, on-device features and inference | `e3695f8`, corrected by `068b08a`, numerical edge fix `c646a07` | `final-checks.log`: prefix causality, bounded buffers, invalid sample/timing rejection, constant-axis moments; integrated sample-to-pooled-output C parity |
| Enforce environment | `9b3e5e2` | `fix3-environment.log`: locked fresh environment, mismatch refusal, accepted export zero coefficient and decision differences |
| A: research, borrowed simulation and optical reference | `d120e52`, gate-order fix `dee3952` | `simulation.log`, `optical-reference.log`: physics assertions and empirical comparison, including failure |
| B: placement and remount stress | `e61a5f5` | `placement.log`: common-cohort LOSO, floors, coverage, subject-bootstrap intervals |
| C: physical evidence and annotation plan | `6693261` | `error-evidence.log`; [instruction/rater protocol](ROUND2-ERROR-PROTOCOL.md) |
| D: complete target cost and all-export verification | `f98ad60` | `target-size.log`, `all-model-checks.log`: every valid model compiled and every stored held-out decision rechecked |

The initial `paired-offline/` and `paired-causal/` exports are **invalid timing history**, not valid
results. Research established that exported starts were synchronized by the authors while retained
timestamps were independent device uptime. The first implementation incorrectly intersected uptime.
The shared aligner now subtracts each recording's initial time and resamples relative timestamps.
An independent EAH gyro-event audit supports that interpretation; gyro is used only for this timing
audit, never as a model input. The corrected exports are `paired-synchronized-*`. No individual
record's lag was fitted to improve a test score. Residual timing/calibration error remains possible.
The correction and numerical edge regression are recorded, not hidden by rewriting history.

## Positions and research

[Pre-code positions and rejected alternatives](ROUND2-PLAN.md) cover the fixes and A–D, with confidence
marks and owner decisions. [Research memo](ROUND2-RESEARCH.md) links the primary sources actually
opened, the unsuccessful Nature HTML access, alternatives not installed/benchmarked, and claims
not verified. In particular, an accelerometer's dynamic signal does not uniquely determine 3D joint
angle or muscle effort. No such claim is made by fusing the pair.

**A — decision, medium confidence in physics, low in distribution fidelity.** Borrowed MuJoCo's
site accelerometers and rigid-body stages; no new physics solver. Independent static-gravity and
analytic-pendulum checks pass. The illustrative two-link trajectories include harmonics, motion
modulation and high-frequency content. The sensor chain is accelerometer-only, at 100 Hz with
per-axis ±3 g clipping, bandwidth/noise, bias and ADC quantization. These settings are assumptions
listed in the pre-code memo, not measured hardware calibration.

Shallow halves excursion, fast compresses time, misaligned changes the motion plane, and a stalled
trajectory stops part way. Weak effort with unchanged kinematics deliberately produces identical
signals. Calling reduced acceleration “weakness” would invent evidence. The SQZ analogue omits
wrist pronation and cloth/grip mechanics; it is particularly unsuitable for task-quality inference.
The simulation also omits patient pathology, pain, soft tissue, band slip, force/load changes,
out-of-band vibration/aliasing, sample skew and real saturation recovery.

Before model responses, nominal simulation was compared with correct held-out recordings by
exercise and segment: magnitude envelope, dominant frequency, cycle peak distributions, detected
cycle durations and high-frequency energy fraction. Nominal period came only from other volunteers;
geometry and other settings were fixed in advance. The predeclared median-ratio/distribution-distance
gate failed for every comparison. **No synthetic accuracy is reported.** The logged classifier
responses are failed-domain diagnostics: even constructed faults can receive “correct” scores.
A confident model response is not evidence that the simulated or real movement was safe/correct.
The validator's failure is the result, not a simulator performance endorsement.

The simultaneous optical trajectories were explicitly preferred as the eventual motion reference.
A deterministic CRC-checked subset covers age groups, exercises and correct/wrong series. They give
closer aggregate envelopes/frequencies/peaks than the constructed links, but retain missing spans
and derivative filtering loses high-frequency energy. Comparisons are distributional, **not clock
aligned**, and chip-to-board position remains unmeasured. No optical quality/angle accuracy is
claimed. Future simulator development should start with calibrated optical replay, not tune smooth
arcs until a classifier agrees. Optical raw files remain under ignored `data/`; the original range
fetcher was reused without modification.

**B — decision, medium confidence for recorded sites, low for self-placement.** Both measured
same-limb pairs and all four single-sensor feature ablations were evaluated on the same retained
cohort. Each ablation uses the pair's forearm-derived causal boundaries; it does not validate a
standalone upper-arm detector. Paired features score higher here than either corresponding
single-sensor feature set. Side-difference bootstrap intervals include zero, so the evidence does
not justify selecting a universally better side. The smaller side difference on a common cohort
also explains why comparing differently filtered side cohorts would mislead.

Use the recorded exterior-lateral upper-arm/forearm pair as the **prototype reference placement**,
on the limb prescribed for the exercise. Exact cm from elbow, wrist alternatives, inside/outside
comparisons, strap tightness and patient self-application were not recorded. There is no numerical
proof of an optimum among those unobserved sites. Indexed straps, clear orientation marks and a
neutral-pose check are proposals to test, not proven remedies. A neutral gravity pose cannot resolve
all rotations or recover dynamic joint angle.

Held-out rigid rotations of measured vectors strongly degrade scores. These are **simulated
remounts of real recordings**, with original series labels, not newly recorded patient placements.
This direct mathematical stress does not depend on the failed synthetic-motion gate. It excludes
translation, bias and soft tissue. Mechanical ±5 cm offset diagnostics are also logged, but A's
failed domain gate forbids using those numbers to rank patient locations. No model was retuned or
selected on these test folds. The study does not establish which placement is best for a patient
who applies the band poorly each day.

**C — decision, high confidence in refusal, low mechanism identifiability.** Duration, acceleration
envelopes and sensor-magnitude correlation show heterogeneous deviations relative to references
from correct same-exercise recordings of other volunteers. Flags overlap and occur in correct
series too. They are non-specific signals, not separable ground-truth mechanisms. Unsupervised
clusters could not establish causal names without external annotations. We therefore export no
error classifier and retain `not enough evidence to say`.

The host diagnostic includes quantity, units, training-only median/scale, robust deviation and
flags; it does not translate them into “you did X wrong.” A future timing explanation would be a
heuristic relative to a prescribed duration, requiring independently annotated video, false-
explanation/abstention checks and held-out-person/remount validation. Acceleration envelope is not
range of motion; muscle weakness needs a separate force/effort target.

The proposed annotation pilot, printable record/instruction sheet, independent raters, disagreement
handling, agreement metrics and planning-cost arithmetic are in [the protocol](ROUND2-ERROR-PROTOCOL.md).
Its sample size is a concrete feasibility proposal, **not a guaranteed sufficient minimum**. Actual
sample needs depend on agreement, effect sizes and person/remount variability. Instruction condition
is kept separate from observed outcome; weak/unobservable causes stay unavailable. No data collection
or patient-facing wording was approved or performed by this round.

**D — decision, high confidence in object/state measurements, medium in a one-pair budget path.**
A sample enters the C API in calibrated g on six synchronized channels. The pipeline clips, filters
its detection signal, detects causal peak-confirmation intervals, extracts both sensors' statistics,
classifies, and averages probabilities for a caller-defined series. Partial/overflow cycles and
invalid timing/samples abstain/reset. Per-cycle scores remain provisional; only series labels exist.
The detector's cycle count differs from offline segmentation, and durations often reach its minimum
interval. No anatomical repetition-count/boundary validation is claimed.

The buffer stores bounded raw samples because exact mean-centered zero crossings and stable central
moments need a second pass. Per axis it computes mean, population standard deviation, min, max,
range, RMS, skew, excess kurtosis, energy and mean-centered crossing rate. The command output below
counts buffer bytes, axis visits, arithmetic, square roots and classifier operations. Per incoming
sample the detector also clips six channels, stores them, computes magnitude/EMA and updates bounded
state; these operations and feature costs are included in the target object.

Complete causal object text includes coefficients, detector, features, classifier, pooling and entry
wrappers. It is a freestanding **unity object**, not a linked Arduino image. Unresolved `expf`,
`sqrtf`, `fminf`, `fmaxf`, and `__aeabi_memclr4`, core, acquisition and display must still be linked
and measured. Compiler stack estimates include a dynamic classifier frame; they are not a measured
whole-program stack bound. The explicit reserves below are estimates. Offline exports are benchmark
controls; the separately trained causal counterparts are the deployable candidates. Single-sensor
controls have an integrated C selection path, including the forearm-only selection macro, but still
use the shared detector and buffer.

One pair has a credible path inside the board limits with these reserves. Two simultaneous float
buffers plus the estimated core reserve exceed RAM before display/stack. A calibrated int16 ADC
buffer or time-sharing is the smaller route if two limbs become mandatory; neither is silently
claimed implemented. Two three-axis accelerometers consume all six analog inputs; the full four-
sensor design still needs an acquisition/interface decision. ADC/display pin scheduling and actual
sample simultaneity remain hardware integration work.

The confirmation component is calculated below; hysteresis waiting and true anatomical repetition
end are unknown. MCU computation, acquisition and display timing are **not measured**. There is no
mid-repetition correctness claim and no end-to-display latency bound. The firmware sketch was left
untouched because the requested experiments use a portable C API, target objects and host replay;
no physical board/application integration was possible or necessary for these measurements.

## Reproduced output and provenance

The following command was run. Its output is pasted verbatim (accuracy rows explicitly identify real
recordings or simulation). Majority-class floors accompany every accuracy. Full training-majority
predictor values, subject folds and per-series predictions are in the per-model results and logs.
The historical baseline row is read from the accepted artifact, not retrained; it is not a matched-
cohort comparison to the new paired rows. All new accuracy experiments use LOSO across the volunteers,
training-only scaling/references and fixed settings. Rotated-series abstentions count as failures.

Real-data rows use the original NGIMU accelerations, software-clipped per axis before detection/features; physical ADXL335 transfer remains unproven.
The main paired accuracy rows are conditional on accepted timing records. The printed retention
fractions and enumerated rejected files prevent mistaking them for all-file coverage. The common
cohort is smaller again. These exclusions and the volunteer-to-patient gap limit generalization.

```text
$ /tmp/tally-round2-env/bin/python scripts/round2_summary.py
Accepted historical baseline, read only (not rerun): {"n_series": 1368, "quality_loso_accuracy": 0.8698830409356725, "quality_majority_class_floor": 0.5, "exercise_loso_accuracy": 0.945906432748538, "exercise_majority_class_floor": 0.34502923976608185}
| Source / configuration | series | quality accuracy / majority floor | exercise accuracy / majority floor |
| --- | ---: | ---: | ---: |
| REAL recordings / L paired offline | 301 | 91.03% / 50.17% | 98.01% / 34.55% |
retention offline/L: 301/342 = 0.880117; rejected reasons: {'timestamps not near 100 Hz, reversed or gap >50 ms': 41}
| REAL recordings / R paired offline | 306 | 88.89% / 50.65% | 96.41% / 33.99% |
retention offline/R: 306/342 = 0.894737; rejected reasons: {'timestamps not near 100 Hz, reversed or gap >50 ms': 36}
| REAL recordings / L paired causal | 301 | 92.36% / 50.17% | 98.01% / 34.55% |
retention causal/L: 301/342 = 0.880117; rejected reasons: {'timestamps not near 100 Hz, reversed or gap >50 ms': 41}
| REAL recordings / R paired causal | 306 | 89.87% / 50.65% | 97.06% / 33.99% |
retention causal/R: 306/342 = 0.894737; rejected reasons: {'timestamps not near 100 Hz, reversed or gap >50 ms': 36}
| real recordings; common cohort; L-pair; common C boundaries | 269 | 91.08% / 50.56% | 97.77% / 33.83% |
| real recordings; common cohort; L-upper; common C boundaries | 269 | 88.85% / 50.56% | 95.17% / 33.83% |
| real recordings; common cohort; L-forearm; common C boundaries | 269 | 86.99% / 50.56% | 96.28% / 33.83% |
| real recordings L 0deg | 269 | 91.08% / 50.56% | 97.77% / 33.83% |
| simulation: mount rotation applied to held-out real recordings L 15deg | 269 | 91.08% / 50.56% | 95.91% / 33.83% |
| simulation: mount rotation applied to held-out real recordings L 30deg | 269 | 87.36% / 50.56% | 89.96% / 33.83% |
| simulation: mount rotation applied to held-out real recordings L 60deg | 269 | 71.38% / 50.56% | 59.85% / 33.83% |
| real recordings; common cohort; R-pair; common C boundaries | 269 | 90.71% / 50.56% | 97.40% / 33.83% |
| real recordings; common cohort; R-upper; common C boundaries | 269 | 87.36% / 50.56% | 95.54% / 33.83% |
| real recordings; common cohort; R-forearm; common C boundaries | 269 | 88.48% / 50.56% | 97.03% / 33.83% |
| real recordings R 0deg | 269 | 90.71% / 50.56% | 97.40% / 33.83% |
| simulation: mount rotation applied to held-out real recordings R 15deg | 269 | 86.99% / 50.56% | 95.54% / 33.83% |
| simulation: mount rotation applied to held-out real recordings R 30deg | 269 | 77.70% / 50.56% | 91.45% / 33.83% |
| simulation: mount rotation applied to held-out real recordings R 60deg | 269 | 65.80% / 50.56% | 65.43% / 33.83% |
Common-cohort retained fraction: 0.7865497076023392
Side difference/subject-bootstrap intervals: {"quality": {"left_minus_right": 0.0037174721189591076, "subject_bootstrap_95_interval": [-0.03309128771434773, 0.042556977360490626], "interpretation": "exploratory side comparison; no model selection or tuning"}, "exercise": {"left_minus_right": 0.0037174721189591076, "subject_bootstrap_95_interval": [-0.011363636363636364, 0.01976480644958905], "interpretation": "exploratory side comparison; no model selection or tuning"}}
Simulation empirical gate: False passed 0 of 84
| Source: real vs SIMULATION / left forearm | real p10/p50/p90 | simulation p10/p50/p90 |
| --- | --- | --- |
| EAH envelope_g | 0.6433, 1.2523, 1.7137 | 2.3273, 2.3273, 2.3273 |
| EAH dominant_hz | 0.3000, 0.5000, 0.6000 | 0.8000, 0.8000, 0.8000 |
| EAH peak_p50_g | 1.3567, 1.7925, 2.2354 | 2.8585, 2.8585, 2.8585 |
| EAH peak_p90_g | 1.5355, 2.0214, 2.6585 | 2.9488, 2.9488, 2.9488 |
| EAH duration_p50_s | 1.2000, 1.2000, 1.4350 | 1.2000, 1.2000, 1.2000 |
| EAH duration_p90_s | 1.4600, 1.5830, 1.9960 | 1.2060, 1.2060, 1.2060 |
| EAH hf_fraction | 0.0032, 0.0062, 0.0273 | 0.0624, 0.0624, 0.0624 |
| EFE envelope_g | 0.3255, 0.6385, 0.8789 | 1.0916, 1.0916, 1.0916 |
| EFE dominant_hz | 0.4900, 0.7000, 1.2100 | 0.8000, 0.8000, 0.8000 |
| EFE peak_p50_g | 1.1748, 1.3401, 1.4870 | 1.7490, 1.7490, 1.7490 |
| EFE peak_p90_g | 1.2492, 1.4286, 1.5937 | 1.8655, 1.8655, 1.8655 |
| EFE duration_p50_s | 1.2000, 1.2000, 1.3825 | 1.2000, 1.2000, 1.2000 |
| EFE duration_p90_s | 1.3081, 1.4560, 1.5993 | 1.2000, 1.2000, 1.2000 |
| EFE hf_fraction | 0.0044, 0.0182, 0.0335 | 0.1414, 0.1414, 0.1414 |
| SQZ envelope_g | 0.2030, 0.3377, 0.5874 | 1.5989, 1.5989, 1.5989 |
| SQZ dominant_hz | 0.7000, 1.2000, 2.2000 | 0.8000, 0.8000, 0.8000 |
| SQZ peak_p50_g | 1.1261, 1.2141, 1.3558 | 2.0517, 2.0517, 2.0517 |
| SQZ peak_p90_g | 1.1578, 1.3184, 1.5287 | 2.1654, 2.1654, 2.1654 |
| SQZ duration_p50_s | 1.2000, 1.2000, 1.3905 | 1.2000, 1.2000, 1.2000 |
| SQZ duration_p90_s | 1.3708, 1.4860, 1.8058 | 1.2000, 1.2000, 1.2000 |
| SQZ hf_fraction | 0.0593, 0.1014, 0.2055 | 0.1349, 0.1349, 0.1349 |
Optical reference: {"selected_files": 30, "comparisons": 39, "interpretation": "not synchronized; Y-up and origin at board rather than chip; derivative filtering attenuates high frequency; reference diagnostics only, no model accuracy or angle validation"}
Physical deviation summaries (NOT mechanism accuracy): [{"source": "real recordings; descriptive deviations, not mechanism accuracy", "series_label": 0, "series": 306, "feature_flag_fraction": {"cycle_duration_s": 0.1503267973856209, "upper_envelope_g": 0.016339869281045753, "forearm_envelope_g": 0.0, "magnitude_correlation": 0.042483660130718956}, "any_flag_fraction": 0.19607843137254902, "multiple_flags_fraction": 0.013071895424836602}, {"source": "real recordings; descriptive deviations, not mechanism accuracy", "series_label": 1, "series": 301, "feature_flag_fraction": {"cycle_duration_s": 0.03322259136212625, "upper_envelope_g": 0.31893687707641194, "forearm_envelope_g": 0.07973421926910298, "magnitude_correlation": 0.1461794019933555}, "any_flag_fraction": 0.46511627906976744, "multiple_flags_fraction": 0.09302325581395349}]
Annotation planning ESTIMATES: {"people": 12, "exercises": 3, "conditions": 5, "repetitions": 8, "total_repetitions": 1440, "collection_hours": 9.0, "rater_hours": 8.0}
| Model | parameter B | classifier allocated text B | complete causal allocated text B | causal BSS B |
| --- | ---: | ---: | ---: | ---: |
| model/paired-synchronized-causal/L | 992 | 1332 | 2546 | 14488 |
| model/paired-synchronized-causal/R | 992 | 1332 | 2546 | 14488 |
| model/paired-synchronized-offline/L | 992 | 1332 | offline control | offline control |
| model/paired-synchronized-offline/R | 992 | 1332 | offline control | offline control |
| model/placement-controls/L-forearm | 512 | 852 | 2090 | 14488 |
| model/placement-controls/L-pair | 992 | 1332 | 2546 | 14488 |
| model/placement-controls/L-upper | 512 | 852 | 2066 | 14488 |
| model/placement-controls/R-forearm | 512 | 852 | 2090 | 14488 |
| model/placement-controls/R-pair | 992 | 1332 | 2546 | 14488 |
| model/placement-controls/R-upper | 512 | 852 | 2066 | 14488 |
Target state/reserves ESTIMATES: {"static_bytes": 14488, "stack_reserve": 4096, "core_reserve": 4096, "oled_reserve": 1024, "interrupt_reserve": 1024, "total": 24728, "headroom_of_32768": 8040}
Actual feature arithmetic contract: {"max_samples": 600, "axes": 6, "buffer_bytes": 14400, "axis_sample_visits_per_cycle": 7200, "approx_multiplications_before_scalar_normalization": 14400, "approx_add_sub_before_scalar_normalization": 21600, "square_roots_per_cycle_features": 12, "classifier_mac_per_pair_cycle": 244, "classifier_expf_per_cycle": 4}
Latency components / limits: {"confirmation_component_s": 0.2, "ema_time_constant_s": 0.04481420117724551, "true_repetition_end_to_display": "not measured; unknown anatomical boundary, hysteresis wait, refractoriness, MCU feature/libm/ADC/display timing", "mid_repetition": "not validated"}
Two runtime states plus core reserve ESTIMATE: 33040
```

Every underlying run keeps its command and output in [runs/round2](runs/round2/):

* [Timing correction/audit and paired runs](runs/round2/timing-correction.log),
  [paired export checks](runs/round2/timing-checks.log).
* [Environment and accepted-export verification](runs/round2/fix3-environment.log).
* [Simulation: all distribution comparisons and diagnostic responses](runs/round2/simulation.log),
  [optical reference](runs/round2/optical-reference.log), [archive/header inspection](runs/round2/optical-inspection.log).
* [Placement, floors, coverage and bootstrap](runs/round2/placement.log).
* [Descriptive evidence and annotation arithmetic](runs/round2/error-evidence.log).
* [Target compiler commands, sections, unresolved symbols and stack files](runs/round2/target-size.log),
  [all-model coefficient/C/LOSO verification](runs/round2/all-model-checks.log),
  [final assertions and unchanged-history checks](runs/round2/final-checks.log).

Machine-readable JSON retains detailed distributions, folds, rejection reasons and evidence. Raw
inertial/optical recordings, archives, feature matrices and any file over the requested size limit
were not committed. All generated result artifacts are small derived summaries/predictions.

Reproduce with the locked environment described in [setup](MODELLING-ENVIRONMENT.md); simulation/
optical/placement commands need the pinned host-only `simulation` extra. Every comparison uses the
existing fixed linear recipe; no baseline retuning, learning-curve re-derivation or data-fetch rebuild
was performed. The original acceptance tests still pass. Platform/BLAS numerical drift remains a
reason to run export verification even with version pins.

## What remains unproven and the next experiment

Unproven: real ADXL335 transfer and clipping/noise response; patient/remount generalization;
anatomical repetition boundaries and per-repetition correctness; force/weakness and named error
mechanisms; chip-level optical alignment and simulation fidelity; a fully linked board image,
actual RAM high-water mark, acquisition simultaneity, latency and display integration. These are
experimental limits, not promised software results.

**Single next experiment:** run the proposed supervised video+real-ADXL335 annotation/remount pilot.
Use both sensors on one limb, the intended self-application instructions and before/after remount
blocks; record the actual ADC cadence and GPIO/visible event timing alongside the sensor/video data.
That one study supplies independent repetition/error evidence, physical sensor transfer information
and remount variation. Evaluate people with LOSO and keep a learning curve; do not train on invented
mechanism labels. Adding another large model or tuning the failed simulator is lower priority.

## Decisions for the owner

* Approve prototype scope: one affected limb/two sensors with a provisional series quality score,
  or fund a different acquisition/memory design for two limbs.
* Specify prescribed exercise ranges/tempo, safe observable error definitions, required calibration,
  and whether any patient-facing score/wording is appropriate. No response to the optional target
  question was received; all experimental targets therefore remain illustrative engineering settings.
* Choose and test indexed mounting instructions; neither left/right superiority nor exact sensor
  distance/tightness has been established for self-application.
* Approve the annotation pilot/codebook, supervision, video handling, raters and student time.
  Decide whether a separate measured-force outcome is actually required for “weak.”
* Allocate board integration/timing/saturation checks before calling the device validated, and
  calibrated optical replay if simulation fidelity is worth further work.
* Import the verified Git bundle when repository metadata is writable. No push is needed.

For a clean checkout at the original base, import the branch into a temporary ref first and inspect
it. This session's shared working files already contain the result; do not discard unrelated work
or reset the tree merely to advance a reference. Bundle verification and a clean imported-checkout
comparison are retained in the delivery log.
