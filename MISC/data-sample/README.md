# Data sample

Twelve recordings from the PHYTMO database, enough to run the scripts end to end and to see the file
format. This is **not** the dataset — it is a 6.5 MB sample of a 3.4 GB archive.

## What is here

```
A/A01EAH0_1.csv  A01EAH1_1.csv   subject A01, arms-over-head, correct then wrong
A/A01EFE0_1.csv  A01EFE1_1.csv   subject A01, elbow flex,     correct then wrong
A/A01SQZ0_1.csv  A01SQZ1_1.csv   subject A01, squeeze,        correct then wrong
B/B01EAH0_1.csv  B01EAH1_1.csv   the same six for subject B01
```

Each file is one recorded series of an upper-limb exercise, from the `Larm` sensor, sampled at
100 Hz. Columns, in order:

```
Time (s), Gyroscope X/Y/Z (deg/s), Accelerometer X/Y/Z (g), Magnetometer X/Y/Z (uT)
```

The filename encodes the label. `GNNEEELP_S`:

| Part | Meaning |
| --- | --- |
| `G` | age band, A–E (A = 20s … E = 60s) |
| `NN` | volunteer number |
| `EEE` | exercise: EAH arms over head, EFE elbow flex, SQZ squeeze |
| `L` | leg, only for the leg exercises (KFE, HAA) |
| `P` | **0 = performed correctly, 1 = performed wrongly** |
| `S` | series index, 1 or 2 |

## Why the full dataset is not in this repository

3.4 GB compressed, 598 MB even for the upper-limb part alone. Git stores every version of every
binary forever, and GitHub rejects files over 100 MB. Cloning the repo would get slower for every
teammate, for data that never changes.

Fetch it instead — it takes one command and about twenty minutes on a home connection:

```bash
./scripts/fetch_data.sh
```

## Licence and attribution

PHYTMO, García-de-Villa, Jiménez-Martín and García-Domínguez, *Scientific Data* 9:266 (2022).
Zenodo doi **10.5281/zenodo.6319979**. Licensed **CC BY 4.0** — free to use and redistribute with
attribution, including commercially, provided the authors are credited and changes noted.

If you publish anything using this data, cite the descriptor paper:
doi:10.1038/s41597-022-01387-2. A copy of the method paper is in `../papers/`.

## What the labels cannot tell you

The label is per series, for a whole set of at least eight repetitions. There is **no
per-repetition label and no description of what was wrong** with a "1" recording. Anything about
"which rep was bad" or "they raised their arm too low" is not in this data.
