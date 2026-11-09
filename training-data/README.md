# Training data

The exact matrices the models were trained on, plus an inventory of every recording. This exists so
the work can be picked up without a 3.4 GB download and without re-deriving features.

## Files

| File | Size | What it is |
| --- | --- | --- |
| `reps_features_acc.npz` | 2.7 MB | one row per repetition, 31 features, grouped into 1,368 series |
| `window_features_300_0.5_acc.npz` | 5.8 MB | one row per 3 s sliding window, 30 features |
| `manifest.csv` | 80 KB | every labelled recording: subject, exercise, label, length, repetitions detected |

The raw CSVs for twelve of those recordings are in [`../data-sample/`](../data-sample/). The full
598 MB set is fetched with `../scripts/fetch_data.sh`; it is deliberately not in git.

## `reps_features_acc.npz`

Keys: `bags` (object array, one `(n_reps, 31)` float32 block per series), `y` (0 correct /
1 wrong), `subject`, `exercise`. Load it with:

```python
import numpy as np
z = np.load("training-data/reps_features_acc.npz", allow_pickle=True)
bags, y, subject, exercise = z["bags"], z["y"], z["subject"], z["exercise"]
```

`allow_pickle` is required only because `bags` is a ragged array of differently sized blocks; it is
plain floats, no objects.

Per repetition, the 31 columns are:

```
duration_s,
then per axis (x, y, z):
  mean, std, min, max, range, rms, skew, kurtosis, energy, zero_crossing_rate
```

The series verdict is the **mean** of the per-repetition probabilities, thresholded at 0.5. Max
pooling was tried and lost (81.1% against 86.5%): these labels describe how the whole set was
performed, not whether one repetition was bad.

## `window_features_300_0.5_acc.npz`

Keys: `X` (29,871 × 30 float32), `y`, `subject`, `exercise`, `source` (the originating filename).
Windows are 300 samples (3 s) at 50% overlap. The 30 columns are the same ten statistics per axis,
without `duration_s`.

## Regenerating either matrix

```bash
./scripts/fetch_data.sh                       # 3.4 GB, extracts the upper-limb part only
uv run --no-project --with numpy --with scipy --with scikit-learn \
  python scripts/train_export.py             # rebuilds both, retrains, re-exports the models
```

`train_export.py` writes to `repo-docs/model/`; the caches it builds are the ones committed here.

## Why not the raw CSVs

598 MB of them. Git keeps every version of every file forever, and GitHub rejects anything over
100 MB, so a clone would get slower for every teammate for data that never changes. The features are
the part that took the work; the raw files are one command away.

If someone genuinely needs the raw set offline, the honest options are Git LFS or a GitHub release
asset, not a commit.

## Provenance

PHYTMO, García-de-Villa, Jiménez-Martín and García-Domínguez, *Scientific Data* 9:266 (2022),
Zenodo doi 10.5281/zenodo.6319979, **CC BY 4.0**. Derived feature matrices here are our own work on
top of that data; if you publish, cite both the dataset and the descriptor paper.

## Persistent local raw data

The modelling continuation saves the complete upper-limb CSV subset at
`data/phytmo/inertial/upper/` in this checkout. `/data/` is ignored by Git: the raw recordings
remain available for future training without adding a large dataset to every clone. These are
the original files, including time and accelerometer columns, so the existing readers work;
the new classifiers use acceleration only. Keep the original channels for provenance.

On a fresh checkout, fetch only the relevant ZIP members, with HTTP-range and per-file CRC checks:

```bash
python3 scripts/fetch_upper_range.py
```

The downloader writes a local completion manifest containing the source, ZIP CRCs and sizes.
It does not retain the large archive. See `docs/MODELLING-REPORT.md` for the exact measured local
inventory, commands, unclipped control and ±3 g experiment. Do not add `/data/` or the archive to Git.
