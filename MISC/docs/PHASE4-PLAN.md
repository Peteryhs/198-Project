# Simulator calibration and placement search — pre-run decisions

2026-11-07. Base `50cec19`; branch `codex/simulator-calibration-search`.
Existing untracked `output/` and `tmp/`, raw data, historical findings, accepted exports and firmware
are preserved. The user explicitly authorized the next calibration/validation/search phase and
subagents. No hardware is available; no push, PR or repository comment is authorized.

## Scope and research

Use the same published PHYTMO dataset, not a new participant collection. Expand the initial optical
subset beyond five volunteers where the original archive supports matched recordings. Inspect
published calibration trials, optical board/marker frames, capture metadata and timestamp semantics
before claiming that an unmeasured transform cannot be estimated. Use CRC-verified range extraction
to avoid downloading the entire archive. Raw downloads and derived sample arrays stay ignored.

Opened primary sources: PHYTMO descriptor (2022), acquisition, calibration and data processing pp.
3–10 ([full text](https://arxiv.org/pdf/2401.12868)); the
[original Zenodo release](https://zenodo.org/records/6319979); and virtual-IMU rigid-body methods in
García-de-Villa et al., Sensors (2021), section 2.2.5
([paper](https://www.mdpi.com/1424-8220/21/2/427)). Source access and additional findings are recorded
by the data/calibration workstreams. No new physics engine or numerical dependencies are planned.

## Calibration experiment

- Reproduce the study's NGIMU acceleration before applying illustrative ADXL335 transfer assumptions.
- Baseline: the existing optical-board, zero-offset replay, descriptor basis and SG11/polynomial-3
  differentiation. Improved replay may fit physically constrained shared origin/frame/bias/gain
  and clock parameters using training volunteers only.
- First investigate whether capture metadata or independently observable events give a deterministic
  clock mapping. Recorded gyro may audit timing independently of the acceleration fit; it is never
  a final quality/exercise-model input. Per-held-out-record lag fitting is an **oracle diagnostic**,
  not held-out calibration or validation.
- Outer validation holds out volunteers. Fit all calibration/reference parameters on other people;
  compare baseline and calibrated predictions on identical eligible recordings and sample masks.
  Print rejected files, per-person retention, missing spans and source lineage.
- Measure actual waveform errors (per-axis RMSE/bias/correlation, dynamic errors and timing evidence)
  and distributions (envelopes, peaks, spectra, detector-interval proxies and clipping). Report
  uncertainty by volunteer. Keep quiet/static cases from artificially establishing dynamic fidelity.
- Preserve the earlier signal gate: median ratios [0.75,1.33] and normalized Wasserstein <=0.5.
  The calibration method/config must record any additional waveform criteria before final runs.
  A change from the prior constructed-motion 0/84 figure is not a matched improvement estimate;
  only new matched baseline/calibrated comparisons may quantify improvement.

Confidence before experiments: medium in rigid-body calculations, unknown in transferable timing,
frame/origin calibration and waveform fidelity; low in ADXL335 transfer without hardware data.

## Placement/model experiment

Use a declared coarse grid of upper/forearm segment fractions and circumferential surfaces, allowing
each sensor to move independently. The proposed first grid is fractions 0.3/0.5/0.7 and surfaces
0/45/90 degrees: nine sites per segment and 81 two-sensor combinations. Segment lengths/radii,
axis registration and allowable mounts remain measured quantities where available and explicit
uncertainty otherwise. These are two sensors on one limb, not 162 sensors at once.

Fit the existing small real-only 61-feature C-path model on other volunteers and freeze it before
virtual relocation of the held-out person's recordings. The all-person accepted export is unsuitable
for an unbiased held-out score on those same people. Keep original-series labels and source identity;
never invent repetition/error labels. Use a fixed real comparison cohort across sites, with rejected
or unscorable cases counted and coverage reported. Print majority floors beside label-agreement
statistics and retain per-source decisions. Do not mix differently filtered cohorts.

If original-site fidelity passes, a second same-architecture virtual-training experiment can
investigate information at each site. If it fails, position/model outputs remain explicitly
**failed-domain sensitivity/series-label-agreement diagnostics**, never predicted real placement
accuracy. A curve can still identify model sensitivity and engineering problems, but cannot prove
an optimum. No synthetic-only score establishes improvement on real untouched recordings.

Report clipping, signal variation and mounting-error sensitivity separately, with no invented
universal placement score. Any site selected from displayed outer-test curves is exploratory;
an unbiased final selection would require inner subject selection or a later independent capture.
The existing four physical mounting instructions remain reference hypotheses unless stronger
anatomical/experimental evidence is established. Do not train or export a replacement accepted model
merely because a simulated location has a higher score.

## Verification and delivery

Independent synthetic tests check gravity, rotations/quaternions, units, known offset acceleration,
timing/gaps, parameter recovery, invalid inputs and held-out exclusion. Independently audit saved
matched metrics and fold lineage. Preserve original assertions and run relevant regressions.
All processing stays on the computer; no additional on-device path, buffers or hardware timing claim.

Deliver executable scripts/configs, a data/source audit, matched before/after simulator metrics,
the placement comparison/diagnostic map, clear mounting definitions, plots and exact commands,
logs and separate local commits. If the current viewer changes, retain its engineering-inspection
layout and provenance distinction, and verify desktop/mobile rendering. No animation may imply
that assumed anatomy or optical/IMU synchronization has been validated.
