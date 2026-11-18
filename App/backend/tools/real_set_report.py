"""Numbers behind ANALYSIS.md: python3 -B backend/tools/real_set_report.py [set_id ...]. Host only, stdlib.

Per set: the reference find_peaks peaks and intervals, each reference window's score decomposed into
quality-head logit contributions, and the bridge's rep_windows with their scores.
"""
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend/src/main/python"), str(ROOT / "reference/scripts"),
                str(ROOT / "backend/src/test/python")]
import tally_app  # noqa: E402
from test_tally_app import real_set_wire  # noqa: E402

rt = tally_app._ts.rt
STATS = ("mean", "std", "min", "max", "range", "rms", "skew", "kurt", "energy", "zcr")
NAMES = ["duration"] + [f"{m}{s}_{a}" for m in ("", "fa.") for s in STATS for a in "xyz"]
LEVEL = {"mean", "min", "max", "rms", "energy"}  # carry gravity and the calibration offset


def decompose(weights, row):
    terms = [c * v for c, v in zip(weights["quality_coef"], row)]
    level = sum(t for t, n in zip(terms, NAMES) if n.split("_")[0].removeprefix("fa.") in LEVEL)
    top = sorted(range(61), key=lambda k: -abs(terms[k]))[:3]
    # EAH logit minus the best other class, split the same way (classes are EAH, EFE, SQZ).
    z = [[c * v for c, v in zip(weights["exercise_coef"][j * 61:(j + 1) * 61], row)] for j in range(3)]
    lv = [sum(t for t, n in zip(zj, NAMES) if n.split("_")[0].removeprefix("fa.") in LEVEL) for zj in z]
    other = [sum(zj) - l for zj, l in zip(z, lv)]
    margin = f"{lv[0] - max(lv[1:]):+.1f}/{other[0] - max(other[1:]):+.1f}"
    return (weights["quality_intercept"][0] + sum(terms), level, sum(terms) - level,
            ", ".join(f"{NAMES[k]} {terms[k]:+.1f}" for k in top) + f" | EAH margin {margin}")


def report(set_id, weights):
    wire, _ = real_set_wire(set_id)
    values = [tally_app._ts.parse_sample(line.split())[2] for line in wire.splitlines() if line.startswith("S ")]
    _, activity = tally_app._centred(values, tally_app.STILL_N)
    d = rt.detrend(rt.magnitude(values))
    peaks = rt.find_peaks(rt.magnitude(values))
    gaps = [(b - a) / rt.FS for a, b in zip(peaks, peaks[1:])]
    print(f"== {set_id}: {len(values) / rt.FS:.2f} s, reference peaks {len(peaks)}, intervals mean "
          f"{statistics.mean(gaps):.2f} sd {statistics.pstdev(gaps):.2f} min {min(gaps):.2f} max {max(gaps):.2f} s")
    print("peak_s detrended_g activity_g:", " ".join(f"{p / rt.FS:.2f}/{d[p]:.2f}/{activity[p]:.2f}" for p in peaks))
    h = tally_app.STILL_N // 2
    rest = min(range(h, len(values) - h), key=activity.__getitem__)
    quiet = values[rest - h:rest + h + 1]
    still = rt.build_rows(values[:50] * 4, [0])[0]  # the first 0.5 s, before any rep, as a 2 s "rep"
    print(f"quietest 0.5 s at {rest / rt.FS:.2f} s: |upper| {statistics.mean(math.dist(r[:3], (0, 0, 0)) for r in quiet):.2f} g, "
          f"|forearm| {statistics.mean(rt.magnitude(quiet)):.2f} g; standing still scored as "
          f"p_wrong {rt.predict(weights, still)[0]:.1e} {rt.predict(weights, still)[1]}")
    bounds = [0] + [(a + b) // 2 for a, b in zip(peaks, peaks[1:])] + [len(values)]
    print("ref | start-end s | class | p_wrong | q | level | other | top quality terms | % still")
    for i, (row, a, b) in enumerate(zip(rt.build_rows(values, peaks), bounds, bounds[1:]), 1):
        p_wrong, label = rt.predict(weights, row)
        q, level, other, top = decompose(weights, row)
        still = 100 * sum(x < tally_app.STILL_G for x in activity[a:b]) / (b - a)
        print(f"{i} | {a / rt.FS:.2f}-{b / rt.FS:.2f} | {label} | {p_wrong:.1e} | {q:.1f} | {level:+.1f} | "
              f"{other:+.1f} | {top} | {still:.0f}")
    for i, (a, b, p) in enumerate(tally_app.rep_windows(values), 1):
        row = rt.build_rows(values[a:b], [p - a])[0]
        p_wrong, label = rt.predict(weights, row)
        q, level, other, top = decompose(weights, row)
        print(f"new {i} | {a / rt.FS:.2f}-{b / rt.FS:.2f} | {label} | {p_wrong:.1e} | {q:.1f} | {level:+.1f} | "
              f"{other:+.1f} | {top}")


if __name__ == "__main__":
    tally_app.init(str(ROOT / "reference/model"))
    for set_id in sys.argv[1:] or sorted(p.stem for p in (ROOT / "data/real-sets").glob("*.csv")):
        report(set_id, tally_app._M["R"])
