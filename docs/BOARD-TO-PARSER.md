# Board-to-parser contract

This document defines the serial boundary for a single-sensor set. The board sends raw accelerometer samples; Linux Yún validates and segments them, extracts the training features, and loads `model/small/form_rep.joblib` for inference. One complete, valid set is the unit of scoring.

## Sensor and model assumptions

- Sample the accelerometer at a fixed target rate of 100 Hz. Send no timestamps.
- Send the three training axes in order: `x`, `y`, `z`, in `g`, including gravity. The sensor must stay in the same limb mounting and orientation represented by `ax`, `ay`, `az` in the training CSVs. The header's axis declarations are fixed; they do not authorize an axis swap or sign change.
- Do not normalize, detrend, filter, remove gravity, resample, or otherwise transform the samples on the board. The parser receives the raw values and applies the training pipeline.
- Each value is an ASCII signed decimal with exactly eight digits after the decimal point (`-0.08730000`). A leading `+` or `-` is allowed; no exponent notation, NaN, or infinity is allowed. Eight decimals reproduce the recorded data exactly: every slot matches the training features to 1e-6: the measured parity against original CSV rows is recorded below.

## Where the code goes

All of this lives in `hardware/198project/`. Two files are empty today and are where the sender
belongs; the sketch gains three call sites.

| file | what you put in it |
| --- | --- |
| `data_transfer.h` | three declarations — block 1 |
| `data_transfer.cpp` | the sender and the sequence counter — block 2 |
| `198project.ino` | `setup()`, `loop()`, and the end-of-set trigger |

**Block 1 — `data_transfer.h`**

```cpp
#pragma once

void tally_begin(void);                            /* header, once per sketch run */
void tally_sample(float ax, float ay, float az);   /* one S line */
void tally_end_set(const char *reason);            /* E done / E aborted / E overflow */
```

**Block 2 — `data_transfer.cpp`**

```cpp
#include "data_transfer.h"
#include <Arduino.h>

static unsigned long seq = 0;

void tally_begin(void) {
    seq = 0;
    Serial1.print("#TALLY1 fs=100 unit=g ax=+x ay=+y az=+z\n");
}

void tally_sample(float ax, float ay, float az) {
    char line[56];
    int n = snprintf(line, sizeof line, "S %lu %+.8f %+.8f %+.8f\n",
                     seq++, ax, ay, az);
    if (n > 0) Serial1.write((const uint8_t *)line, (size_t)n);
}

void tally_end_set(const char *reason) {
    Serial1.print("E "); Serial1.print(reason); Serial1.print('\n');
}
```

`%+.8f` forces the sign and exactly eight decimals. This relies on the R4's `snprintf`, which
supports `%f`; an AVR board would need the float printf library linked.

**Call site 1 — `setup()`.** The sketch opens `Serial` at 9600 today. The stream needs its own port
at 115200.

```cpp
void setup() {
    Serial.begin(9600);        // keep: your debug console
    Serial1.begin(115200);     // the shield's Linux side reads this one
    tally_begin();
}
```

**Call site 2 — `loop()`.** Replace the `delay(200)` printing loop with a 10 ms scheduler. One sample
every 10,000 us, no blocking delay.

```cpp
static unsigned long next_us = 0;

void loop() {
    unsigned long now = micros();
    if ((long)(now - next_us) < 0) return;
    next_us += 10000;                        // 100 Hz

    float x = accelerometer1.convertX();     // sensor 1 is the streamed limb
    float y = accelerometer1.convertY();
    float z = accelerometer1.convertZ();
    tally_sample(x, y, z);

    // see call site 3
}
```

**Call site 3 — ending the set.** One `E` line per set, no more.

```cpp
    if (digitalRead(BUTTON_PIN) == LOW) {     // button press ends the set
        tally_end_set("done");
        next_us = micros() + 10000;
    }
```

Without a button, use a fixed count: `if (seq == 3000) tally_end_set("done");` ends the set after
30 s. The next set must restart at `seq 0`, so call `tally_begin()` again or reset the counter.

| decision you have to make | why it matters |
| --- | --- |
| one sensor only | The model takes one 3-axis vector per repetition. The sketch reads two accelerometers; stream `accelerometer1` unless the limb mapping says otherwise. Streaming both needs a new wire field and a parser change — do not improvise it. |
| which UART | `Serial1` as written. Confirm against the shield wiring notes; the Linux side opens that UART, which on the Yun is `/dev/ttyATH0`. Check with `ls /dev/tty*` on the Linux side first. |
| calibration | The existing `(raw - 338) * 0.0148` produces g from an ADXL335. Send what that returns; do not rescale the range or remove the 1 g offset. |

## Serial framing

Use **115200 baud, 8 data bits, no parity, 1 stop bit (8N1)**. Lines are ASCII and terminate with LF (`\n`). CRLF (`\r\n`) is also accepted; both terminator bytes count toward the limit. Every complete line, including its terminator, must be at most 64 bytes. Do not send blank lines, prompts, debug text, or a byte-order mark on this stream.

Send the session header once after reset, before the first set. Each set then contains zero or more sample records and exactly one terminal record:

```text
#TALLY1 fs=100 unit=g ax=+x ay=+y az=+z
S <seq> <ax> <ay> <az>
...
E done
```

The header fields and order must match the example; extra whitespace and CRLF are tolerated. Other lines beginning with `#` are comments. The header is session metadata, not a comment to ignore. `<seq>` is a base-10 integer from 0 through 2147483647. Start at 0 for every set, increment by 1 for each sample, and wrap from 2147483647 to 0 only. A gap, duplicate, invalid value, malformed line, overlong line, or unexpected record invalidates the whole set.

`E done` completes a candidate set. `E aborted` and `E overflow` end a discarded set. After either failure terminal, start the next set with sequence zero; retain the session header. Restart the parser after a board reset; do not resend the header between normal sets. A duplicate header inside a parser session invalidates the current set. Never score a partial set. The 60,000-sample cap is per set; exceeding it makes the parser return `aborted` at the end marker; the parser discards remaining samples through that marker. Firmware should terminate sooner with `E overflow` if its own buffer fills. At 100 samples/s, that cap corresponds to 600 seconds (arithmetic estimate, not a supported-duration measurement).

The board must not invent zero-valued samples after a sensor/read failure. Abort the whole set, discard any incomplete sample line, and emit `E aborted`. If the serial link stalls, retain complete raw lines in RAM and send the queued lines once, intact and in order when transmission resumes. There is no acknowledgement or duplicate-resend protocol. If the board cannot retain the backlog, terminate the set with `E overflow`; do not continue with a gap or a partial set.

Example framing (six sample records):

```text
#TALLY1 fs=100 unit=g ax=+x ay=+y az=+z
S 0 +0.01230000 -0.00450000 +1.00120000
S 1 +0.01400000 -0.00380000 +1.00010000
S 2 +0.01620000 -0.00200000 +0.99860000
S 3 +0.01840000 +0.00010000 +0.99630000
S 4 +0.02010000 +0.00260000 +0.99390000
S 5 +0.02100000 +0.00470000 +0.99180000
E done
```

At 8N1, each byte occupies 10 serial bits. A 46-byte sample line at 100 Hz is about 4,600 bytes/s; the nominal serial capacity is 11,520 bytes/s at 115200 baud. These are line-rate arithmetic estimates; actual record lengths vary with sequence digits, signs and values. At the full 64-byte limit, 100 lines/s would be 6,400 bytes/s, still below 11,520 bytes/s. These capacities exclude any competing traffic. For reference, 9600 baud would provide 960 bytes/s at 8N1, below the 4,600-byte/s estimate for 46-byte records at 100 Hz.

## Arrival timing

The model was fitted on 100 Hz data. Sampling drift changes the physical duration of sample-based filters and repetitions; its effect on classification accuracy has not been measured here. The board sends at the fixed 100 Hz target and does not add timestamps. Enforce the 95–105 Hz tolerance on live sample arrival rate only, using host monotonic receive times. The parser measures `(stored samples − 1) / (last arrival time − first arrival time)`. A live set outside that range is invalid. This average does not prove acquisition timing or bound per-sample jitter, and transport buffering can alter it. A saved log has no trustworthy acquisition timestamps: report its timing as `null` / unverified and do not infer, reconstruct, or claim a measured sample rate from line spacing or replay speed. Do not resample either live data or saved logs.

## Segmentation and inference

Use the training implementations in `scripts/reps.py` and `scripts/harness.py` without changing their cuts or feature definitions:

- Repetition peaks use the norm of the three raw acceleration axes, the 201-sample moving-average detrend, and SciPy peak finding with 1.2-second minimum spacing and prominence equal to 0.35 times the 90th percentile of absolute detrended magnitude.
- Cut at sample 0, the integer midpoints between adjacent peak indices, and the final sample. Keep each segment with at least 10 samples. Fewer than 3 retained segments produces `insufficient_reps` and no verdict.
- A repetition row is its duration in seconds followed by the 30 `window_features` values. Feature order is statistic-major (`mean`, `std`, `min`, `max`, `range`, `rms`, `skew`, `kurtosis`, `energy`, `zcr`), with axes `x`, `y`, `z` inside each statistic. The reusable model input is 31 finite float32 values.
- For each retained repetition, get `P(wrong)` from the repetition model; average those probabilities over the set and call the set `wrong` when the mean is at least 0.5. The training labels apply to whole series, not individual repetitions; do not claim per-repetition correctness or error type.

Invalid framing, sequence, sensor, or timing makes the set invalid with a null verdict. `E aborted` and `E overflow` also yield a null verdict. Valid sets with too few retained repetitions use `insufficient_reps`, also with a null verdict. Include diagnostics that identify the failure. Do not turn failures into a `correct` or `wrong` result.

## Output and evidence

Write one JSON object per input set as JSONL to stdout. `--out PATH` writes the same JSONL records to the requested file; diagnostics must also be represented in those records so the file mirrors stdout. Include a clear status, nullable verdict, and timing value (`null` for saved logs). The six-sample example is deliberately too short for a verdict. Running it through `--stdin` produced this JSON:

```json
{
  "status": "insufficient_reps",
  "end": "done",
  "sample_count": 6,
  "vector_count": 0,
  "dropped_count": 0,
  "gap_count": 0,
  "measured_rate_hz": null,
  "mean_p_wrong": null,
  "verdict": null,
  "vectors_sha256": null,
  "repetitions": [],
  "diagnostics": [
    "rate_unverified",
    "fewer_than_2_peaks"
  ]
}
```

For feature inspection, `--npz PATH` writes `rep_X` as `n × 31` float32 and `rep_starts` as cumulative row offsets, one interval per emitted set. Rows are concatenated across sets using temporary files, so vectors do not accumulate in Python memory. Provide enough temporary storage (`TMPDIR`); RAM-backed temporary files still consume RAM. The NPZ is finalized on EOF or an interrupted/read-failed session. A rejected set without extracted vectors contributes an empty interval. Hashes use the concatenated rows as little-endian float32 bytes in row order. Repetition sample intervals are zero-based and half-open: `start_sample` is included and `end_sample` is excluded. Durations use sample count divided by the training rate, not host elapsed time.

`sample_count` counts stored valid samples before rejection or the cap. `gap_count` counts missing sequence positions at the first forward sequence violation; `dropped_count` counts subsequent sample lines discarded after invalidation or the memory cap. Neither count claims to recover missing sensor values. Diagnostics are bounded per set; a rejected set is discarded through its end marker.

The training pipeline's feature extraction produces float64 values from the source CSV before fitting inputs are cast to float32. At eight decimals the wire reproduces the recorded sample values, and the measured parity against original CSV rows is within `1e-6` on every slot (see the table above). That removes wire round-off as a source of drift, but it says nothing about live sampling jitter, online segmentation timing, or board behaviour: do not use the offline model accuracy as evidence for those.

## Run it and check parity

Run from the repository root with the pinned modelling environment and keep `scripts/` and `model/small/form_rep.joblib` available to the bridge:

```sh
.venv/bin/python scripts/tally_stream.py --port /dev/ttyATH0 --fs 100 --out result.json
.venv/bin/python scripts/tally_stream.py --file capture.log --out result.json --npz vectors.npz
.venv/bin/python scripts/tally_stream.py --stdin
.venv/bin/python scripts/tally_stream.py --self-test --series 25
.venv/bin/python -m unittest discover -s bridge -p 'test_*.py' -v
```

`--out` is JSONL even if the filename ends in `.json`. Diagnostics go to stderr and are included in each result. EOF during a set returns `rejected` with `incomplete_set_at_eof`; a read failure during a set returns `aborted`. The input must include complete LF-terminated lines, including the end marker.

The self-test writes [parser-parity.json](runs/stream/parser-parity.json). The actual run above compared 25 deterministic training-eligible PHYTMO series; it is a reproduction check, not a new accuracy evaluation.

| Comparison | Repetitions compared | Maximum absolute feature delta | Median absolute feature delta | Slots above `1e-6` | Series verdict agreement |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original CSV training rows vs eight-decimal wire | 591 paired rows | 2.384185791015625e-07 | 0.0 | 0 | 25/25 (100%) |
| Training extraction on decoded wire vs parser | 592 | 0 | 0 | 0 | 25/25 (100%) |

The original-input `< 1e-6` target was **not met**. Four-decimal rounding changed `A/Larm/A02EFE0_1.csv` from 21 to 22 repetitions. There were 591 original repetitions and 592 wire repetitions overall. Feature deltas cover all 31 slots of the 570 rows in the 24 same-shape series; the different-shape series is reported separately rather than aligned or truncated. Same decoded-input extraction is exactly equal across all 18352 slots. Achieving original-CSV feature parity would require a higher-precision wire contract, which is outside this contract.

File/NPZ integration was also exercised on two real series: 72 float32 rows with offsets `[0, 38, 72]`; both hashes matched the self-test. The default cap was exercised with 60,010 lines: the parser stored 60,000, discarded 10, and returned `aborted` with a null verdict. The example lines measured 40 bytes for the header, 28 for each sample, and 7 for the end marker, including LF. All 14 protocol checks passed. They exercise framing, sequence errors, caps, EOF, output path collision protection and simulated arrival rates; they do not measure board timing.

## Bench acceptance

Before using a physical setup, verify the serial contract with a clean set and a set that includes a deliberate link stall. Confirm:

- baud and 8N1 configuration, exact header, line endings and 64-byte maximum;
- sequence starts at zero, increments once per sample, and wraps only at the specified limit;
- sample acquisition stays at 100 Hz under load: measure jitter and mean rate with a timer or logic analyzer; live arrivals stay within 95–105 Hz;
- a stall preserves every queued line once and in order, or ends the set as overflow;
- sensor/read errors abort the whole set without fabricated zeros or a partial line;
- malformed input, too few repetitions, abort, and overflow all produce a null verdict with useful diagnostics;
- stdout and `--out` contain matching JSONL records, and NPZ rows are finite float32 with 31 columns.

No real board or real serial port was exercised on this machine; no `ttyATH`, `ttyACM`, or `ttyUSB` device was present. Yún deployment, process RAM and sampling-drift accuracy were not measured. The sample cap bounds input storage; it is not proof that the Python/scikit-learn process fits the board. No new physical-board accuracy is claimed.
