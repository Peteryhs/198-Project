"""Exploratory optical pose replay for hypothetical mount locations; never model accuracy."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from scipy.signal import savgol_filter

G = 9.80665
PATTERN = re.compile(r"^optical interp/rigid_bodies/upper/([A-E])/([A-E]\d{2})(EAH|EFE|SQZ)([01])_1_interp\.csv$")


def runs(valid):
    indices = np.flatnonzero(valid)
    if not len(indices):
        return []
    return [part for part in np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1) if len(part)]


def read_board(path: Path, side: str):
    """Return time, position and local-to-world rotation for arm and forearm boards."""
    names = ("thigh2", "shin2") if side == "L" else ("thigh", "shin")
    with path.open(newline="") as handle:
        header = [next(csv.reader([next(handle)])) for _ in range(7)]
    kinds, labels = header[2], header[3]
    cols = [1]
    for name in names:
        block = [i for i, (kind, label, field) in enumerate(zip(kinds, labels, header[5]))
                 if kind == "Rigid Body" and label == name and field in ("Rotation", "Position")]
        if len(block) != 7:
            raise ValueError(f"{name}: expected quaternion plus position, got {len(block)} columns")
        cols.extend(block)
    data = np.genfromtxt(path, delimiter=",", skip_header=7, usecols=cols)
    if data.ndim != 2 or not len(data):
        raise ValueError("no optical samples")
    boards = []
    for start in (1, 8):
        q = data[:, start:start + 4]
        pos = data[:, start + 4:start + 7]
        valid = np.isfinite(q).all(axis=1) & np.isfinite(pos).all(axis=1) & (np.linalg.norm(q, axis=1) > .5)
        boards.append((q, pos, valid))
    return data[:, 0], boards


def virtual_mount(time_s, quaternion_xyzw, board_position_m, valid, fraction, surface_deg, length_m, radius_m,
                  board_from_sensor=None):
    """Rigid-body acceleration at a hypothetical point; board-to-chip origin is unknown."""
    time_s = np.asarray(time_s, dtype=float)
    q = np.asarray(quaternion_xyzw, dtype=float).copy()
    board_position_m = np.asarray(board_position_m, dtype=float)
    valid = np.asarray(valid, dtype=bool).copy()
    if time_s.ndim != 1 or q.shape != (len(time_s), 4) or board_position_m.shape != (len(time_s), 3) or valid.shape != time_s.shape or len(time_s) < 15:
        raise ValueError("time, pose and validity arrays have incompatible shapes")
    if not np.isfinite(time_s).all() or not np.allclose(np.diff(time_s), .01, atol=1e-5):
        raise ValueError("optical timestamps must be finite, forward and regular at 100 Hz")
    if (not np.isfinite([fraction, surface_deg, length_m, radius_m]).all()
            or not 0 < fraction < 1 or length_m <= 0 or radius_m < 0):
        raise ValueError("placement fraction, surface angle and geometry are outside valid bounds")
    dt = .01
    valid &= np.isfinite(q).all(axis=1) & np.isfinite(board_position_m).all(axis=1) & (np.linalg.norm(q, axis=1) > .5)
    q[~valid] = [0., 0., 0., 1.]
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    rot = Rotation.from_quat(q)
    local_offset = np.zeros((len(time_s), 3))
    local_offset[:, 0] = (fraction - .5) * length_m
    angle = np.deg2rad(surface_deg)
    # Lateral-midpoint optical board origin is the reference surface point; circumference is assumed.
    local_offset[:, 1] = radius_m * (np.cos(angle) - 1.)
    local_offset[:, 2] = radius_m * np.sin(angle)
    point = board_position_m + rot.apply(local_offset)
    out = np.full_like(point, np.nan, dtype=float)
    for run in runs(valid):
        if len(run) < 15:
            continue
        p = point[run]
        a = savgol_filter(p, 11, 3, deriv=2, delta=dt, axis=0)
        sensor = rot[run] * Rotation.from_rotvec([np.deg2rad(surface_deg), 0, 0])
        if board_from_sensor is not None:
            sensor *= board_from_sensor
        # Specific force is translational acceleration minus world gravity (Y-up in PHYTMO).
        out[run] = sensor.inv().apply(a - np.array([0., -G, 0.])) / G
    return out


def read_inertial(path):
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        names = ["Time (s)"] + [f"Accelerometer {axis} (g)" for axis in "XYZ"]
        values = np.asarray([[float(row[name]) for name in names] for row in reader])
    time_s, values = values[:, 0], values[:, 1:]
    if len(time_s) < 100 or not np.isfinite(time_s).all() or np.any(np.diff(time_s) <= 0):
        raise ValueError("inertial timestamps are missing or non-monotonic")
    dt = float(np.median(np.diff(time_s)))
    sample_valid = np.isfinite(values).all(axis=1)
    boundaries = np.flatnonzero((np.diff(time_s) > 1.5 * dt) | ~sample_valid[:-1] | ~sample_valid[1:]) + 1
    signal_runs = [r for r in np.split(np.arange(len(time_s)), boundaries) if len(r) and sample_valid[r].all()]
    if not signal_runs:
        raise ValueError("no finite inertial samples")
    longest = max(signal_runs, key=len)
    dynamic = values[sample_valid] - np.median(values[sample_valid], axis=0)
    magnitude = np.linalg.norm(dynamic, axis=1)
    spectrum_magnitude = np.linalg.norm(values[longest] - np.median(values[longest], axis=0), axis=1)
    from scipy.signal import welch
    freq, power = welch(spectrum_magnitude, fs=1. / dt, nperseg=min(len(spectrum_magnitude), 1000))
    primary = (freq >= .15) & (freq <= 3.)
    total = float(power[freq > 0].sum())
    return {"dynamic_rms_g": float(np.sqrt(np.mean(dynamic**2))),
            "dynamic_p95_g": float(np.percentile(magnitude, 95)),
            "axis_p10_p50_p90_g": np.percentile(values[sample_valid], [10, 50, 90], axis=0).T.tolist(),
            "clipped_fraction_at_3g": float(np.mean(np.abs(values[sample_valid]) >= 3.)),
            "dominant_hz": float(freq[primary][np.argmax(power[primary])]) if primary.any() else None,
            "hf_fraction": float(power[(freq >= 5.) & (freq <= 40.)].sum() / max(total, 1e-20)),
            "longest_contiguous_samples": int(len(longest)), "coverage_fraction": float(sample_valid.mean())}


def summarize(accel_g):
    valid = np.isfinite(accel_g).all(axis=1)
    x = accel_g[valid]
    if len(x) < 100:
        raise ValueError("fewer than 1s valid optical acceleration")
    dynamic = x - np.median(x, axis=0)
    mag = np.linalg.norm(dynamic, axis=1)
    longest = max(runs(valid), key=len)
    spectral_mag = np.linalg.norm(accel_g[longest] - np.median(accel_g[longest], axis=0), axis=1)
    from scipy.signal import welch
    freq, power = welch(spectral_mag, fs=100, nperseg=min(len(spectral_mag), 1000))
    primary = (freq >= .15) & (freq <= 3.)
    total = float(power[freq > 0].sum())
    return {"valid_samples": int(len(x)), "coverage_fraction": float(valid.mean()),
            "longest_contiguous_samples": int(len(longest)), "dynamic_rms_g": float(np.sqrt(np.mean(dynamic**2))),
            "dynamic_p95_g": float(np.percentile(mag, 95)), "axis_rms_g": np.sqrt(np.mean(dynamic**2, axis=0)).tolist(),
            "axis_p10_p50_p90_g": np.percentile(x, [10, 50, 90], axis=0).T.tolist(),
            "fraction_at_or_beyond_3g": float(np.mean(np.abs(x) >= 3)),
            "dominant_hz": float(freq[primary][np.argmax(power[primary])]) if primary.any() else None,
            "hf_fraction": float(power[(freq >= 5.) & (freq <= 40.)].sum() / max(total, 1e-20))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("data/phytmo"))
    ap.add_argument("--placements", type=Path, default=Path("simulation/placements.json"))
    ap.add_argument("--out", type=Path, default=Path("docs/runs/phase3/simulation-placement.json"))
    args = ap.parse_args()
    cfg = json.loads(args.placements.read_text())
    candidates = cfg["candidates"]
    if cfg.get("version") != 1 or len(candidates) != 4:
        raise ValueError("expected placements schema v1 with four candidates")
    # Gate is declared before replay: optical-to-inertial clock offset/drift and board-to-chip
    # extrinsics must be identified from training people only, then pass held-out people untouched.
    # PHYTMO metadata has device uptime and optical frame time, but no shared timestamp or extrinsic.
    gate = {"train_people": "A-D", "held_out_people": "E", "calibration": "fit clock and board-to-chip transform using A-D only", "pass_rule": "all held-out paired records have identifiable shared clock (residual lag <=10 ms) and measured board-to-chip transform; otherwise no measured-site calibration is claimed", "passed": False, "failed_before_metric_comparison": ["inertial timestamps are time since device turn-on; optical timestamps are frame-relative and no shared start event or optical-to-inertial clock mapping is supplied", "optical rigid-body pose is for the mounting board; chip-to-board translation/rotation is unmeasured"]}
    rows = []
    rejected = []
    # PHYTMO describes this IMU-to-board basis: X_I=-X_B, Y_I=Z_B, Z_I=Y_B.
    board_from_sensor = Rotation.from_matrix([[-1., 0., 0.], [0., 0., 1.], [0., 1., 0.]])
    for path in sorted(args.root.glob("optical interp/rigid_bodies/upper/*/*_interp.csv")):
        member = path.relative_to(args.root).as_posix()
        match = PATTERN.match(member)
        if not match:
            continue
        group, person, exercise, quality = match.groups()
        for side in "LR":
            try:
                time_s, boards = read_board(path, side)
            except (OSError, ValueError) as error:
                rejected.append({"file": member, "side": side, "reason": str(error)})
                continue
            for candidate in candidates:
                for segment, board_i, assumed_length, assumed_radius in (("upper", 0, .30, .045), ("forearm", 1, .25, .035)):
                    body = candidate[segment]
                    q, pos, valid = boards[board_i]
                    device = "arm" if segment == "upper" else "forearm"
                    inertial_path = args.root / "inertial" / "upper" / group / f"{side}{device}" / path.name.replace("_interp", "")
                    try:
                        measured = read_inertial(inertial_path)
                        measured_error = None
                    except (OSError, KeyError, ValueError) as error:
                        measured = None
                        measured_error = f"{type(error).__name__}: {error}"
                    for geom_error, surface_error in ((0., 0.), (-.20, -15.), (.20, 15.)):
                        length = assumed_length * (1 + geom_error)
                        radius = assumed_radius * (1 + geom_error)
                        signal = virtual_mount(time_s, q, pos, valid,
                                               body["fraction"], body["surface_deg"] + surface_error, length, radius,
                                               board_from_sensor=board_from_sensor)
                        try:
                            metrics = summarize(signal)
                        except ValueError:
                            continue
                        rows.append({"person": person, "age_group": group, "exercise": exercise,
                                     "quality_label": int(quality), "side": side, "candidate": candidate["id"],
                                     "segment": segment, "geometry_error_fraction": geom_error,
                                     "assumed_segment_length_m": length, "assumed_surface_radius_m": radius,
                                     "surface_error_deg": surface_error, **metrics,
                                     "measured_inertial": measured, "measured_inertial_error": measured_error})
    summaries = []
    for candidate in candidates:
        for segment in ("upper", "forearm"):
            for geometry_error, surface_error in ((0., 0.), (-.20, -15.), (.20, 15.)):
                subset = [r for r in rows if r["candidate"] == candidate["id"] and r["segment"] == segment
                          and r["geometry_error_fraction"] == geometry_error and r["surface_error_deg"] == surface_error]
                if subset:
                    summaries.append({"candidate": candidate["id"], "segment": segment,
                                      "geometry_error_fraction": geometry_error, "surface_error_deg": surface_error,
                                      "n_recordings": len(subset), "people": sorted({r["person"] for r in subset}),
                                      "n_measured_pairs": sum(r["measured_inertial"] is not None for r in subset),
                                      "missing_inertial_reasons": sorted({r["measured_inertial_error"] for r in subset if r["measured_inertial_error"]}),
                                      "dynamic_rms_g_p10_p50_p90": np.percentile([r["dynamic_rms_g"] for r in subset], [10, 50, 90]).tolist(),
                                      "dynamic_p95_g_p10_p50_p90": np.percentile([r["dynamic_p95_g"] for r in subset], [10, 50, 90]).tolist(),
                                      "axis_rms_g_median": np.median([r["axis_rms_g"] for r in subset], axis=0).tolist(),
                                      "axis_p10_p50_p90_g_median": np.median([r["axis_p10_p50_p90_g"] for r in subset], axis=0).tolist(),
                                      "fraction_at_or_beyond_3g_p10_p50_p90": np.percentile([r["fraction_at_or_beyond_3g"] for r in subset], [10, 50, 90]).tolist(),
                                      "coverage_fraction_p10_p50_p90": np.percentile([r["coverage_fraction"] for r in subset], [10, 50, 90]).tolist(),
                                      "optical_dominant_hz_p10_p50_p90": np.percentile([r["dominant_hz"] for r in subset], [10, 50, 90]).tolist(),
                                      "optical_hf_fraction_p10_p50_p90": np.percentile([r["hf_fraction"] for r in subset], [10, 50, 90]).tolist(),
                                      "matched_optical_dynamic_rms_g_p10_p50_p90": np.percentile([r["dynamic_rms_g"] for r in subset if r["measured_inertial"] is not None], [10, 50, 90]).tolist() if any(r["measured_inertial"] is not None for r in subset) else None,
                                      "measured_inertial_dynamic_rms_g_p10_p50_p90": np.percentile([r["measured_inertial"]["dynamic_rms_g"] for r in subset if r["measured_inertial"] is not None], [10, 50, 90]).tolist() if any(r["measured_inertial"] is not None for r in subset) else None,
                                      "measured_inertial_clip_fraction_p10_p50_p90": np.percentile([r["measured_inertial"]["clipped_fraction_at_3g"] for r in subset if r["measured_inertial"] is not None], [10, 50, 90]).tolist() if any(r["measured_inertial"] is not None for r in subset) else None,
                                      "measured_inertial_dominant_hz_p10_p50_p90": np.percentile([r["measured_inertial"]["dominant_hz"] for r in subset if r["measured_inertial"] is not None], [10, 50, 90]).tolist() if any(r["measured_inertial"] is not None for r in subset) else None,
                                      "measured_inertial_hf_fraction_p10_p50_p90": np.percentile([r["measured_inertial"]["hf_fraction"] for r in subset if r["measured_inertial"] is not None], [10, 50, 90]).tolist() if any(r["measured_inertial"] is not None for r in subset) else None,
                                      "measured_inertial_axis_p10_p50_p90_g_median": np.median([r["measured_inertial"]["axis_p10_p50_p90_g"] for r in subset if r["measured_inertial"] is not None], axis=0).tolist() if any(r["measured_inertial"] is not None for r in subset) else None})
    out = {"source": "PHYTMO optical mounting-board pose replay; exploratory mechanical metrics only",
           "predeclared_validation_gate": gate, "n_optical_files": len({r["person"] + r["exercise"] + str(r["quality_label"]) for r in rows}),
           "n_people": len({r["person"] for r in rows}), "people": sorted({r["person"] for r in rows}),
           "n_rows": len(rows), "rejected": rejected, "candidate_summaries": summaries, "rows": rows,
           "interpretation": "The measured-site calibration gate failed before candidate comparison. Per-record optical and inertial distributions are shown descriptively without clock alignment; correlation is unavailable without a shared time map. These are virtual rigid-body accelerations at assumed offsets from the board origin, not measured chip accelerations, clinical placement validation, or evidence to rank a patient-optimal mount. No classifier was fit or queried.",
           "assumptions": ["100 Hz rigid-body position and orientation; Y-up optical coordinates", "upper/forearm proxy lengths 0.30/0.25 m and surface radii 0.045/0.035 m are assumptions, not participant measurements", "hypothetical midpoint-surface board origin; local board X is treated as segment long axis; anatomy-to-board origin and chip extrinsics remain unknown", "surface offset is relative to lateral surface: [longitudinal, radius*(cos(theta)-1), radius*sin(theta)]", "geometry stress is +/-20% of length and radius; surface stress is +/-15 degrees", "group-wise summaries are descriptive; no training or tuning used held-out records", "no temporal correlation computed because optical/IMU clock mapping is missing", "spectrum uses only each signal's longest contiguous span; coverage and rejected optical files are listed"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Optical pose replay: {len(rows)} rows, {len(summaries)} group summaries")
    print("Measured-site calibration gate:", gate["passed"], "(clock and board-to-chip extrinsics unidentified)")
    print("| Candidate | segment | length error | surface error | recordings | dynamic RMS g p10/p50/p90 |")
    for r in summaries:
        print(f'| {r["candidate"]} | {r["segment"]} | {r["geometry_error_fraction"]:+.0%} | {r["surface_error_deg"]:+.0f} | {r["n_recordings"]} | {np.round(r["dynamic_rms_g_p10_p50_p90"], 4).tolist()} |')


if __name__ == "__main__":
    main()
