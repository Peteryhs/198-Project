# Copyable continuation prompt for the next agent

**Latest steering:** the user asked to park costly simulator reconstruction and focus on the actual
wearable. A fixed tiny GRU has now been trained on matched real recordings across all 30 volunteers
on both sides; see `docs/TINY-RNN-REPORT.md` before the older Phase5 priorities below. Its quality
agreement is 88.37%/86.60% versus 92.36%/89.87% for the accepted classifier, so it was not adopted.
This architecture change does not create missing error-type labels. Preserve that distinction and
do not resume simulator optimisation as the default next step. The current branch contains the
new experiment; inspect actual HEAD rather than the historical branch named below.

You are continuing Tally, a student rehabilitation-sensing project, in the Git repository
`/home/peter/work/198-Project` (Peteryhs/198-Project). Work from the actual checked-out HEAD on
`codex/reconstruction-audit-handoff`; inspect status/log before assuming the branch is unchanged.
The previous Phase 4 delivery was `bdb8bfd`. Phase 5 adds the focused audit described below.
Read this entire prompt, then the linked evidence. Do the work; do not merely restate a plan.

## User intent and newest steering

The user has no physical Arduino/sensors available. They want a credible virtual model, an honest
assessment of where upper-arm/forearm accelerometers should be mounted, and understandable graphics.
They authorized a second attempt to establish sensor location, verify reconstruction and audit the
whole testing/reporting pipeline: a reporting defect could otherwise conceal or fabricate progress.
They asked for all findings to be committed locally and this prompt so another agent can continue.

They also asked two important questions:

1. Why did the study not document placement? Correct the premise: it DOES describe exterior-lateral
   upper-arm/forearm placement, nominal axes and approximate positions in Figure 1. What we have
   not established is per-wearer landmark distance, chip origin and complete trustworthy registration.
   Do not imply the authors omitted all placement information or assert undocumented metadata
   cannot exist elsewhere.
2. Could software calibrate to each user's arm instead of requiring an exact placement? This is
   a promising alternative to evaluate, not an implemented feature or authorization to pretend it
   already works. Separate sensor calibration from classifier personalization. Propose a reasonably
   consistent mounting region plus brief calibration before considering learned adaptation. Bias,
   gain and some orientation differences are correctable; arbitrary longitudinal relocation,
   soft-tissue motion, mounting slip and unobserved joint motion are not automatically removed.
   A single gravity pose cannot resolve all orientation or sensor bias/gain. Never teach the
   classifier that a user's unverified habitual movement is correct. Validate any personalization
   on later untouched real recordings with the allowed calibration data/labels explicitly defined.

The latest conversation has not cancelled the reconstruction audit. Present the personalized
calibration route alongside the remaining virtual-model limitations. Do not ask the user to repeat
context already in this repository, or imply that hardware is required for every next software step.

## Working rules

- Read `/home/peter/.codex/skills/ponytail/SKILL.md` first. Use the smallest complete solution.
- The user requested GPT-6 Luna/high reasoning subagents where available, with clear ownership.
  Prior agents audited reporting, anatomy and clock code independently. Their findings are committed.
- Make separate local commits for completed items. No push, PR, email or repository comments.
- Preserve raw data, archives, accepted exports, firmware, historical failures and preexisting
  untracked `output/` and `tmp/`. Do not stage those folders or commit files over 50 MB.
- Numerical tests must stay strict. Explain coefficient drift; do not refresh accepted exports
  or weaken assertions to get a pass. A finite audit cannot prove the absence of all bugs.
- Use plain language. Explain what changed, what was measured and what remains uncertain. Include
  simple graphics where useful, with assumed anatomy and illustrative signals labelled clearly.

## Read in this order

1. `docs/PHASE5-REPORT.md`, `docs/PHASE5-REPORTING-AUDIT.md`,
   `docs/PHASE5-SENSOR-LOCATION.md`, `docs/PHASE5-PLAN.md`.
2. `docs/PHASE4-REPORT.md`, `docs/PHASE4-DATA-AND-SOURCES.md`,
   `docs/PHASE4-CALIBRATION-METHOD.md`, `docs/PHASE4-ANATOMY-METHOD.md`,
   `docs/PHASE4-PLACEMENT-METHOD.md` and their JSON/config/script counterparts.
3. `docs/PHASE3-REPORT.md`, `docs/SIMULATOR-AUDIT-PHASE3.md`,
   `docs/AUGMENTATION-PHASE3.md`, `docs/FEEDBACK-PHASE3.md`.
4. `docs/README.md`, `docs/CONTEXT-AND-CONSTRAINTS.md`, `docs/MODELLING-REPORT.md`,
   `docs/ROUND2-REPORT.md`, `docs/ROUND2-PLAN.md`, `docs/ROUND2-RESEARCH.md`,
   `docs/ROUND2-ERROR-PROTOCOL.md`, `docs/QA-REVIEW-2026-11-07.md`,
   `docs/QA-REVIEW-ROUND2.md` including corrections, `docs/MODELLING-ENVIRONMENT.md`, `model/PAIRED.md`.
5. `docs/ORIGINAL-MODELLING-BRIEF.md` is the user's original full request, preserved verbatim.
   Its old branch/HEAD statements are historical; current Git state and subsequent evidence prevail.

## Hardware, labels and current classifier

The intended board is UNO R4 Minima: 256 kB flash, 32 kB RAM, 48 MHz Cortex-M4F. Four ADXL335 analog
accelerometers require 12 analog channels; the board has six analog inputs. Acquisition remains
an owner/hardware decision. One runtime pair consumes six acceleration channels. Simulation,
augmentation/training and visualization run on the computer. More training data do not enlarge a
fixed model; extra runtime features/buffers do. One float-buffered pair has a plausible RAM path;
two simultaneous float-buffered pairs exceed the earlier budget. Object measurements are not a
linked firmware footprint or physical timing. No physical hardware test was done.

The model recognizes the three study upper-limb exercises and whole-series correct/incorrect
labels using paired acceleration, 61 features and 992 bytes of float32 coefficients. The causal
C path includes sample handling, filtering, bounded cycle detection/features, inference and pooling.
Only `model/paired-synchronized-*` are valid paired exports. `paired-offline/` and `paired-causal/`
are invalid timing history. Read exact accepted metrics/cohorts in Round 2 and Phase 3; do not mix
conditional retained-series accuracy with all-file coverage or clinical/patient accuracy.

PHYTMO labels exercise identity and WHOLE-RECORDING correct/incorrect. There are no independent
per-repetition quality, error-type or effort labels. Detector cycles are not verified anatomical
repetitions. No posture/weakness/grip-force/effort diagnosis is supported. The feedback groundwork
only compares valid measurements to supplied prescribed timing targets and abstains when evidence
is unavailable; it does not invent targets or explain why the binary classifier voted incorrect.

## Dataset and provenance

All optical data come from the same original PHYTMO study, not new captures. The former five-person
subset was only a download choice. The local reference now includes 402 CRC/size-verified files:
171 raw first-series exercise trials +171 matching interpolated trials +30 upper Calib takes in
each representation, covering all 30 volunteers. Total uncompressed size is 2,465,165,313 bytes.
The archive contains 390 upper rigid-body files in each representation: 360 exercises +30 Calib.
Nine of 180 first-series conditions lack a local inertial counterpart. Do not turn these into
observed outcomes. Raw data/caches are ignored; small catalogues and derived decisions are committed.

Paths: `data/phytmo/inertial/upper/`, `data/phytmo/optical raw/rigid_bodies/upper/`,
`data/phytmo/optical interp/rigid_bodies/upper/`. A03 is named `A3...` in raw optical exports;
normalize identity for matching/folds but preserve exact paths. A01's raw-folder Calib file has
`_interp` in its name; flag it and do not infer representation from suffix alone. Extra marker-error
columns occur in some calibration headers. Select only rigid-body Position/Rotation fields.

92/201 paired raw/interpolated exports start at nonzero optical frame/time. Preserve crop origins.
Inertial timestamps are device uptime. Published IMU starts were manually synchronized/cropped by
the authors; this does not establish a shared optical/device clock. The correct paired classifier
uses relative recording starts, not intersection of independent device uptime.

The current optical mapping is L=(thigh2, shin2), R=(thigh, shin), ordered upper/forearm. It is the
repository's existing mapping. The inspected descriptor does not directly provide that rigid-body
name lookup; independently checking correspondence remains useful. Bilateral symmetric motion
can make magnitude-only matching ambiguous. Published nominal board/sensor basis IS known:
sensor X = negative board X, sensor Y = board Z, sensor Z = board Y. Y is world up; acceleration
is specific force including gravity. Do not describe all axes as unknown.

## What happened in Phase 4

- Original hand-driven MuJoCo simulation passes mathematical checks but failed its real-signal gate
  (historical 0/84 comparisons). It was not rewritten or declared validated.
- Added optical replay at displaced physical points, rotating both position and sensor axes when
  surface changes; SG11/polynomial3 second derivative; missing spans and five edge samples excluded.
- Fitted shared bounded orientation/origin/gain/bias corrections for four sensors in each of 30
  leave-one-person-out folds (120 fits). Training people only. Primary clock was training-person
  median gyro lag; held-out per-record gyro lag was separate reference-assisted diagnostic.
- Historical cohort: 653/684 sensor-records accepted, 31 rejected; 611 primary matched overlaps,
  591 active at measured dynamic RMS >=0.05 g. Mean active dynamic error .424600 -> .389286 g
  (8.317% reduction). Median total RMSE .384061 -> .359508 g. Dynamic correlation .1202 and NRMSE
  1.1953 fail declared thresholds. Clock-estimator discrepancy p95=67.69 s is not an independently
  measured clock error. All120 ranks12, 58 boundary-hit fits; numerical rank is not anatomy truth.
- Historical per-record gyro-assisted diagnostic: 571 matches, 380 active. Active mean dynamic
  error falls 4.348%, but median total error worsens .108666 -> .134250 g. Do not compare this
  different timing/cohort as an improvement over the primary track.
- Gate remains FAILED. Required timing p95<=.01s, coverage>=.95; active dynamic correlation>=.70,
  NRMSE<=.50, max abs bias<=.10g, mean dynamic RMSE improvement>=10%, rank12. Legacy distribution
  gate median ratio [.75,1.33], normalized Wasserstein<=.5 unchanged; not rerun as a new pass count
  after clock/waveform failure. Do not lower thresholds to manufacture success.
- Swept fractions .3/.5/.7 × surfaces0/45/90 for each sensor independently: 81 pairs per arm;
  rotations0/15/30 gives486 scenarios, 83,106 saved source decisions. Real-data models trained on
  other29 volunteers, fixed171 virtual-source denominator per side; abstentions count as failures.
  Zero-rotation quality agreement L46.2–57.9%, R58.5–74.9%; coverage L72.5–73.7%, R88.3–90.6%.
  These are failed-domain diagnostics, NOT real-location accuracy or an optimum. Historical fitted
  calibration has since had an interpolation bug corrected; do not treat old curves as current
  verified predictions. No virtual-training replacement export was produced on failed simulation.
- Mid-lateral upper/forearm positions remain starting hypotheses. Nominal lengths30/25cm imply
  15/12.5cm proximal distances at50%, not measured participant distances.

## Phase 5 findings and fixes

Read the actual Phase 5 report for corrected run numbers and hashes. Key findings:

- Independent reporting recomputation confirms historical cohort arithmetic, every one of the486
  placement summaries, all83,106 decisions, held-out exclusions and saved waveform-cache metrics.
  Reporting consistency is not physical validation.
- A real preprocessing defect was found: fitting discarded source points just outside target-grid
  boundaries, while scoring retained interpolation brackets. In24 real checks at a fractional lag,
  discrepancies affected mean0.111% of samples, reaching0.14747g. Shared preprocessing is fixed;
  known noninteger positive/negative lag + gap fixtures require fit/scoring equality to1e-10.
  Identical full calibration is rerun under `docs/runs/phase5/calibration-corrected.json`, with
  separate `data/phase5-cache/corrected/`. Original Phase 4 artifacts/cache are preserved.
- `figure-summary.json` now calls its ratio-of-marginal-medians field
  `reduction_between_medians_percent`; it was misleadingly named `median_rmse_reduction_percent`.
  Values unchanged. Tests now distinguish that quantity from median paired percentage reductions.
  `dynamic_correlation` is cosine similarity of concatenated per-axis demeaned vectors, not the
  mean of axis Pearson correlations; `correlation_xyz` is axis-wise Pearson.
- Functional anatomy: original60 side fits had shoulder22/60 and elbow54/60 pass screens;
  both19 yielded median projected upper-board fraction.533. New chronological valid-sample halves
  have6/60 pass both halves' screens and0/6 pass <=25mm centers/<=.10 fraction stability. Median
  shoulder shift118.5mm in those6. Halves may contain different calibration movements/excitation;
  this does not prove boards moved. No phase-specific motion selection or independently verified
  anatomical landmarks. Exact per-wearer chip/anatomy coordinates have not been established.
- New timing diagnostic fits lag from first40% optical time, skips20%, then validates last40% with
  frozen lag using gyro magnitude, never acceleration. Uses overlap-local Pearson and >=5s/80%
  coverage; early corr>=.8, distinct-peak margin>=.05, late corr>=.8 and lag stability<=.01s are
  descriptive screens, not a replacement validation gate. Initial run passes only20/653 sensor
  records from6 people. On those20, nominal median late total error .072513g versus historical
  calibrated .103067g. Corrected-fit follow-up is saved separately. This selected diagnostic
  cannot establish population fidelity, chip location or blind held-out synchronization.

## Reproduction and important source-version handling

Pinned numerical environment: Python3.12.14, NumPy2.3.4, SciPy1.16.3, sklearn1.7.2; MuJoCo3.3.7
for host simulation. Use `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`. Local interpreter is
`/tmp/tally-round2-env/bin/python`; if absent, follow `docs/MODELLING-ENVIRONMENT.md` and use
`uv run --locked --extra simulation python ...`. System Python/Matplotlib only renders saved
figures; never use it to refit accepted numerical models.

Core commands (from repo root, with the thread env above):

```
python scripts/test_calibrated_replay.py
python scripts/test_clock_reconstruction_audit.py
python scripts/test_sensor_location_followup.py
python scripts/test_audit_phase4_reporting.py
python scripts/audit_phase4_reporting.py
python scripts/verify_phase5_results.py
python scripts/verify_phase4_results.py --calibration-source-ref aa61caa
python scripts/verify_round2.py
python scripts/calibrated_replay.py --out docs/runs/phase5/calibration-corrected.json --cache-dir data/phase5-cache/corrected
python scripts/clock_reconstruction_audit.py --prior docs/runs/phase5/calibration-corrected.json --out docs/runs/phase5/clock-reconstruction-corrected.json
```

The explicit `aa61caa` verifies unchanged historical Phase4 against the code that generated it;
the strict SHA assertion is retained. Default verification against current changed source should
fail for an old report. Never silently erase that provenance mismatch. Avoid overwriting Phase4
JSON/cache when rerunning corrected code. Read Phase5 logs for exact tests that actually ran.

## What to do next

First review the audit/fixes and independently reproduce selected known-value and saved-source
checks. Separate mathematical correctness, internal reporting consistency, physical fidelity and
real downstream benefit. Verify board correspondence and inspect distinctive synchronization
motions/crop metadata. Consider phase-specific calibration movements rather than whole-take or
arbitrary halves, with conditioning/stability tests. A new clock model or drift correction needs
predeclared rules, independent later events and explicit reference-assisted status. Do not use
held-out acceleration to pick lag, axes, geometry, thresholds or model settings.

Evaluate whether a modest user-calibration route is more useful than increasingly detailed virtual
placement inference. An allowable study would train a base classifier on29 people, use only a
clearly reserved calibration block from the held-out user, then evaluate later untouched sources
from that user. Report exactly which labels/reference poses the adaptation was allowed to see;
keep all relatives in the same person/session split. Compare frozen-model/no-calibration,
signal-calibration and any carefully justified personalization on matched real trials, with
coverage, majority floors, remount robustness, false feedback and abstention. Do not adapt to the
held-out evaluation recording itself or assume an unverified movement is a correct target.
No new hardware is needed to inspect existing reference data, but intended-ADXL335 transfer and
new-site physical performance ultimately need real captures. No success guarantee or exact optimum
is established by present evidence.

End with an understandable result, complete artifact/command/commit references, what remains
unverified, and the single most useful next experiment. Keep negative results visible.

## Corrected-run checkpoint

The completed recalibration changes the mean active dynamic error from the historical .3892857g
to .3892867g, versus the same .4246003g baseline (8.3169% reduction); gate still FAILED. The new
early/late experiment using corrected fits still passes 20/653 records from 6 people. In those 20,
median nominal late total RMSE is 0.072513 g and corrected calibrated is 0.103091 g. This is selected
reference-assisted evidence with poor coverage, not a successful sensor-placement calibration.
`verify_phase5_results.py` independently checks corrected source hashes, unchanged baselines/cohorts,
fold exclusion, timing screen counts/medians and one actual raw-source late comparison.

Phase5 local milestones: a1a2c77 (protocol), 1b50ec6 (interpolation/metric-name fixes),
f83db38 (reconstruction/anatomy results), 9b1645b (independent audit). The handoff commit is in the current branch
log. Inspect HEAD to obtain the exact final handoff revision; nothing was pushed.
