"""Measure temporal stability of functional joint-center hypotheses in upper Calib takes."""
import argparse
import json
import re
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from anatomical_reference import fixed_center, paired_center
from placement_replay import read_board


def _fit_side(path, side, config):
    match = re.match(r"([A-E])(\d{1,2})Calib(?:_interp)?\.csv$", path.name)
    if not match:
        raise ValueError("Expected upper-limb Calib filename")
    time, boards = read_board(path, side)
    (qu, pu, vu), (qf, pf, vf) = boards
    valid = vu & vf & np.isfinite(time)
    indices = np.flatnonzero(valid)[::config["sample_stride"]]
    if len(indices) < 2 * config["split_minimum_samples"]:
        raise ValueError("Insufficient paired samples for two temporal halves")
    midpoint = len(indices) // 2
    results = []
    for subset in (indices[:midpoint], indices[midpoint:]):
        ru, rf = Rotation.from_quat(qu[subset]).as_matrix(), Rotation.from_quat(qf[subset]).as_matrix()
        shoulder = fixed_center(ru, pu[subset], config["fit_config"])
        elbow = paired_center(ru, pu[subset], rf, pf[subset], config["fit_config"])
        accepted = all(fit[key] for fit in (shoulder, elbow) for key in (
            "conditioning_screen_passed", "residual_screen_passed", "plausibility_screen_passed"))
        geometry = None
        if accepted:
            s = np.asarray(shoulder["board_to_center_m"])
            e = np.asarray(elbow["upper_board_to_center_m"])
            axis = e - s
            length = float(np.linalg.norm(axis))
            if length > 1e-8:
                fraction = float(np.dot(-s, axis) / length**2)
                geometry = {"upper_length_m": length, "shoulder_to_elbow_board_fraction": fraction,
                            "projection_inside_board_segment": bool(0 <= fraction <= 1),
                            "perpendicular_distance_m": float(np.linalg.norm(-s - fraction * axis))}
        results.append({"samples": len(subset), "shoulder": shoulder, "elbow": elbow,
                        "joint_screens_pass": accepted, "geometry": geometry})
    return {"person": match[1] + match[2].zfill(2), "side": side, "source": str(path),
            "selected_paired_samples": len(indices), "halves": results}


def summarize(rows, config):
    valid = [r for r in rows if all(h["joint_screens_pass"] and h["geometry"] for h in r["halves"])]
    deltas = []
    for row in valid:
        a, b = row["halves"]
        fraction_delta = abs(a["geometry"]["shoulder_to_elbow_board_fraction"] -
                             b["geometry"]["shoulder_to_elbow_board_fraction"])
        centers = [np.linalg.norm(np.asarray(a["shoulder"]["board_to_center_m"]) - b["shoulder"]["board_to_center_m"]),
                   np.linalg.norm(np.asarray(a["elbow"]["upper_board_to_center_m"]) - b["elbow"]["upper_board_to_center_m"]),
                   np.linalg.norm(np.asarray(a["elbow"]["forearm_board_to_center_m"]) - b["elbow"]["forearm_board_to_center_m"])]
        deltas.append({"person": row["person"], "side": row["side"], "fraction_abs_delta": float(fraction_delta),
                       "shoulder_board_offset_delta_m": float(centers[0]),
                       "upper_elbow_offset_delta_m": float(centers[1]),
                       "forearm_elbow_offset_delta_m": float(centers[2]),
                       "stable_under_declared_screen": bool(max(centers) <= config["maximum_center_shift_m"]
                                                            and fraction_delta <= config["maximum_fraction_shift"]),
                       "both_halves_projection_inside_segment": bool(all(h["geometry"]["projection_inside_board_segment"] for h in (a, b)))})
    return {"cases": len(rows), "both_halves_pass_joint_screens": len(valid),
            "declared_stability_passes": sum(d["stable_under_declared_screen"] for d in deltas),
            "both_halves_project_inside_segment": sum(d["both_halves_projection_inside_segment"] for d in deltas),
            "median_absolute_fraction_shift": float(np.median([d["fraction_abs_delta"] for d in deltas])) if deltas else None,
            "median_center_shifts_m": {key: float(np.median([d[key] for d in deltas])) for key in
                ("shoulder_board_offset_delta_m", "upper_elbow_offset_delta_m", "forearm_elbow_offset_delta_m")} if deltas else None,
            "case_deltas": deltas}


def run(root, config):
    rows, rejected = [], []
    for path in sorted(root.glob("*/*Calib*.csv")):
        for side in "LR":
            try:
                rows.append(_fit_side(path, side, config))
            except (OSError, ValueError) as error:
                rejected.append({"source": str(path), "side": side, "reason": str(error)})
    if not rows:
        raise ValueError("No usable upper Calib optical files")
    return {"source": "Published PHYTMO upper Calib optical board poses",
            "method": "Within-take chronological split; fit each half independently. No inferred points enter replay, model fitting, or calibration.",
            "board_mapping_used": {"L": ["thigh2", "shin2"], "R": ["thigh", "shin"],
                                   "basis": "Existing placement_replay.read_board mapping; PHYTMO descriptor names upper-limb IMU sides/segments and says optical exports contain mounting-board poses, but does not directly map these rigid-body labels to side/segment."},
            "predeclared_engineering_screens": config,
            "rows": rows, "rejected": rejected, "summary": summarize(rows, config),
            "split_half_limit": "Chronological valid-sample halves can contain different calibration movements and excitation; observed fit differences do not by themselves show mount movement. No phase-specific anatomical calibration was performed.",
            "identifiability": "This only tests repeatability of conditional fixed-shoulder/shared-elbow hypotheses. Published placement gives exterior-lateral surfaces, approximate Figure 1 locations and nominal sensor axes. The inspected metadata and this analysis do not establish the exact chip origin/residual board-to-chip registration or anatomical distances; this is not proof that no method could ever recover them."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/phytmo/optical raw/rigid_bodies/upper"))
    parser.add_argument("--config", type=Path, default=Path("configs/anatomy-reference.json"))
    parser.add_argument("--out", type=Path, default=Path("docs/runs/phase5/location-followup.json"))
    args = parser.parse_args()
    base = json.loads(args.config.read_text())
    if base.get("version") != 1 or base["sample_stride"] < 1:
        raise ValueError("Invalid anatomy audit configuration")
    config = {"fit_config": {**base, "minimum_samples": 40}, "sample_stride": base["sample_stride"],
              "split_minimum_samples": 40, "maximum_center_shift_m": 0.025, "maximum_fraction_shift": 0.10}
    report = run(args.root, config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"summary": {k: v for k, v in report["summary"].items() if k != "case_deltas"},
                      "rejected": len(report["rejected"])}, indent=2))


if __name__ == "__main__":
    main()
