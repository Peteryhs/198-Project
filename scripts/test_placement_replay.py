import json
from pathlib import Path

import numpy as np

from placement_replay import virtual_mount


def main():
    config = json.loads(Path("simulation/placements.json").read_text())
    candidates = config["candidates"]
    assert len(candidates) == 4 and len({c["id"] for c in candidates}) == 4
    for candidate in candidates:
        for segment in ("upper", "forearm"):
            mount = candidate[segment]
            assert 0 < mount["fraction"] < 1
            assert 0 <= mount["surface_deg"] <= 90
            assert candidate["definitions"][segment]

    # Independent static specific-force check: a stationary sensor reads +1 g upward.
    t = np.arange(200) / 100
    q = np.tile([0., 0., 0., 1.], (len(t), 1))
    p = np.zeros((len(t), 3))
    signal = virtual_mount(t, q, p, np.ones(len(t), dtype=bool), .5, 0., .30, .04)
    assert np.allclose(signal[5:-5], [0., 1., 0.], atol=1e-9), signal

    # Rigid translation acceleration is retained at every point on the segment.
    p[:, 1] = .5 * t**2
    signal = virtual_mount(t, q, p, np.ones(len(t), dtype=bool), .3, 45., .30, .04)
    assert np.allclose(np.median(np.linalg.norm(signal[5:-5], axis=1)), 1. / 9.80665 + 1., atol=1e-5)

    # An off-axis point on a uniformly rotating body has inward centripetal acceleration.
    omega, radius = 1.2, .04
    qrot = np.array([[np.sin(omega * time / 2), 0., 0., np.cos(omega * time / 2)] for time in t])
    center = np.zeros((len(t), 3))
    at_center = virtual_mount(t, qrot, center, np.ones(len(t), bool), .5, 90., .30, 0.)
    off_axis = virtual_mount(t, qrot, center, np.ones(len(t), bool), .5, 90., .30, radius)
    assert np.isclose(np.median(np.linalg.norm((off_axis - at_center)[10:-10], axis=1)), np.sqrt(2) * radius * omega**2 / 9.80665, atol=1e-5)

    valid = np.ones(len(t), dtype=bool)
    valid[70:120] = False
    gaps = virtual_mount(t, q, p, valid, .5, 0., .30, .04)
    assert np.isnan(gaps[70:120]).all() and np.isfinite(gaps[:70]).all() and np.isfinite(gaps[120:]).all()
    irregular = t.copy()
    irregular[100:] += .02
    try:
        virtual_mount(irregular, q, p, np.ones(len(t), bool), .5, 0., .30, .04)
    except ValueError:
        pass
    else:
        raise AssertionError("irregular optical time base was accepted")
    for fraction, surface, length, radius in ((0., 0., .30, .04), (.5, np.nan, .30, .04),
                                               (.5, np.inf, .30, .04), (np.nan, 0., .30, .04),
                                               (.5, 0., np.nan, .04), (.5, 0., .30, np.inf),
                                               (.5, 0., 0., .04), (.5, 0., .30, -.01)):
        try:
            virtual_mount(t, q, p, np.ones(len(t), bool), fraction, surface, length, radius)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid placement geometry was accepted")
    print("placement replay schema, static/analytic acceleration, centripetal offset, gap and boundary checks passed")


if __name__ == "__main__":
    main()
