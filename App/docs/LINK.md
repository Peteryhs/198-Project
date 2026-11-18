# The link, hop by hop

One set travels this chain once. Units are stated at every hop. The rule is **millivolts on the wire,
g at the model**: the only mV → g conversion is `Calibration.toG`, called from `SetRecorder`.

| # | Hop | File that performs it | Unit at this hop |
|---|---|---|---|
| 1 | Board AP: SoftAP `Tally-<last 2 MAC bytes>`, WPA2, 192.168.4.1, one station | `firmware/TallyFirmwareV2/src/wifi_ap.c` | none |
| 2 | Phone joins: `WifiNetworkSpecifier`, `Tally-` prefix, open if the password is blank, else WPA2 | `backend/src/main/kotlin/link/WifiJoiner.kt` | none |
| 3 | Sampling: 100 Hz `esp_timer` tick, six ADC1 channels, `adc_cali` line fit | `firmware/.../sampler.c`, `accelerometer.c`, `session.c` | **mV** (u16), **µs** since set start (u32) |
| 4 | TCP frames: HELLO, SET_STARTED, SAMPLES (≤10 samples, 179 B at n=10), SET_END, HEARTBEAT on port 5198 | `firmware/.../link_server.c`, `frame.c` | **mV**, **µs** |
| 5 | `DeviceLink`: network-bound socket, CRC32, 3 s stall = Lost | `backend/src/main/kotlin/link/DeviceLink.kt`, `FrameCodec.kt` (`Samples.millivolts`, `timeUs`) | **mV**, **µs** |
| 6 | `SetRecorder`: sequence, timing and ≤3300 mV checks, then **mV → g** per channel through the active `Calibration` | `backend/src/main/kotlin/session/SetRecorder.kt`, `calib/Calibration.kt` (`g = (mV − offsetMv) / mvPerG`) | in **mV**, out **g** |
| 7 | Storage: `SampleStore.g(i, ch)` for scoring, `LiveRing` for the live trace; the archive keeps the raw frames | `session/SampleStore.kt`, `session/LiveRing.kt`, `store/SetRepository.kt` | store and ring **g**; archive **mV** |
| 8 | Scorer input: `#TALLY2 fs=100 unit=g range=3`, one `S` line per sample | `backend/src/main/kotlin/score/TallyWireWriter.kt` | **g**, time in **ms** (`t_us / 1000`) |
| 9 | Python, once per set after SET_END: parse and validate | `score/PythonScorer.kt` → `backend/src/main/python/tally_app.py` → `reference/scripts/tally_stdlib.py` | **g** |
| 10 | Features: cycle segmentation on the acceleration magnitude, 61 features per rep | `reference/scripts/stdlib_runtime.py` (`find_peaks`, `build_rows`) | **g**, cycle durations in **s** |
| 11 | Model: 61-input linear softmax (EAH/EFE/SQZ) plus logistic quality head, side L or R | `reference/model/paired-synchronized-offline/{L,R}/realtime_model.npz`, `stdlib_runtime.predict` | features from **g**; out probabilities |
| 12 | Verdict: per-rep and set verdict, chart, provenance, persisted | `score/ScoredResult.kt`, `AndroidTallyBackend.scoreRecording`, `store/SetRepository.kt` | probability; chart magnitudes **g** |

Between hops 11 and 12, `tally_app.score_wire` turns a scored set into `insufficient_reps` / `no_movement`
when p90 of the detrended forearm magnitude is below `NO_MOTION_P90_G` (0.03 g, provisional; see REPORT5.md).

Two exceptions to "g after hop 6", both deliberate:
- **CSV export** (`export/CsvExport.kt`) replays the archived frames and writes `*_mv` columns: raw data, not model input.
- **Calibration pose capture** (`AndroidTallyBackend.onFrame`) averages 100 samples and converts g back to mV with the
  same calibration, because `Calibration.fromPoses` fits offsets and scales in mV.

Recovery: if HELLO reports `active_set_id ≠ 0` (a set the board still holds after a lost link or app restart),
`AndroidTallyBackend.abortHeldDeviceSet` sends ABORT and waits up to 3 s for SET_END before sending START. The
firmware ignores START until that SET_END has gone out (`session_start` requires `SESSION_IDLE`).

Wire authority: `docs/ESP32-WIRE-V1.md`. Firmware obligations: `docs/FIRMWARE-HANDOFF.md`.
