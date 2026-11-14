> Status: superseded. This report covers the C streaming featuriser, which is kept as an appendix; the shipped path is the Python parser described in docs/PIPELINE.md.

# Streaming repetition features

Built `model/small/form_stream.c` and `.h`: caller-owned C99 state, no heap,
stdio, or mutable globals. At 100 Hz, magnitude is detrended by a trailing
201-sample mean (partial mean during startup). The gate is
`max(0.005 g, 0.35 * peak_ema)`; confirmed local maxima of absolute detrended
magnitude update the EMA with weight 0.1. Rising activity opens a segment;
20 consecutive samples below the gate close it, including that deadband in
the segment. Segments shorter than 120 samples are discarded; 500 samples
force closure. No samples are invented to flush an incomplete recording tail.

`form_stream_init(&state)` starts a user session. Call
`form_stream_push(&state, ax, ay, az)` then
`form_stream_poll(&state, x, &p_wrong)` for every sample. Poll returns 1 with
31 features and `form_rep_predict(x)`, 0 with no completed segment, or -1 on
error. Invalid samples, arithmetic overflow, counter exhaustion, or a second
unread result latch an error until init. The header documents allocation,
sample boundary diagnostics, and retaining user calibration across recordings.

Output order is duration, then mean/std/min/max/range/rms/skew/excess-kurtosis/
energy/zcr, with x/y/z inside each statistic. All accumulators are float32.
The first pass sums deviations from the first sample for a stable mean,
squares for energy, and min/max; the second sums centred powers two through
four and mean-relative sign transitions. Centred moments follow the actual
training formulas and avoid cancellation from subtracting raw gravity-offset
moments. Constant axes produce skew 0, excess kurtosis -3, and zcr 0.

## Measured replay

Command below replayed **all 1,484 CSVs** in **22.530 s**, including 1,368
exercise and 116 calibration files from 30 subjects. Files are sorted by path;
peak calibration persists per subject, while each file resets the filter and
active segment. The offline reference uses the existing `find_peaks`, midpoint
boundaries including recording edges, and `window_features`, cast to float32.
This diagnostic includes calibration and recordings with fewer than three rows,
which training excludes. Matching greedily consumes nearest start pairs within
±50 samples, with deterministic ties; end proximity is not a matching condition.

| Measure | All CSVs |
|---|---:|
| Files replayed | 1,484 |
| Python / C repetitions | 29,367 / 14,020 |
| One-to-one matches | 8,847 |
| Unmatched Python / C | 20,520 / 5,173 |
| Absolute start offset, median / p90 | 21 / 44 samples |
| Absolute end offset, median / p90 | 235 / 365 samples |
| Absolute pooled boundary offset, median / p90 | 40 / 335 samples |
| Matched feature absolute delta, median / max | 0.0340314 / 394.584229 |
| Matched verdict agreement at `>= 0.5` | 89.9627% |
| Matched mean absolute probability delta | 0.0947698 |
| Same-boundary feature absolute delta, median / max | 2.79397e-9 / 0.0150376 |
| Same-boundary feature slots within tolerance | 99.9983894% |
| Forced closures / files with unfinished tails | 7,196 / 1,438 |
| `sizeof(form_stream)`, host and ARM ABI | 6,976 bytes |
| Peak reserved state / state plus output and probability | 6,976 / 7,104 bytes |
| Maximum segment occupancy observed | 500 samples |

Feature tolerance is `abs(delta) <= 0.001 + 0.001 * abs(reference)`; matched
feature deltas pool all 31 slots and include segmentation differences. The
separate same-boundary check recomputes Python features on every exact C segment
using original float64 CSV values. Seven slots exceeded tolerance, all zcr:
float32 sample/mean rounding changes signs at values extremely close to the mean.
For example, `A/Lforearm/A04EFE1_2.csv` samples `[280,413)` has zcr_y
0.0827068 in Python versus 0.0977444 in C. All exceptions are recorded in JSON.

Exercise files alone have 24,632 Python / 11,555 C segments, with 7,641 matches;
calibration files contribute 4,735 / 2,465 segments. These are implementation
comparisons, not per-repetition classification accuracy: labels describe whole
recordings. The supplied joblib estimator is a HistGradientBoostingClassifier,
despite the task's random-forest description; its exported API is unchanged.

## Reproduce

From the repository root, using the existing pinned environment:

```sh
.venv/bin/python scripts/verify_stream_export.py --report docs/runs/stream/verification.json > docs/runs/stream/verification.log
```

The script prints the measured table, compiles with
`gcc -std=c99 -Wall -Wextra -Werror -pedantic -O2 -fPIC -shared`, and runs
seven detector/error checks. Both untouched model exports pass all eight supplied
golden input vectors against joblib: verdict agreement is 100%; maximum
probability differences are 9.43155e-8 for rep and 4.77873e-8 for window.
The full results, exact host compile commands, per-file unmatched sample ranges,
boundary offsets and numerical outliers are in `verification.json`.

ARM object compilation was also exercised with the installed compiler:

```sh
stream_cc=/home/peter/.arduino15/packages/arduino/tools/arm-none-eabi-gcc/7-2017q4/bin/arm-none-eabi-gcc
mkdir -p /tmp/form-stream-target
"$stream_cc" -std=c99 -Wall -Wextra -Werror -pedantic -Os -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -fstack-usage -c model/small/form_stream.c -o /tmp/form-stream-target/form_stream.o
"$stream_cc" -std=c99 -Wall -Wextra -Werror -pedantic -Os -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -fstack-usage -c model/small/form_rep.c -o /tmp/form-stream-target/form_rep.o
"${stream_cc%gcc}size" /tmp/form-stream-target/form_stream.o
printf '#include "form_stream.h"\nconst unsigned char stream_state_bytes[sizeof(form_stream)];\n' > /tmp/form-stream-target/state_size.c
"$stream_cc" -std=c99 -Wall -Wextra -Werror -pedantic -Os -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -fstack-usage -Imodel/small -c /tmp/form-stream-target/state_size.c -o /tmp/form-stream-target/state_size.o
"${stream_cc%gcc}nm" -S /tmp/form-stream-target/state_size.o
```

`target.json` records commands and outputs. Stream object text is 1,576 bytes,
with zero data/bss; this excludes linked math routines. Compiler stack frames
are 72 bytes for feature closure, 40 for push, 16 for poll, and 24 for model
prediction, excluding callees. Peak reserved RAM above includes the entire fixed
state and optional caller result storage, **not measured stack/interrupt or
library high-water**. It is not a whole-firmware RAM measurement.

## Limits

- This causal amplitude gate is not interchangeable with the centred-filter,
  global-p90, positive-peak midpoint training segmenter. Continuous activity often
  lacks a 20-sample quiet interval and merges cycles until the cap. For example,
  `B/Larm/B02EFE0_1.csv` has 46 Python / 15 C segments, 10 matches, and 14
  forced closures. Python `[129,334)` is unmatched; C `[181,681)` is unmatched.
  All unmatched intervals are retained in the JSON. The low overall match rate
  and large end offsets require validation or retraining with causal boundaries
  before treating existing offline model quality as firmware quality.
- Absolute-magnitude excursions can split a cycle or be rejected below the
  minimum length. Startup, recording-edge segments, discarded short events,
  fixed caps, and unflushed tails further differ from Python's complete partition.
  The fixed noise floor and EMA need physical-sensor/user validation; sorted file
  replay is a reproducible protocol, not a chronological user session.
- AVR GCC was unavailable. ARM object compilation passed, but no Arduino board
  link, physical board run, sampling deadline test, or integration with the
  existing sketch was performed. Host ASan/UBSan links were attempted but their
  runtime libraries were missing; ordinary C99/C++11 contract checks passed.
- All ten protected inputs, including the hardware sketch, were checked
  byte-for-byte unchanged. No commit, push, or branch was created.
- The requested external milestone log was read-only in this session (the first
  append failed). Milestones were recorded in `docs/runs/stream/progress.log`.

The full per-file diagnostic dump is regenerated by the same command and is not committed:

    .venv/bin/python scripts/verify_stream_export.py --report docs/runs/stream/verification.json
