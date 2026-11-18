# Phase 4 placement search protocol

This protocol is fixed before inspecting placement-specific model responses. It expands the four
phase-three hypotheses into a 3×3 coarse grid for each sensor: longitudinal fractions 0.30, 0.50,
and 0.70 crossed with exterior-lateral, 45°, and anterior surfaces (0°, 45°, 90°). The paired grid
has 81 upper-arm/forearm combinations. Geometry starts from the phase-three 0.30/0.25 m segment
lengths and 0.045/0.035 m radii. Classifier-response curves run at rigid remount rotations of 0°,
15°, and 30° for every cell. Signal-feasibility summaries also run ±20% coupled length/radius and
±15° coupled surface-angle corners on the nine-cell 50%/50% longitudinal slice. These are assumed
geometry and rig stresses, not measurements of wearer anatomy or soft-tissue movement.

The candidate evaluator uses the existing causal C detector and 61-feature extractor. For each
source volunteer, both task models are fit on paired measured recordings from the other volunteers
using the existing C=1, per-series-weighted logistic path. No held-out source contributes to a fit.
The source manifest contains the first series for 171 person/exercise/quality rows from all 30
volunteers; archive person IDs such as `A3` are normalized to the inertial `A03` identity while the
original archive path is retained in the per-source file. All locations within a side use the same
held-out source series. Rejections and abstentions remain
in the predeclared all-eligible-series denominator; report conditional scores only beside coverage
and the majority floor. Keep whole-series quality/exercise labels and their source/series lineage.
They do not establish repetition correctness or clinical error categories.

An outer held-out curve is not used to choose a location and then report it as unbiased. Any
candidate selected after viewing these curves is exploratory and needs a new untouched cohort.
Calibration must be trained on training volunteers only and pass the predeclared held-out clock and
board-to-chip transform gate before site-specific patient accuracy or a placement ranking can be
reported. No test-person lag, transform, scaler, threshold, or model fitting is allowed.

If the calibration gate fails, permitted output is explicitly diagnostic model response and
series-label agreement. Such results are not patient-placement accuracy and cannot establish a
placement ranking or winner. Waveform agreement, clipping, feature coverage, source-level variation,
and remount sensitivity remain diagnostics under the assumed optical-board/geometry chain. The
ADXL335 ±3 g input range is treated only as a rig approximation.

The versioned settings are in `configs/placement-search.json`; run with the pinned environment and
single-threaded numerical libraries:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/calibrated_replay.py \
  --root data/phytmo --out docs/runs/phase4/calibration.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/placement_model_sweep.py \
  --root data/phytmo --config configs/placement-search.json --calibration docs/runs/phase4/calibration.json \
  --out docs/runs/phase4/placement-sweep.json
```
