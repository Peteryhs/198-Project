# Paired acceleration models

**Timing correction:** `paired-offline` and `paired-causal` are INVALID CLOCK-ALIGNMENT
history. They aligned unrelated device uptime clocks and must not be used. The valid exports are
`paired-synchronized-offline` and `paired-synchronized-causal`. They subtract each synchronized
recording start before interpolation. The old files/logs remain solely to preserve the audit trail;
the description below of the original run is superseded by `docs/ROUND2-REPORT.md`.


`paired-offline/L` and `R` fuse timestamp-aligned upper-arm and forearm recordings on the
corresponding side. See `docs/ROUND2-PLAN.md` for the position fixed before training and
`docs/runs/round2/fix1-pairs.log` for commands/results. The 61 inputs share a single cycle
boundary; a model now sees both sensors simultaneously. No gyro or magnetometer is used.

These are series-level LOSO scores, not repetition-level validation or actual joint angles.
Different retained cohorts prohibit a direct superiority claim between sides. `results.json`
contains every rejected file/reason and each held-out subject. Generated header/NPZ exports
are new artifacts; previous single-sensor exports are unchanged. Simulation, self-placement,
on-board performance and patient error categories remain unproven.

`paired-causal/L` and `R` use the actual C source in `streaming/` during raw-data replay.
`PairRuntime` accepts timestamped, calibrated g inputs, clips, detects, extracts and classifies,
then accumulates series probabilities. Its first and last partial cycles are discarded; static
inputs produce no decision; >6 s buffers overflow and abstain for that partial cycle; timing gaps
and nonfinite samples reset the stream. Model headers must match the causal feature pipeline.

The detector uses an EMA coefficient 0.2, 0.04 g rise/descent hysteresis, 20 confirmation samples,
and a 120-sample minimum interval. These engineering settings were fixed before replay. A causal
boundary is confirmation of a magnitude peak, not the end of an anatomically verified repetition.
41 buffers overflowed during the two-side replay (see log); they were discarded, not classified.
All retained cycles remain pseudo-labelled from their source series. A real-time implementation
now exists, but MCU timing, calibrated ADC ingestion, anatomical boundaries and display remain
unmeasured/unintegrated. The firmware sketch is untouched because this experiment only needs a
portable C API and raw replay, not a change to the existing hardware application.

`placement-controls/` contains the common-cohort comparison and four single-sensor feature ablations.
Those ablations reuse the pair's forearm-derived causal boundaries; an upper-only feature score is
not validation of an upper-only detector. These are controls, not a recommendation to remove the
second sensor. `docs/runs/round2/placement.log` prints floors with every accuracy, coverage for
simulated remounts, and a subject-block bootstrap side comparison. A seeded rigid rotation of
measured vectors is a direct stress transformation; it does not depend on the failed MuJoCo
movement-distribution gate and does not simulate soft tissue, translation, bias or band slip.

For causal models, compile `streaming/paired_stream.c` and `streaming/paired_runtime.c` with the
selected model directory on the include path. Instantiate `PairRuntime` in static storage, call
`pair_reset`, then `pair_push` every 10 ms with all six calibrated channels from the same acquisition
cycle. After a user-defined series ends, `pair_series` returns mean probabilities or abstains
without completed cycles. Preserve the unavailable mechanism string in any display layer.
For `placement-controls/*-forearm`, also define `PAIR_FOREARM_ONLY`; upper controls use the leading
31 features, pair controls use all 61. These single-sensor controls still require the forearm detector.

The feature/detector object and complete causal target objects are measured in
`docs/runs/round2/target-size.log`. They are unlinked Cortex-M4F objects, not a complete Arduino image.
Causal runtime state, library/core integration, acquisition cadence and display delays must all be
included before declaring the actual device validated. No hardware or firmware sketch was changed.

## Basic application integration

`application/tally_app.h` now wraps the accepted synchronized causal pair runtime with
explicit configuration/start/pause/resume/finish and separate output state. The Arduino
Serial scaffold selects the L export; host replay uses that same model. No accepted model
changed. See [the integration report](../docs/BASIC-FEEDBACK.md) for commands, fault/availability
policy and full-path resource limits. Detector intervals remain unvalidated anatomical
repetitions and cannot enable timing feedback. Physical ADC acquisition and four-sensor
channel/memory constraints remain unresolved. Earlier paragraphs describe historical stages.
