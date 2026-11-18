# Phase 5: sensor location follow-up

## Question and scope

This follow-up asks whether the available PHYTMO upper-limb `Calib` optical recordings can
pinpoint where the original sensor sat along the arm. It uses all 30 raw-folder upper Calib
files, each side separately, and splits each take chronologically into equal sample halves. The
fixed-shoulder and shared-elbow fits from Phase 4 are re-estimated independently in each half.
The output is descriptive and is not read by any classifier, simulator calibration, or held-out
evaluation.

The PHYTMO descriptor does specify the intended placement: upper-limb IMUs were on the exterior
lateral surface, with approximate locations illustrated in Figure 1. The paper says this location
was chosen for ease of placement. It also gives nominal axis setup: with a participant standing,
the sensor X axis points upward; with hands pointing down, sensor Y is perpendicular to the
coronal plane and Z to the sagittal plane. Recordings are named by side (`L`/`R`) and segment
(`arm`/`forearm`). Optical rigid-body files contain mounting-board poses. Those descriptions
establish intended surface, segment, approximate placement, and nominal axes. They do not establish
the exact chip origin and residual board-to-chip registration or a measured distance to an
anatomical landmark. The analysis follows the repository's established optical mapping (`L` =
`thigh2`/`shin2`, `R` = `thigh`/`shin`) and verifies those names are present as rigid-body pose
blocks when read. See the [PHYTMO data descriptor](https://pmc.ncbi.nlm.nih.gov/articles/PMC9166805/)
and [Phase 4 source audit](PHASE4-DATA-AND-SOURCES.md).

## Predeclared engineering screens

Each half needs at least 40 paired samples after the existing every-fifth-frame sampling. Each
shoulder and elbow fit must pass the Phase 4 engineering screens: design singular-value ratio at
least 0.02, constraint RMS at most 20 mm, and each inferred board-to-center offset at most 0.60 m.
These are numerical plausibility filters, not anatomical accuracy thresholds.

For cases where both halves pass and yield a shoulder-to-elbow projection, split-half repeatability
is screened at 25 mm maximum movement in each inferred board-local center and 0.10 maximum absolute
change in projected shoulder-to-elbow board fraction. The thresholds are fixed for this audit and
are not clinically validated. Fractions outside [0, 1] are retained and marked as outside the
segment; no clipping is performed.

## Results

All 30 files produced both left and right cases (60 total) with no rejected input. Only 6/60 cases
passed the joint fit screens in both halves. All six projected the inferred shoulder-elbow axis
inside the board segment, but **0/6** met the split-half stability screen. Their median absolute
fraction shift was **0.121**. Median board-local center shifts were **118.5 mm** for the inferred
shoulder, **20.9 mm** for the upper-board elbow, and **22.4 mm** for the forearm-board elbow.
Across the six selected cases, fraction shifts ranged from 0.034 to 0.374; shoulder-center shifts
ranged from 27.9 to 214.8 mm.

This analysis does not support a stable placement fraction. The paired elbow offsets are much more
repeatable than the shoulder offsets in this small selected subset, but they remain functional
constraint solutions, not measured anatomical epicondyles. A fixed shoulder in world coordinates
can fail when the shoulder/trunk moves, and elbow hinge motion can leave a center poorly identified
along the hinge axis. Also, chronological valid-sample halves can contain different calibration
movements and different excitation of the joints. The observed split-half differences therefore do
not by themselves show that a sensor mount moved. A phase-specific anatomical calibration protocol
was not performed here. The screen-passing cases are a selected subset, not population estimates.

## What can be recovered

The recordings support conditional estimates of a board-local functional shoulder point and paired
upper/forearm board-local elbow points. The publication specifies the nominal lateral placement,
approximate illustrated locations, and nominal axes. The inspected metadata and this analysis do not
establish an exact chip origin/residual board-to-chip registration, a measured distance from a
landmark, a wrist endpoint, or a reliable population sensor fraction. Thus an exact original
sensor/anatomy coordinate has **not been established here**; this is a limit of the inspected
metadata and analyses, not proof that no method could ever recover it. The supported claim remains
the published approximate lateral segment placement plus the numerical caveats above.

## Reproduction and artifacts

Run with the pinned environment and single-threaded BLAS:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/test_sensor_location_followup.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/sensor_location_followup.py --out docs/runs/phase5/location-followup.json
```

The full per-side, per-half fit parameters and source paths are in
[location-followup.json](runs/phase5/location-followup.json); captured command output is in
[location-followup.log](runs/phase5/location-followup.log). Synthetic checks recover known
split-half shoulder/elbow offsets, normalize `A3` to `A03`, and reject malformed filenames.

## Handoff prompt

> Continue the Phase 5 sensor-location investigation from `docs/PHASE5-SENSOR-LOCATION.md` and
> `docs/runs/phase5/location-followup.json`. Preserve the paper's published exterior-lateral
> placement, Figure 1 approximate locations, and nominal axes as known study facts. Do not relabel
> functional estimates as exact chip/anatomy coordinates or use inferred held-out geometry in
> classifiers/calibration. The split-half attempt did not establish a stable fraction: 6/60 cases
> pass both halves' fit screens and 0/6 pass the declared 25 mm / 0.10-fraction repeatability
> screen. Chronological halves may contain different movements/excitation; their differences do
> not imply mount movement. A phase-specific anatomical calibration was not performed. The exact
> chip origin/residual board registration and anatomical distances are not established by inspected
> metadata/this analysis, which is not a proof no method could recover them. Any further numerical
> analysis must predeclare thresholds, preserve raw files, and include synthetic checks.
