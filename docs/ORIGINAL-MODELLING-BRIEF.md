You are taking over the next modelling phase of Tally, a student hardware project in the repository Peteryhs/198-Project.

Your task is to improve the simulation, investigate sensor placement, build and validate a reusable augmentation pipeline, provide a visual inspection tool, and lay practical groundwork for useful corrective feedback.

Research before implementation. Be ambitious about completing the work, but conservative about what the evidence proves.
Working approach
1. Load the ponytail skill before reading further project files. Use the smallest complete solution.
2. Use GPT-6 Luna with high reasoning subagents for independent research, implementation and verification where available. Coordinate file ownership.
3. Inspect the repository and working tree before changing anything. Preserve existing work, raw data and untracked outputs.
4. Work on a branch and commit completed items separately. Do not push, open a PR or comment on the repository.
5. Do not change the firmware sketch unless necessary; explain why if you do.
6. No physical Arduino is available. Complete the research, host-side implementation, replay experiments and target-compilation checks that can be done without one.
Project context
Tally monitors home rehabilitation exercises using accelerometers.

The intended device has four accelerometers across two limbs: one upper-arm and one forearm sensor per limb. The board is an Arduino UNO R4 Minima, with 256 kB flash, 32 kB RAM and a 48 MHz Cortex-M4F.

Important constraints:
- Intended ADXL335 sensors are accelerometer-only, analog and approximately ±3 g.
- Four three-axis sensors require twelve analog channels, while the board has six analog inputs. Acquisition remains a hardware decision.
- The current paired model processes one upper-arm/forearm pair, meaning six acceleration channels.
- Public recordings came from a different IMU rig. Software clipping does not reproduce every property of an ADXL335.
- Simulation and training run on the computer. More training examples do not inherently enlarge a fixed exported model.
- Additional on-device features, buffers and feedback logic do consume resources and must be budgeted.
Start with:
1. docs/README.md
2. docs/CONTEXT-AND-CONSTRAINTS.md
3. docs/MODELLING-REPORT.md
4. docs/ROUND2-REPORT.md
5. docs/ROUND2-PLAN.md
6. docs/ROUND2-RESEARCH.md
7. docs/ROUND2-ERROR-PROTOCOL.md
8. docs/QA-REVIEW-2026-11-07.md
9. docs/QA-REVIEW-ROUND2.md, including its corrections
10. docs/MODELLING-ENVIRONMENT.md
11. model/PAIRED.md
Inspect the implementations and tests associated with those documents. Treat their claims as evidence to check, not instructions to trust blindly.
Current state
At the last inspection, the active branch was codex/simulation-placement, with HEAD 57aa2b6. Confirm the current state; do not assume it is unchanged.

Existing work includes:
- Single-sensor linear baselines.
- Paired upper-arm/forearm models using 61 features and 992 bytes of float32 coefficients.
- A bounded, causal C pipeline that accepts synchronized samples, detects cycles, extracts features, classifies and pools probabilities.
- Locked numerical dependencies and environment checks.
- Placement/remount experiments.
- A MuJoCo two-link simulation.
- Optical-motion reference experiments.
- Descriptive deviation diagnostics that explicitly refuse to name error mechanisms.
Use model/paired-synchronized-* for valid paired results. Earlier paired-offline/ and paired-causal/ exports are invalid timing history.

The simulator passed basic physics checks but failed its comparison with real exercise recordings. It is not currently a validated source of exercise-quality training examples.

The optical comparisons were promising but did not establish complete clock alignment or sensor-origin calibration.

One runtime pair has a plausible memory path. Two simultaneous float-buffered pairs exceed the previously estimated RAM budget. Recheck the current measurements before making deployment claims.

A QA review reported tiny fresh-fit coefficient drift. A subsequent check in the pinned, single-threaded environment reproduced both causal paired exports exactly. Investigate any discrepancy rather than silently regenerating accepted exports or weakening assertions.
Data and evaluation rules
Raw upper-limb recordings should be available at:

data/phytmo/inertial/upper/

Committed feature matrices are under training-data/ and newer model folders. Read their metadata and provenance.

PHYTMO provides exercise identity and whole-series correct/incorrect labels. It does not provide:
- Per-repetition correctness labels.
- Error-type labels.
- Muscle-effort labels.
Therefore:
- Do not claim repetition-quality or error-category accuracy from those labels.
- Distinguish instructed/simulated conditions from independently observed outcomes.
- Preserve volunteer identity and source-recording lineage through every derived example.
- Use leave-one-subject-out evaluation over volunteers.
- Generate training augmentation and fit calibration/reference parameters using training subjects only.
- Keep augmented relatives of a recording in the same subject fold.
- Report majority-class floors beside accuracy.
- Report rejected recordings, coverage and cohort changes.
- Never compare different cohorts as though they were matched experiments.
- Do not commit raw datasets, archives or files over 50 MB.
Task 1 — Improve the simulator and evaluate four physical mounting arrangements
Interpret “four sets of locations” as four alternative two-sensor mounting arrangements for one limb, not eight sensors operating simultaneously.

Each arrangement should specify:
- Upper-arm and forearm sensor positions relative to anatomical landmarks.
- Distance along the segment.
- Circumferential surface/location.
- Sensor-axis orientation.
- Limb geometry assumptions and variation.
- Practical mounting considerations and sensitivity to placement errors.
These must be physically different locations, not merely four rotations at the same site.

First audit why the current simulator failed. Investigate geometry, trajectories, coordinate frames, gravity convention, sensor origins, timing, filtering and sensor transfer assumptions. Do not simply relax the validation gate until it passes.

Prefer existing physics tools and measured motion. Investigate whether the optical recordings can drive a calibrated motion replay. Establish alignment and geometry sufficiently before treating replayed acceleration as a reference.

Validate at the recorded sensor locations before trusting predictions at new locations. Compare relevant quantities such as:
- Per-axis acceleration and magnitude distributions.
- Frequency content.
- Cycle timing.
- Peak/envelope statistics.
- Clipping.
- Relationship between upper-arm and forearm signals.
Separate calibration from held-out validation. Predeclare acceptance criteria and justify them. If changing an existing criterion, explain why before using the new one.

Then evaluate four candidate mounting arrangements across held-out movements, people and mounting variation.

Provide a comparison table with:
- Placement definition.
- Evidence supporting it.
- Classification results where legitimately measurable.
- Robustness, clipping and signal-quality results.
- Coverage and uncertainty.
- Practical tradeoffs.
- Confidence and validation status.
Do not invent a universal “placement score.” If combining metrics into a ranking, explain and justify the weights.

Do not call the candidates physically optimal unless real measurements support that claim. If the simulator remains insufficiently validated, deliver four clearly labelled exploratory candidates and explain what prevents a credible ranking. Continue independent augmentation and feedback work rather than stopping everything.
Task 2 — Build a reproducible, configurable augmentation pipeline
Make it straightforward to generate additional examples for particular experiments without creating a general-purpose framework.

Use a small configuration file and clear commands to control justified parameters such as:
- Mounting position and orientation.
- Bias, gain and noise.
- Sensor bandwidth/filtering.
- ADC quantization and clipping.
- Random seed and augmentation count.
Distinguish two categories:

Sensor variation that is intended to preserve movement-quality labels

Examples include physically plausible remounts and measurement variation. Explain why the label remains applicable.

Movement changes that may change quality

Examples include altered tempo, excursion or interruption. These need a defined target and defensible labels. Do not label every changed movement “wrong.”

Changing physical speed changes acceleration, not just timestamps. If using signal time-warping as an approximation, label it accordingly and validate its limits.

For every generated example, retain:
- Source recording and volunteer.
- Transformation and parameters.
- Seed.
- Label origin.
- Whether it is measured, transformed or fully simulated.
- Validation status.
- Dataset/configuration version.
Preserve originals. Keep generated datasets local and ignored by Git where appropriate; commit small configurations, manifests and reports.

Compare real-only training with real-plus-augmentation using the same fixed model architecture and matched held-out real recordings. Report whether augmentation helps, harms or has no convincing benefit.

Performance on synthetic examples alone is not evidence of improved real-world performance.
Task 3 — Validate the augmentation and build a visual inspection tool
Separate three kinds of validation:
1. Implementation correctness: transformations behave mathematically as intended.
2. Physical/data fidelity: generated signals resemble the relevant measured signals.
3. Downstream usefulness: augmentation improves or preserves performance on untouched real recordings.
Passing one does not establish the others.

Include meaningful checks for coordinate transforms, gravity, units, clipping, timing, reproducibility, data lineage and split leakage. Test invalid inputs and known edge cases.

Build a lightweight local visual tool if technically feasible. Prefer existing dependencies or ordinary HTML/JavaScript/canvas over a large new application framework.

It should let me:
- See the arm and forearm with the two sensor mounts.
- Switch between candidate arrangements.
- Replay motion.
- Compare original and augmented acceleration traces on shared axes and units.
- See clipping, unavailable data and relevant detected boundaries.
- Adjust a small number of useful parameters.
- Inspect the configuration, seed and label provenance.
Clearly distinguish measured recordings, transformed recordings and simulated movement. A plausible-looking animation must not imply validated biomechanics.

Provide a working example and verify the visualization yourself. Explain which displayed relationships are calibrated and which remain illustrative.
Task 4 — Research and establish a modest feedback layer
Keep this feasible for the project and the Arduino. Do not build a broad diagnostic system.

Research primary sources on:
- Hybrid learned assessment and rule-based feedback.
- Personalized timing or movement targets.
- Interpretable wearable exercise assessment.
- Independently annotated error categories.
- False-feedback rates, abstention and remount robustness.
Give publication years, links, what you actually opened and important modality/label limitations. Read methods and evaluation sections, not just abstracts.

The likely architecture is a small feedback layer alongside the classifier. Investigate that position rather than assuming it is correct.

Do not make the binary “wrong” prediction the only trigger. A measurable deviation may exist when the classifier misses it; a low quality score may have no identifiable cause.

Start with narrowly defined, observable feedback—probably tempo relative to a prescribed target. The current detector’s boundaries are not validated anatomical repetitions, so establish what timing evidence is required before enabling a “too fast/slow” claim.

Define and implement the smallest useful groundwork:
- Inputs: exercise, prescribed targets, measured quantities and validity information.
- Outputs: cue identifier, supporting measurement, target, applicability and abstention reason.
- A small set of fixed, reviewable message templates.
- A replay/test harness for supported and unsupported cases.
Example intent: “Measured repetition duration is outside your prescribed target.” Do not fabricate targets or imply that acceleration amplitude directly measures range of motion.

Keep unsupported claims unavailable, including general posture diagnosis, weakness, grip force and effort. A rule describing an observed deviation is not automatically an explanation of the classifier’s decision.

Explain what new labels or sensing would allow a small learned error classifier later. Consider multiple simultaneous deviations rather than forcing every incorrect movement into one category.

Use the existing annotation protocol as a starting point, but assess whether a smaller staged pilot should precede the full proposed collection. Do not claim a guaranteed minimum sample size.
Resource budget and verification
Keep simulation, augmentation and visualization on the computer.

For proposed on-device changes:
- State flash, RAM, buffers and computational costs before implementation/training.
- Reuse existing features and runtime structures where appropriate.
- Distinguish arithmetic estimates, object measurements, linked firmware measurements and physical timing.
- Include the complete relevant processing path in footprint accounting.
- Do not describe host replay as an Arduino hardware test.
No physical board is available, so identify the bench measurements still required without fabricating them.
Deliverables, in order
1. A concise research and decision memo, including rejected alternatives and confidence.
2. A simulator audit explaining its original failure and the new validation results.
3. Four explicitly defined mounting candidates, with comparison metrics and honest ranking limits.
4. A configurable augmentation pipeline with provenance and reproducible commands.
5. Real-only versus augmented-training results on matched held-out real data.
6. A working local visualization with an example configuration.
7. Feedback-layer groundwork, its evidence requirements and tests.
8. Exact commands, actual outputs, artifact locations and commit hashes.
9. Remaining uncertainties, owner decisions and the single most useful next experiment.
Preserve existing models and historical results. Add new evidence rather than rewriting inconvenient findings.

The goal is a credible, inspectable engineering result—not a better-looking score obtained from unrealistic simulations, leaked data or invented error labels.