"""Numbers BRIEF5 asks for, from one set exported by the app: python3 -B backend/tools/set_check.py SET.csv [REPS]

Uses the set's own calibration from the CSV `# meta=` line and the unchanged reference scorer.
Prints per-channel std and peak-to-peak in g, the no-movement statistic, how many cycles find_peaks
cuts, and the three class probabilities plus p(wrong) for the first REPS cycles (default 5).
"""
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend/src/main/python"), str(ROOT / "reference/scripts")]
import tally_app  # noqa: E402

rt = tally_app._ts.rt


def main(path, reps=5):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    meta = json.loads(next(line[len("# meta="):] for line in lines if line.startswith("# meta=")))
    cal = meta["calibration"]
    rows = [line.split(",") for line in lines if line and line[0].isdigit()]
    g = [[rt.f32((int(r[4 + ch]) - cal["offset_mv"][ch]) / cal["mv_per_g"][ch]) for ch in range(6)] for r in rows]
    print(f"set {meta['id']} side {meta['side']} samples {len(g)} calibration {cal['id']}")
    for ch, name in enumerate(("upper_x", "upper_y", "upper_z", "forearm_x", "forearm_y", "forearm_z")):
        col = [row[ch] for row in g]
        print(f"  {name:9s} mean {statistics.fmean(col):+.4f} g  std {statistics.pstdev(col):.4f} g  "
              f"p-p {max(col) - min(col):.4f} g")
    d = rt.detrend(rt.magnitude(g))
    p90 = rt.percentile90([abs(v) for v in d])
    peaks = rt.find_peaks(rt.magnitude(g))
    print(f"p90 |detrended forearm magnitude| {p90:.4f} g (no-movement gate {tally_app.NO_MOTION_P90_G} g: "
          f"{'still' if p90 < tally_app.NO_MOTION_P90_G else 'moving'}); find_peaks cycles {len(rt.build_rows(g, peaks))}")
    w = rt.load_model(ROOT / "reference/model/paired-synchronized-offline" / meta["side"] / "realtime_model.npz")
    classes = w["exercise_classes"]
    for i, row in enumerate(rt.build_rows(g, peaks)[:reps], start=1):
        z = [rt.f32(w["exercise_intercept"][j] + rt.dot32(w["exercise_coef"][j * 61:(j + 1) * 61], row)) for j in range(3)]
        e = [math.exp(v - max(z)) for v in z]
        p_wrong = rt.predict(w, row)[0]
        print(f"  rep {i}: " + " ".join(f"P({c}) {v / sum(e):.3f}" for c, v in zip(classes, e)) + f"  p_wrong {p_wrong:.3f}")


if __name__ == "__main__":
    main(sys.argv[1], *(int(a) for a in sys.argv[2:3]))
