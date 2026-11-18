# Codex task: a form-classifier that actually fits the board

Status: open. Owner: Codex, reviewed by Peter.

## The problem

`model/form-*.joblib` are two `RandomForestClassifier`s with 80 trees, `max_depth=14`,
`min_samples_leaf=8`. They were chosen for leave-one-subject-out accuracy and nobody checked
whether they fit the target board. They do not.

Measured this session, straight off the pickled trees:

| artefact | trees | nodes | joblib | plain C arrays (22 B/node) | 8-bit quantised (10 B/node) |
| --- | --- | --- | --- | --- | --- |
| `form-rep-rf` | 80 | 107,528 | 2,523 KB | 2,310 KB | 1,050 KB |
| `form-window-rf` | 80 | 114,860 | 2,699 KB | 2,467 KB | 1,121 KB |

Re-emitting these trees as C does not help: a node is a threshold, a feature index, two child
indices and a class probability either way, so an `emlearn` export lands within ~10% of the
`joblib` size. **The fit itself has to be smaller**, not the file format.

## Hard budget (measured, not estimated)

From `docs/CONTEXT-AND-CONSTRAINTS.md:44-48`, UNO R4 Minima (Renesas RA4M1, 48 MHz Cortex-M4F):

- 256 kB flash, 32 kB RAM in total
- empty Serial sketch: 38,984 B flash / 3,940 B RAM
- TensorFlow Lite Micro for a sine model (patched board gate): 77,540 B flash / 7,444 B RAM
- **~180 kB flash and ~25 kB RAM are free** for everything else

Your model, its feature extraction, `tally_app`, `feedback` and `Serial` all come out of that
180 kB. Treat **120 kB of flash as the model ceiling** (including the C inference code) unless you
prove with a real `arduino-cli compile` that more is safely available. At 22 B/node that is under
~5,000 nodes total; at 10 B/node, under ~10,000. Today's models are 107,528 and 114,860 nodes.

RAM: the 32 kB SRAM also has to hold the 3 s window ring buffer. State your RAM arithmetic.

## Accuracy that must be retained

LOSO over all 30 volunteers, chance floor 50.0%. Every number below is already measured; reproduce
the ones you touch, do not re-quote from memory (`docs/RESULTS.md`, `scripts/why_rf.json`):

| model | LOSO accuracy | note |
| --- | --- | --- |
| rep RF, mean-pooled (shipped, 2.6 MB) | **88.3%** | the capability to match |
| rep logistic regression | 86.5% | 31 weights; the trivial fallback |
| window RF, 3 s (shipped, 2.8 MB) | **80.9%** | windowed capability to match |
| window HGB, 3 s | 80.7% | |
| rep MIL, max pooling | 81.1% | |

`scripts/why_rf.json` records that the forest beats logistic regression by 1.8 points and that the
disagreement is tree-favouring: forest-only-correct 83 series, logreg-only-correct 58,
McNemar p = 0.043. So the gap is small, marginally significant, and sits on 1,368 series — treat
"the trees are worth it" as a claim you have to test at the small size, not an assumption.

**Acceptance:** rep model LOSO ≥ 87.3% (within 1.0 point of 88.3%), window model ≥ 79.9%.
Hard floor for either: 86.5% / 80.9% respectively — do not ship something worse than the simple
baseline that already exists. Report the exact loss, per-exercise EAH/EFE/SQZ splits included, and
say plainly if the target is unreachable.

## What exists

- `scripts/harness.py` — CSV readers, sliding windows, the 30 summary features, `--root`
- `scripts/reps.py` — `find_peaks` segmentation, `FS = 100`
- `scripts/train_export.py` — the current fit. Note `ROOT` points at `scripts/data/inertial/upper`,
  which does not exist; the data is at `data/phytmo/inertial/upper` (1,484 CSVs, 1,368 labelled,
  598 MB, already downloaded)
- env: `.venv` with sklearn 1.7.2, numpy 2.3.4, scipy 1.16.3 (`scripts/requirements-modelling.txt`)
- board firmware: `hardware/198project/198project.ino`, app layer `model/application/tally_app.c`,
  which consumes `mean_quality_probability` — the series verdict is the mean of per-repetition
  probabilities, and that contract must not change silently
- input contract: 100 Hz, 3 axes in g; 31 features for the rep model (`duration_s` + 10 stats × 3
  axes), 30 for the window model. Feature order is in `model/metadata.json`

The dataset labels whole series correct/incorrect only. No per-repetition or error-type label
exists, so do not build a model that claims to say which rep was bad.

## Deliverables

1. `scripts/train_small.py` (or `train_export.py --model-budget-bytes`) that fits, evaluates LOSO,
   and **asserts the node/byte budget before writing anything**. A build that overflows must fail
   loudly, not print a size and pass.
2. Exported C: `model/small/form_rep.c/.h` and `model/small/form_window.c/.h`, plain C99, no
   allocation, no libm if you can avoid it. `emlearn` is the expected route; a hand-written tree
   walker over a packed array is acceptable if you measure it smaller.
3. `scripts/verify_small_export.py`: runs the exported C inference against sklearn on N real rows
   from the dataset and reports max absolute probability deviation (target ≤ 1e-3; integer-quantised
   variants report their quantisation step) plus the predicted-label agreement rate. A pytest next
   to it with a handful of golden rows, in the style of the existing `scripts/test_*.py`.
4. Size report: node counts, bytes of `.text`/`.rodata` per model, and a real
   `arduino-cli compile --fqbn arduino:renesas_uno:minima` flash/RAM figure if the core installs on
   the machine. If it does not, say "object sizes, not linked flash" in the same words the repo
   already uses at `docs/BASIC-FEEDBACK.md:164` — do not dress an estimate up as a measurement.
5. Updated `model/metadata.json` (new hyperparameters, node/byte budget, new LOSO numbers, feature
   contract) and a short `model/README.md` section replacing "Getting this onto the board —
   Not done."

## What I want in your write-up

- The candidate you shipped, and the ones you rejected, each with the LOSO number that killed it.
  Candidates worth pricing before you commit: smaller/deeper-limited forest, a single shallow tree
  ensemble per exercise, quantised thresholds, feature reduction (which of the 31 features earn
  their slot — `why_rf.json` has the importances), logistic regression or a tiny MLP, a tiny GRU
  (`model/rnn-experiment/tiny_gru.c` already exists). You are not required to like any of these.
- Whether the small tree ensemble still earns its 1.8-point edge over logistic regression at the
  same node budget — measured, not argued.
- One self-critique: the most likely way your result is wrong.
- Confidence per claim: measured with a command I can re-run, or estimated.
- Any point where the 1.0-point tolerance is doing work you would rather Peter decided.

## Rules

- Every number you report must come from a command in this repo. No remembered values, no accuracy
  quoted from `docs/` without re-running it.
- LOSO stays leave-one-subject-out over all 30 volunteers, refit on all 30 for the shipped artefact.
  Splitting by file leaks the same person into train and test.
- Do not modify or delete the existing 2.5 MB `model/form-*.joblib` artefacts, and do not restate
  their numbers; the small-model route is additive until Peter says otherwise.
- `docs/CONTEXT-AND-CONSTRAINTS.md` measured the budget by compiling. Match that standard or label
  the difference.
