# Tiny GRU C inference probe

This is a standalone research probe built around the first saved leave-one-subject-out fold (`L-A01`). It does not change the accepted model or firmware. The generated [weight header](c-probe-weights.h) comes from the matching [NPZ checkpoint](example-fold-L-A01.npz); the full tool and section report are in [rnn_c_probe.py](/home/peter/work/198-Project/scripts/rnn_c_probe.py) and [c-probe.json](c-probe.json).

## Inference path

`tiny_gru_predict` accepts already grouped 25 Hz six-axis samples and actual duration in seconds. It applies the fold's six input means/scales, evaluates a single PyTorch-compatible GRU layer (reset/update/new gate order), concatenates the standardized duration to the final hidden state, then returns quality sigmoid and EAH/EFE/SQZ softmax probabilities. Each call starts with zero hidden state and rejects empty or nonfinite sequences.

The integrated probe uses the accepted `PairStream` C detector without editing it. It retains each detected raw cycle, averages causal groups of four including the final partial group, supplies detector duration `features[0]`, runs the GRU per cycle, and averages probabilities across cycles. It abstains below three detected cycles, matching this experiment's retained-series threshold.

## Parity check

Run with the pinned CPU Torch environment:

```sh
/tmp/tally-rnn-env/bin/python scripts/test_rnn_c_probe.py --weights docs/runs/phase6-rnn/example-fold-L-A01.npz
```

The test compares C with an independent NumPy recurrence and `torch.nn.GRU` at lengths 1, 2, 7, and 31. It also feeds a deterministic 100 Hz raw fixture through the accepted detector, compares detected cycles and grouped samples with `rnn_data._Capture` and `_downsample`, and checks the eight-cycle mean-probability result against PyTorch. Reset behavior, short-series abstention, nonfinite-input abstention, and normalized probability sums pass.

The same host probe was run across every retained A01 left-arm source:

```sh
/tmp/tally-rnn-env/bin/python scripts/test_rnn_c_probe.py \
  --weights docs/runs/phase6-rnn/example-fold-L-A01.npz \
  --fold-json docs/runs/phase6-rnn/fold-L-A01.json \
  --data-root data/phytmo/inertial/upper \
  --report docs/runs/phase6-rnn/c-probe.json
```

All 11 held-out sources produced matching cycle counts. Against the saved PyTorch fold probabilities, maximum absolute error was `5.96e-8` for quality and `1.20e-7` for exercise probabilities. Source-level counts and errors are listed in the JSON report.

## Cortex-M4F object and memory scope

The report compiles three separate, unlinked Cortex-M4F (`clang --target=arm-none-eabi -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -Oz`) objects: GRU kernel, accepted detector, and integrated wrapper with embedded weights.

- Code sections sum to 2,496 bytes across those objects.
- The weight arrays plus the 40-byte model descriptor occupy 1,784 bytes of `.rodata`. The float32 parameters including duration normalization are 1,752 bytes.
- LLVM reports 18,296 bytes of static `.bss`: 14,452-byte `PairStream`, 3,600-byte `[150][6]` grouped-cycle buffer, and 244-byte detector feature array.
- Clang `.su` reports a largest individual frame of 384 bytes for `tiny_gru_predict`. The known wrapper → GRU → sigmoid call path sums to 504 bytes of frames. This excludes unresolved math/compiler helper frames.
- Unresolved symbols are `expf`, `fmaxf`, `fminf`, `sqrtf`, `tanhf`, `__aeabi_memclr4`, and cross-object detector/GRU functions. The objects are not linked into a board image.

These are compiler object and state measurements for this isolated probe. They do not establish board-level latency, integrated firmware size, runtime stack high-water, or hardware feasibility. No hardware timing was measured.
