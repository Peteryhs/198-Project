# Research memo — opened 2026-11-07

## Simulation decision, before code

**Borrow MuJoCo's rigid-body kinematics and site accelerometers; confidence medium.** Its
[official sensor contract](https://mujoco.readthedocs.io/en/stable/XMLreference.html#sensor-accelerometer)
returns local-frame acceleration including gravity. A kinematically prescribed two-link trajectory
can isolate mounting and timing effects; it does not establish muscle effort. Use its native
position/velocity/acceleration stages and verify static gravity and a pendulum against analytic
specific force before trusting the wrapper. Pin the optional host dependency; nothing from MuJoCo
runs on the Arduino. This is borrowed sensor physics, not a new biomechanics solver.

Alternatives opened and rejected for this bounded round:

* [OpenSim synthetic IMU utility](https://github.com/opensim-org/opensim-core/blob/main/OpenSim/Simulation/SimulationUtilities.h):
  computes local linear acceleration minus gravity from model states/controls. Excellent for an
  independently scaled musculoskeletal study, but model registration and controls are unavailable.
* [OpenSense](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data):
  starts from IMU orientations; it does not solve acceleration-only dynamic orientation ambiguity.
* [IMUSim tutorial](https://github.com/martinling/imusim/blob/master/docs/tutorial.rst) favors MoCap
  trajectories; [its setup](https://raw.githubusercontent.com/martinling/imusim/master/setup.py)
  uses Python 2 syntax, Mayavi and old SimPy. No port attempted. The similarly named PyPI package
  is a different project; do not silently substitute it.
* [WIMUSim](https://github.com/STRCWearlab/WIMUSim) explicitly models body, motion, placement and
  hardware, with parameter fitting against recordings, but requires torch and pytorch3d. Its
  fidelity on PHYTMO/ADXL335 has not been verified here.
* [CROMOSim](https://github.com/wisermaclab/CROMOSIM) synthesizes from MoCap/video using a learned
  pipeline; no PHYTMO calibration or need for that learned dependency was established.

## Optical option explicitly considered

The [dataset record](https://zenodo.org/records/6319979) supplies simultaneous inertial and optical
recordings; its accuracy claim is a publisher claim, not independently measured here. The
[descriptor, pp. 7–10](https://arxiv.org/pdf/2401.12868) identifies right shin/thigh and left
shin2/thigh2, reused as forearm/upper-arm boards, quaternion XYZW and position in meters. Inertial
times are device uptime; interpolated optical files may retain long occlusions. The catalogue
and an actual header were inspected using the existing CRC-validating range reader; see
[runnable inspection and output](runs/round2/optical-inspection.log).

**Decision:** optical trajectories are a better eventual source of actual motion and wrong-motion
variation than invented clean arcs. Inspect at least one matching correct/wrong exercise from every
age group, derive virtual acceleration, and compare magnitudes independent of unknown constant sensor
rotation. They are a reference diagnostic this round, not assumed synchronized ground truth. The descriptor specifies IMU-to-board axis permutation and Y-up optical coordinates, but no
optical/device clock mapping or chip-to-board origin offset has been independently verified. Do not
fit either on a held-out person or claim angle validation. Extract only a deterministic small
subset with the existing reader; leave all raw files under ignored `data/`.

## ADXL335 and placement

The [manufacturer datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ADXL335.pdf)
specifies minimum ±3 g, nominal sensitivity 300 mV/g at 3 V, noise densities 150/150/300 µg/√Hz,
and capacitor-selected bandwidth. Use an illustrative 20 Hz single-pole filter, noise RMS
`density*sqrt(1.6*20)`, 0.02 g fixed bias stress and per-axis ±3 g saturation at 100 Hz. With a
5 V ADC reference and illustrative 0.300 V/g gain, quantize at `5/(16383*.300)` g. Real board gain,
reference, filter, bias, sample skew and saturation recovery require measurement; white noise and
ideal hard clipping are approximations.

[Analog Devices AN-1057](https://www.analog.com/en/resources/app-notes/an-1057.html) explains that
tilt from acceleration assumes gravity is the only stimulus; centripetal/other acceleration
corrupts it. Two accelerometers therefore do not uniquely identify dynamic 3D joint angle.
Self-placement rotation changes gravity projection; translating a sensor changes centripetal and
tangential acceleration. The recorded left/right upper-arm+forearm pairs measure side, not distance
from elbow or band tightness. No patient placement preference can be inferred from a clean-side
accuracy alone.

## Error inference

PHYTMO supplies series correctness, without repetition mechanism labels. The descriptor's example
shows duration/amplitude variation; that is not a taxonomy or mechanism ground truth. Tempo,
acceleration envelope and inter-sensor relation can describe deviations. Low acceleration cannot
establish low muscle force: the same kinematics can occur with different loads/effort. Clustering
cannot name causes without independent video/annotation. A threshold needs a prescribed target,
physical quantity, uncertainty and validation; classifier confidence cannot supply that evidence.

## Claims not verified

No patient-transfer performance, sensor-to-board calibration, optical clock alignment, muscle-force
inference, actual ADXL335 saturation/noise, hardware latency, or published simulator fidelity on this
setup has been verified. Nature's HTML redirected to inaccessible authentication; the same descriptor
PDF was successfully opened via arXiv. IMUSim compatibility was inspected, not installed; WIMUSim,
CROMOSim and OpenSim were read, not benchmarked. No clinical advice is derived from these sources.

## Findings after running A

The MuJoCo wrapper passed independent static-gravity and analytic-pendulum assertions, but its
nominal exercise distribution failed the empirical gate. Its prescribed SQZ analogue does not
model wrist pronation, cloth resistance or grip. No patient ranking or error accuracy may be
inferred from its responses. Detailed statistics, including spectral content, are printed in
`runs/round2/simulation.log`; the corresponding JSON retains every held-subject diagnostic.

The optical reference produced closer aggregate envelopes/peaks/frequencies than the prescribed
link model, but lost high-frequency energy. Its comparison uses continuous finite spans without
inventing samples across occlusions. Unusable references and timing-gap rejections are enumerated
in `runs/round2/optical-reference.json`. This supports prioritizing calibrated, synchronized optical
replay next; it does not establish chip-level acceleration, joint-angle or quality validation.
