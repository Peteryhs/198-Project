"""Teaching figure: our feature-based models versus a recurrent network.

Built from one real repetition in the PHYTMO data, so the demonstration on the first panel is exact:
shuffling the samples leaves mean, standard deviation, minimum and maximum bit-identical, because
all four are permutation-invariant. That is the whole point of the picture.

Run: ~/.hermes/bin/uv run --no-project --with numpy --with matplotlib python lesson_figure.py
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

# matplotlib does not read the system font cache; register the two faces by path.
for _f in ("Inter[opsz,wght].ttf", "Fraunces[SOFT,WONK,opsz,wght].ttf"):
    _p = os.path.expanduser(f"~/.local/share/fonts/{_f}")
    if os.path.exists(_p):
        font_manager.fontManager.addfont(_p)
plt.rcParams["font.family"] = "Inter"
plt.rcParams["font.sans-serif"] = ["Inter", "DejaVu Sans"]

HERE = os.path.dirname(os.path.abspath(__file__))
INK = "#1C1917"
PAPER = "#FFFFFF"
CLAY = "#9A3B12"
SAGE = "#3F5A46"
ASH = "#6B6157"
FAINT = "#E8E3D9"

W, H = 1100, 1400


def load_rep() -> np.ndarray:
    """One real repetition, accelerometer magnitude, from the downloaded dataset."""
    import sys
    sys.path.insert(0, os.path.dirname(HERE))
    from harness import CHANNEL_SETS, COLS, read_inertial
    from reps import find_peaks

    acc = [COLS.index(c) for c in CHANNEL_SETS["acc"]]
    path = os.path.join(os.path.dirname(HERE), "data/inertial/upper/A/Larm/A01EAH0_1.csv")
    sig = read_inertial(path)
    peaks = find_peaks(sig)
    a, b = peaks[0], peaks[1]
    seg = sig[a:b, acc]
    return np.linalg.norm(seg, axis=1)


def box(ax, x, y, w, h, label, color=INK, fc="white", fs=13, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=6,rounding_size=10",
                                linewidth=1.4, edgecolor=color, facecolor=fc))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=fs,
            color=color, family="Inter", weight=weight)


def arrow(ax, x1, y1, x2, y2, color=ASH):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
                                 linewidth=1.2, color=color, shrinkA=4, shrinkB=4))


def trace(ax, data, x0, y0, w, h, color):
    n = len(data)
    lo, hi = data.min(), data.max()
    xs = x0 + np.arange(n) / max(1, n - 1) * w
    ys = y0 + (data - lo) / max(1e-9, hi - lo) * h
    ax.plot(xs, ys, color=color, linewidth=1.6, solid_joinstyle="round")


def main() -> None:
    rep = load_rep()
    rng = np.random.default_rng(7)
    shuffled = rng.permutation(rep)

    feats = lambda v: (v.mean(), v.std(), v.min(), v.max())  # noqa: E731
    f_rep, f_shuf = feats(rep), feats(shuffled)

    fig, ax = plt.subplots(figsize=(11, 14), dpi=150)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    fig.patch.set_facecolor(PAPER)

    def T(y_top: float) -> float:
        return H - y_top

    # ---------- title ----------
    ax.text(48, T(58), "Same numbers, different movement", fontsize=26, color=INK,
            family="Fraunces", weight="600")
    ax.text(48, T(92), "Why the way we feed a model decides what it can notice.",
            fontsize=13, color=ASH, family="Inter")

    # ---------- 1. the problem ----------
    ax.text(48, T(146), "1.  One real repetition, twice", fontsize=15, color=INK,
            family="Inter", weight="600")

    bx, bw, bh = 70, 430, 120
    for i, (data, label, col) in enumerate(
            [(rep, "in the order it happened", CLAY),
             (shuffled, "the same 62 samples, shuffled", ASH)]):
        x0 = bx + i * (bw + 90)
        y0 = T(320)
        ax.add_patch(FancyBboxPatch((x0 - 10, y0 - 8), bw + 20, bh + 16,
                                    boxstyle="round,pad=2,rounding_size=8",
                                    linewidth=1, edgecolor=FAINT, facecolor="#FCFBF8"))
        trace(ax, data, x0, y0, bw, bh, col)
        ax.text(x0, T(348), label, fontsize=12, color=col, family="Inter")

        vals = feats(data)
        names = ["mean", "std", "min", "max"]
        for j, (nm, v) in enumerate(zip(names, vals)):
            yy = T(392 + j * 26)
            ax.text(x0 + 20, yy, nm, fontsize=12, color=ASH, family="Inter")
            ax.text(x0 + 160, yy, f"{v:.3f}", fontsize=13, color=INK, family="Inter",
                    weight="600")

    ax.text(48, T(520), "Identical to three decimals, because all four of them ignore the order "
                        "the samples arrived in.",
            fontsize=12.5, color=INK, family="Inter")

    # ---------- 2. our models ----------
    ax.text(48, T(600), "2.  What our models do: squeeze the window, then decide", fontsize=15,
            color=INK, family="Inter", weight="600")

    y0 = T(700)
    trace(ax, rep, 70, y0, 200, 90, CLAY)
    ax.text(70, T(724), "1 s window", fontsize=11, color=ASH, family="Inter")
    arrow(ax, 285, T(655), 330, T(655), CLAY)

    box(ax, 335, T(700), 250, 90,
        "mean, std, min, max\nper axis  ->  12 numbers", CLAY, "#FDF6F2", 12.5)
    arrow(ax, 595, T(655), 640, T(655), CLAY)

    box(ax, 645, T(700), 210, 90, "tree / logistic\nregression", INK, "white", 12.5)
    arrow(ax, 865, T(655), 910, T(655), CLAY)
    box(ax, 915, T(700), 130, 90, "good / bad", CLAY, "#FDF6F2", 13, "600")

    ax.text(70, T(752), "The wiggles are gone before the model ever sees them. Every sample "
                        "is thrown away and replaced by four summaries.",
            fontsize=12.5, color=INK, family="Inter")

    # ---------- 3. an RNN ----------
    ax.text(48, T(830), "3.  What an RNN does: read the samples in order and keep a memory",
            fontsize=15, color=INK, family="Inter", weight="600")

    y0 = T(930)
    trace(ax, rep, 70, y0, 230, 90, SAGE)
    ax.text(70, T(954), "the same 1 s window", fontsize=11, color=ASH, family="Inter")

    xs = [390, 520, 650, 780]
    labels = ["h1", "h2", "h3", "h4"]
    for i, (x, lab) in enumerate(zip(xs, labels)):
        ax.add_patch(plt.Circle((x, T(885)), 34, facecolor="#F1F6F2", edgecolor=SAGE,
                                linewidth=1.4))
        ax.text(x, T(885), lab, ha="center", va="center", fontsize=13, color=SAGE,
                family="Inter", weight="600")
        if i:
            arrow(ax, xs[i - 1] + 36, T(885), x - 36, T(885), SAGE)
        arrow(ax, 310 + i * 8, T(885), x - 36, T(885), SAGE)

    ax.text(390, T(938), "each circle = what it has seen so far", fontsize=11,
            color=SAGE, family="Inter", ha="center")
    arrow(ax, 818, T(885), 862, T(885), SAGE)
    box(ax, 867, T(925), 150, 80, "good / bad", SAGE, "#F1F6F2", 13, "600")

    ax.text(70, T(985), "Each step reads one sample plus whatever it remembered. By the end it "
                        "has seen the shape, not a summary of it.",
            fontsize=12.5, color=INK, family="Inter")

    # ---------- payoff ----------
    ax.plot([48, W - 48], [T(1030), T(1030)], color=FAINT, linewidth=1)
    ax.text(48, T(1082), "What this buys you", fontsize=15, color=INK, family="Inter",
            weight="600")
    rows = [
        ("Sees the shape of the movement", "no", "yes", CLAY, SAGE),
        ("Can say where in the rep it went wrong", "gone", "yes", CLAY, SAGE),
        ("Works on 12 numbers instead of 62 samples", "yes", "no", SAGE, CLAY),
        ("Fits in 25 kB of RAM on the board", "yes", "not directly", SAGE, CLAY),
    ]
    for i, (what, ours, rnn, col_a, col_b) in enumerate(rows):
        y = T(1150 + i * 40)
        ax.text(48, y, what, fontsize=12.5, color=INK, family="Inter")
        ax.text(760, y, ours, fontsize=12.5, color=col_a, family="Inter")
        ax.text(940, y, rnn, fontsize=12.5, color=col_b, family="Inter")
    ax.text(760, T(1108), "our models", fontsize=11, color=ASH, family="Inter", weight="600")
    ax.text(940, T(1108), "RNN", fontsize=11, color=ASH, family="Inter", weight="600")

    ax.text(48, T(1330), "Middle ground for the device: a 1D CNN reads the same window in order, "
                         "keeps the shape, and still fits the memory budget.",
            fontsize=12, color=ASH, family="Inter")

    out = os.path.join(HERE, "lesson-ours-vs-rnn.png")
    fig.savefig(out, facecolor=PAPER, bbox_inches="tight", pad_inches=0.3)
    print(out, os.path.getsize(out), "bytes")

    # Also a chat-sized copy.
    import subprocess
    subprocess.run(["magick", out, "-resize", "1500x", "-quality", "92",
                    os.path.join(HERE, "lesson-ours-vs-rnn-chat.jpg")], check=True)
    print("chat copy written")


if __name__ == "__main__":
    main()
