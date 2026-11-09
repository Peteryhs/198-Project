import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import augmentation_pipeline as ap


def main():
    cfg = ap.validate_config({"orientation": {"max_degrees": 40.0}, "lowpass_hz": None,
                              "bias_g": [0.1, -0.2, 0.3], "noise_std_g": 0.01,
                              "quantization_step_g": 0.005, "clip_g": 2.0})
    t = np.arange(500) / 100
    gravity = np.tile([0.0, 0.0, 1.0], (len(t), 1))
    pair = np.c_[gravity, gravity]
    c = ap.validate_config({"orientation": {"max_degrees": 0.0}, "lowpass_hz": None,
                             "bias_g": [0, 0, 0], "gain": [1, 1, 1], "noise_std_g": 0,
                             "quantization_step_g": None, "clip_g": 3})
    rotated, detail = ap.transform_with_provenance(pair, {**c, "orientation": {"max_degrees": 35.0}}, 17)
    assert np.allclose(np.linalg.norm(rotated[:, :3], axis=1), 1, atol=1e-12)
    assert np.allclose(np.linalg.norm(rotated[:, 3:], axis=1), 1, atol=1e-12)
    assert np.allclose(rotated[:, :3], gravity @ np.asarray(detail["orientation_matrices"][0]).T)
    assert np.allclose(rotated[:, 3:], gravity @ np.asarray(detail["orientation_matrices"][1]).T)
    assert np.array_equal(rotated, ap.transform(pair, {**c, "orientation": {"max_degrees": 35.0}}, 17))
    assert not np.array_equal(rotated, ap.transform(pair, {**c, "orientation": {"max_degrees": 35.0}}, 18))
    x = np.c_[3 + np.sin(t), np.cos(t), np.ones_like(t), 3 + np.sin(t), np.cos(t), np.ones_like(t)]
    y = ap.transform(x, cfg, 9)
    assert np.isfinite(y).all() and y.shape == x.shape and np.max(np.abs(y)) <= 2
    # Constant gravity stays constant because the causal filter starts at its first sample.
    lp = ap.transform(pair, {**c, "lowpass_hz": 20.0}, 0)
    assert np.allclose(lp[20:-20], pair[20:-20], atol=1e-5)
    quant = ap.transform(pair, {**c, "quantization_step_g": 0.1}, 0)
    assert np.allclose(quant / 0.1, np.round(quant / 0.1))
    known = ap.transform(np.tile([0.5, -0.5, 0.25], (100, 1)), {**c, "gain": [2, 0.5, 4], "bias_g": [0.1, 0.2, -0.1]}, 0)
    assert np.allclose(known[20], [1.1, -0.05, 0.9])
    clipped = ap.transform(np.tile([2.0, -2.0, 0.25], (100, 1)), {**c, "clip_g": 1}, 0)
    assert np.array_equal(clipped[20], [1, -1, .25])
    # With noise disabled, the causal low-pass prefix cannot depend on future samples.
    lowpass_cfg = {**c, "lowpass_hz": 8.0}
    signal = np.c_[np.sin(2*np.pi*2*t), np.sin(2*np.pi*30*t), np.zeros_like(t)]
    full = ap.transform(signal, lowpass_cfg, 4)
    prefix = ap.transform(signal[:200], lowpass_cfg, 4)
    assert np.allclose(full[:200], prefix)
    assert np.std(full[100:, 1]) < 0.5 * np.std(signal[100:, 1])
    assert ap.config_hash(cfg) == ap.config_hash(ap.validate_config(cfg))
    assert ap.config_hash(cfg) != ap.config_hash({**cfg, "seed": cfg["seed"] + 1})
    for bad in ({"orientation": {"max_degrees": 181}}, {"lowpass_hz": 50}, {"clip_g": 0}, {"sample_rate_hz": 99},
                {"augmentation_count": 0}, {"time_warp": 0.9}, {"noise_std_g": True},
                {"orientation": {"max_degrees": True}}, {"gain": [True, 1, 1]}):
        try:
            ap.validate_config(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid config accepted: {bad}")
    for bad_seed in (True, -1):
        try:
            ap.transform(pair, c, bad_seed)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid transform seed accepted")
    try:
        ap.validate_config({"version": True})
    except ValueError:
        pass
    else:
        raise AssertionError("boolean version accepted")
    try:
        ap.transform(np.full((20, 6), np.nan), c, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("nonfinite input accepted")
    subjects = np.array(["A01", "A01", "A02", "A03"])
    train, test = ap.loso_indices(subjects, "A02")
    assert set(subjects[train]) == {"A01", "A03"} and np.array_equal(test, [2])
    assert not (set(subjects[train]) & {"A02"})
    print("augmentation math, deterministic lineage keys, config refusal, clipping and LOSO split checks passed")


if __name__ == "__main__":
    main()
