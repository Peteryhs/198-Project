# Focused reconstruction and reporting audit

Base `bdb8bfd`, branch `codex/reconstruction-audit-handoff`. User requests another location/
reconstruction attempt, an audit for reporting/testing errors, local commits and a self-contained
handoff prompt. Preserve Phase 4 evidence, raw data, accepted models, firmware and existing
untracked output/tmp. No push/PR/comments. No further placement ranking.

Before running new diagnostics:

- Independently audit saved metrics/denominators, known-value metric calculations and source/fold
  lineage. Passing bookkeeping checks does not prove physical accuracy.
- Investigate anatomy/board mapping and temporal stability of the functional joint hypotheses.
  Do not convert conditional joint fits into exact measured chip/anatomical positions.
- Use optical quaternion angular-rate magnitude and measured gyro only for reference-assisted
  per-take timing. Fit an offset on the first 40% of optical time, leave a 20% separation, and
  validate on the last 40%. No acceleration chooses the lag. Independently estimate a late lag
  only to expose instability; freeze the early lag for all scored late waveforms.
- Use overlap-specific Pearson correlation, preserve missing spans and require >=5 s and >=80%
  of available window gyro samples at candidate lags. Search +/-60 s relative to stream starts;
  secondary peaks must be at least 0.5 s away. Descriptive engineering screen: early peak >=0.8,
  early distinct-peak margin >=0.05, late fixed-lag correlation >=0.8, late coverage >=0.8,
  and independent early/late lag difference <=0.01 s. These are screening choices, not a replacement
  for the failed Phase 4 validation gate, nor evidence of a shared acquisition clock.
- Save every accepted/rejected source and every timing outcome. Compare nominal versus existing
  training-only Phase 4 physical fit on exactly the same late measured samples. Those old physical
  fits were trained under a different timing policy; this follow-up is a diagnostic, not a newly
  validated end-to-end calibration or an accuracy improvement estimate against Phase 4.
- Known synthetic tests must cover offset sign, nonzero origins, unequal lengths/crops, periodic
  ambiguity, missing spans, local demeaning, invalid inputs, and later-window mismatch. Do not fit
  clock drift unless early/late evidence supports a separately declared future model.

Deliver new scripts/tests/results, correct actual bugs additively without overwriting old evidence,
a concise findings report and a thorough continuation prompt. Exact anatomy may remain unidentifiable;
the handoff must state what failed and the narrowest useful next experiment.

## Audit-triggered correction, before rerunning

Independent review found calibration preprocessing discarded bracketing points when interpolating
to the scoring grid. Correct this shared boundary interpolation and add exact fit-versus-score
regression fixtures with fractional offsets/gaps. Rerun the identical 30-fold calibration without
changing bounds or gates; save under phase5/calibration-corrected.json with a separate ignored cache.
Keep Phase 4 outputs historical. Its source-hash verifier must explicitly name source revision
aa61caa; never weaken the hash assertion or rewrite the historical report. Re-evaluate the frozen
early/late diagnostic against corrected training-only fits and retain the earlier diagnostic too.
Rename the figure summary's ratio-of-medians field; numerical values do not change.
