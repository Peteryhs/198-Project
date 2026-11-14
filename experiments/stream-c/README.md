# Abandoned: the C streaming featuriser

This is the first attempt at feeding the repetition model from firmware: a C module that
detected repetitions on the board and built the 31 values itself.

It is not used. Its causal detector matched only 8,847 of 29,367 repetitions from the recorded
series, and one non-finite sensor sample latched a permanent error that stopped all further
scoring. The shipped path is `scripts/tally_paired_stream.py` on the Linux side of the Yun,
described in `docs/BOARD-TO-PARSER.html`.

Each file here is kept only as evidence:

- `form_stream.c`, `form_stream.h` — the detector and feature builder.
- `verify_stream_export.py` — the replay harness that produced the numbers in `docs/REPORT.md`.
  It imports `scripts/train_small.py` and defaults to `model/small`, both removed in the 2026-11
  cleanup; recover them from git history at `f7fb8ac` before running it.
- `docs/` — its report, the boundary-sensitivity measurement, and the parity files.

Nothing here is maintained.
