# Tally basic feedback application

Implemented on `codex/basic-feedback`, starting from `fbb4181`. The accepted paired
logistic-regression model is unchanged. One left upper-arm/forearm pair now has a portable
application, host CSV replay and Arduino Serial integration scaffold. **Real timing cues
remain unavailable: detector cycles have no independently validated anatomical boundaries.**
No model was retrained, no simulator work was resumed, and no physical board was tested.

## Application contract

`model/application/tally_app.h` owns one `PairRuntime`, configuration and `TallyOutput`.
Zero-initialize `TallyApp` in static storage; never put its ~14.6 kB on the Arduino stack.
Supply a `TallyConfig` containing exercise (EAH/EFE/SQZ), requested count, explicit positive
min/target/max duration, prescription identifier and caller attestation that it is prescribed.
Missing or invalid targets reject configuration; there is no default therapeutic range.
Borrowed prescription strings must remain immutable/alive throughout the set. Attestations
are input metadata, not authenticated clinical approval.

Call `tally_configure`, `tally_start`, `tally_push`, optional `tally_pause`/`tally_resume`,
then `tally_finish`. Start after finish resets counters, faults, pooling and policy;
reconfiguration is allowed only outside running/paused sets. `target_count` is a requested
repetition goal; `cycles` counts detected intervals. **Reaching the goal never automatically
finishes a set or claims completed anatomical repetitions**; finish is explicit.

Each `tally_push` takes one timestamp and all six synchronized acceleration channels in g.
Nominal cadence is 100 Hz; the reused runtime accepts deltas 8–12 ms. Detector-cycle duration
uses actual confirmation timestamps, while the unchanged classifier feature contract still
assumes 10 ms/sample. A displayed detector interval is not an eligible anatomical-repetition
duration. `duration_available` describes only the latest detector interval in a fault-free
set. Initial and final partial cycles are discarded by the existing detector.

`active_ms` includes active-set time through the latest processing/control call, excludes
explicit pauses, and never uses host replay wall time. Use one uint32 clock for acquisition
and controls (Serial replay supplies this clock). Wrapping timestamps are supported if
successive control calls are less than 2^31 ms apart; backward clocks and accumulated elapsed
overflow are rejected. Pause drops the partial cycle and clears cues while preserving
completed-cycle pooling. Resume needs a fresh first boundary before a completed interval.
Mark rests with pause/resume. Unmarked inactivity is not reliably separable from a hold;
static spans can overflow the bounded buffer, never validate a repetition or trigger slow advice.

Nonfinite/null samples and timing gaps reset the existing runtime. The visible set cycle
count remains cumulative, but pooled probabilities restart, as in `pair_push`. Clipping
(at or beyond ±3 g, conservative for already-clipped inputs) and buffer overflow retain the
existing classifier processing but latch a fault. All faults suppress timing availability
and final assessment for the **rest of the set**, even if later input recovers. This deliberate
first-version policy favors explicit unavailable results over quietly scoring incomplete data.
The fault bitmask and cumulative counts remain visible; start a new set to clear faults.

At finish, `assessment_available` requires at least three pooled cycles and no data fault,
matching the accepted training/replay retention floor. When true, expose the existing mean
exercise probabilities (EAH/EFE/SQZ) and mean model probability of **study class 1: incorrect**,
with the existing 0.5 study-label decision. This is a series-label model assessment, not a
verified percentage of correct/incorrect repetitions, a clinical judgment, or an explanation.
Ignore populated probability fields when availability is false; host logs retain them only
as explicitly labelled diagnostic means. The only supported error explanation remains
“not enough evidence to say”. Paused/segmented use has software parity tests, not a separate
held-person performance evaluation.

Processing never writes to Serial/display. Consumers read `TallyOutput`; `cue` is an event
for the current call. Render one cue at a time and clear any visible cue on pause, unavailable
measurement or fault. The scaffold reports new fault transitions rather than flooding Serial.

## Feedback rule and evidence

`feedback_policy.c` calls the existing unchanged `feedback_evaluate`. Two consecutive
eligible durations must yield the same cue; an ineligible duration or changed cue clears
persistence. One shared five-second active-clock cooldown limits all cue types, including
on-target. There is no averaging of intervals across pauses, no confidence threshold and no
classifier input into the timing policy. Pause/new set resets the policy. This is a small
engineering policy, not a clinically validated smoothing choice.

Only known-duration synthetic fixtures attest boundary evidence, in the isolated policy tests:
1.0 s emits “Faster than target”, 3.0 s “Slower than target”, and 2.0 s “Pace on target” for
an explicitly **test-only** inclusive range [1.8, 2.2] s. Both endpoints emit on-target.
The first measurement is suppressed; the second eligible matching measurement emits, subject
to cooldown. The fixture IDs explicitly identify synthetic timing; they are not human labels.

The application always passes `repetition_boundary_independently_validated=0`. There is no
runtime demonstration override or command that promotes a peak, recording label or classifier
score to boundary evidence. A future validated boundary source must identify the particular
source clip/cycle, exercise, prescription version, start/end evidence, independent raters,
uncertainty/adjudication and supported scope. Collect synchronized video and intended-device
signals, with visible/logged sync events and remounts; have raters mark observed boundaries
blinded to assigned timing and model output. Keep assigned instructions, observed timing,
disagreements and adjudicated references separate. Quantify per-exercise boundary error,
false cues, coverage and abstention, including interrupted/unobservable cycles, before wiring
that source into live feedback. The feasibility protocol in `FEEDBACK-PHASE3.md` is the next
evidence step, not completed validation or a sample-size guarantee.

## Arduino and replay

The previous hardware files contain only pin-holder scaffolding and no display driver.
`hardware/198project/198project.ino` therefore uses Serial without adding hardware. Its local
`tally_processing.c` compiles the existing C sources once and selects the accepted synchronized
causal L model. The runtime's default model include remains unchanged for existing callers.
The sketch uses `setup`/`loop`, a bounded 160-byte input line and 48-byte prescription storage.
It rejects oversize/control-byte/malformed frames and signed/out-of-range unsigned fields.
During a running set, bad transport input also suppresses assessment through a sample fault.

Serial commands (LF or CRLF), exercise IDs 1=EAH, 2=EFE, 3=SQZ:

```text
C <exercise> <count> <min_s> <target_s> <max_s> <prescribed_attestation_1> <prescription_version>
S <time_ms>
P <time_ms>
R <time_ms>
F <time_ms>
```

The attestation must explicitly be 1; it is never inferred from the supplied numeric range.
Then send data rows with the seven CSV fields below, **without the CSV header**. The host
harness reads the header and parses CSV separately from physical acquisition:

```text
time_ms,upper_ax_g,upper_ay_g,upper_az_g,forearm_ax_g,forearm_ay_g,forearm_az_g
```

A future ADC driver calls `submitAccelerationG` with the same synchronized, calibrated g
frame and timestamp. No `analogRead` conversion, bias/gain calibration, ADC schedule or
channel-skew claim is invented. Do not run Serial replay and physical acquisition together.
The parser and Serial timing still need a real core link and bench evaluation.

The two supplied replay examples are PHYTMO NGIMU recordings, aligned relative to synchronized
starts, interpolated at 100 Hz and clipped to ±3 g. They are not ADXL335 captures, ADC counts
or voltages. Their README/manifest and original source hashes are retained in replay output.
No study labels are used by the processing or feedback decisions.

| Recording | Samples | Active elapsed | Detected cycles | Faults | Final assessment | Mean model P(class 1), diagnostic | Timing cues |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| A01EAH0_1 left pair | 7,555 | 75.54 s | 50 | Buffer overflow | Unavailable | 0.322702 | 0 |
| A01EAH1_1 left pair | 4,576 | 45.75 s | 30 | None | Available model series label: incorrect | 0.621927 | 0 |

Both have identical per-sample cycle statuses, retained counts and pooled probabilities to
direct `PairRuntime` replay. The first recording's tail without another completed cycle overflows the existing six-second
buffer; the application reports it rather than hiding it. The counts are **not** annotated
repetition totals. Study filenames/labels do not independently validate this exported model
on these examples (the all-person export may have trained on them).

## Resource result and limits

`docs/runs/basic-feedback/target.json` and `target.log` compile the actual processing wrapper
and sketch for Cortex-M4F with Clang `-Oz`, then combine them as a relocatable object. Arduino
and libc headers are declaration-only shims. All compiler commands, section/symbol sizes,
compiler stack frames and unresolved functions are retained. Budget assertions enforce the
pre-implementation 512-byte extra-static-state and 8 kB extra-object-text caps.

| Quantity | Bytes |
| --- | ---: |
| PairRuntime / TallyApp | 14,472 / 14,584 |
| Increment inside application structure | 112 |
| Full actual sketch + processing BSS / data | 14,800 / 0 |
| Full static overhead beyond PairRuntime, including parser | 328 |
| Full text/rodata/exidx | 6,376 |
| Text/rodata/exidx growth over historical-style baseline | 3,830 |
| Stack/core/display/interrupt reserves | 4,096 / 4,096 / 1,024 / 1,024 |
| Provisional RAM scenario / headroom of 32,768 | 25,040 / 7,728 |

No second sample buffer or heap storage was added. The historical-style baseline includes
16 bytes of separate output floats; the application now holds output internally. Thus the
new aggregate BSS is 312 bytes above that baseline (328 bytes above PairRuntime alone).
The stack reserve already includes compiler frames; do not add them twice. Known call frames
fit inside the reserve, but library/core/interrupt high-water use is unmeasured.

These are **unlinked object sizes plus arithmetic reserves**, not linked flash/RAM or measured
stack high-water. Unresolved Serial, `strtof`, string, libm and ARM memory helpers can add flash,
RAM and stack. Arduino CLI/core and GNU ARM toolchain are unavailable here. No board execution,
ADC throughput, control latency, sampling simultaneity, display timing or power was measured.
Four ADXL335 units still require twelve analog channels versus six exposed inputs. Two
existing float-buffered pair states plus the earlier core reserve exceed 32 kB. The longer-term
four-sensor requirement remains: acquisition/channel expansion and memory redesign need a
separate hardware/software decision; this one-pair implementation does not remove them.

## Reproduce and hand off

From the repository root, use `/tmp/tally-round2-env/bin/python` (Python 3.12.14, NumPy 2.3.4,
SciPy 1.16.3, scikit-learn 1.7.2), or rebuild the pinned environment described in
`MODELLING-ENVIRONMENT.md`. Set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` for numerical runs.

```sh
/tmp/tally-round2-env/bin/python scripts/test_tally_app.py
/tmp/tally-round2-env/bin/python scripts/test_tally_replay.py
/tmp/tally-round2-env/bin/python scripts/test_feedback.py
/tmp/tally-round2-env/bin/python scripts/test_streaming_pipeline.py
/tmp/tally-round2-env/bin/python scripts/test_paired_runtime.py
/tmp/tally-round2-env/bin/python scripts/test_modelling_environment.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python scripts/verify_round2.py
/tmp/tally-round2-env/bin/python scripts/measure_tally_target.py
/tmp/tally-round2-env/bin/python scripts/tally_replay.py data/arduino-replay-demo/A01EAH0_1-left-pair.csv --exercise EAH --count 10 --min-seconds 1.8 --target-seconds 2 --max-seconds 2.2 --prescription-id SYNTHETIC-TARGET-ONLY-NOT-A-PRESCRIPTION --prescribed --out /tmp/tally-replay.json
```

All new/existing relevant host checks pass (`tests.log`). Seven host parser/replay tests cover
malformed input and a gap after completed cycles; C tests cover inclusive timing boundaries,
fast/slow/on-target, persistence/cooldown/wrap, boundary abstention, pause/partial/insufficient
cycles, reset, fixed 8/10/12 ms and alternating 8/12 ms timestamp durations, samples/gaps/clipping/overflow, clock errors,
classifier parity, Serial CSV versus direct application parity, and bounded Serial output. Stub tests execute the actual sketch on the host;
they do not run the Arduino core. The unchanged strict ten-model verifier passes exact stored
coefficients, C probability parity and every stored LOSO decision (`verify-round2.log`).
No assertion was weakened and no accepted export regenerated. Optional UBSan could not link
because the host `libubsan.so.1.0.0` is missing (`tool-availability.log`).

Actual replay JSONs and commands are in `docs/runs/basic-feedback/replay-A01EAH{0,1}.json` and
`replay.log`; synthetic cue stdout is in `tests.log`. The separate implementation plan records
the starting branch/HEAD and incremental budget. GPT-6 Luna agents independently reviewed
requirements/code and implemented replay/resource checks; final fixes were integrated and rerun.
Raw data, accepted models, historical results and pre-existing untracked `output/`/`tmp/` remain.
All commits are local; no push, PR or repository message was sent.

Hardware handoff: install the UNO R4 core/toolchain and link the actual sketch; record map-file
flash/RAM and stack high-water. Calibrate each axis, verify rate/bandwidth/saturation and six-channel
skew, then measure compute/Serial end-to-end latency under worst-case feature work and faults.
Validate target input/control ergonomics and interrupted sets. Resolve four-sensor acquisition
and buffering separately. Collect independently observed boundary evidence before enabling real
repetition-timing cues. Software lifecycle/replay checks are complete; hardware and feedback
validity remain open.

Local milestones: `872dea7` plan/budget; `77979b3` application/replay/scaffold; `b374169`
Serial-to-direct regression. The evidence/handoff commit follows these. `delivery.json` records
the implementation checkpoint, source hashes and a Git comparison proving protected tracked
model/data/history paths unchanged from the starting HEAD. Final commit/status are in `git log`.
