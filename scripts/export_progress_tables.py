"""Build the plottable progress tables for the 198 form-model work.

Inputs (all measured, committed under docs/runs/small-model/):
  fit.json, baselines.json, predictions.npz, baselines.npz,
  forest-candidates.json, boost-candidates.json, target.json
Outputs: CSVs under docs/runs/small-model/figures/

Run from the repository root:
  .venv/bin/python scripts/export_progress_tables.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

RUNS = Path("docs/runs/small-model")
OUT = RUNS / "figures"


def lab(a):
    a = np.asarray(a, dtype=float)
    return (a >= 0.5).astype(int)


def write(name, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"{path}  {len(rows)} rows")


def main():
    fit = json.loads((RUNS / "fit.json").read_text())
    base = json.loads((RUNS / "baselines.json").read_text())
    forest = json.loads((RUNS / "forest-candidates.json").read_text())
    boost = json.loads((RUNS / "boost-candidates.json").read_text())
    P = np.load(RUNS / "predictions.npz", allow_pickle=True)
    B = np.load(RUNS / "baselines.npz", allow_pickle=True)

    # 1. accuracy against model size, every fitted candidate
    rows = []
    for c in boost["candidates"]:
        rows.append([
            "hist-gradient-boosting", c["name"], c["kind"], c["nodes"],
            f"{c['accuracy'] * 100:.3f}",
            "selected" if c["name"].endswith("float32") else "not selected",
        ])
    for c in forest["candidates"]:
        rows.append([
            c["family"].replace("Classifier", ""), c["candidate"],
            "rep" if c["candidate"].startswith("rep") else "window",
            c["full_fit_nodes"], f"{c['accuracy'] * 100:.3f}", "not selected",
        ])
    rows.append(["reference", "form-rep-rf (shipped 2.5 MB)", "rep", 107528, "88.304", "reference"])
    rows.append(["reference", "form-window-rf (shipped 2.7 MB)", "window", 114860, "80.941", "reference"])
    write("candidates-size-vs-accuracy.csv",
          ["family", "candidate", "task", "nodes", "loso_accuracy_pct", "status"], rows)

    # 2. per-exercise accuracy, long format: one row per model/exercise
    rows = []
    for task, newk, oldk, y, ex, unit, basek in (
        ("rep", "rep", "rep_rf80", P["series_y"], P["series_exercise"], "series", "rep_logreg"),
        ("window", "window", "window_rf80", P["window_y"], P["window_exercise"], "rows", None),
    ):
        y = np.asarray(y).astype(int)
        ex = np.asarray(ex)
        new, old = lab(P[newk]), lab(B[oldk])
        for e in sorted(set(ex.tolist())):
            m = ex == e
            n = int(m.sum())
            a, b = int((new[m] == y[m]).sum()), int((old[m] == y[m]).sum())
            rows.append([task, "small-hgb", e, n, f"{a / n * 100:.2f}",
                         f"{(a - b) / n * 100:+.2f}",
                         int(((old[m] == y[m]) & (new[m] != y[m])).sum()),
                         int(((old[m] != y[m]) & (new[m] == y[m])).sum())])
            rows.append([task, "reference-rf80", e, n, f"{b / n * 100:.2f}", "", "", ""])
            if basek:
                pe = base[basek]["per_exercise"][e]
                rows.append([task, "logreg", e, n, f"{pe['accuracy'] * 100:.2f}", "", "", ""])
        n = len(y)
        a, b = int((new == y).sum()), int((old == y).sum())
        rows.append([task, "small-hgb", "ALL", n, f"{a / n * 100:.2f}", f"{(a - b) / n * 100:+.2f}", "", ""])
        rows.append([task, "reference-rf80", "ALL", n, f"{b / n * 100:.2f}", "", "", ""])
        if basek:
            rows.append([task, "logreg", "ALL", n, f"{base[basek]['accuracy'] * 100:.2f}", "", "", ""])
    write("per-exercise.csv",
          ["task", "model", "exercise", "n", "accuracy_pct",
           "delta_vs_reference_pp", "lost", "gained"], rows)

    # 4. window length sweep, from the rerun baselines in docs/RESULTS.md
    rows = [
        [1, "logreg", 70.2], [1, "rf", 76.2], [1, "hgb", 75.9],
        [2, "logreg", 75.4], [2, "rf", 79.4], [2, "hgb", 79.5],
        [3, "logreg", 78.4], [3, "rf", 80.9], [3, "hgb", 80.7],
    ]
    write("window-length-sweep.csv", ["window_s", "model", "accuracy_pct"], rows)

    # 5. headline numbers used in the summary
    rows = [
        ["series", fit["series"]],
        ["subjects", fit["subjects"]],
        ["csv_files", fit["csv_count"]],
        ["rep_series_rows", fit["rep_rows"]],
        ["window_rows", fit["window_rows"]],
        ["chance_floor_pct", f"{fit['chance_floor'] * 100:.1f}"],
        ["rep_small_loso_pct", f"{fit['models']['rep']['accuracy'] * 100:.3f}"],
        ["window_small_loso_pct", f"{fit['models']['window']['accuracy'] * 100:.3f}"],
        ["rep_reference_rf_pct", f"{base['rep_rf80']['accuracy'] * 100:.3f}"],
        ["window_reference_rf_pct", f"{base['window_rf80']['accuracy'] * 100:.3f}"],
        ["rep_logreg_pct", f"{base['rep_logreg']['accuracy'] * 100:.3f}"],
        ["rep_small_nodes", fit["budget"]["models"]["form_rep"]["sections"][".rodata.feature"]],
    ]
    write("headline.csv", ["metric", "value"], rows)


if __name__ == "__main__":
    main()
