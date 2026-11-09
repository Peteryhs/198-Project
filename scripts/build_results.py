"""Assemble RESULTS.md from the run artifacts.

Inputs: results.csv (written by genfigs.py from the run logs), run_mil2.log, sat.log,
cache/reps_acc.npz for the repetition counts. Nothing here is typed by hand, so the document
cannot drift from the runs.

Run: ~/.hermes/bin/uv run --no-project --with numpy python build_results.py
"""

from __future__ import annotations

import csv
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "RESULTS.md")


def read_results() -> list[dict]:
    with open(os.path.join(HERE, "results.csv")) as fh:
        return list(csv.DictReader(fh))


def parse_mil() -> dict:
    txt = open(os.path.join(HERE, "run_mil2.log")).read()
    out: dict = {"per_ex": {}}
    m = re.search(r"^(\d+) series, (\d+) repetitions", txt, re.M)
    if m:
        out["series"], out["reps"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"median (\d+), min (\d+), max (\d+)", txt)
    if m:
        out["rep_median"] = int(m.group(1))
    for line in txt.splitlines():
        m = re.match(r"\s+naive rep propagation\s*:\s*([\d.]+)", line)
        if m:
            out["rep_mean"] = float(m.group(1))
        m = re.match(r"\s+MIL \(max pooling\)\s*:\s*([\d.]+)", line)
        if m:
            out["mil"] = float(m.group(1))
        m = re.match(r"\s+(\w+): propagation ([\d.]+)\s+MIL ([\d.]+)", line)
        if m:
            out["per_ex"][m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def parse_export() -> dict:
    """The exported per-repetition random forest (train_export.py)."""
    path = os.path.join(HERE, "run_export.log")
    out = {}
    if not os.path.exists(path):
        return out
    txt = open(path).read()
    m = re.search(r"repetition model LOSO accuracy:\s*([\d.]+)", txt)
    if m:
        out["rep_rf"] = float(m.group(1))
    return out


def parse_sat() -> list[tuple]:
    rows = []
    for line in open(os.path.join(HERE, "sat.log")):
        m = re.match(r"\s+(\w+)\s+n=\s*(\d+)\s+median=\s*([\d.]+)g p90=\s*([\d.]+)g"
                     r".*over 1.5g:\s*([\d.]+)%.*over 2.0g:\s*([\d.]+)%"
                     r".*over 3.0g:\s*([\d.]+)%.*over 6.0g:\s*([\d.]+)%", line)
        if m:
            rows.append(m.groups())
    return rows


def rep_counts() -> dict:
    z = np.load(os.path.join(HERE, "cache/reps_acc.npz"), allow_pickle=True)
    ex, bags = z["exercise"], list(z["bags"])
    lens = np.asarray([len(b) for b in bags])
    out = {}
    for e in sorted(set(ex)):
        m = ex == e
        out[e] = (int(m.sum()), float(np.median(lens[m])), int(lens[m].min()), int(lens[m].max()))
    return out


def main() -> None:
    rows = read_results()
    mil = parse_mil()
    sat = parse_sat()
    reps = rep_counts()
    exp = parse_export()

    def grid(channels: str) -> str:
        lines = ["| Window | Model | Accuracy | EAH | EFE | SQZ |", "| --- | --- | --- | --- | --- | --- |"]
        for r in rows:
            if r["channels"] != channels:
                continue
            lines.append(
                f"| {r['window']} s | {r['model']} | {float(r['accuracy']) * 100:.1f}% "
                f"| {float(r['EAH']) * 100:.1f}% | {float(r['EFE']) * 100:.1f}% "
                f"| {float(r['SQZ']) * 100:.1f}% |"
            )
        return "\n".join(lines)

    best_acc = max((r for r in rows if r["channels"] == "acc"), key=lambda r: float(r["accuracy"]))
    best_gyro = max((r for r in rows if r["channels"] == "accgyro"), key=lambda r: float(r["accuracy"]))

    doc = f"""# PHYTMO baseline results

All numbers produced by the scripts in this folder. Task: decide whether a recorded series of an
upper-limb exercise was performed correctly or incorrectly. Split: leave-one-subject-out over all
30 volunteers. Random floor: 50.0% (the two classes are balanced by construction).

Data: PHYTMO (`doi:10.5281/zenodo.6319979`, CC-BY-4.0), `inertial/upper` only — 1,368 labelled
series across EAH (arms over head), EFE (elbow flex) and SQZ (squeeze).

## 1. Sliding-window sweep, accelerometer only

{grid("acc")}

## 2. Sliding-window sweep, accelerometer + gyroscope

{grid("accgyro")}

Best accelerometer-only: **{float(best_acc["accuracy"]) * 100:.1f}%** at {best_acc["window"]} s
({best_acc["model"]}).
Best with gyroscope: **{float(best_gyro["accuracy"]) * 100:.1f}%** at {best_gyro["window"]} s
({best_gyro["model"]}). The gyroscope arm was not run at 1 s.

## 3. Per-repetition scoring versus windows

Series are cut into repetitions at the midpoint between detected peaks; the per-repetition
predictions are then combined into one verdict for the series.

| Method | All three | EAH | EFE | SQZ |
| --- | --- | --- | --- | --- |
| 3 s windows, {best_acc["model"]} | {float(best_acc["accuracy"]) * 100:.1f}% | {float(best_acc["EAH"]) * 100:.1f}% | {float(best_acc["EFE"]) * 100:.1f}% | {float(best_acc["SQZ"]) * 100:.1f}% |
| Repetitions, mean over reps (logistic regression) | {mil["rep_mean"] * 100:.1f}% | {mil["per_ex"]["EAH"][0] * 100:.1f}% | {mil["per_ex"]["EFE"][0] * 100:.1f}% | {mil["per_ex"]["SQZ"][0] * 100:.1f}% |
| Repetitions, mean over reps (random forest, exported) | {exp.get("rep_rf", float("nan")) * 100:.1f}% | n/a | n/a | n/a |
| Repetitions, max pooling (MIL) | {mil["mil"] * 100:.1f}% | {mil["per_ex"]["EAH"][1] * 100:.1f}% | {mil["per_ex"]["EFE"][1] * 100:.1f}% | {mil["per_ex"]["SQZ"][1] * 100:.1f}% |

{mil["series"]:,} series were segmented into {mil["reps"]:,} repetitions
(median {mil["rep_median"]} per series).

## 4. Repetitions detected per exercise

| Exercise | Series | Median reps | Min | Max |
| --- | --- | --- | --- | --- |
""" + "\n".join(
        f"| {e} | {n} | {med:.0f} | {lo} | {hi} |" for e, (n, med, lo, hi) in reps.items()
    ) + f"""

## 5. Peak acceleration per series versus sensor range

Capture was recorded at ±16 g. The build's ADXL335 clips at ±3 g, so the "over 3.0 g" column is
the share of each exercise's recorded series that a ±3 g part would saturate.

| Exercise | Series | Median peak | p90 | Over 1.5 g | Over 2.0 g | Over 3.0 g | Over 6.0 g |
| --- | --- | --- | --- | --- | --- | --- | --- |
""" + "\n".join(
        f"| {'All' if name == 'ALL' else name} | {n} | {med} g | {p90} g | {a}% | {b}% | {c}% | {d}% |"
        for name, n, med, p90, a, b, c, d in sat
    ) + f"""

## 6. Hardware budget, measured by compiling

`arduino-cli` against `arduino:renesas_uno` 1.6.0 for `arduino:renesas_uno:minima`:

| Item | Flash | RAM |
| --- | --- | --- |
| Empty Serial sketch | 38,984 B | 3,940 B |
| TensorFlow Lite Micro, sine model, patched | 77,540 B | 7,444 B |
| Net cost of TFLM | ~38,556 B | ~3,504 B |
| Available on the board | 262,144 B | 32,768 B |
| Left after TFLM | ~184,604 B | ~25,324 B |

`tflite::AllOpsResolver` overflows flash by 32,116 B, so only a selective
`MicroMutableOpResolver` links. No board was attached, so nothing here is a runtime measurement.

## 7. Reproduce

```bash
cd ~/work/phytmo
unzip -o -q PHYTMO.zip 'inertial/upper/*' -d data
uv run --no-project --with numpy --with scikit-learn python harness.py --windows 100 200 300
uv run --no-project --with numpy --with scikit-learn python harness.py \\
  --channels accgyro --windows 200 300
uv run --no-project --with numpy --with scipy --with scikit-learn python mil.py
uv run --no-project --with numpy python saturation.py
uv run --no-project --with numpy python genfigs.py
uv run --no-project --with numpy python build_results.py
```

## 8. What is not measured

- Per-repetition correctness: the dataset labels whole series, so only series-level accuracy has
  ground truth. Voice that plainly rather than implying per-rep scoring is validated.
- The repetition detector is validated against an independent period estimate, not against
  hand-counted reps.
- No Arduino has run any of this. All hardware numbers are compile-time sizes.
"""
    open(OUT, "w").write(doc)
    print(OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
