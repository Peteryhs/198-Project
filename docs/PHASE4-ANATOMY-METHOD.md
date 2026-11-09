# Functional anatomy audit from the study's calibration trials

The original archive contains 30 upper-limb optical `Calib` takes. The paper describes shoulder
circles, shoulder flexion/extension and elbow flexion/extension. These are published reference
recordings, not a new capture. The raw folder unusually names A01's take `A01Calib_interp.csv`;
the audit retains that exact path and flags the suffix rather than claiming it is uninterpolated.
A3 is normalized to participant A03 without renaming source files.

The pre-run settings in `configs/anatomy-reference.json` define two least-squares rigid-body
constraint checks using simultaneous optical board poses only:

- Fixed shoulder hypothesis: `p_upper + R_upper r_shoulder = c_world`.
- Shared elbow hypothesis: `p_upper + R_upper r_upper = p_forearm + R_forearm r_forearm`.

Report residual distances, six-parameter design rank and singular values. The screening thresholds
are at least 100 samples, smallest/largest singular-value ratio >=0.02, 3D constraint RMS <=0.02 m
and board-to-center distances <=0.60 m. These are engineering plausibility/conditioning checks,
not clinically validated anatomical accuracy bounds. Source frames are sampled every five frames.

A low residual alone does not prove anatomy: a pure hinge leaves the center free to slide along
its axis, and shoulder translation violates the fixed-world-center assumption. Synthetic tests
recover known centers and explicitly reject the rank-five hinge ambiguity. No wrist reference
establishes a complete forearm length here. Results describe functional joint-center hypotheses;
they are not substituted for measured landmarks or used to fit held-out classifier/replay results.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/test_anatomical_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/anatomical_reference.py
```

## Observed results

All 30 published Calib takes were analyzed, producing 60 side-specific cases with no rejected
files. Fixed-shoulder fits pass all engineering screens in 22/60 cases; median constraint RMS
is 23.0 mm. Shared-elbow fits pass in 54/60; median constraint RMS is 7.88 mm. These residuals
measure consistency with the assumed rigid-body constraint, **not error from a true joint center**.

Both screens pass simultaneously in 19 cases. Within this conditional subset, the projected
upper-board fraction from the inferred shoulder is 0.448 / 0.533 / 0.600 at the 10th/50th/90th
percentiles; inferred shoulder-to-elbow distance is 0.255 / 0.277 / 0.299 m. The median perpendicular
board distance from that inferred axis is 0.059 m. This supports investigating a middle upper-arm
reference but cannot establish an optimal mounting site. Selection by these screens and the
whole-trial fixed-shoulder assumption limit anatomical interpretation. Neither these 19 cases nor
their inferred geometry are used to tune the simulator/classifier.

Saved numerical outputs and all singular values: [anatomy-reference.json](runs/phase4/anatomy-reference.json).
