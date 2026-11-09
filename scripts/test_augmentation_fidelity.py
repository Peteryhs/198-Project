import numpy as np
from augmentation_fidelity import metrics


def main():
    t = np.arange(1000) / 100
    segment = np.c_[.3 * np.sin(2 * np.pi * t), .2 * np.cos(2 * np.pi * t), 1 + .2 * np.sin(2 * np.pi * t)]
    x = np.c_[segment, segment]
    original = metrics(x)
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    rotated = metrics(np.c_[segment @ rotation.T, segment @ rotation.T])
    for a, b in zip(original["segments"], rotated["segments"]):
        for key in ["magnitude_envelope_g", "dominant_hz", "hf_fraction", "rail_fraction"]:
            assert np.isclose(a[key], b[key])
        assert a["dominant_hz"] == 1
    assert np.isclose(original["upper_forearm_magnitude_correlation"], 1)
    static = metrics(np.ones((1000, 6)))
    assert static["upper_forearm_magnitude_correlation"] is None
    assert static["segments"][0]["dominant_hz"] is None
    assert metrics(np.full((1000, 6), 3))["segments"][0]["rail_fraction"] == 1
    try:
        metrics(np.full((100, 6), np.nan))
    except ValueError:
        pass
    else:
        raise AssertionError("nonfinite input accepted")
    print("Fidelity diagnostics: analytic 1 Hz, rigid-rotation magnitude invariance, pair relation, rail fractions, constant/invalid edge cases passed")


if __name__ == "__main__":
    main()
