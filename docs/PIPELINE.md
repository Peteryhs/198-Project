# How a set gets scored

One page for the whole system. The firmware detail lives in `docs/BOARD-TO-PARSER.html`.

## The goal

Two accelerometers sit on one limb, upper arm and forearm. A student performs a set of repetitions;
the system answers one question about the set: **was its form correct or wrong?** The angle between
the two segments is what makes a shallow repetition distinguishable from a full one, so both sensors
are part of the answer, not a spare.

The model is `model/paired-synchronized-offline/{L,R}`: 61 inputs, 992 parameter bytes, 91.03 % quality
accuracy on the left-side pair (301 series, 30 held-out subjects, 5,190 cycles), 88.89 % on the right.
A causal-boundary twin in `model/paired-synchronized-causal` scores 92.36 % and 89.87 %, but only with
cycles from the causal detector, which the Python script does not use.

## The path a set takes

```
  upper arm + forearm accelerometers, same side
          │  100 Hz, calibrated g, ±3 g, one clock
          ▼
  Arduino sketch (hardware/198project)
          │  #TALLY2 fs=100 unit=g range=3 side=L          once after reset
          │  S <seq> <t_ms> <ux> <uy> <uz> <fx> <fy> <fz>   one per sample, 8 decimals
          │  E done                                        once, when the set ends
          ▼
  serial, 115200 8N1, ≤128 bytes per line, ~89 bytes per sample ≈ 8.9 kB/s
          ▼
  Python on the Yún:  python3 scripts/tally_paired_stream.py
          │  aligns the two streams on t_ms, interpolating to a common grid
          │  finds one cycle boundary per repetition, shared by both sensors
          │  builds 61 values: duration, upper statistics, forearm statistics
          ▼
  61 × float32 per repetition  →  paired model for that side  →  P(wrong) per repetition
          │  mean over the set, threshold at 0.5
          ▼
  JSON: {"verdict": ..., "exercise": ..., "mean_p_wrong": ..., "repetitions": [...]}
          │  and one short line per set, for the board:
          │  V <verdict> <mean_p_wrong> <exercise>   → written to verdicts.log and back to the port
```

## Division of labour

| Firmware | Linux side |
| --- | --- |
| read both sensors in the same 10 ms tick | receive and validate the line stream |
| one timestamp per sample, from `micros()` | align the pair, interpolate |
| print `S` lines, 8 decimals, sequence +1 | cut cycles once for both sensors |
| print `E done` / `E aborted` / `E overflow` | build the 61 values, run the model for that side |
| never compute features, never score | pool probabilities, answer correct/wrong + exercise |

## Why one sensor is not enough

`docs/NEXT-ROUND-BRIEF.md:31` names this as the first defect in the earlier work: every model in
`model/small` consumed a single mount's 31 features, so a shallow repetition and a full one could look
alike. The paired exports fix that. The single-mount path (`model/small`, 89.33 %) is kept only as
history; `model/PAIRED.md` also marks the first `paired-offline` / `paired-causal` exports invalid
because they aligned device uptime clocks instead of synchronized recording starts.

## Measured, not assumed

| Fact | Number | Where |
| --- | --- | --- |
| Paired model, left side | **91.03 %** quality, 301 series, 5,190 cycles | `model/paired-synchronized-offline/L/results.json` |
| Paired model, right side | 88.89 %, 306 series, 5,265 cycles | `.../R/results.json` |
| Causal-boundary twin, not used by the script | 92.36 % left, 89.87 % right | `model/paired-synchronized-causal/*/results.json` |
| Exercise recognition | 98.01 % left, 97.06 % right | same |
| Model size | 61 inputs, 992 parameter bytes | `realtime_model.h` |
| Labels | series-level, per-cycle pseudo-labels | `docs/ROUND2-REPORT.md` |
| Shield RAM | 64 MB on the Linux processor | Yún shield manual |

## Run it

```
python3 scripts/tally_paired_stream.py                 # finds the port, reads the side from the header
python3 scripts/tally_paired_stream.py --file capture.log
python3 scripts/tally_paired_stream.py --self-test
```

## Still open

- No set has been sent from a real board: the sketch, the port, the 100 Hz pairing and the timestamp
  accuracy are untested on hardware.
- Cycle labels are pseudo-labels from series labels, so per-repetition correctness is not claimed.
- Sending the verdict back to the board does not exist.
