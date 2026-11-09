# Experimental tiny GRU inference

This is a host-tested and Cortex-M4F object-compiled research kernel, not an accepted replacement
model or integrated Arduino firmware. The benchmark is documented in `docs/TINY-RNN-REPORT.md`.
No error-type, repetition-correctness, hardware latency or clinical accuracy is established.

`tiny_gru.c/.h` implements PyTorch GRU gate order r,z,n, per-cycle reset, train-fold normalization,
actual duration as the ninth head input, binary wrong probability and three exercise probabilities.
The probe generator adds the unchanged C detector, causal group-of-four downsampling and whole-series
mean pooling for implementation parity/footprint checks. It uses a 3,600-byte static downsample buffer
rather than redesigning the accepted stream. The model-local kernel does not require the entire
sequence to be retained conceptually; this is the explicit measured research implementation.

Example weights in `docs/runs/phase6-rnn/example-fold-L-A01.npz` and `c-probe-weights.h` exclude A01
from training and are only parity/footprint fixtures. They are not a full-cohort production export.
Accepted paired logistic models remain unchanged under `model/paired-synchronized-causal/`.
