"""Small synthetic calibration, synchronization, gap and physics checks."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from calibrated_replay import (canonical_person, estimate_gyro_lag, fit_calibration, predict_virtual,
                               waveform_metrics, _resample_pair, _prepare_fit_record)

G = 9.80665


def record(seed: int, duration: float = 12.):
    rng = np.random.default_rng(seed)
    t = np.arange(int(duration * 100)) / 100
    phase = rng.uniform(0, 2*np.pi, 3)
    q = Rotation.from_euler("xyz", np.column_stack((.55*np.sin(.71*t+phase[0]),
        .43*np.sin(.59*t+phase[1]), .31*np.sin(.93*t+phase[2])))).as_quat()
    pos = np.column_stack((.12*np.sin(.7*t+phase[1]), .08*np.cos(.53*t+phase[2]), .09*np.sin(.9*t+phase[0])))
    return {"t": t, "q": q, "pos": pos, "valid": np.ones(len(t), bool),
            "real6": np.zeros((len(t), 6)),
            "meta": {"imu_t": t.copy(), "optical_path": f"S{seed}.csv", "person": f"S{seed}",
                     "segment": "upper", "side": "L", "exercise": "EAH", "quality": 1}}


def main():
    assert canonical_person("A3") == "A03" and canonical_person("E30") == "E30"
    try:
        canonical_person("A003")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid volunteer alias was accepted")
    truth = {"rotation_rotvec_rad": [.05, -.035, .04], "origin_board_m": [.018, -.012, .009],
             "gain": [1.04, .96, 1.02], "bias_g": [.012, -.018, .009]}
    train = [record(i) for i in range(1, 6)]
    for r in train:
        r["real6"][:, 3:] = np.nan_to_num(predict_virtual(r, truth))
    source_q = [r["q"].copy() for r in train]
    source_valid = [r["valid"].copy() for r in train]
    fitted = fit_calibration(train, {f"S{i}.csv|L|upper": 0. for i in range(1, 6)})
    assert fitted["fit_success"] and fitted["fit_records"] == len(train)
    for key in ("origin_board_m", "rotation_rotvec_rad", "gain", "bias_g"):
        assert np.allclose(fitted[key], truth[key], atol=1e-4), (key, fitted[key], truth[key])
    assert all(np.array_equal(r["q"], q) and np.array_equal(r["valid"], v)
               for r, q, v in zip(train, source_q, source_valid))
    held = record(9)
    held["real6"][:, 3:] = np.nan_to_num(predict_virtual(held, truth))
    before = waveform_metrics(held, 0., {})["dynamic_rmse_g"]
    after = waveform_metrics(held, 0., fitted)["dynamic_rmse_g"]
    assert after < before * .5, (before, after)

    # Fitting and scoring must use identical interpolation, including fractional clock offsets
    # and both sides of optical gaps; bracketing samples may lie outside the target grid.
    for fractional_lag in (.0037, -.0063):
        boundary = record(31, 10.)
        boundary['valid'][280:380] = False
        base, lever, measured = _prepare_fit_record(boundary, fractional_lag)
        fitted_prediction = Rotation.from_rotvec(truth['rotation_rotvec_rad']).inv().apply(
            base + np.einsum('nij,j->ni',lever,truth['origin_board_m']))*truth['gain']+truth['bias_g']
        scored, scored_measured = _resample_pair(boundary, fractional_lag, truth)
        assert np.array_equal(measured, scored_measured)
        assert np.allclose(fitted_prediction, scored, atol=1e-10), np.max(abs(fitted_prediction-scored))

    # Independent gyro timing must recover a known offset even with a nonzero optical crop origin.
    t = 2.0 + np.arange(1200) / 100
    theta = .5*np.sin(.73*t) + .22*np.sin(1.31*t) + .13*np.sin(2.07*t + .4)
    q = Rotation.from_rotvec(np.column_stack((theta, np.zeros((len(t), 2))))).as_quat()
    imu_t = np.arange(0., 18., .01)
    optical_w = np.abs(np.gradient(theta, .01))
    gyro = np.interp(imu_t - 2.35, t, optical_w, left=0., right=0.) * 180 / np.pi
    timing_record = {"t": t, "q": q, "valid": np.ones(len(t), bool),
                     "real6": np.column_stack((gyro, np.zeros((len(gyro), 5)))),
                     "meta": {"imu_t": imu_t}}
    lag = estimate_gyro_lag(timing_record)
    assert abs(lag["lag_s"] - 2.35) <= .03, lag

    # Surface rotation changes gravity projection; input quaternion remains untouched.
    stationary = record(20, 8.)
    stationary["q"][:] = [0., 0., 0., 1.]
    stationary["pos"][:] = 0.
    original_q = stationary["q"].copy()
    a = predict_virtual(stationary, {})
    b = predict_virtual(stationary, {}, {"fraction": .5, "surface_deg": 90.})
    expected = (Rotation.from_rotvec([np.pi/2, 0., 0.]) * Rotation.from_matrix([[-1., 0., 0.], [0., 0., 1.], [0., 1., 0.]])).inv().apply([0., 1., 0.])
    assert np.allclose(np.nanmedian(b, axis=0), expected, atol=1e-10)
    assert np.allclose(np.nanmedian(a, axis=0), Rotation.from_matrix([[-1., 0., 0.], [0., 0., 1.], [0., 1., 0.]]).inv().apply([0., 1., 0.]))
    assert np.array_equal(stationary["q"], original_q)
    assert np.isnan(a[:5]).all() and np.isnan(a[-5:]).all()

    # Invalid optical spans stay absent; waveform resampling never bridges the gap.
    gap = record(21, 8.)
    gap["valid"][280:380] = False
    x, y, time_s = _resample_pair(gap, 0., include_time=True)
    assert len(x) == len(y) == len(time_s)
    assert not np.any((time_s >= 2.8) & (time_s < 3.8))
    assert len(time_s) < 700
    bad = dict(gap); bad["t"] = gap["t"].copy(); bad["t"][100:] += .02
    try:
        predict_virtual(bad, {})
    except ValueError:
        pass
    else:
        raise AssertionError("irregular optical timestamps were accepted")
    for calibration, mount in [({"origin_board_m": [np.nan, 0, 0]}, None),
                               ({"gain": [0, 1, 1]}, None),
                               ({}, {"fraction": .5, "surface_deg": np.inf}),
                               ({"geometry": {"upper": {"length_m": np.inf}}}, {"fraction": .5})]:
        try:
            predict_virtual(stationary, calibration, mount)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid calibration geometry accepted")
    print("calibrated replay synthetic recovery, timing, gravity/frame, surface, gap and immutability checks passed")


if __name__ == "__main__":
    main()
