# Phase 4 optical replay calibration

The outputs below are historical. [Phase 5](PHASE5-REPORT.md) corrects fitting's interpolation
support at target-grid boundaries, adds `--cache-dir`, and saves a separate recalibration.
Verify this original result with `scripts/verify_phase4_results.py --calibration-source-ref aa61caa`;
the strict source-hash check must use the revision that generated the report.

## Question and input cohort

This experiment asks whether a virtual accelerometer reconstructed from PHYTMO's optical upper-limb rigid-body trajectories can reproduce the co-recorded NGIMU accelerometer waveform after a training-only calibration. It is a sensor replay experiment; it does not estimate exercise quality, joint angle, effort, or patient placement preference.

The canonical input is the first-series raw optical rigid-body cohort under `data/phytmo/optical raw/rigid_bodies/upper/`, matched to `data/phytmo/inertial/upper/`. The raw files are CRC/size-verified in [the archive manifest](runs/phase4/data-raw-archive.json). The selector normalizes the archive's `A3...` filename to volunteer A03 for pairing and fold assignment while retaining the exact original optical source path. The complete selected cohort covers 30 volunteers; unmatched archive conditions are listed in the manifest/rejection table. Each source row preserves its optical frame time; the first row is not assumed to have timestamp zero. Invalid rigid-body samples remain missing, derivative edge samples are excluded, and optical/IMU gaps are never interpolated across. The expanded interpolated cohort is a separate raw-vs-interpolated audit and is not substituted for the raw canonical run.

`load_record(optical_path, inertial_root, side, segment)` returns one body's optical `t`, `q`, `pos`, `valid`, six-axis inertial `real6`, and metadata with its separate `imu_t`. `predict_virtual(record, calibration, mount=None)` returns the virtual three-axis specific force in g. `fit_calibration(train_records, lags_s, config)` only receives the training volunteers' records. `estimate_gyro_lag(record)` uses quaternion angular-rate magnitude and recorded gyro magnitude, never acceleration, to audit timing.

## Physics and fitted parameters

For board pose rotation `R` and position `p`, a board-local origin offset `r` has world position `p + R r`. Its specific force is

`f_sensor = R_sensor_world.T * (d²(p + R r)/dt² - gravity_world) / g`.

PHYTMO uses Y-up coordinates, so `gravity_world = [0, -g, 0]`. The baseline uses the descriptor's IMU-to-board basis (sensor X is negative board X; sensor Y is board Z; sensor Z is board Y), zero chip-origin offset, unit axis gain, zero bias, and the existing Savitzky-Golay window 11 / polynomial 3 differentiator. A requested surface mount rotates both the point offset and sensor basis around the board long axis.

The calibrated model estimates one shared transform per side and segment within each leave-one-volunteer-out fold. It fits a correction relative to the published basis, a board-local origin, three axis gains, and three axis biases using only training volunteers. Configured bounds are ±25° per rotation component, ±0.10 m per origin component, gains 0.8–1.2, and biases ±0.15 g. Train records are weighted equally; fit rank, singular values, boundary hits and residual are retained. Segment lengths/radii are only for hypothetical site offsets; the original-site comparison uses the optical board reference point plus the fitted chip origin.

The train-only primary clock policy is the median gyro-derived event lag among training records for the same side and segment, applied unchanged to the held-out volunteer. A held-out record's own gyro-derived lag is calculated separately as a reference-assisted timing diagnostic; it never enters that held-out record's fit or primary score. The fit uses training records' per-record gyro event lag to estimate physical parameters. Optical and inertial clocks are independent in the published files, so the primary policy is an empirical transfer check, not a published shared clock. The gate requires a held-out 95th-percentile absolute event-lag residual no greater than 10 ms and at least 95% coverage.

## Matched scoring and decision rules

Baseline and calibrated predictions are scored on the same held-out source, continuous overlap, time grid and measured samples. The report retains per-axis correlation and bias, total and dynamic RMSE, dynamic NRMSE, dynamic correlation, overlap duration, held-out event lag, and fit diagnostics. Dynamic-correlation fidelity is assessed only for recordings with measured dynamic RMS at least 0.05 g; quiet recordings remain in the report and contribute to bias/coverage, but cannot establish dynamic fidelity.

The predeclared criteria in [the calibration config](../configs/replay-calibration.json) require the clock gate, a full-rank training transform, median dynamic correlation ≥0.70, median dynamic NRMSE ≤0.50, maximum absolute axis bias ≤0.10 g, and at least 10% aggregate dynamic-RMSE improvement on the matched active recordings. Passing a waveform metric does not override a failed clock gate.

The earlier simulation distribution gate remains unchanged: median statistic ratios 0.75–1.33 and normalized Wasserstein distance ≤0.5 across envelope, dominant frequency, peak, duration and high-frequency fraction. Its historical 0/84 result from a constructed two-link simulation is not a matched before/after effect estimate and is reported separately. The optical waveform metrics here are the new original-site matched comparison.

## Reproduction and limits

Use the pinned modelling environment and deterministic BLAS thread settings:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/test_calibrated_replay.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/calibrated_replay.py --config configs/replay-calibration.json --out docs/runs/phase4/calibration.json
```

The run log and per-fold estimates are in [calibration.log](runs/phase4/calibration.log) and [calibration.json](runs/phase4/calibration.json). Example paired waveforms stay under ignored `data/phase4-cache/`.

PHYTMO optical poses track mounting boards, not chip centers, and no measured chip-to-board fiducial or optical-to-device clock map is supplied. Training-only acceleration fit can estimate a transferable effective origin/frame only if the held-out timing and parameter-identifiability checks support it. NGIMU measurements are not ADXL335 captures; this run does not apply an assumed ADXL335 transfer, filter, clipping, bias, or ADC model. Gyro is a timing audit only and is not a classifier input.

## Primary references

- García-de-Villa et al., [PHYTMO dataset descriptor](https://arxiv.org/pdf/2401.12868), acquisition and coordinate conventions, data export and calibration records.
- García-de-Villa et al., [virtual acceleration from optical rigid-body motion](https://www.mdpi.com/1424-8220/21/2/427), Section 2.2.5.
