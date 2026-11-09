"""How much of PHYTMO would saturate a +-3 g accelerometer?

The ADXL335 on the build is +-3 g; PHYTMO recorded at +-16 g. This counts, per file, the peak
acceleration so we can state the clipping risk with a number instead of a worry.
"""

from __future__ import annotations

import os
from collections import defaultdict

import numpy as np

from harness import CHANNEL_SETS, COLS, parse_name, read_inertial

ROOT = "data/inertial/upper"
ACC = [COLS.index(c) for c in CHANNEL_SETS["acc"]]
LIMITS = (1.5, 2.0, 3.0, 6.0)


def main() -> None:
    per_ex = defaultdict(list)
    for dirpath, _, files in os.walk(ROOT):
        for f in sorted(files):
            if not f.endswith(".csv"):
                continue
            path = os.path.join(dirpath, f)
            meta = parse_name(path)
            if meta is None:
                continue
            sig = read_inertial(path)[:, ACC]
            per_ex[meta[1]].append(float(np.abs(sig).max()))
            per_ex["ALL"].append(float(np.abs(sig).max()))

    print(f"{len(per_ex['ALL'])} files, peak |accel| per axis\n")
    for ex in ["EAH", "EFE", "SQZ", "ALL"]:
        a = np.array(per_ex[ex])
        line = [f"{ex:4s} n={len(a):4d} median={np.median(a):5.2f}g p90={np.percentile(a, 90):5.2f}g"]
        for lim in LIMITS:
            line.append(f"over {lim}g: {100 * (a > lim).mean():5.1f}%")
        print("  " + "  ".join(line))


if __name__ == "__main__":
    main()
