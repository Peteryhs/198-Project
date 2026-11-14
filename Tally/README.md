# Tally

An Arduino-first exercise logger and telemetry viewer for Android, inspired by phyphox. Connect to a board over Wi-Fi/TCP, count and log exercise sets, or discover its sensor plugs, record a run, inspect graphs and statistics, and export CSV. Phone sensors and full phyphox experiment compatibility are not implemented.

Tally accompanies the ECE 198 Home Exercise Monitoring project. The UNO R4 Minima / Yún shield transport remains subject to hardware validation.

## Connect and record

1. Join the same network as the board.
2. Enter the board's IP address and TCP port (example: `5555`) and connect.
3. Open one of the advertised plugs. With an older sketch that sends no advertisement, Accelerometer and Gyroscope remain available.
4. Record, pause to inspect, then save locally or export CSV.

Timed runs and start delays are available. Pauses create separate graph segments; saved recordings can reopen without the original board. Recording currently stops at 20,000 samples.

## Exercise sets

The **Exercise** tab is the app's main screen. It does what the project README asks of the device: count each repetition, keep the pace honest, tell a full repetition from a shallow one, and produce one summary for the instructor.

1. Connect to the board, then tap **Set up exercise**.
2. Choose the exercise (arms over head, elbow flexion or squeeze, the EAH/EFE/SQZ codes in `feedback.h`), the target count and, if the instructor prescribed one, a pace range in seconds per repetition. There is no default pace range.
3. **Calibrate**: hold the start position, then the end position, for two seconds each.
4. **Start**, exercise, **Pause**/**Resume** for rests, **Finish**. **Reset count** discards the set.
5. Enter the count you actually observed, then **Save** and **Share** the report.

### Who counts

| Source | When | What Tally logs |
| --- | --- | --- |
| Board firmware | The board sends `TALLY` status frames | The firmware's count, per-cycle duration and cue, active time, fault bitmask, and at finish the model's exercise probabilities and series label. The board's Start/Pause/Finish buttons drive the app's set. |
| Tally app estimate | Only synchronized arm-pair rows arrive | Its own count from the two sensors, following the project README: the angle the exercise moves through, a hysteresis band (a rep starts above 40% of the calibrated range and completes back below 20%), and peaks at 80% or more counted as full. A rep can only start after the arm has been seen at rest, so a pause mid-movement never completes a rep. |

The board's count always wins: when the first `TALLY` frame arrives, the app's estimate for that set is dropped.

Calibration measures three candidate angles from gravity (upper-arm tilt, forearm tilt and the angle between the segments) and uses whichever changes most between the two poses. Gravity-based angles are only valid for movements slow enough that gravity dominates.

### What each set logs

| Metric | Definition |
| --- | --- |
| Repetitions, completion | Count, and count ÷ target |
| Full / shallow, range efficiency | Peak ≥ 80% of the calibrated range is full; range efficiency = full ÷ reps with a range reading |
| Pace | Seconds since the previous repetition (the same quantity as the board's `cycle_seconds`); last, mean, fastest, slowest, reps per minute |
| Pace check | Each rep on pace, too fast or too slow against the inclusive prescribed range |
| **Efficiency** | Reps that were neither shallow nor off-pace ÷ reps logged. Unavailable when no rep has a range reading or a pace check |
| Active time, pauses | Pauses excluded; from the board's `active_ms` when it reports |
| Samples recorded | Rows received ÷ rows expected at 100 Hz, on the board's clock (`time_ms`) |
| Timing gaps, clipped, dropped | Steps over 12 ms (the `tally_push` limit), values at or beyond ±3 g, phone-side buffer evictions |
| Faults | Board bits (bad sample, timing gap, clipped, overflow, model error) plus app bits (samples dropped, connection lost) |
| Calibration | Chosen signal, range in degrees, number of calibrations |
| Model assessment | Only when the board's `assessment_available` is 1: likely exercise and the 0.5-threshold series label. Not a per-repetition or clinical judgment |
| Counting error | \|counted − observed\| per 10 observed repetitions |

The summary checks itself against the project's design targets: at most 1 counting error per 10 repetitions, at least 95% of samples recorded, and 60 minutes of continuous running. These remain requirements; a passing set on a phone is not a validated device measurement. Repetition boundaries come from a detector, not from validated observation (see `docs/BASIC-FEEDBACK.md`), so pace and range are estimates.

Saved sets are plain-text `TALLY-SET-1` files in app storage. **Share** sends the readable summary as the message body with a CSV attached: one row per metric, then one row per repetition.

## Generic sensor plugs

`PlugSpec` is a pure Kotlin metadata model: ID, display name, wire-axis names/count, unit, interpretation, icon key, accent color, optional range, and optional derived magnitude. A single `ArduinoPlugStream` maps any spec to `SensorStream` (`Flow<SensorSample>` plus batched delivery). No new sensor-specific Kotlin class is required.

Supported interpretations:

| Kind | Wire values | Behaviour |
| --- | --- | --- |
| `vector` | 1–16 finite floats | Independent named axes; legacy 3-axis motion plugs also derive magnitude |
| `scalar` | One finite float | Single trace and numeric readout |
| `boolean` | One value, `0` or `1` | State displayed as a numeric trace/readout |
| `event` | One value, `0` or `1` | Each received event sample is retained; no pulse counting or interpolation is implied |

Known value ranges are descriptive metadata, not clipping thresholds. Units are labels: Tally does not silently convert or calibrate values. Unknown scalar/vector plugs default to `raw` units. Boolean/event types currently share the graph/readout UI, rather than a dedicated event timeline.

## Wire protocol

UTF-8 text over TCP, one newline-terminated frame per message. LF and CRLF are accepted. Frames are limited to 8,192 characters. An oversized frame closes the connection with an error instead of allocating unbounded memory.

### Advertise the catalog

Send this once immediately after each client connects, before readings:

```text
PLUGS,accel:3,gyro:3,temp:1
```

The first valid advertisement replaces the fallback catalog atomically. Further advertisements are ignored until reconnect; reconnect resets discovery to the legacy fallback. There may be 1–32 plugs, with unique IDs after alias normalization. An invalid advertisement is ignored as a whole. A valid advertisement can arrive late, but sending it first avoids readings being ignored before their plug is known.

An extended descriptor supplies metadata:

```text
id:count[:kind[:unit[:displayName[:axis1|axis2[:minimum[:maximum[:icon]]]]]]]
```

Examples:

```text
PLUGS,temp:1:scalar:degC:Temperature:temperature:-40:125:temperature,contact:1:boolean:state:Contact:closed:::event
D,temp,23.5
D,contact,1
```

IDs use letters, digits, `_`, and `-`, begin with a letter, and are at most 40 characters. IDs are case-insensitive; `accel`/`a` map to `accelerometer`, and `gyro`/`g` to `gyroscope`. Do not use those reserved aliases for unrelated sensors.

Optional fields may be empty. Metadata fields cannot contain protocol delimiters (comma, colon, or newline); axis names are separated by `|`. Display names are limited to 80 characters; units and individual axis names to 40. Axis names must be unique and match the advertised count. Ranges must be finite and increasing when both endpoints are present.

Known icon keys: `motion`, `rotation`, `temperature`, `event`; other keys use a generic sensor icon. Accents are assigned by the app's brand palette: Ink for the accelerometer and Clay for other plugs. The wire format intentionally does not accept arbitrary remote colors.

### Send readings

```text
D,<plug-id>,<value1>,<value2>,...
```

A reading must match the advertised axis count and interpretation. Unknown IDs, malformed frames, nonfinite values, and dimension mismatches are ignored. The line carries no device timestamp, sequence number, or checksum; those remain protocol work for precision acquisition.

### Exercise frames

```text
time_ms,upper_ax_g,upper_ay_g,upper_az_g,forearm_ax_g,forearm_ay_g,forearm_az_g
TALLY,<state>,<cycles>,<target>,<active_ms>,<faults>,<cycle_s>,<duration_available>,<cue>,<timing_reason>,<assessment_available>,<p_eah>,<p_efe>,<p_sqz>,<p_incorrect>
TALLYCFG,<exercise 1-3>,<count>,<min_s>,<target_s>,<max_s>,<prescribed 0|1>[,<prescription_id>]
CAL,<1|0>[,<detail>]
```

The first is the documented replay row from `docs/BASIC-FEEDBACK.md`, without its header: a synchronized six-channel frame in g with the board's timestamp. `D,arm_pair,<6 values>` from an advertised `arm_pair:6` plug also feeds exercise sets, but without a board clock coverage falls back to arrival time.

`TALLY` copies `TallyOutput` field for field: `state` 0–4 (idle, ready, running, paused, finished), `cue` 0–3 (abstain, on target, too fast, too slow), `timing_reason` 0–6, and the `TALLY_*` fault bits. Probabilities may be `nan` unless `assessment_available` is 1; any other malformed value drops the frame. Send one after each output change and at least once a second while running. `TALLYCFG` echoes the board's `C` command so a set started on the board uses its prescription; `CAL` reports the calibrate button. `arduino_example/tally_exercise_bridge.ino` shows all of them.

### Older sketches

```text
A,<x>,<y>,<z>
G,<x>,<y>,<z>
```

These remain supported, including ignored trailing fields. Without an advertisement, their built-in labels are `m/s²` and `°/s`; verify that the sketch actually sends those units. The app appends vector magnitude. Advertised motion plugs may override unit and axis labels. Generic `D` messages require an exact value count; extra fields are not ignored.

## Add a sensor without rebuilding the app

1. Choose an ID, interpretation, axes, and units.
2. Add its descriptor to the sketch's `PLUGS` line.
3. Read actual hardware and send `D,id,...` with the same number of values.
4. Reconnect Tally. The home list follows the advertisement automatically.

For the proposed four single-axis limb sensors, an example catalog is:

```text
PLUGS,left_upper:1,left_lower:1,right_upper:1,right_lower:1
```

Replace `raw` defaults with explicit units once the hardware conversion is defined. This describes four channels, not four complete three-axis sensors.

## Acquisition and storage

The TCP reader runs on its own thread. Each consumer has a bounded 4,096-sample FIFO; overload evicts the oldest unread sample and reports the eviction count. Delivery is batched on a nominal 16 ms cadence to reduce Compose updates. This is not a guaranteed rendering frame rate or lossless capture claim.

Samples carry monotonic TCP-arrival timestamps into the session. These preserve arrival spacing despite delayed UI work, but cannot correct network jitter or reconstruct the board's sampling clock. Consumer cancellation ends its subscription and discards any unread tail; a durable drain-on-stop recorder is still required for precision acquisition.

`TALLY-2` saved files embed plug metadata and variable-axis values. Existing `TALLY-1` recordings remain readable. Overflow diagnostics are currently session-local and are not persisted in the saved format. CSV uses the plug's axis names and actual values; formula-like header labels are neutralized and CSV-special characters are escaped.

## Source map

| File | Responsibility |
| --- | --- |
| `sensors/PlugSpec.kt` | Validated metadata and value interpretation |
| `sensors/LineProtocol.kt` | Pure JVM protocol parser |
| `sensors/ArduinoLink.kt` | Connection lifecycle, discovery, and routing |
| `sensors/SampleBuffer.kt` | Bounded queues, batches, and overflow accounting |
| `sensors/ArduinoSensorStreams.kt` | Generic runtime adapter |
| `ExperimentRegistry.kt` | Maps discovered specs to UI entries |
| `recording/ExperimentSession.kt` | Recording lifecycle and UI state |
| `recording/RecordingStore.kt` | Versioned local recording persistence |
| `ui/LiveChart.kt` | Time plot and sample inspection |
| `export/CsvFormatter.kt` | Pure CSV formatting |
| `exercise/ExerciseModel.kt` | Exercise, prescription, board status and repetition types mirroring `tally_app.h` |
| `exercise/RepCounter.kt` | Calibration and the app's hysteresis repetition estimate |
| `exercise/SetTracker.kt` | Set lifecycle, board mirroring, data quality, and every derived metric |
| `exercise/SetStore.kt`, `SetReport.kt` | `TALLY-SET-1` persistence and the instructor report |
| `recording/ExerciseSetSession.kt` | Routes connection feeds into a set; mirrors board buttons |
| `ui/ExerciseScreen.kt`, `SetSummaryView.kt`, `ExerciseHome.kt` | Set setup, live count, summary and history |

## Theme and toolchain

The app uses Material3 **1.5.0-rc01** (release candidate), Compose BOM **2026.09.00**, Kotlin/Compose compiler plugin **2.4.10**, Android Gradle Plugin **9.1.1**, Gradle **9.3.1**, and compile SDK **37**. The minimum Android version remains API 26.

The app uses the public `MaterialExpressiveTheme`, `MotionScheme.expressive()`, emphasized typography with Atkinson Hyperlegible, and Material animated button shapes for Record/Pause. The fixed brand palette and monospace numeric readouts are preserved. Material3 is deliberately pinned to a release candidate to enable these APIs; see the [official release notes](https://developer.android.com/jetpack/androidx/releases/compose-material3#1.5.0-rc01).

All typography roles use the bundled Atkinson Hyperlegible family; live numeric readouts retain monospace with tabular numerals. The fixed light brand theme uses Ink `#26372C`, Paper `#F5F1E8`, Oat `#D9C9A8`, Clay `#995438`, and White `#FFFFFF`. Chart series may also use muted olive `#586442` and brown `#72523D`. Dynamic wallpaper colors and automatic dark recoloring are disabled to preserve the requested palette. Launcher and splash assets use the same brand tokens.

## Build and tests

Open this folder in Android Studio and use a compatible Gradle JDK (Java 21 is verified in this workspace).

```sh
./gradlew testDebugUnitTest
./gradlew assembleDebug lintDebug
```

Tests cover parsing, metadata validation, variable-axis recordings, old file compatibility, buffer overflow and cancellation, session timing, reconnect races, statistics, and CSV formatting. Exercise tests drive synthetic 100 Hz elbow-flexion frames through calibration and counting (full, shallow, too small, wobble near the threshold, pause mid-movement, starting with the arm raised), check every set metric in both app and board modes, parse every exercise frame and its malformed variants, and round-trip saved sets. Hardware calibration, throughput, and frame-time benchmarks require separate device testing.

## Arduino example

`arduino_example/tally_bridge.ino` advertises one 3-axis accelerometer and streams raw 12-bit ADC counts from A0–A2. It does not claim calibrated acceleration. It differs from the ECE 198 four-sensor, single-axis proposal. Confirm ADXL335 module power requirements and board/shield/library compatibility before using it; the example has not been compiled against a verified UNO R4/Yún toolchain.

## Remaining platform work

A modular DSP pipeline, FFT/spectrum views, phone sensor/audio adapters, configurable experiment pipelines, XLSX/TSV/JSON exports, and an HTTP/WebSocket or BLE remote interface remain unimplemented. Tally is not yet feature- or precision-equivalent to phyphox.

## License

MIT — see [LICENSE](LICENSE).
