# Tally

An Arduino-first telemetry viewer for Android, inspired by phyphox. Connect to a board over Wi-Fi/TCP, discover its sensor plugs, record a run, inspect graphs and statistics, and export CSV. Phone sensors and full phyphox experiment compatibility are not implemented.

Tally accompanies the ECE 198 Home Exercise Monitoring project. The UNO R4 Minima / Yún shield transport remains subject to hardware validation.

## Connect and record

1. Join the same network as the board.
2. Enter the board's IP address and TCP port (example: `5555`) and connect.
3. Open one of the advertised plugs. With an older sketch that sends no advertisement, Accelerometer and Gyroscope remain available.
4. Record, pause to inspect, then save locally or export CSV.

Timed runs and start delays are available. Pauses create separate graph segments; saved recordings can reopen without the original board. Recording currently stops at 20,000 samples.

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

Tests cover parsing, metadata validation, variable-axis recordings, old file compatibility, buffer overflow and cancellation, session timing, reconnect races, statistics, and CSV formatting. Hardware calibration, throughput, and frame-time benchmarks require separate device testing.

## Arduino example

`arduino_example/tally_bridge.ino` advertises one 3-axis accelerometer and streams raw 12-bit ADC counts from A0–A2. It does not claim calibrated acceleration. It differs from the ECE 198 four-sensor, single-axis proposal. Confirm ADXL335 module power requirements and board/shield/library compatibility before using it; the example has not been compiled against a verified UNO R4/Yún toolchain.

## Remaining platform work

A modular DSP pipeline, FFT/spectrum views, phone sensor/audio adapters, configurable experiment pipelines, XLSX/TSV/JSON exports, and an HTTP/WebSocket or BLE remote interface remain unimplemented. Tally is not yet feature- or precision-equivalent to phyphox.

## License

MIT — see [LICENSE](LICENSE).
