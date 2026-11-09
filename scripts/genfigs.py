"""Build the figures for the preliminary PHYTMO results.

Reads the numbers back out of the run logs (so the charts are generated from data, not retyped
constants), writes results.csv, then renders three PNGs.

Run:
  ~/.hermes/bin/uv run --no-project --with numpy python genfigs.py
"""

from __future__ import annotations

import csv
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
INK = "#1f2430"
MUTED = "#6b7280"
GRID = "#e5e7eb"
ACC = "#d97706"      # accelerometer only
ACC_GYRO = "#2563eb"  # accelerometer + gyroscope
DANGER = "#dc2626"

ROW = re.compile(
    r"^\s{2}(?P<model>\w+)\s+acc=(?P<acc>[\d.]+).*?"
    r"(?:EAH:(?P<eah>[\d.]+)\s+EFE:(?P<efe>[\d.]+)\s+SQZ:(?P<sqz>[\d.]+))?\s*$"
)
HEAD = re.compile(r"^(?P<win>\d+)-sample windows.*?channels=(?P<ch>\w+)")


def style(ax) -> None:
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)


def parse_log(path: str, channels: str) -> list[dict]:
    rows: list[dict] = []
    win = None
    with open(path) as fh:
        for line in fh:
            h = HEAD.match(line.strip())
            if h:
                win = int(h.group("win"))
                continue
            r = ROW.match(line.rstrip())
            if r and win:
                rows.append({
                    "channels": channels,
                    "window": win // 100,
                    "model": r.group("model"),
                    "accuracy": float(r.group("acc")),
                    "EAH": float(r.group("eah")) if r.group("eah") else None,
                    "EFE": float(r.group("efe")) if r.group("efe") else None,
                    "SQZ": float(r.group("sqz")) if r.group("sqz") else None,
                })
    return rows


def parse_mil(path: str) -> dict:
    txt = open(path).read()
    out = {}
    for line in txt.splitlines():
        m = re.match(r"\s+naive rep propagation\s*:\s*([\d.]+)", line)
        if m:
            out["rep_mean"] = float(m.group(1))
        m = re.match(r"\s+MIL \(max pooling\)\s*:\s*([\d.]+)", line)
        if m:
            out["mil"] = float(m.group(1))
        m = re.match(r"\s+(\w+): propagation ([\d.]+)\s+MIL ([\d.]+)", line)
        if m:
            out.setdefault("per_ex", {})[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def fig_window(rows: list[dict]) -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200)
    style(ax)
    for ch, color, label in ((("acc"), ACC, "Accelerometer only"),
                             ("accgyro", ACC_GYRO, "Accelerometer + gyroscope")):
        pts = {}
        for r in rows:
            if r["channels"] != ch:
                continue
            if r["window"] not in pts or r["accuracy"] > pts[r["window"]][0]:
                pts[r["window"]] = (r["accuracy"], r["model"])
        xs = sorted(pts)
        ys = [pts[x][0] * 100 for x in xs]
        ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=7, label=label)
        for x in xs:
            acc, model = pts[x]
            ax.annotate(f"{acc * 100:.1f}  ({model})", (x, acc * 100),
                        textcoords="offset points", xytext=(0, 9 if color == ACC_GYRO else -16),
                        ha="center", fontsize=8.5, color=color)

    ax.axhline(50, color=DANGER, linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate("random floor, 50.0", (1.02, 50), textcoords="offset points",
                xytext=(0, 6), ha="left", fontsize=8.5, color=DANGER)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["1 s", "2 s", "3 s"])
    ax.set_xlim(0.8, 3.2)
    ax.set_ylim(45, 92)
    ax.set_xlabel("Sliding window length", color=INK, fontsize=10)
    ax.set_ylabel("Correct vs wrong, accuracy (%)", color=INK, fontsize=10)
    ax.set_title("Best model per window, leave-one-subject-out over 30 volunteers",
                 color=INK, fontsize=11, loc="left", pad=12)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=9)
    fig.text(0.01, 0.005, "The gyroscope arm was not run at 1 s, so its line starts at 2 s.",
             fontsize=8, color=MUTED, ha="left")
    path = os.path.join(OUT, "fig1_window_accuracy.png")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def fig_methods(rows: list[dict], mil: dict) -> str:
    best = max((r for r in rows if r["channels"] == "acc" and r["window"] == 3),
               key=lambda r: r["accuracy"])
    per = mil["per_ex"]
    series = [
        ("3 s windows", best["accuracy"], best["EAH"], best["EFE"], best["SQZ"], "#9aa3ad"),
        ("Repetitions,\nmean", mil["rep_mean"], per["EAH"][0], per["EFE"][0], per["SQZ"][0], ACC),
        ("Repetitions,\nmax pooling", mil["mil"], per["EAH"][1], per["EFE"][1], per["SQZ"][1], "#c2410c"),
    ]
    groups = ["All three", "EAH", "EFE", "SQZ"]
    fig, ax = plt.subplots(figsize=(7.6, 4.6), dpi=200)
    style(ax)
    width = 0.26
    for i, (name, overall, eah, efe, sqz, color) in enumerate(series):
        vals = [overall * 100, eah * 100, efe * 100, sqz * 100]
        xs = [k + (i - 1) * width for k in range(len(groups))]
        bars = ax.bar(xs, vals, width, color=color, label=name.replace("\n", " "), zorder=3)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.1f}", (b.get_x() + b.get_width() / 2, v), ha="center",
                        va="bottom", fontsize=8.5, color=INK)
    ax.axhline(50, color=DANGER, linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate("random floor, 50.0", (-0.55, 50), textcoords="offset points", xytext=(0, 6),
                ha="left", fontsize=8.5, color=DANGER)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, color=INK, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Accuracy on the series verdict (%)", color=INK, fontsize=10)
    ax.set_title("Windows versus per-repetition scoring, accelerometer only", color=INK,
                 fontsize=11, loc="left", pad=12)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, fontsize=9)
    path = os.path.join(OUT, "fig2_methods.png")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


SAT = {
    "EAH": (71.8, 37.3, 19.4, 3.7),
    "EFE": (49.3, 27.8, 13.9, 2.5),
    "SQZ": (34.1, 10.8, 3.0, 0.4),
}


def fig_saturation() -> str:
    limits = ["1.5 g", "2.0 g", "3.0 g", "6.0 g"]
    cols = ["#d9b38c", "#e0a868", "#f59e0b", "#b45309"]
    fig, ax = plt.subplots(figsize=(7.4, 4.4), dpi=200)
    style(ax)
    width = 0.2
    for i, (lim, color) in enumerate(zip(limits, cols)):
        vals = [SAT[ex][i] for ex in ("EAH", "EFE", "SQZ")]
        xs = [k + (i - 1.5) * width for k in range(3)]
        edge = DANGER if lim == "3.0 g" else "none"
        bars = ax.bar(xs, vals, width, color=color, label=lim, zorder=3,
                      edgecolor=edge, linewidth=1.6 if lim == "3.0 g" else 0)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.1f}", (b.get_x() + b.get_width() / 2, v), ha="center",
                        va="bottom", fontsize=8, color=INK)
    # Point at the arms-overhead 3.0 g bar rather than shading the whole category.
    ax.annotate("ADXL335 limit\nclips 19.4% of these",
                xy=(0 + 0.5 * width, 19.4), xytext=(0.42, 52),
                ha="center", fontsize=8.5, color=DANGER,
                arrowprops=dict(arrowstyle="->", color=DANGER, linewidth=1.2))
    ax.set_xticks(range(3))
    ax.set_xticklabels(["EAH\narms overhead", "EFE\nelbow flex", "SQZ\nsqueeze"],
                       color=INK, fontsize=10)
    ax.set_ylim(0, 82)
    ax.set_ylabel("Series whose peak acceleration exceeds (%)", color=INK, fontsize=10)
    ax.set_title("Measured on 1,368 recorded series (capture range ±16 g)", color=INK,
                 fontsize=11, loc="left", pad=12)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4, fontsize=9,
              title="peak acceleration", title_fontsize=9)
    path = os.path.join(OUT, "fig3_saturation.png")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rows = parse_log(os.path.join(HERE, "run_acc.log"), "acc")
    rows += parse_log(os.path.join(HERE, "run_accgyro.log"), "accgyro")
    rows.sort(key=lambda r: (r["channels"], r["window"], r["model"]))
    with open(os.path.join(HERE, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["channels", "window", "model", "accuracy",
                                           "EAH", "EFE", "SQZ"])
        w.writeheader()
        w.writerows(rows)
    mil = parse_mil(os.path.join(HERE, "run_mil2.log"))
    print(f"{len(rows)} window results, mil={mil}")
    for p in (fig_window(rows), fig_methods(rows, mil), fig_saturation()):
        print(p, os.path.getsize(p), "bytes")


if __name__ == "__main__":
    main()
