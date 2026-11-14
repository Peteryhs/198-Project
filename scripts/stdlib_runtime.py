"""Score a paired set with the Python standard library only.

No NumPy, no SciPy: a shield image that ships nothing but CPython can still run the
paired model. Reproduces `tally_paired_stream.score_set` field for field — same cycle
cutting, same 61 features, same affine model read straight out of the `.npz`.

Verified against the NumPy path on real paired recordings; see docs/PEAK-DETECTION.md.
"""
from __future__ import annotations

import ast
from array import array
import math
import struct
import zipfile

FS = 100.0
WIN = 201
MIN_GAP_S = 1.2
PROMINENCE_FRAC = 0.35


# ---------------------------------------------------------------- .npy / .npz reading
_DTYPES = {"<f4": ("f", 4), "<f8": ("d", 8), "<i4": ("i", 4), "<i8": ("q", 8),
           "|S": ("s", 1), "<U": ("s", 1)}


def _read_npy(raw: bytes):
    if len(raw) < 12 or raw[:6] != b"\x93NUMPY" or raw[6:8] not in (b'\x01\x00', b'\x02\x00'):
        raise ValueError('unsupported or corrupt .npy member')
    major = raw[6]
    if major == 1:
        hlen = struct.unpack("<H", raw[8:10])[0]
        start = 10
    else:
        hlen = struct.unpack("<I", raw[8:12])[0]
        start = 12
    header = ast.literal_eval(raw[start:start + hlen].decode("latin1").strip())
    body = raw[start + hlen:]
    descr = header["descr"].lstrip("=|")
    if descr[:1] in "<>":
        descr = descr[1:]
    shape = header["shape"]
    n = 1
    for dim in shape:
        n *= dim
    if descr.startswith("U"):
        size = int(descr[1:])
        text = body[:n * size * 4].decode("utf-32-le", "replace")
        return [text[i * size:(i + 1) * size].rstrip("\x00") for i in range(n)]
    if descr.startswith("S"):
        size = int(descr[1:])
        return [body[i * size:(i + 1) * size].split(b"\x00")[0].decode() for i in range(n)]
    fmt, width = _DTYPES["<" + descr]
    return list(struct.unpack("<%d%s" % (n, fmt), body[:n * width]))


def load_model(path) -> dict:
    """Read realtime_model.npz with zipfile only."""
    out = {}
    try:
        with zipfile.ZipFile(path) as z:
            if len(z.infolist()) > 32 or sum(i.file_size for i in z.infolist()) > 65536:
                raise ValueError('model archive exceeds size limit')
            for name in z.namelist():
                if name.endswith(".npy"):
                    out[name[:-4]] = _read_npy(z.read(name))
    except (zipfile.BadZipFile, KeyError, TypeError, SyntaxError, struct.error, UnicodeError) as exc:
        raise ValueError(f'corrupt model: {exc}') from exc
    return out


# ---------------------------------------------------------------- signal helpers
def f32(v: float) -> float:
    """Round to float32, which is the precision the NumPy path carries."""
    return struct.unpack("<f", struct.pack("<f", v))[0]


def magnitude(samples):
    return [math.sqrt(s[3] * s[3] + s[4] * s[4] + s[5] * s[5]) for s in samples]


def detrend(x):
    """np.convolve(x, ones(201)/201, mode='same') with zero padding, as a running sum."""
    n = len(x)
    if n < WIN:
        m = sum(x) / n
        return [v - m for v in x]
    half = (WIN - 1) // 2
    scale = 1.0 / WIN
    out = []
    run = 0.0
    lo = hi = 0
    for i in range(n):
        target_lo = max(0, i - half)
        target_hi = min(n, i - half + WIN)
        while hi < target_hi:
            run += x[hi]
            hi += 1
        while lo < target_lo:
            run -= x[lo]
            lo += 1
        out.append(x[i] - run * scale)
    return out


def percentile90(values):
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    pos = 0.9 * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def local_maxima(x):
    out = []
    n = len(x) - 1
    i = 1
    while i < n:
        if x[i - 1] < x[i]:
            j = i
            while j < n and x[j] == x[i]:
                j += 1
            if x[j] < x[i]:
                out.append((i + j - 1) // 2)
            i = j
        else:
            i += 1
    return out


def prominence(x, peak):
    left_min = x[peak]
    i = peak
    while i >= 0 and x[i] <= x[peak]:
        if x[i] < left_min:
            left_min = x[i]
        i -= 1
    right_min = x[peak]
    i = peak
    n = len(x)
    while i < n and x[i] <= x[peak]:
        if x[i] < right_min:
            right_min = x[i]
        i += 1
    return x[peak] - max(left_min, right_min)


def find_peaks(mag):
    d = detrend(mag)
    floor = PROMINENCE_FRAC * percentile90([abs(v) for v in d])
    gap = max(1, int(MIN_GAP_S * FS))
    chosen = []
    blocked = bytearray(len(d))
    for p in sorted(local_maxima(d), key=lambda p: -d[p]):
        if not blocked[p]:
            chosen.append(p)
            lo, hi = max(0, p - gap + 1), min(len(d), p + gap)
            blocked[lo:hi] = b'\x01' * (hi - lo)
    return sorted(p for p in chosen if prominence(d, p) >= floor)


# ---------------------------------------------------------------- features and model
def _stats(w, offset=0):
    """10 statistics x 3 channels for one mount, in harness.window_features order."""
    n = len(w)
    # Packed doubles keep the same arithmetic without six full-set slice copies.
    cols = [array('d', (s[j] for s in w)) for j in range(offset, offset + 3)]
    mean = [sum(c) / n for c in cols]
    std = []
    for c, m in zip(cols, mean):
        std.append(math.sqrt(sum((v - m) ** 2 for v in c) / n))
    mn = [min(c) for c in cols]
    mx = [max(c) for c in cols]
    rng = [a - b for a, b in zip(mx, mn)]
    rms = [math.sqrt(sum(v * v for v in c) / n) for c in cols]
    skew, kurt, energy, zcr = [], [], [], []
    for c, m, s in zip(cols, mean, std):
        sd = s if s else 1.0
        skew.append(sum(((v - m) / sd) ** 3 for v in c) / n)
        kurt.append(sum(((v - m) / sd) ** 4 for v in c) / n - 3.0)
        energy.append(sum(v * v for v in c) / n)
        changes = 0
        prev = None
        for v in c:
            d = v - m
            sign = (d > 0) - (d < 0)
            if prev is not None and sign != prev:
                changes += 1
            prev = sign
        zcr.append(changes / n)
    return mean + std + mn + mx + rng + rms + skew + kurt + energy + zcr


def build_rows(samples, peaks):
    """61 features per repetition: duration, upper statistics, forearm statistics."""
    bounds = [0] + [(peaks[i + 1] + peaks[i]) // 2 for i in range(len(peaks) - 1)] + [len(samples)]
    rows = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b - a < 10:
            continue
        window = samples[a:b]
        row = [(b - a) / FS]
        row += _stats(window)
        row += _stats(window, 3)
        rows.append([f32(v) for v in row])
    return rows


def dot32(coefs, row):
    """Float32 accumulate, matching the NumPy path's float32 matrix-vector product."""
    acc = 0.0
    for c, v in zip(coefs, row):
        acc = f32(acc + f32(c * v))
    return acc


def predict(weights, row):
    q = weights["quality_intercept"][0] + dot32(weights["quality_coef"], row)
    p_wrong = 0.0 if q < -700.0 else 1.0 / (1.0 + math.exp(-q))
    classes = weights["exercise_classes"]
    k = len(classes)
    z = [f32(weights["exercise_intercept"][j] +
             dot32(weights["exercise_coef"][j * 61:(j + 1) * 61], row)) for j in range(k)]
    top = max(z)
    e = [math.exp(v - top) for v in z]
    total = sum(e)
    best = max(range(k), key=lambda j: e[j] / total)
    return p_wrong, classes[best]


def score_set(samples, weights) -> dict:
    rows = build_rows(samples, find_peaks(magnitude(samples)))
    if len(rows) < 3:
        return {"status": "insufficient_reps", "vector_count": len(rows), "mean_p_wrong": None,
                "verdict": None, "exercise": None, "repetitions": [],
                "diagnostics": ["fewer_than_3_cycles"]}
    probs, exercises, reps = [], [], []
    for i, row in enumerate(rows, start=1):
        p, label = predict(weights, row)
        probs.append(p)
        exercises.append(label)
        reps.append({"rep_index": i, "verdict": "wrong" if p >= 0.5 else "correct",
                     "exercise": label, "duration_s": round(row[0], 3),
                     "p_wrong": round(p, 6)})
    mean_p = sum(probs) / len(probs)
    counts = {}
    for label in exercises:
        counts[label] = counts.get(label, 0) + 1
    return {"status": "scored", "vector_count": len(rows), "mean_p_wrong": round(mean_p, 6),
            "verdict": "wrong" if mean_p >= 0.5 else "correct",
            "exercise": max(counts, key=counts.get), "repetitions": reps, "diagnostics": []}
