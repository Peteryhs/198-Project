# Round two: positions before implementation

Read in order: NEXT-ROUND-BRIEF, independent QA, existing pipeline and contracts. Existing exports,
benchmarks and data fetching remain comparison history. No firmware sketch change is required.

## Fixes, in required order

1. **Pair fusion (high confidence in engineering, unproven performance):** join matching filenames
   within subject and side; interpolate only the shared timestamp interval onto 100 Hz. Reject
   backwards time, >50 ms gaps, <3 detected cycles. Duplicate timestamps are averaged. Use common
   forearm-derived boundaries, 61 features: one duration plus both sensors' 30 existing statistics.
   Two heads, equal series weights, fixed existing regularization, LOSO over all volunteers.
   This is paired acceleration evidence, not a measured joint angle. Independent segmentation of
   each sensor and concatenating arbitrary repetition indices are rejected.
2. **Causal processing (medium):** a separate bounded C implementation ingests six accelerations at
   100 Hz, clips at ±3 g, detects cycles with an EMA magnitude and fixed hysteresis, and computes the
   same statistics after a causal boundary. Predeclare 1.2 s refractory interval, 6 s maximum cycle,
   0.04 g descent hysteresis and 0.2 s confirmation. Drop incomplete/overflow cycles; no tail flush.
   Train separate exports on C replay features; never feed these into an offline-trained model.
   No promise of true repetition boundaries or mid-repetition correctness without labels.
3. **Enforce environment (high):** one pinned bootstrap/runner, plus fail-fast runtime checks in
   modelling entry points. Keep original requirements as the single version authority. Verify the
   accepted export, without retraining or retuning the accepted benchmark.

## A — simulation (position to be finalized after research, before simulator code)

Compare existing biomechanics/sensor simulation and paired optical data first. Prefer measured
kinematics if accessible and interpretable. Only trust simulation within a declared empirical
validation gate on envelope, frequency, peaks, duration and high-frequency energy. A failed gate is
an experimental result, not permission to publish synthetic accuracy as real performance.

## B — placement (medium for recorded sides, low for self-application)

Compare left upper-arm/forearm and right upper-arm/forearm using the same fixed protocol. No wrist,
elbow-distance or band tightness comparison exists in these recordings. Stress held-out recordings
with fixed sensor rotations and translations from the simulator; label these synthetic perturbations.
Evaluate an orientation-invariant small alternative only if needed, with its own C export and size.
Do not select a model or placement using held-out-fold scores and report that score as unbiased.

## C — errors (low identifiability, high confidence in refusal)

Inspect duration, excursion proxies and inter-sensor relationships within training-only references.
Unsupervised separation cannot name mechanisms without external labels. Test descriptive deviations,
retain unavailable error categories. Write a feasible video+sensor annotation protocol with raters,
held-out people and safety/scope decisions for the owner before any exploratory error analysis code.

## D — board (medium until linked and timed)

Measure parameter bytes, Cortex-M4 object sections, static state and compiler stack estimates for
both offline and causal paired exports. Include actual feature computation/detection, not merely
classifier code. Six channels fit the six analog inputs; ADC/display/core integration and board
latency remain unmeasured. Give latency arithmetic only for detector delay; reject a hardware
latency claim from host timing. No firmware edit without needing it for the experiment.

## Decisions reserved for owner

Prescribed range/tempo, safe definition of weak, limb dimensions, patient wording, clinical scope,
placement and calibration procedure, annotation budget, and physical hardware tests. An asynchronous
question asks whether prescribed targets exist; absent targets experiments use explicitly illustrative
engineering settings and make no patient instruction. No clinical thresholds are silently assumed.

## A — final pre-code position following research

Use MuJoCo site accelerometers on a two-link prescribed arm with 0.30 m upper and 0.25 m lower
segments and midpoint sites (illustrative geometry, not measured anthropometry). Generate shoulder
and elbow trajectories for EAH/EFE/SQZ analogues, with low harmonics, 7/11 Hz perturbations and
cycle-to-cycle modulation. Fit only nominal period per exercise from the other 29 volunteers;
no classifier or simulator parameter selection on the held-out person. Sensor-chain settings are
in ROUND2-RESEARCH.md. Shallow scales excursion by 0.5; fast compresses time by 0.6; weak is an
explicitly NON-IDENTIFIABLE effort counterfactual with the same kinematics; misaligned moves the
exercise plane by 20 degrees, distinct from rotating the sensor mount. Also inject a stalled
half-cycle example to show the model's limits. No synthetic category becomes a clinical label.

Before inference, compare held-out real recordings and nominal simulation by exercise and segment:
100 Hz magnitude envelope p95-p05, dominant frequency (0.15–3 Hz), cycle peak acceleration p50/p90,
causal cycle duration p50/p90, and 5–40 Hz energy fraction. Predeclared engineering gate: each median
ratio in [0.75, 1.33] and normalized Wasserstein distance <=0.5 for envelope/frequency/peaks/duration/HF.
A gate failure forbids an accuracy or clinical conclusion from synthetic predictions. Still run
model responses as explicit failed-domain diagnostics to test refusals and sensitivity. Compare
optical-derived statistics separately; do not tune the simulator to make the gate pass.

## Timing correction discovered during A research (before further experiments)

The descriptor pp. 3–4 explicitly says the authors synchronized exported IMU starts using motion
events, but Table 3 defines retained timestamps as device uptime. The first pair implementation
mistook these clocks as shared. An independent EAH gyro-event audit compares near-zero relative
lags against multi-second uptime offsets; it is timing evidence, never an extra model input.
**Correct the shared aligner once:** subtract each file's initial timestamp before interpolation.
Do not cross-correlate/test-tune individual lags. Keep original outputs/logs as invalid-clock
history and add `paired-synchronized-*` exports. All final modelling/simulation/stress results
must use this correction. The first three fix commits remain useful implementation history;
the timing correction commit is required to close fixes 1 and 2 correctly.

## B — final position after the simulation gate failure, before placement code

Compare both measured sides on the intersection of usable recordings, keeping every volunteer and
printing both majority and training-majority floors. Side scores on different retained cohorts are
not a placement test. Use subject-block paired bootstrap intervals (fixed seed, 2,000 resamples)
for the side difference; do not choose a side/model and describe its score as unbiased selection.
Then train on clean other-29 data and perturb only held-out raw accelerations: independent fixed
mount rotations of 15/30/60 degrees about seeded axes, before ±3 g clipping and the C detector.
Keep unscorable series in the denominator as abstentions/failures and report coverage. These are
SIMULATED remounts of real recordings, not newly measured placements or clinical performance.

Use the MuJoCo sensor offset knob to compare midpoint with ±5 cm along each link as a mechanical
sensitivity diagnostic only; A's failed domain gate forbids ranking patient placements from it.
The only defensible measured placement is an exterior-lateral upper-arm+forearm pair on either
recorded side. Indexed straps and a supervised neutral-pose check are proposals for remount
repeatability; no cm-from-elbow optimum or patient robustness is established by this dataset.

## D — final pre-code measurement position

Cross-compile every valid paired/control classifier, the shared C detector/statistics, and each
causal complete runtime for Cortex-M4F with size sections, unresolved symbols and stack-usage
files. Measure static state from target object symbols, not host pointer assumptions. Include
correct forearm-feature selection for the single-sensor ablation runtime. Recheck all exported
coefficients, host probabilities and held-out predictions after any numerical fix; no accuracy
improvement is a reason to change detector thresholds. Reserve stack/core/display/interrupt space
explicitly as estimates; no full Arduino toolchain or board is available. Report true-repetition
and display latency as not measured; confirmation time is only a component, not total latency.
A single pair must fit; two simultaneous float-buffer pairs may not. Recommend int16 ADC buffers
or time-sharing only if that larger scope is requested and calibrated, not silently.
