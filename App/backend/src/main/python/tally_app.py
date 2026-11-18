"""One completed set per call; the validated scorer is copied unchanged at build.

Rep windows are cut here (rep_windows); each window is scored by the validated features and model.
"""
import hashlib as _hashlib
import io as _io
import json as _json
import math as _math
from pathlib import Path as _Path

import tally_stdlib as _ts

try:
    from _scorer_build import SHA256 as _SCORER_SHA256
except ModuleNotFoundError:  # Host tests run directly against the reference sources.
    _SCORER_SHA256 = None

__all__ = ("init", "score_wire", "scorer_version", "exercise_classes")
_M = None


def init(model_root: str) -> str:
    global _M
    _M = None
    _ts.MODEL_DIR = _Path(model_root)
    models = {side: _ts.load_model(side) for side in _ts.SIDES}
    hashes = {
        side: _hashlib.sha256(
            (_ts.MODEL_DIR / "paired-synchronized-offline" / side / "realtime_model.npz")
            .read_bytes()
        ).hexdigest()
        for side in _ts.SIDES
    }
    _M = models
    return _json.dumps(hashes)


def exercise_classes() -> str:
    if _M is None:
        raise RuntimeError("init must succeed first")
    return _json.dumps(sorted({c for weights in _M.values() for c in weights["exercise_classes"]}))


def score_wire(wire: str, intended=None) -> str:
    """intended: the exercise the user chose (a model class), or None when not specified."""
    if _M is None:
        raise RuntimeError("init must succeed before scoring")
    if intended is not None and intended not in _json.loads(exercise_classes()):
        raise ValueError(f"unknown intended exercise {intended!r}")
    out, replies = _io.StringIO(), []
    _ts.run(_io.StringIO(wire), emit=False, out=out, reply=replies.append,
            models=_M, live=False)
    records = out.getvalue().splitlines()
    if len(records) != 1:
        raise ValueError("expected exactly one set record")
    record = _json.loads(records[0])
    parsed, windows = [], []
    if record.get("status") in ("scored", "insufficient_reps"):
        parsed = [_ts.parse_sample(row) for row in map(str.split, wire.splitlines()) if row and row[0] == "S"]
        values = [row[2] for row in parsed]
        windows = rep_windows(values)
        record.update(_score_windows(values, _M[record["side"]], windows))
        replies = list(_ts.reply_lines(record))
    if record.get("status") in ("scored", "insufficient_reps") and _no_movement([row[2] for row in parsed]):
        # find_peaks' floor is relative to the set itself, so a still set always yields cycles.
        record.update(status="insufficient_reps", vector_count=0, mean_p_wrong=None, verdict=None,
                      exercise=None, repetitions=[], diagnostics=["no_movement"])
        replies = [_ts.reply_line(record)]
        windows = []
    _decide(record, intended)
    if record.get("status") == "scored":
        replies[-1] = _ts.reply_line(record)
    chart = _chart_data(parsed, record, windows)
    if chart is not None:
        record["chart"] = chart
    return _json.dumps({"record": record, "reply": replies}, allow_nan=False)


def _decide(record, intended):
    """Report the set wrong if any rep is wrong or the class is not the intended exercise.

    The reference verdict (mean p_wrong >= 0.5, stdlib_runtime.score_set) is kept as mean_verdict.
    """
    record["intended_exercise"] = intended
    if record.get("status") != "scored":
        return
    reps = record["repetitions"]
    record["mean_verdict"] = record["verdict"]
    record["wrong_reps"] = sum(rep["verdict"] == "wrong" for rep in reps)
    record["exercise_check"] = ("unverified" if intended is None
                                else "match" if record["exercise"] == intended else "mismatch")
    record["verdict"] = ("wrong_exercise" if record["exercise_check"] == "mismatch"
                         else "wrong" if record["wrong_reps"] else "correct")


# Derived, provisional (REPORT5.md): 90th percentile of |detrended forearm magnitude| in g, the same
# quantity find_peaks scales its floor from. Replace with 3x the p90 of a still recording on the board.
NO_MOTION_P90_G = 0.03


def _no_movement(values):
    d = _ts.rt.detrend(_ts.rt.magnitude(values))
    return _ts.rt.percentile90([abs(v) for v in d]) < NO_MOTION_P90_G


# Rep segmentation replacing find_peaks' cycle cutting (ANALYSIS.md). Measured on data/real-sets:
# still periods have 0.5 s activity <= 0.17 g and posture bumps <= 0.043 g; reps move >= 0.506 g.
SMOOTH_N = 25         # 0.25 s low-pass before measuring posture
STILL_N = 51          # 0.5 s window for activity and for the rest posture
STILL_G = 0.2         # activity below this is still (measured max 0.17 g)
REP_FLOOR_G = 0.3     # minimum excursion prominence of a rep (gap measured: 0.043 .. 0.506 g)
MIN_GAP_N = int(_ts.rt.MIN_GAP_S * _ts.FS)  # 1.2 s: sub-humps <= 0.48 s apart, reps >= 1.5 s
EDGE_FRAC = 0.1       # assumed: a window ends where the excursion is back within 10 % of its prominence


def _centred(values, n):
    """Per-channel centred n-sample mean, and sqrt of the summed per-channel variance, per sample."""
    count, h = len(values), n // 2
    means, var = [], [0.0] * count
    for c in range(len(values[0])):
        s, q = [0.0], [0.0]
        for row in values:
            s.append(s[-1] + row[c])
            q.append(q[-1] + row[c] * row[c])
        col = []
        for i in range(count):
            a, b = max(0, i - h), min(count, i + h + 1)
            mu = (s[b] - s[a]) / (b - a)
            col.append(mu)
            var[i] += max(0.0, (q[b] - q[a]) / (b - a) - mu * mu)
        means.append(col)
    return means, [_math.sqrt(v) for v in var]


def rep_windows(values):
    """(start, end, peak) sample indices, one per rep.

    A rep is an excursion of the smoothed 6-channel posture away from the rest posture, which is the
    quietest 0.5 s of the set. Differences of raw g cancel calibration offsets, unlike magnitude.
    """
    if len(values) < STILL_N:
        return []
    smooth, _ = _centred(values, SMOOTH_N)
    posture, activity = _centred(values, STILL_N)
    h = STILL_N // 2
    rest = min(range(h, len(values) - h), key=activity.__getitem__)
    e = [_math.sqrt(sum((col[i] - mean[rest]) ** 2 for col, mean in zip(smooth, posture)))
         for i in range(len(values))]
    chosen, blocked = [], bytearray(len(e))
    for p in sorted(_ts.rt.local_maxima(e), key=lambda p: -e[p]):
        if not blocked[p]:
            chosen.append(p)
            lo, hi = max(0, p - MIN_GAP_N + 1), min(len(e), p + MIN_GAP_N)
            blocked[lo:hi] = b"\x01" * (hi - lo)
    peaks = sorted(p for p in chosen if _ts.rt.prominence(e, p) >= REP_FLOOR_G)
    cuts = [0] + [min(range(p, r), key=e.__getitem__) for p, r in zip(peaks, peaks[1:])] + [len(e)]
    windows = []
    for p, a, b in zip(peaks, cuts, cuts[1:]):
        # Moving: active, or far from rest (a top hold is quiet but far away; measuring from the
        # rep's own base absorbs slow posture drift). Keep the moving run around the peak.
        level = e[p] - (1 - EDGE_FRAC) * _ts.rt.prominence(e, p)
        lo, hi = p, p + 1
        while lo > a and (e[lo - 1] >= level or activity[lo - 1] >= STILL_G):
            lo -= 1
        while hi < b and (e[hi] >= level or activity[hi] >= STILL_G):
            hi += 1
        if hi - lo >= 10:
            windows.append((lo, hi, p))
    return windows


def _score_windows(values, weights, windows):
    """rt.score_set's fields, with the validated features and model applied to each rep window."""
    rows = [_ts.rt.build_rows(values[a:b], [p - a])[0] for a, b, p in windows]
    if len(rows) < 3:
        return {"status": "insufficient_reps", "vector_count": len(rows), "mean_p_wrong": None,
                "verdict": None, "exercise": None, "repetitions": [],
                "diagnostics": ["fewer_than_3_cycles"]}
    reps, counts, probs = [], {}, []
    for i, row in enumerate(rows, start=1):
        p, label = _ts.rt.predict(weights, row)
        probs.append(p)
        counts[label] = counts.get(label, 0) + 1
        reps.append({"rep_index": i, "verdict": "wrong" if p >= 0.5 else "correct", "exercise": label,
                     "duration_s": round(row[0], 3), "p_wrong": round(p, 6)})
    mean_p = sum(probs) / len(probs)
    return {"status": "scored", "vector_count": len(rows), "mean_p_wrong": round(mean_p, 6),
            "verdict": "wrong" if mean_p >= 0.5 else "correct",
            "exercise": max(counts, key=counts.get), "repetitions": reps, "diagnostics": []}


def _chart_data(parsed, record, windows=()):
    """Display metadata only; the validated runtime still computes every prediction."""
    if record.get("status") not in ("scored", "insufficient_reps"):
        return None
    if len(parsed) < 2:
        return None
    times = [row[1] / 1000.0 for row in parsed]
    values = [row[2] for row in parsed]
    upper = [_math.sqrt(sum(v * v for v in row[:3])) for row in values]
    forearm = [_math.sqrt(sum(v * v for v in row[3:])) for row in values]
    # Keep actual extrema and timestamps, bounded independently of the raw set size.
    width = max(1, _math.ceil(len(values) / ((1200 - 2) // 4)))
    selected = {0, len(values) - 1}
    for start in range(0, len(values), width):
        stop = min(start + width, len(values))
        indices = range(start, stop)
        for signal in (upper, forearm):
            selected.add(min(indices, key=signal.__getitem__))
            selected.add(max(indices, key=signal.__getitem__))
    samples = [{"time_s": times[i], "upper_arm_g": upper[i], "forearm_g": forearm[i]}
               for i in sorted(selected)]
    reps = record.get("repetitions", [])
    spans = []
    if reps:
        if len(windows) == len(reps) and all(round((b - a) / _ts.FS, 3) == rep["duration_s"]
                                           for (a, b, _), rep in zip(windows, reps)):
            spans = [{"index": rep["rep_index"], "start_s": times[a], "end_s": times[b - 1]}
                     for (a, b, _), rep in zip(windows, reps)]
        else:
            record.setdefault("diagnostics", []).append("chart_rep_alignment_unavailable")
    return {"samples": samples, "reps": spans}


def scorer_version() -> str:
    if _SCORER_SHA256 is not None:
        return _SCORER_SHA256
    root = _Path(_ts.__file__).parent
    return _hashlib.sha256(b"".join(
        (root / name).read_bytes() for name in ("stdlib_runtime.py", "tally_stdlib.py")
    )).hexdigest()
