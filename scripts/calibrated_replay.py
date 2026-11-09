"""Train-only optical-to-IMU calibration and held-out waveform diagnostics.

Optical frame time and IMU uptime are separate clocks. This module never silently
aligns them: `meta['imu_t']` must be mapped explicitly before waveform scoring.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from scipy.signal import savgol_filter, correlate, correlation_lags

from placement_replay import G, read_board, runs
from modelling_environment import check_environment

PINS = check_environment()

PATTERN = re.compile(r"^optical (?:interp|raw)/rigid_bodies/upper/([A-E])/([A-E]\d{1,2})(EAH|EFE|SQZ)([01])_1(?:_interp)?\.csv$")
BOARD_FROM_SENSOR = Rotation.from_matrix([[-1., 0., 0.], [0., 0., 1.], [0., 1., 0.]])
GEOMETRY = {"upper": {"length_m": .30, "radius_m": .045}, "forearm": {"length_m": .25, "radius_m": .035}}


def canonical_person(source_person: str) -> str:
    if not re.fullmatch(r"[A-E]\d{1,2}", source_person):
        raise ValueError(f"invalid PHYTMO volunteer identifier: {source_person}")
    return f"{source_person[0]}{int(source_person[1:]):02d}"


def load_record(optical_path: Path, inertial_root: Path, side: str, segment: str) -> dict:
    """Load one board pose and its corresponding physical sensor, retaining separate clocks."""
    if side not in {"L", "R"} or segment not in GEOMETRY:
        raise ValueError("side must be L/R and segment must be upper/forearm")
    optical_path, inertial_root = Path(optical_path), Path(inertial_root)
    match = PATTERN.match(optical_path.as_posix())
    if not match:
        # Accept a non-rooted fixture basename when the canonical PHYTMO suffix is intact.
        match = re.search(r"([A-E])/([A-E]\d{1,2})(EAH|EFE|SQZ)([01])_1(?:_interp)?\.csv$", optical_path.as_posix())
    if not match:
        raise ValueError(f"not a PHYTMO upper rigid-body file: {optical_path}")
    group, source_person, exercise, quality = match.groups()
    person = canonical_person(source_person)
    t, boards = read_board(optical_path, side)
    board_i = 0 if segment == "upper" else 1
    q, pos, valid = boards[board_i]
    device = "arm" if segment == "upper" else "forearm"
    source_name = optical_path.name.replace("_interp", "")
    imu_name = person + source_name[len(source_person):]
    imu_path = inertial_root / group / f"{side}{device}" / imu_name
    with imu_path.open(newline="") as f:
        reader = csv.DictReader(f)
        fields = ["Time (s)", *(f"Gyroscope {a} (deg/s)" for a in "XYZ"),
                  *(f"Accelerometer {a} (g)" for a in "XYZ")]
        rows = [[float(row[k]) for k in fields] for row in reader]
    data = np.asarray(rows, dtype=float)
    if data.ndim != 2 or data.shape[1] != 7 or len(data) < 100:
        raise ValueError("inertial series must contain at least 100 timestamped gyro/accelerometer samples")
    imu_t, real6 = data[:, 0], data[:, 1:]
    if not np.isfinite(data).all() or np.any(np.diff(imu_t) <= 0):
        raise ValueError("inertial timestamps or six-axis values are non-finite/non-monotonic")
    return {"t": t, "q": q, "pos": pos, "valid": valid, "real6": real6,
            "meta": {"optical_t": t.copy(), "imu_t": imu_t, "person": person, "group": group,
                     "exercise": exercise, "quality": int(quality), "side": side, "segment": segment,
                     "optical_path": str(optical_path), "inertial_path": str(imu_path)}}


def _point_offset(record: dict, calibration: dict, mount: dict | None) -> np.ndarray:
    segment = record["meta"]["segment"]
    offset = np.asarray(calibration.get("origin_board_m", [0., 0., 0.]), float).copy()
    if offset.shape != (3,) or not np.isfinite(offset).all():
        raise ValueError("origin_board_m must be a finite 3-vector")
    if mount is not None:
        if set(mount) - {"fraction", "surface_deg"} or not (0 < float(mount["fraction"]) < 1):
            raise ValueError("mount must contain fraction in (0,1) and optional surface_deg")
        geometry = {**GEOMETRY[segment], **calibration.get("geometry", {}).get(segment, {})}
        angle = np.deg2rad(float(mount.get("surface_deg", 0.)))
        if not np.isfinite([angle, geometry["length_m"], geometry["radius_m"]]).all() or geometry["length_m"] <= 0 or geometry["radius_m"] < 0:
            raise ValueError("mount surface and geometry must be finite with positive length and nonnegative radius")
        offset += [(float(mount["fraction"]) - .5) * geometry["length_m"],
                   geometry["radius_m"] * (np.cos(angle) - 1.), geometry["radius_m"] * np.sin(angle)]
    return offset


def _time_runs(time_s: np.ndarray, valid: np.ndarray) -> list[np.ndarray]:
    ix = np.flatnonzero(valid)
    if not len(ix):
        return []
    dt = np.diff(time_s)
    nominal = float(np.median(dt[dt > 0]))
    cut = np.flatnonzero((np.diff(ix) > 1) | (dt[np.minimum(ix[:-1], len(dt)-1)] > 1.5 * nominal)) + 1
    return [part for part in np.split(ix, cut) if len(part)]


def predict_virtual(record: dict, calibration: dict, mount: dict | None = None) -> np.ndarray:
    """Return board-pose-derived specific force in g; gaps and derivative edges are NaN."""
    t, pos = (np.asarray(record[k], float) for k in ("t", "pos"))
    q = np.asarray(record["q"], float).copy()
    valid = np.asarray(record.get("valid", np.ones(len(t), bool)), bool).copy()
    if t.ndim != 1 or q.shape != (len(t), 4) or pos.shape != (len(t), 3) or valid.shape != t.shape:
        raise ValueError("record time, quaternion, position and validity shapes differ")
    dt = np.diff(t)
    if len(t) < 15 or not np.isfinite(t).all() or not np.allclose(dt, .01, atol=1e-5):
        raise ValueError("optical timestamps must be finite, regular at 100 Hz, and contain >=15 frames")
    valid &= np.isfinite(q).all(axis=1) & np.isfinite(pos).all(axis=1) & (np.linalg.norm(q, axis=1) > .5)
    q[~valid] = [0., 0., 0., 1.]
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    rotation = Rotation.from_quat(q)
    point = pos + rotation.apply(np.broadcast_to(_point_offset(record, calibration, mount), pos.shape))
    out = np.full((len(t), 3), np.nan)
    origin_sensor = Rotation.from_rotvec(np.asarray(calibration.get("rotation_rotvec_rad", [0., 0., 0.]), float))
    gain = np.asarray(calibration.get("gain", [1., 1., 1.]), float)
    bias = np.asarray(calibration.get("bias_g", [0., 0., 0.]), float)
    if gain.shape != (3,) or bias.shape != (3,) or np.any(gain <= 0) or not np.isfinite([*gain, *bias]).all():
        raise ValueError("gain and bias must be finite 3-vectors with positive gains")
    for run in runs(valid):
        if len(run) < 15:
            continue
        acc_world = savgol_filter(point[run], 11, 3, deriv=2, delta=.01, axis=0)
        # PHYTMO is Y-up: subtract world gravity [0,-g,0] to obtain specific force.
        force_world = acc_world - np.array([0., -G, 0.])
        surface = Rotation.from_rotvec([np.deg2rad(float((mount or {}).get("surface_deg", 0.))), 0., 0.])
        sensor_world = rotation[run] * surface * BOARD_FROM_SENSOR * origin_sensor
        virtual = sensor_world.inv().apply(force_world) / G
        out[run] = virtual * gain + bias
        # Savitzky-Golay's edge polynomial is not a trustworthy second derivative.
        out[run[:5]] = np.nan
        out[run[-5:]] = np.nan
    return out


def _resample_pair(record: dict, lag_s: float, calibration: dict | None = None, mount: dict | None = None,
                   include_time: bool = False):
    """Explicitly lag-align one record for fitting/diagnostics; never called implicitly."""
    virtual = predict_virtual(record, calibration or {}, mount)
    optical_t = np.asarray(record["t"], float) + lag_s
    imu_t = np.asarray(record["meta"]["imu_t"], float)
    measured = np.asarray(record["real6"], float)[:, 3:6]
    good = np.isfinite(virtual).all(axis=1)
    ygood = np.isfinite(measured).all(axis=1)
    opt_runs = _time_runs(optical_t, good)
    imu_runs = _time_runs(imu_t, ygood)
    xs, ys, ts = [], [], []
    for ro in opt_runs:
        for ri in imu_runs:
            lo, hi = max(optical_t[ro[0]], imu_t[ri[0]]), min(optical_t[ro[-1]], imu_t[ri[-1]])
            if hi - lo < 2:
                continue
            grid = np.arange(np.ceil(lo * 100 - 1e-6) / 100, hi + 1e-7, .01)
            if len(grid) < 200:
                continue
            x = np.column_stack([np.interp(grid, optical_t[ro], virtual[ro, j]) for j in range(3)])
            y = np.column_stack([np.interp(grid, imu_t[ri], measured[ri, j]) for j in range(3)])
            xs.append(x); ys.append(y); ts.append(grid)
    if not xs:
        raise ValueError("no >=2 s common continuous span after explicit clock mapping")
    result = (np.concatenate(xs), np.concatenate(ys), np.concatenate(ts))
    return result if include_time else result[:2]


def estimate_gyro_lag(record: dict, max_lag_s: float = 20.) -> dict:
    """Independent diagnostic lag from angular-rate magnitude; never uses acceleration fit."""
    t, q = np.asarray(record["t"], float), np.asarray(record["q"], float).copy()
    valid = np.asarray(record.get("valid", np.ones(len(t), bool)), bool).copy()
    valid &= np.isfinite(q).all(axis=1) & (np.linalg.norm(q, axis=1) > .5)
    ix = np.flatnonzero(valid)
    adjacent = (np.diff(ix) == 1) & (np.diff(t[ix]) > .008) & (np.diff(t[ix]) < .012)
    if adjacent.sum() < 100:
        return {"lag_s": None, "peak_correlation": None, "status": "insufficient optical rotation samples"}
    qa, qb = q[ix[:-1][adjacent]], q[ix[1:][adjacent]]
    qa /= np.linalg.norm(qa, axis=1, keepdims=True); qb /= np.linalg.norm(qb, axis=1, keepdims=True)
    ra, rb = Rotation.from_quat(qa), Rotation.from_quat(qb)
    optical_w = np.linalg.norm((ra.inv() * rb).as_rotvec(), axis=1) / np.diff(t[ix])[adjacent]
    optical_t = (t[ix[:-1][adjacent]] + t[ix[1:][adjacent]]) / 2
    imu_t = np.asarray(record["meta"]["imu_t"], float)
    gyro = np.linalg.norm(np.asarray(record["real6"], float)[:, :3], axis=1) * np.pi / 180.
    optical_grid = np.arange(t[0], t[-1] + 1e-7, .01)
    imu_grid = np.arange(imu_t[0], imu_t[-1] + 1e-7, .01)
    ow, om = np.zeros(len(optical_grid)), np.zeros(len(optical_grid))
    oi = np.floor((optical_t - optical_grid[0]) / .01 + .5).astype(int)
    keep = (oi >= 0) & (oi < len(ow)); ow[oi[keep]] = optical_w[keep]; om[oi[keep]] = 1.
    iw, im = np.zeros(len(imu_grid)), np.zeros(len(imu_grid))
    iruns = _time_runs(imu_t, np.isfinite(gyro))
    for run in iruns:
        grid = np.floor((imu_t[run] - imu_grid[0]) / .01 + .5).astype(int)
        keep = (grid >= 0) & (grid < len(iw)); iw[grid[keep]] = gyro[run[keep]]; im[grid[keep]] = 1.
    if om.sum() < 100 or im.sum() < 100:
        return {"lag_s": None, "peak_correlation": None, "status": "insufficient contiguous gyro samples"}
    ow[om > 0] -= np.mean(ow[om > 0]); iw[im > 0] -= np.mean(iw[im > 0])
    raw = correlate(iw * im, ow * om, mode="full", method="fft")
    lag_samples = correlation_lags(len(iw), len(ow), mode="full")
    overlap = correlate(im, om, mode="full", method="fft")
    energy_i = correlate(iw * iw * im, om, mode="full", method="fft")
    energy_o = correlate(im, ow * ow * om, mode="full", method="fft")
    score = raw / np.sqrt(np.maximum(energy_i * energy_o, 1e-20))
    allowed = np.abs(lag_samples) <= int(max_lag_s * 100)
    allowed &= overlap >= 200
    if not allowed.any():
        return {"lag_s": None, "peak_correlation": None, "status": "no allowed lag"}
    candidates = np.flatnonzero(allowed)
    peak = candidates[np.argmax(score[allowed])]
    independent = allowed & (np.abs(lag_samples - lag_samples[peak]) >= 20)
    second = float(np.max(score[independent])) if independent.any() else None
    return {"lag_s": float((imu_grid[0] - optical_grid[0]) + lag_samples[peak] * .01),
            "peak_correlation": float(score[peak]), "status": "gyro-magnitude oracle diagnostic",
            "second_peak_correlation": second,
            "peak_margin": float(score[peak] - second) if second is not None else None,
            "overlap_samples": int(round(overlap[peak]))}


def waveform_metrics(record: dict, lag_s: float, calibration: dict | None = None) -> dict:
    x, y = _resample_pair(record, lag_s, calibration)
    error = x - y
    xd, yd = x - x.mean(axis=0), y - y.mean(axis=0)
    denom = np.linalg.norm(yd)
    return {"n_samples": len(x), "duration_s": float(len(x) / 100),
            "rmse_g": float(np.sqrt(np.mean(error ** 2))), "bias_g": np.mean(error, axis=0).tolist(),
            "correlation_xyz": [float(np.corrcoef(x[:, i], y[:, i])[0, 1]) if np.std(x[:, i]) > 0 and np.std(y[:, i]) > 0 else None for i in range(3)],
            "dynamic_rmse_g": float(np.sqrt(np.mean((xd - yd) ** 2))),
            "dynamic_nrmse": float(np.linalg.norm(xd - yd) / max(denom, 1e-12)),
            "dynamic_correlation": float(np.sum(xd * yd) / max(np.linalg.norm(xd) * np.linalg.norm(yd), 1e-12)),
            "measured_dynamic_rms_g": float(np.sqrt(np.mean(yd ** 2)))}


def aligned_waveforms(record: dict, lag_s: float, calibration: dict) -> dict:
    """Return baseline, fitted and measured series on exactly the same oracle-aligned grid."""
    base, real, time_s = _resample_pair(record, lag_s, include_time=True)
    fitted, real2, fitted_t = _resample_pair(record, lag_s, calibration, include_time=True)
    if not np.array_equal(real, real2):
        raise AssertionError("baseline and fitted arms must share an identical measured cohort/grid")
    if not np.array_equal(time_s, fitted_t):
        raise AssertionError("baseline and fitted arms must use identical time samples")
    return {"time_s": time_s, "real_g": real, "baseline_g": base, "calibrated_g": fitted,
            "meta": {k: record["meta"][k] for k in ("person", "exercise", "quality", "side", "segment", "optical_path", "inertial_path")}}


def save_waveform_cache(record: dict, lag_s: float, calibration: dict, path: Path) -> None:
    """Write an ignored compact held-out waveform example for plotting/review."""
    data = aligned_waveforms(record, lag_s, calibration)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, time_s=data["time_s"], real_g=data["real_g"],
                        baseline_g=data["baseline_g"], calibrated_g=data["calibrated_g"],
                        metadata_json=json.dumps(data["meta"]))


def fit_calibration(train_records: list[dict], lags_s: dict[str, float] | None = None,
                    config: dict | None = None) -> dict:
    """Fit a shared small rotation, board origin, axis gains and biases on training people only."""
    lags_s = lags_s or {}
    bounds_cfg = (config or {}).get("bounds", {})
    rotation_deg = float(bounds_cfg.get("rotation_correction_deg", 25.))
    origin_m = float(bounds_cfg.get("origin_board_m_each_axis", .10))
    gain_bounds = np.asarray(bounds_cfg.get("axis_gain", [.8, 1.2]), float)
    bias_bounds = np.asarray(bounds_cfg.get("axis_bias_g", [-.15, .15]), float)
    if (rotation_deg <= 0 or origin_m <= 0 or gain_bounds.shape != (2,) or bias_bounds.shape != (2,)
            or not np.isfinite([rotation_deg, origin_m, *gain_bounds, *bias_bounds]).all()
            or gain_bounds[0] <= 0 or gain_bounds[0] >= gain_bounds[1] or bias_bounds[0] >= bias_bounds[1]):
        raise ValueError("invalid calibration fit bounds in config")
    pairs = []
    for record in train_records:
        key = record["meta"]["optical_path"] + "|" + record["meta"]["side"] + "|" + record["meta"]["segment"]
        prepared = _prepare_fit_record(record, float(lags_s.get(key, 0.)))
        if prepared is not None:
            if len(prepared[0]) > 400:
                take = np.linspace(0, len(prepared[0]) - 1, 400).astype(int)
                prepared = tuple(a[take] for a in prepared)
            pairs.append(prepared)
    if len(pairs) < 4:
        raise ValueError("calibration requires at least four training records")
    # Train records receive equal weight regardless of duration or valid-frame count.
    def residual(params):
        correction = Rotation.from_rotvec(params[:3])
        origin, gain, bias = params[3:6], params[6:9], params[9:12]
        chunks = []
        for base_sensor, offset_sensor, y in pairs:
            nominal = base_sensor + np.einsum("nij,j->ni", offset_sensor, origin)
            x = correction.inv().apply(nominal) * gain + bias
            chunks.append((x - y) / np.sqrt(len(x)))
        return np.concatenate(chunks).ravel()
    lower = np.r_[np.full(3, -np.deg2rad(rotation_deg)), np.full(3, -origin_m), np.full(3, gain_bounds[0]), np.full(3, bias_bounds[0])]
    upper = np.r_[np.full(3, np.deg2rad(rotation_deg)), np.full(3, origin_m), np.full(3, gain_bounds[1]), np.full(3, bias_bounds[1])]
    result = least_squares(residual, np.r_[np.zeros(6), np.ones(3), np.zeros(3)], bounds=(lower, upper),
                           loss="soft_l1", f_scale=.1, max_nfev=25)
    p = result.x
    singular = np.linalg.svd(result.jac, compute_uv=False)
    rank = int(np.linalg.matrix_rank(result.jac))
    bound_hits = [i for i, (v, lo, hi) in enumerate(zip(p, lower, upper))
                  if min(abs(v - lo), abs(v - hi)) < 1e-4]
    return {"rotation_rotvec_rad": p[:3].tolist(), "origin_board_m": p[3:6].tolist(),
            "gain": p[6:9].tolist(), "bias_g": p[9:12].tolist(), "filter_hz": None,
            "fit_rmse_g": float(np.sqrt(np.mean(result.fun ** 2))), "fit_success": bool(result.success),
            "fit_rmse_scope": "optimizer residual normalized by sqrt(samples per source); use held-out waveform metrics for physical prediction error",
            "fit_message": result.message, "fit_records": len(pairs), "jacobian_rank": rank,
            "jacobian_singular_values": singular.tolist(), "transform_identifiable": rank == 12,
            "bound_hits": bound_hits,
            "bounds": {"rotation_correction_deg": rotation_deg, "origin_board_m_each_axis": origin_m,
                       "axis_gain": gain_bounds.tolist(), "axis_bias_g": bias_bounds.tolist()}}


def _prepare_fit_record(record: dict, lag_s: float):
    """Precompute rigid-body acceleration and lever-arm basis once for optimizer calls."""
    t, pos = np.asarray(record["t"], float), np.asarray(record["pos"], float)
    q = np.asarray(record["q"], float).copy()
    valid = np.asarray(record.get("valid", np.ones(len(t), bool)), bool).copy()
    valid &= np.isfinite(q).all(axis=1) & np.isfinite(pos).all(axis=1) & (np.linalg.norm(q, axis=1) > .5)
    q[~valid] = [0., 0., 0., 1.]
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    board_rot = Rotation.from_quat(q)
    optical_t = t + lag_s
    imu_t = np.asarray(record["meta"]["imu_t"], float)
    measured = np.asarray(record["real6"], float)[:, 3:6]
    imu_good = np.isfinite(measured).all(axis=1)
    fixed = Rotation.from_matrix(BOARD_FROM_SENSOR.as_matrix())
    chunks = []
    for ro in runs(valid):
        if len(ro) < 15:
            continue
        run_t, run_r = t[ro], board_rot[ro]
        acc_world = savgol_filter(pos[ro], 11, 3, deriv=2, delta=.01, axis=0)
        lever_world = np.stack([savgol_filter(run_r.apply(axis), 11, 3, deriv=2, delta=.01, axis=0) / G
                                for axis in np.eye(3)], axis=2)
        base_force = (acc_world - np.array([0., -G, 0.])) / G
        base_sensor = fixed.inv().apply(run_r.inv().apply(base_force))
        offset_sensor = np.stack([fixed.inv().apply(run_r.inv().apply(lever_world[:, :, j]))
                                  for j in range(3)], axis=2)
        # Discard five derivative edge samples before any interpolation.
        valid_ro = ro[5:-5]
        for ri in _time_runs(imu_t, imu_good):
            lo, hi = max(optical_t[valid_ro[0]], imu_t[ri[0]]), min(optical_t[valid_ro[-1]], imu_t[ri[-1]])
            if hi - lo < 2:
                continue
            grid = np.arange(np.ceil(lo * 100 - 1e-6) / 100, hi + 1e-7, .01)
            if len(grid) < 200:
                continue
            # Keep bracketing samples at each target-grid edge, as waveform scoring does.
            grid_source = optical_t[valid_ro]
            def interp_array(a):
                flat = a[5:-5].reshape(len(valid_ro), -1)
                return np.column_stack([np.interp(grid, grid_source, flat[:, j]) for j in range(flat.shape[1])])
            base_grid = interp_array(base_sensor).reshape(len(grid), 3)
            offset_grid = interp_array(offset_sensor).reshape(len(grid), 3, 3)
            imu_grid = np.column_stack([np.interp(grid, imu_t[ri], measured[ri, j]) for j in range(3)])
            # These arrays are already in the published nominal sensor basis; the optimizer
            # applies only the small residual correction after this transform.
            chunks.append((base_grid, offset_grid, imu_grid))
    if not chunks:
        return None
    return tuple(np.concatenate([c[i] for c in chunks], axis=0) for i in range(3))


def calibration_gate(fold_results: list[dict], acceptance: dict) -> dict:
    reasons = []
    clock_residuals, clock_counts, test_counts, params, baseline, calibrated = [], 0, 0, [], [], []
    if not fold_results:
        reasons.append("no completed held-out folds")
    for fold in fold_results:
        test_counts += len(fold.get("rows", []))
        params.extend(p for p in fold.get("params_by_sensor", {}).values() if p)
        for row in fold.get("rows", []):
            if row.get("clock_residual_s") is not None:
                clock_counts += 1
                clock_residuals.append(abs(row["clock_residual_s"]))
            a, b = row.get("primary_train_mapped", {}).get("baseline"), row.get("primary_train_mapped", {}).get("calibrated")
            if a and b and "dynamic_rmse_g" in a and "dynamic_rmse_g" in b:
                baseline.append(a); calibrated.append(b)
    clock_coverage = clock_counts / max(test_counts, 1)
    clock_p95 = float(np.percentile(clock_residuals, 95)) if clock_residuals else None
    max_clock = float(acceptance["clock_residual_abs_p95_s_max"])
    min_coverage = float(acceptance["minimum_heldout_clock_coverage"])
    clock_pass = clock_p95 is not None and clock_p95 <= max_clock and clock_coverage >= min_coverage
    if not clock_pass:
        reasons.append("train-median clock mapping failed held-out gyro timing residual/coverage criteria")
    min_rank = int(acceptance["minimum_transform_jacobian_rank"])
    rank_pass = bool(params) and all(int(p.get("jacobian_rank", 0)) >= min_rank for p in params)
    if not rank_pass:
        reasons.append("one or more train-only physical transforms are unidentifiable")
    if baseline:
        threshold = float(acceptance["minimum_measured_dynamic_rms_g"])
        active = [(a, b) for a, b in zip(baseline, calibrated) if b["measured_dynamic_rms_g"] >= threshold]
        if not active:
            base_rmse = cal_rmse = improvement = corr = nrmse = bias_max = None
            waveform_pass = False
        else:
            active_base, active_cal = zip(*active)
            base_rmse = float(np.mean([r["dynamic_rmse_g"] for r in active_base]))
            cal_rmse = float(np.mean([r["dynamic_rmse_g"] for r in active_cal]))
            improvement = 1 - cal_rmse / max(base_rmse, 1e-12)
            corr = float(np.median([r["dynamic_correlation"] for r in active_cal]))
            nrmse = float(np.median([r["dynamic_nrmse"] for r in active_cal]))
            bias_max = float(max(np.max(np.abs(r["bias_g"])) for r in calibrated))
            waveform_pass = (corr >= acceptance["minimum_dynamic_correlation"]
                             and nrmse <= acceptance["maximum_dynamic_nrmse"]
                             and bias_max <= acceptance["maximum_abs_axis_bias_g"]
                             and improvement >= acceptance["minimum_dynamic_rmse_improvement_fraction"])
    else:
        base_rmse = cal_rmse = improvement = corr = nrmse = bias_max = None
        waveform_pass = False
    if not waveform_pass:
        reasons.append("matched held-out waveform metrics failed preregistered improvement/fidelity criteria")
    return {"passed": not reasons, "reasons": reasons,
            "clock": {"heldout_lag_coverage": clock_coverage, "heldout_residual_p95_abs_s": clock_p95,
                      "threshold_s": max_clock, "minimum_coverage": min_coverage, "passed": clock_pass},
            "transform_identifiability": {"min_required_rank": min_rank, "fitted_transforms": len(params), "passed": rank_pass},
            "matched_waveform": {"n_matched_records": len(baseline), "baseline_dynamic_rmse_g_mean": base_rmse,
                                 "minimum_dynamic_rms_g_for_fidelity": acceptance["minimum_measured_dynamic_rms_g"],
                                 "n_dynamic_active_records": sum(r["measured_dynamic_rms_g"] >= acceptance["minimum_measured_dynamic_rms_g"] for r in calibrated),
                                 "calibrated_dynamic_rmse_g_mean": cal_rmse, "relative_improvement": improvement,
                                 "calibrated_dynamic_correlation_median": corr, "calibrated_dynamic_nrmse_median": nrmse,
                                 "max_axis_bias_abs_g": bias_max, "passed": waveform_pass},
            "rule": "all clock, train-only identifiability, and matched held-out waveform criteria must pass"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("data/phytmo"))
    ap.add_argument("--out", type=Path, default=Path("docs/runs/phase4/calibration.json"))
    ap.add_argument("--config", type=Path, default=Path("configs/replay-calibration.json"))
    ap.add_argument("--cache-dir", type=Path, default=Path("data/phase4-cache"))
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    records, rejected = [], []
    optical_root = args.root / "optical raw/rigid_bodies/upper"
    inertial_root = args.root / "inertial/upper"
    optical_files = sorted(optical_root.glob("*/*_1.csv"))
    if not optical_files:
        optical_files = sorted((args.root / "optical interp/rigid_bodies/upper").glob("*/*_interp.csv"))
    for optical in optical_files:
        for side in "LR":
            for segment in ("upper", "forearm"):
                try:
                    records.append(load_record(optical, inertial_root, side, segment))
                except (OSError, ValueError) as exc:
                    rejected.append({"file": str(optical), "side": side, "segment": segment, "reason": str(exc)})
    by_person = sorted({r["meta"]["person"] for r in records})
    lag_info = {}
    for rec in records:
        key = rec["meta"]["optical_path"] + "|" + rec["meta"]["side"] + "|" + rec["meta"]["segment"]
        lag_info[key] = estimate_gyro_lag(rec, cfg["timing"]["max_relative_lag_search_s"])
    folds = []
    cache_dir = args.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    example_written = False
    for heldout in by_person:
        train = [r for r in records if r["meta"]["person"] != heldout]
        test = [r for r in records if r["meta"]["person"] == heldout]
        params_by_sensor, train_lags, lag_medians = {}, {}, {}
        fit_errors = {}
        for segment in GEOMETRY:
            for side in "LR":
                sensor_key = f"{side}|{segment}"
                segment_train = [r for r in train if r["meta"]["segment"] == segment and r["meta"]["side"] == side
                                 and lag_info[r["meta"]["optical_path"] + "|" + side + "|" + segment]["lag_s"] is not None
                                 and lag_info[r["meta"]["optical_path"] + "|" + side + "|" + segment]["peak_correlation"] >= cfg["timing"]["minimum_gyro_magnitude_correlation"]
                                 and lag_info[r["meta"]["optical_path"] + "|" + side + "|" + segment]["peak_margin"] >= cfg["timing"]["minimum_peak_margin"]]
                for r in segment_train:
                    key = r["meta"]["optical_path"] + "|" + side + "|" + segment
                    train_lags[key] = lag_info[key]["lag_s"]
                try:
                    params_by_sensor[sensor_key] = fit_calibration(segment_train, train_lags, cfg)
                except (ValueError, np.linalg.LinAlgError) as exc:
                    params_by_sensor[sensor_key] = None
                    fit_errors[sensor_key] = f"{type(exc).__name__}: {exc}"
                values = [train_lags[r["meta"]["optical_path"] + "|" + side + "|" + segment]
                          for r in segment_train if r["meta"]["side"] == side
                          and r["meta"]["optical_path"] + "|" + side + "|" + segment in train_lags]
                lag_medians[f"{side}|{segment}"] = float(np.median(values)) if values else None
        rows = []
        for rec in test:
            m = rec["meta"]; key = m["optical_path"] + "|" + m["side"] + "|" + m["segment"]
            params = params_by_sensor[f"{m['side']}|{m['segment']}"]
            train_lag = lag_medians.get(f"{m['side']}|{m['segment']}")
            oracle = lag_info[key]
            row = {"person": heldout, "exercise": m["exercise"], "quality": m["quality"],
                   "source_id": f"{m['optical_path']}|{m['side']}|{m['segment']}",
                   "side": m["side"], "segment": m["segment"], "train_median_lag_s": train_lag,
                   "heldout_gyro_oracle_lag": oracle,
                   "clock_residual_s": oracle["lag_s"] - train_lag if train_lag is not None and oracle["lag_s"] is not None else None}
            for name, lag in (("primary_train_mapped", train_lag), ("oracle_diagnostic", oracle["lag_s"])):
                if lag is None:
                    row[name] = {"error": "no training lag"}
                    continue
                try:
                    row[name] = {"baseline": waveform_metrics(rec, lag),
                                 "calibrated": waveform_metrics(rec, lag, params) if params else None}
                    if params and name == "primary_train_mapped" and not example_written:
                        cache_name = f"example-{heldout}-{m['exercise']}-{m['quality']}-{m['side']}-{m['segment']}-primary.npz"
                        save_waveform_cache(rec, lag, params, cache_dir / cache_name)
                        row["cache"] = str(cache_dir / cache_name)
                        example_written = True
                except (ValueError, IndexError) as exc:
                    row[name] = {"error": f"{type(exc).__name__}: {exc}"}
            if params is None:
                row["calibration_error"] = fit_errors.get(f"{m['side']}|{m['segment']}", "fit unavailable")
            rows.append(row)
        # Oracle heldout lag never enters the primary train-mapped comparison above.
        residuals = [r["heldout_gyro_oracle_lag"]["lag_s"] - r["train_median_lag_s"] for r in rows
                     if r["train_median_lag_s"] is not None and r["heldout_gyro_oracle_lag"]["lag_s"] is not None]
        folds.append({"heldout_person": heldout, "train_people": [p for p in by_person if p != heldout],
                      "heldout_people": [heldout],
                      "train_source_ids": [f"{r['meta']['optical_path']}|{r['meta']['side']}|{r['meta']['segment']}" for r in train],
                      "heldout_source_ids": [f"{r['meta']['optical_path']}|{r['meta']['side']}|{r['meta']['segment']}" for r in test],
                      "n_train_people": len(by_person) - 1,
                      "n_train_records": len(train), "n_test_records": len(test),
                      "train_lag_medians_s": lag_medians, "fit_errors": fit_errors,
                      "params_by_sensor": params_by_sensor, "clock_status": "training median from independent gyro magnitude; per-record heldout gyro lag diagnostic only",
                      "heldout_clock_residual_median_s": float(np.median(residuals)) if residuals else None,
                      "heldout_clock_residual_p95_abs_s": float(np.percentile(np.abs(residuals), 95)) if residuals else None,
                      "n_heldout_clock_residuals": len(residuals), "rows": rows})
        print(f"LOSO {heldout}: train={len(train)} heldout={len(test)}; fitted sensors={sum(p is not None for p in params_by_sensor.values())}/4", flush=True)
    report = {"source": "PHYTMO upper rigid-body pose and measured upper/forearm IMUs",
              "cohort": {"n_people": len(by_person), "people": by_person, "n_records": len(records)},
              "rejected": rejected, "clock_status": "primary uses train-only median gyro event lag; heldout gyro oracle lag is diagnostic only",
              "calibration_gate": calibration_gate(folds, cfg["acceptance"]), "folds": folds,
              "runtime": {"python": platform.python_version(), "pins": PINS,
                          "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
                          "calibration_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
              "acceptance_criteria": cfg["acceptance"],
              "interpretation": "Primary heldout results use a train-only median optical-to-IMU lag by side and segment. A per-record heldout lag estimated from gyro/optical rotation is reported separately as reference-assisted diagnostic and never used for primary scoring or fitting. Waveform metrics are calibration evidence only; absent published shared clock timestamps, they do not qualify as deployment validation."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"rejected", "folds"}}, indent=2))


if __name__ == "__main__":
    main()
