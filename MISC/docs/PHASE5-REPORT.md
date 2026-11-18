# Tally: second reconstruction attempt and independent pipeline audit

Base `bdb8bfd`; branch `codex/reconstruction-audit-handoff`. This phase responds to the request to
try again at sensor location/reconstruction, audit the testing/reporting pipeline, commit the work
and prepare a complete continuation prompt. No hardware, accepted-model replacement, firmware edit,
push, PR or repository comment. Existing raw data and untracked output/tmp are preserved.

## Plain-language result

The audit found and fixed a genuine calibration-preprocessing bug. It also independently reproduced
the historical reported numbers. Correcting the bug makes fitting/scoring internally consistent,
but **does not make the simulator pass physical validation**. The second anatomical attempt did
not establish an exact sensor position. A new per-record timing experiment works consistently in
a small selected subset, with inadequate population coverage for a validation claim.

A passed software check establishes that the code performs its defined calculation. It does not
prove that the physical assumptions, labels or source correspondence are correct. No finite test
suite proves the entire pipeline error-free. We now have more specific tests and clearer provenance.

## What the original study actually documents

The study does specify upper-arm/forearm sensors on the exterior-lateral surfaces, approximate
positions in Figure 1, and nominal sensor/board axes. Its placement rationale is ease of application.
We should not say it never told us where sensors were placed. What inspected metadata/these analyses
have not established is a measured landmark distance for each wearer and the chip's exact origin
relative to the optical rigid body. The existing optical name-to-side lookup also needs independent
confirmation. See [PHYTMO acquisition protocol, p. 3](https://arxiv.org/pdf/2401.12868#page=3).

The nominal basis is published and already used: sensor X = negative board X, Y = board Z,
Z = board Y. Residual effective registration is different from having no axis information.
The optical board trajectory is measured; a precise anatomical chip coordinate is not thereby given.

## Real pipeline defect, correction and effect

The calibration optimizer precomputed its inputs differently from waveform scoring. It discarded
source samples immediately outside each target-grid interval, causing endpoint holding instead of
interpolation between the proper neighboring points. This occurred at fractional clock offsets.

An independent check on the first 24 eligible real sensor-records at lag 0.0037 s found a maximum
boundary discrepancy of **0.14747 g**, median per-record maximum 0.01865 g, with mean 0.111% of samples
affected. The fix retains the complete derivative-edge-trimmed source run as interpolation support.
On the same real check, maximum discrepancy is now **4.44e-15 g**, with zero samples differing by
more than 1e-8 g. New synthetic fixtures require fit/scoring agreement at both positive/negative
fractional lags with an optical gap and nonzero origin/rotation/gain/bias parameters.

All 30 folds / 120 physical fits were rerun with unchanged bounds, training people, clock policy and
acceptance criteria. New outputs/caches are separate; the old Phase 4 evidence is not overwritten.

| Primary active held-out measure | Historical Phase 4 | Corrected Phase 5 |
| --- | ---: | ---: |
| Matched records / active records | 611 / 591 | 611 / 591 |
| Baseline mean dynamic RMSE | 0.4246003 g | 0.4246003 g |
| Calibrated mean dynamic RMSE | 0.3892857 g | 0.3892867 g |
| Mean dynamic RMSE reduction | 8.3171% | 8.3169% |
| Median calibrated total RMSE, all 611 | 0.3595075 g | 0.3594691 g |
| Active demeaned-vector cosine correlation, median | 0.12021 | 0.12023 |
| Active dynamic normalized RMSE, median | 1.19531 | 1.19533 |
| Calibration gate | Failed | Failed |

The bug was real; its aggregate correction is small and does not explain the much larger waveform
and timing failures. The clock discrepancy remains 67.69 s P95 versus per-record gyro estimates,
which themselves can be ambiguous. This is not an independently measured clock error.
The corrected gyro-assisted diagnostic median total RMSE is 0.1086665 g nominal versus 0.1342385 g
calibrated, still worse after the shared physical fit. All 120 fits have numerical rank 12 and 58
hit a bound. Neither result establishes exact sensor anatomy.

## Reporting audit

A separate implementation recomputed historical active/quiet cohorts, means/medians, max axis bias,
all 486 placement summaries from 83,106 source decisions and the 30 calibration / 60 model split
exclusions. It also reconstructed each saved example-waveform metric directly with independent
NumPy formulas: RMSE, signed XYZ bias, axis Pearson correlation, dynamic error, normalized error,
demeaned-vector cosine correlation and measured dynamic RMS. The calculations match.

One presentation defect was fixed: the figure summary field formerly named
`median_rmse_reduction_percent` actually meant reduction **between the two marginal medians**.
It is now `reduction_between_medians_percent`, with numerical values unchanged. A known-value
fixture now distinguishes this from the median of paired record-wise percent reductions.
`dynamic_correlation` is explicitly described as cosine similarity of demeaned XYZ vectors;
`correlation_xyz` contains the three separate Pearson correlations.

The original source hash is checked against explicit Git revision `aa61caa` when verifying historical
Phase 4. Current-source verification of an old report should fail, and the strict assertion remains.
Do not regenerate old reports with corrected code just to remove that mismatch. Historical placement
maps remain failed-domain diagnostics based on historical fits; no new best-location ranking is made.

## Second anatomical-location attempt

All 30 upper Calib takes / 60 side cases were split into chronological halves of valid sampled
frames. Shoulder and elbow constraints were fitted independently in each half. Six cases pass fit
screens in both halves; **none of those six pass** the declared repeatability screen of at most
25 mm center shifts and 0.10 change in upper-board fraction. Their median shoulder-center shift is
118.5 mm and median absolute fraction shift is 0.121.

Different halves can contain different calibration movements/excitation. These failures do not
prove that a physical mount moved or that no possible method could recover its location. They show
that this whole-take/half-take inference does not establish a stable exact coordinate. Phase-specific
motion identification, stronger board correspondence evidence and externally defined anatomical
landmarks remain useful investigations. The prior conditional median upper-board fraction of 53.3%
from 19 whole-take cases must not become an exact placement instruction.

## Timing experiment: fit early, check later

The new diagnostic fits an optical-to-IMU offset from gyro magnitudes in the first 40% of optical
time, skips the middle 20%, then checks the last 40% with the early lag frozen. Acceleration never
chooses the lag. A separate late lag is estimated only to expose disagreement. Overlap-local Pearson
correlation avoids treating global means as local means. Missing spans are never bridged.

The pre-run engineering screen requires an early peak correlation >=0.8, distinct-peak margin >=0.05
with peaks at least 0.5 s apart, at least 5 s / 80% overlap, later correlation >=0.8, later coverage
>=80%, and early/late lag disagreement <=0.01 s. These screens do not replace the original physical
validation gate. They use held-out-person gyro reference data, so this is reference-assisted
reconstruction, not blind synchronization of an accelerometer-only product.

The initial run using historical physical fits processes all 653 records without processing errors.
All yield an early lag estimate, but only 39 reach early correlation 0.8 and only 20 pass all screens,
covering six volunteers. Late acceleration overlap is available in 392 cases. In the selected 20,
nominal median late waveform RMSE is 0.072513 g versus 0.103067 g calibrated: the inherited physical
correction again worsens this metric. The subset is selected on gyro evidence, not acceleration
error, but has low coverage and cannot establish population fidelity. Physical fits were trained
under the old clock policy, so this is not a newly calibrated end-to-end system.

The rerun with corrected physical fits yields the same 20/653 timing-screen passes, the same six
people and 392 available late comparisons. In those 20, calibrated median late RMSE is **0.103091 g**
versus the same nominal 0.072513 g. Across all 392 available late comparisons it is 0.263280 g versus
nominal 0.286585 g. These different cohorts must remain separate. Nothing here establishes better
classification accuracy or a valid new-location model. The initial clock-source hash can be
reconstructed from the current script with the saved one-line `clock-initial-source.patch`; its
only code difference rejects non-finite target grids, which no real run supplied.

## User-calibration alternative

A more practical product may use a reasonably consistent lateral mounting region plus a brief
per-user/per-remount calibration. That could reduce sensitivity to reproducible offsets and
orientation without requiring everyone to match an exact centimeter coordinate. It has not been
implemented or validated here. Established accelerometer offset/gain calibration is described in
[Analog Devices AN-1057](https://www.analog.com/en/resources/app-notes/2020/07/22/16/49/an-1057.html).
A neutral static pose, multiple controlled orientations and functional movements provide different
information; a single gravity vector does not identify full orientation and all bias/gain terms.

Keep two experiments separate:

- **Signal calibration:** estimate justified sensor corrections from known reference poses/movements;
  freeze those corrections before classifying later recordings. Arbitrary longitudinal displacement,
  skin/band slip or movement differences are not automatically corrected by a vector rotation.
- **Classifier personalization:** adapt using explicitly verified exercise examples, with allowed
  calibration labels recorded. A user's unverified habitual exercise must not become a correct target.
  Subtracting a person's movement amplitude/tempo differences could erase real quality signals.

A defensible comparison would train the base on 29 volunteers, reserve an explicit calibration
block from the held-out person, and evaluate later untouched source recordings from that person.
Compare no adaptation, signal calibration and any justified learned adaptation on the same tests;
report coverage, majority floors, false cues and remount sensitivity. This is a personalized-user
protocol, not a claim that the person is entirely unseen. No leakage from the evaluated recording
or invented reference-pose/per-repetition labels is allowed. The current hardware is accelerometer-
only; study gyro may be an engineering reference, never silently assumed available on the product.

Existing data can support method development and some transfer experiments. Intended ADXL335
noise/bandwidth/ADC behavior, practical per-user setup and new-site performance still need real
captures. User calibration is an alternative worth investigating, not a way to bypass validation
of the virtual signals or label correctness.

## Reproduction and verification

Use the pinned environment and single-thread BLAS; no numerical dependency changed:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/test_calibrated_replay.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/calibrated_replay.py --out docs/runs/phase5/calibration-corrected.json --cache-dir data/phase5-cache/corrected
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/test_clock_reconstruction_audit.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/clock_reconstruction_audit.py --prior docs/runs/phase5/calibration-corrected.json --out docs/runs/phase5/clock-reconstruction-corrected.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/test_sensor_location_followup.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/sensor_location_followup.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/test_audit_phase4_reporting.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/audit_phase4_reporting.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/verify_phase4_results.py --calibration-source-ref aa61caa
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/verify_round2.py
MPLCONFIGDIR=/tmp/tally-phase4-mpl python3 scripts/test_phase4_figures.py
```

Artifacts under `docs/runs/phase5/`:

- `calibration-corrected.json` / `.log`: full corrected 30-fold fit and held-out metrics.
- `clock-reconstruction.json` / `.log`: initial reference-assisted experiment using historical fits;
  `clock-reconstruction-corrected.json` / `.log`: same experiment with corrected fits.
- `location-followup.json` / `.log`: all 60 split-half cases and exact sources/engineering screens.
- `reporting-audit-before-fix.json`, `reporting-audit.json` / `.log`: independent metric checks,
  boundary discrepancy before/after, source decision reconstruction and corrected-calibration audit.
- `regression-before-fix.log`: original 18 checks; `regression.log`: 17 post-fix numerical/runtime/
  reconstruction/export checks. Historical Phase 4 verification is separately recorded in
  `historical-verification.log`, retaining the exact historical-source SHA assertion.
- `inspection-server-tests.log`: local transform/provenance and HTTP trust-boundary tests pass.
  A temporary localhost socket required sandbox escalation; the test passed after that allowance.
- `figure-tests.log`, `calibration-tests.log`, `clock-tests.log`: focused fixtures. Known-value
  checks distinguish ratio-of-medians from median paired reductions. No new app UI or on-device
  inference path was added. The earlier static plots remain historical, with corrected field naming.

All ten valid accepted models still reproduce exact coefficients, C probability parity and every
stored LOSO series decision. Four hundred and two source files pass independent CRC/size checks.
Physical sensor placement, intended-sensor transfer and patient assessment remain unverified.

## Most useful next work and handoff

First verify the board-to-side correspondence and use the study's distinctive synchronization
movements/crop metadata to establish clock mapping with independent later events. Investigate
phase-specific functional calibration with adequate excitation rather than treating the complete
Calib take as a fixed shoulder. Refit shared physical corrections only after training-record timing
is trustworthy; simplify the fit if the corrections harm aligned held-out signals. Do not enlarge
bounds or tune on held-out acceleration to manufacture a pass.

Evaluate modest user signal calibration as a separate practical route, with the protocol above.
Avoid another placement sweep until original-site reconstruction is credible. Do not claim exact
placement is mathematically impossible; this evidence has not established it.

The complete continuation prompt is [TALLY-CONTINUATION-PROMPT.md](TALLY-CONTINUATION-PROMPT.md).
The user's full original brief is preserved in [ORIGINAL-MODELLING-BRIEF.md](ORIGINAL-MODELLING-BRIEF.md).
Local commit history is available with `git log --oneline bdb8bfd..HEAD`; nothing was pushed.

Additional saved audit: `scripts/verify_phase5_results.py` cross-checks corrected source hashes,
unchanged baseline/cohorts, fit exclusions, independently reproduced timing screens/medians and
an actual late raw-source comparison. Run with the same pinned environment; outputs are
`runs/phase5/verification.json` and `.log`.

| Completed item | Local commit |
| --- | --- |
| Pre-run audit protocol | `a1a2c77` |
| Shared interpolation and reporting-provenance fixes | `1b50ec6` |
| Corrected reconstruction and anatomy stability experiments | `f83db38` |
| Independent reporting and corrected-source verification | `9b1645b` |
