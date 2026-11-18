# Basic feedback implementation plan

Starting inspection: `codex/tiny-rnn-benchmark`, HEAD
`fbb41816887bbc3a4af4a2608d6f5487b2c18491`; only untracked `output/` and `tmp/`.
Work continues on `codex/basic-feedback`. No accepted export, raw recording or historical
result will change. No simulator or model training is part of this work.

1. Reuse the paired causal runtime and duration gate. Add a fixed-size application with
   configuration, start/pause/resume/finish, cycle count, active elapsed time and pooled result.
2. Add a two-consecutive-duration persistence rule and a five-second cue cooldown. Invalid
   evidence clears pending/visible cues. Exercise confidence never enters timing logic.
3. Feed the same timestamped six-g-channel interface from strict host CSV replay and an
   Arduino Serial scaffold. Physical ADC calibration/acquisition stays an explicit hook.
4. Check synthetic cue cases, lifecycle/fault handling, direct-runtime parity on measured
   replay, existing strict classifier verification, and available Cortex-M4 object compilation.
   Commit implementation and verification/handoff separately, locally only.

## Incremental budget before implementation

Reuse the existing ~14.5 kB runtime, including its 600 × 6 float sample buffer. Add **no
sample buffers**, heap allocations or classifier copies. Budget at most **512 B persistent
application/configuration/output/policy state beyond PairRuntime**, with borrowed immutable
prescription strings; temporary scalar/feature frames stay inside the existing 4096 B stack
reserve. Target text growth is provisionally <=8 kB; measure rather than infer it from the
581 B scalar feedback function. Host CSV parsing is excluded from firmware. The small Serial
line parser must be included in the scaffold object/state measurement.

The earlier 24,832 B RAM scenario is arithmetic object accounting plus explicit reserves,
not linked firmware RAM. Report new full-path BSS and all reserve assumptions. Four ADXL335s
still need twelve channels versus six exposed analog inputs; two existing float pair buffers
exceed the earlier RAM budget. This first one-pair milestone does not resolve either issue.

## Evidence limit

Detected cycles are peak-confirmation intervals, not independently validated repetitions.
The application never promotes them to validated evidence. Synthetic known-duration inputs
exercise the cue policy separately; neither study series labels nor detected peaks can turn
on real timing cues. Targets must be explicitly supplied; examples are test values only.
