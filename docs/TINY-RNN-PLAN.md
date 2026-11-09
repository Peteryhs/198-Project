# Tiny RNN: declared experiment and resource budget

Base `61ede24`; branch `codex/tiny-rnn-benchmark`. The user authorized trying an RNN on the existing
real data, hoping for specific error explanations. That expectation was corrected before work:
PHYTMO supports exercise identity and whole-recording quality, not verified repetition correctness,
error categories or effort. A recurrent network cannot supply missing ground truth.

Keep the simulator parked. Do not alter raw data, accepted models, firmware or old output/tmp.
No push/PR/repository messages. This is one bounded recurrent baseline comparison, not a hyperparameter
search or a replacement deployment decision.

## Fixed model and data path

- One forward GRU with six inputs and eight hidden units, PyTorch CPU 2.9.1. No future-sample layer.
- Actual C causal detector determines the same cycle intervals and 61-feature comparison bags as
  the valid accepted paired causal models. Check all source IDs, cycle counts and feature values.
- Sequence inputs are the same +/-3 g clipped acceleration, causally averaged in groups of four
  at 100 Hz to give 25 Hz, including the final partial group. Do not resize cycles to equal time,
  invent movement changes or pass gyro/magnetometer to the classifier. Duration is retained exactly.
- Last valid GRU hidden state (8) plus standardized measured cycle duration (1) feed four affine
  logits: binary quality and three exercise identities. Sigmoid/softmax cycle probabilities are
  averaged for whole-series decisions, matching the current pooling contract.
- Each cycle inherits the source's series label only for weak supervision. Each source contributes
  equal total weight. Train-only channel and duration normalization. All augmentation relatives
  remain within person; this experiment uses no augmentation and no virtual signals.
- Thirty LOSO folds on each side; expected retained cohort301/342 L,306/342 R, all30 volunteers.
  Reproduce accepted baseline decisions rather than comparing a different cohort.
- Adam, lr.003, weight decay1e-4, 30 fixed epochs, batch128 cycles, gradient norm cap1, one fixed
  initialization seed per side/fold. No early stopping or setting choices from outer-test results.
  Up to four independent CPU workers, one numerical thread each. A label-free timing probe may
  assess compute budget; it may not choose settings from held-out performance.

The GRU sees a different representation/bandwidth from the 100 Hz summary baseline. This compares
complete candidate pipelines on identical sources/cycles, not a controlled isolation of recurrence
alone. The short causal moving-average/downsample is an engineering approximation, not a measured
ADXL335 antialias response. Variable lengths remain masked; final states must ignore padding.

## Resource estimate before training

GRU parameters: 3*(6*8+8*8+2*8)=384; head:4*(8+1)+4=40; total424 floats=1,696 B, plus14 floats=56 B
for stored six-channel/duration means and scales (1,752 B total with normalization). Existing linear
coefficients are992 B. Recurrent arithmetic336 MAC per25 Hz frame (8,400/s), plus36 head MAC per
cycle, gating/interpolation/pooling/detection and 16 sigmoid +8 tanh evaluations per frame. These
counts are not latency/energy measurements. Hidden state32 B; simple gate scratch up to96 B;
actual C stack/object sizes will be measured. Keep the existing14,488 B stream state for comparable
intervals; do not claim saved raw-buffer RAM unless a separate detector/inference redesign proves it.
[Primary sources and fuller budget](RNN-RESEARCH-AND-BUDGET.md).

## Evaluation and verification

Report quality/exercise whole-series agreement, majority floors, 301/342 and306/342 retention,
rejected sources, all per-source predictions and source/fold lineage. Compute paired differences
versus accepted baseline with volunteer-block bootstrap intervals. Include per-exercise breakdown,
training-loss traces and evidence of inadequate convergence if present. Single-seed results do not
establish a best RNN or general benefit. No future architecture choice turns outer scores into an
unbiased selection result.

Tests cover exact C cycle/raw-sample parity, downsample/timing edges, known synthetic temporal order,
padding immunity, train/held-out exclusion, train-only normalization and loss weighting, deterministic
seeds, and plain-C versus Torch probability agreement. Independent saved-decision audit and existing
export checks protect reports/accepted models. Crosscompile the small C inference for Cortex-M4F;
account for normalization, downsampling, detector, features/buffers, pooling and outputs as relevant.
Distinguish kernel objects/arithmetic from linked firmware and physical timing.

Deliver executable scripts/config, isolated training requirements, source manifests, complete LOSO
results/logs, example-fold weights and C parity/footprint, a plain-language report and local commits.
No accepted model is automatically replaced. Specific corrective feedback remains unsupported.
