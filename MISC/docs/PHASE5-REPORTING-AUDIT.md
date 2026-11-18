# Phase 5 reporting and pipeline audit

This audit independently recomputes saved Phase 4 cohort arithmetic and placement summaries from
the calibration JSON and the 83,106-row placement source export. It checks reporting consistency,
fold exclusions, matched counts, active/quiet splits, fixed denominators, and the reported placement
ranges. It does not establish that optical reconstruction, clock transfer, anatomy, or physical
sensor placement is correct.

## Findings

- The primary timing track has 611 matched recordings: 591 active at measured dynamic RMS ≥0.05 g
  and 20 quiet. Baseline and calibrated sample counts and durations match for every pair. The
  active mean dynamic RMSE is 0.424600 g versus 0.389286 g (8.317% reduction); the active median
  dynamic correlation is 0.1202 and median dynamic NRMSE is 1.1953. Maximum absolute calibrated
  axis bias over all 611 matched recordings, including quiet ones, is 0.9019 g. These recomputations
  match the saved calibration gate and the rounded Phase 4 report.
- The gyro-assisted diagnostic has 571 matched recordings: 380 active and 191 quiet. Its active
  mean dynamic RMSE reduction is 4.348%, while median total RMSE increases from 0.108666 g to
  0.134250 g. The report correctly labels this a separate diagnostic cohort.
- The stored per-axis correlations are Pearson correlations by axis. The singular `dynamic_correlation`
  used by the gate is instead cosine similarity of the concatenated, per-axis demeaned vectors.
  The method document names both quantities, but the report's short label could be made clearer;
  the gate value must not be read as the mean of the three axis correlations.
- An independent NumPy calculation from the saved primary waveform cache reproduces every stored
  value for that source: sample count, total/dynamic RMSE, signed axis biases, per-axis Pearson
  correlations, dynamic NRMSE/correlation, and measured dynamic RMS.
- The fit-preparation interpolation does not exactly match held-out scoring at chunk boundaries.
  In 24 real records checked at a 3.7 ms lag, differences affected a mean 0.11% of grid samples,
  with a median per-record peak discrepancy of 0.0186 g and a maximum of 0.1475 g. The cause is
  `_prepare_fit_record` dropping source samples outside the target grid before `np.interp`; it then
  holds the first/last in-range value where scoring interpolates from neighboring valid source
  samples. The discrepancy is localized and sparse, so its aggregate effect on fitted parameters
  is not measured here. A small correction is to interpolate the edge-trimmed valid optical run
  while retaining its samples just outside the target grid as brackets. Refit and regenerate
  calibration outputs before treating that correction as numerically neutral.
- All 30 calibration folds and 60 placement folds exclude held-out volunteers from their training
  IDs. The placement export has 486 scenarios and 83,106 source decisions. Independently recomputed
  coverage, quality agreement, and exercise agreement match every saved scenario summary at the
  fixed 171-series denominator; the rounded zero-rotation ranges in the report agree.
- The saved `figure-summary.json` field `median_rmse_reduction_percent` is computed as the percent
  difference between the marginal median baseline and calibrated RMSEs. It is not the median of
  per-record paired reductions. Its current values (6.39% primary, −23.54% diagnostic) match that
  ratio-of-medians definition, but the field name overstates its meaning. Rename it to something
  like `reduction_between_medians_percent`, or compute the median paired reduction and label that.
  This field is not used in the Phase 4 report text or calibration decision gate.

## Audit artifact

The machine-readable recomputation is in [reporting-audit.json](runs/phase5/reporting-audit.json).
The independent audit code and small known-value checks are in `scripts/audit_phase4_reporting.py`
and `scripts/test_audit_phase4_reporting.py`.

Physical correctness remains unverified: the saved calibration gate fails its clock-transfer and
waveform criteria, and the virtual sensor geometry/registration remains assumed.

## Correction and rerun

The shared fit interpolation now retains the full edge-trimmed valid run, including the
bracketing source samples on either side of target-grid endpoints. Exact regression fixtures
cover positive/negative fractional clock offsets and optical gaps. The same independent 24-record
real-data check now has maximum discrepancy **4.44e-15 g**, with zero samples differing above 1e-8 g.
The before-fix snapshot is `runs/phase5/reporting-audit-before-fix.json`; the main audit JSON
reflects current corrected preprocessing. The figure field is renamed to
`reduction_between_medians_percent` without changing values; the original figures log remains
historical. A known-value test distinguishes this ratio of medians from a median of paired
reductions. The short report label for dynamic correlation means demeaned-vector cosine similarity.

All 30 calibration folds were rerun with the same physical bounds, clock policy and gates, saved
as `runs/phase5/calibration-corrected.json` with a separate ignored cache. The corrected active
mean dynamic error is 0.3892867 g versus baseline 0.4246003 g (8.3169% reduction). The old value was
0.3892857 g (8.3171%). This numerical correction does not rescue the failed validation gate or
explain the large timing/waveform disagreement. Old placement curves remain historical failed-domain
diagnostics and were not rerun to hunt a better score.
