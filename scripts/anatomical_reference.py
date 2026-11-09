"""Audit functional joint-center hypotheses in published upper-limb optical Calib trials."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from modelling_environment import check_environment
check_environment()
import numpy as np
from scipy.spatial.transform import Rotation

from placement_replay import read_board


def solve_constraint(design, target, config):
    if design.ndim != 3 or design.shape[1:] != (3, 6) or target.shape != design.shape[:2]:
        raise ValueError("Expected N×3×6 design and N×3 target")
    if len(design) < config["minimum_samples"] or not np.isfinite(design).all() or not np.isfinite(target).all():
        raise ValueError("Insufficient finite geometry samples")
    matrix, values = design.reshape(-1, 6), target.ravel()
    solution, _, rank, singular = np.linalg.lstsq(matrix, values, rcond=1e-10)
    error = (matrix @ solution - values).reshape(-1, 3)
    ratio = float(singular[-1] / singular[0])
    rms = float(np.sqrt(np.mean(np.sum(error ** 2, axis=1))))
    return dict(solution=solution.tolist(), samples=len(design), rank=int(rank),
                singular_values=singular.tolist(), smallest_to_largest_singular_ratio=ratio,
                constraint_rms_m=rms,
                conditioning_screen_passed=bool(rank == 6 and ratio >= config["minimum_singular_value_ratio"]),
                residual_screen_passed=bool(rms <= config["maximum_constraint_rms_m"]),
                weakest_parameter_direction=np.linalg.svd(matrix, full_matrices=False)[2][-1].tolist())


def fixed_center(rotation, position, config):
    identity = np.broadcast_to(np.eye(3), rotation.shape)
    fit = solve_constraint(np.concatenate([rotation, -identity], axis=2), -position, config)
    fit["board_to_center_m"], fit["world_center_m"] = fit["solution"][:3], fit["solution"][3:]
    fit["board_to_center_distance_m"] = float(np.linalg.norm(fit["solution"][:3]))
    fit["plausibility_screen_passed"] = fit["board_to_center_distance_m"] <= config["maximum_board_to_joint_distance_m"]
    return fit


def paired_center(upper_rotation, upper_position, fore_rotation, fore_position, config):
    fit = solve_constraint(np.concatenate([upper_rotation, -fore_rotation], axis=2),
                           fore_position - upper_position, config)
    fit["upper_board_to_center_m"], fit["forearm_board_to_center_m"] = fit["solution"][:3], fit["solution"][3:]
    fit["board_to_center_distances_m"] = [float(np.linalg.norm(fit["solution"][k:k + 3])) for k in (0, 3)]
    fit["plausibility_screen_passed"] = max(fit["board_to_center_distances_m"]) <= config["maximum_board_to_joint_distance_m"]
    fit["ambiguity"] = "A hinge permits sliding the inferred center along its axis; a low residual alone cannot identify the anatomical elbow center."
    return fit


def analyze(path, config):
    match = re.match(r"([A-E])(\d{1,2})Calib(?:_interp)?\.csv$", path.name)
    if not match:
        raise ValueError("Expected an upper-limb Calib filename")
    person = match[1] + match[2].zfill(2)
    rows = []
    for side in "LR":
        time, boards = read_board(path, side)
        qu, pu, vu = boards[0]
        qf, pf, vf = boards[1]
        valid = vu & vf & np.isfinite(time)
        selected = np.flatnonzero(valid)[::config["sample_stride"]]
        ru = Rotation.from_quat(qu[selected]).as_matrix()
        rf = Rotation.from_quat(qf[selected]).as_matrix()
        shoulder = fixed_center(ru, pu[selected], config)
        elbow = paired_center(ru, pu[selected], rf, pf[selected], config)
        fields = ["conditioning_screen_passed", "residual_screen_passed", "plausibility_screen_passed"]
        upper_geometry = None
        if all(fit[key] for fit in [shoulder, elbow] for key in fields):
            rs = np.asarray(shoulder["board_to_center_m"])
            r_elbow = np.asarray(elbow["upper_board_to_center_m"])
            axis = r_elbow - rs
            length = float(np.linalg.norm(axis))
            if length > 1e-8:
                fraction = float(np.dot(-rs, axis) / (length * length))
                upper_geometry = dict(functional_joint_distance_m=length,
                                      projected_board_fraction_from_shoulder=fraction,
                                      perpendicular_board_distance_m=float(np.linalg.norm(-rs - fraction * axis)),
                                      interpretation="Conditional whole-trial rigid-body hypothesis, not independently measured anatomy")
        rows.append(dict(person=person, side=side, source=str(path),
                         filename_indicates_interpolation="_interp" in path.stem,
                         source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         finite_pair_fraction=float(valid.mean()),
                         shoulder_fixed_world_hypothesis=shoulder, elbow_shared_point_hypothesis=elbow,
                         conditional_upper_geometry=upper_geometry,
                         used_in_classifier_or_replay_calibration=False))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/phytmo/optical raw/rigid_bodies/upper"))
    parser.add_argument("--config", type=Path, default=Path("configs/anatomy-reference.json"))
    parser.add_argument("--out", type=Path, default=Path("docs/runs/phase4/anatomy-reference.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if config.get("version") != 1 or config["sample_stride"] < 1 or config["minimum_samples"] < 3:
        raise ValueError("Invalid anatomy audit configuration")
    rows, rejected = [], []
    for path in sorted(args.root.glob("*/*Calib*.csv")):
        try:
            rows.extend(analyze(path, config))
        except (ValueError, OSError) as error:
            rejected.append(dict(source=str(path), reason=str(error)))
    if not rows:
        raise ValueError("No usable upper Calib optical files; fetch published calibration references first")
    summary = {}
    for key in ["shoulder_fixed_world_hypothesis", "elbow_shared_point_hypothesis"]:
        fits = [row[key] for row in rows]
        passed = [fit for fit in fits if all(fit[k] for k in ["conditioning_screen_passed", "residual_screen_passed", "plausibility_screen_passed"])]
        summary[key] = dict(fits=len(fits), passed_engineering_screens=len(passed),
                            rank_counts={str(rank): sum(f["rank"] == rank for f in fits) for rank in sorted({f["rank"] for f in fits})},
                            median_constraint_rms_m=float(np.median([f["constraint_rms_m"] for f in fits])))
    report = dict(source="Published PHYTMO upper Calib optical board poses", config=config,
                  people=sorted({row["person"] for row in rows}), rows=rows, rejected=rejected, summary=summary,
                  interpretation="A successful rigid-body constraint fit is not externally validated anatomy. Whole-trial fixed-shoulder assumptions may fail with trunk translation; elbow hinge-axis ambiguity may remain. No wrist tracker establishes full forearm length. No result in this descriptive audit is used to fit held-out replay or classification.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(people=len(report["people"]), rows=len(rows), rejected=len(rejected), summary=summary), indent=2))


if __name__ == "__main__":
    main()
