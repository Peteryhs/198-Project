"""Coarse paired optical-site replay scored by frozen real-data C-path models.

Placement outputs are diagnostic if the held-out clock/extrinsic calibration gate fails.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
import paired_pipeline as pp
import realtime_pipeline as rp
from calibrated_replay import predict_virtual
from placement_replay import read_board
from streaming_pipeline import StreamExtractor

PATTERN = re.compile(r"^([A-E])(\d{1,2})(EAH|EFE|SQZ)([01])_([12])(?:_interp)?\.csv$")
G = 9.80665


def grid(config):
    g = config["grid"]
    keys = ("upper_fraction", "forearm_fraction", "upper_surface_deg", "forearm_surface_deg")
    if any(not isinstance(g.get(k), list) or not g[k] for k in keys):
        raise ValueError("grid needs four nonempty coordinate lists")
    if any(not np.isfinite(v).all() for v in [np.asarray(g[k], float) for k in keys]):
        raise ValueError("grid values must be finite")
    if any(not 0 < v < 1 for k in keys[:2] for v in g[k]):
        raise ValueError("placement fractions must be strictly between zero and one")
    if any(not 0 <= v <= 360 for k in keys[2:] for v in g[k]):
        raise ValueError("surface angles must be in [0, 360]")
    return [dict(upper_fraction=float(uf), forearm_fraction=float(ff),
                 upper_surface_deg=float(us), forearm_surface_deg=float(fs))
            for uf, ff, us, fs in itertools.product(*(g[k] for k in keys))]


def rotation_stress(x, degrees, seed):
    if degrees == 0:
        return x.copy()
    out = x.copy()
    rng = np.random.default_rng(seed)
    for start in (0, 3):
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        out[:, start:start+3] = Rotation.from_rotvec(axis*np.deg2rad(degrees)).apply(out[:, start:start+3])
    return out


def select_sources(candidates, cap):
    person = lambda row: row["person"] if isinstance(row, dict) else row[2][0]
    people = sorted({person(row) for row in candidates})[:cap]
    return [row for row in candidates if person(row) in people]


def training_mask(subjects, heldout):
    if heldout not in set(subjects):
        raise ValueError(f"held-out volunteer absent: {heldout}")
    mask = np.asarray(subjects) != heldout
    if set(np.asarray(subjects)[mask]) & {heldout}:
        raise AssertionError("held-out volunteer leaked into training")
    return mask


def signal_metrics(x):
    valid = np.isfinite(x).all(axis=1)
    if not valid.any():
        return {"valid_fraction": 0., "clip_fraction": None, "dynamic_rms_g": None}
    good = x[valid]
    dynamic = good - np.median(good, axis=0)
    return {"valid_fraction": float(valid.mean()),
            "clip_fraction": float(np.mean(np.abs(good) >= 3.)),
            "dynamic_rms_g": float(np.sqrt(np.mean(dynamic ** 2)))}


def virtual_pair(records, mount, config, geometry_scale=1., surface_delta=0., calibration=None):
    result = []
    for record, segment in zip(records, ("upper", "forearm")):
        frac = mount[f"{segment}_fraction"]
        surface = mount[f"{segment}_surface_deg"] + surface_delta
        geom = config["geometry"]
        cal = {**(calibration or {}).get(segment, {}),
               "geometry": {segment: {"length_m": geom[f"{segment}_length_m"] * geometry_scale,
                                      "radius_m": geom[f"{segment}_radius_m"] * geometry_scale}}}
        result.append(predict_virtual(record, cal, {"fraction": frac, "surface_deg": surface}))
    return np.column_stack(result)


def run(root, config_path, out_path, calibration_path):
    config = json.loads(config_path.read_text())
    if config.get("version") != 1 or config.get("protocol_id") != "phase4-placement-coarse-v1":
        raise ValueError("unsupported or unversioned placement protocol")
    mounts = grid(config)
    calibration_report = json.loads(calibration_path.read_text())
    fold_calibrations = {f["heldout_person"]: f["params_by_sensor"] for f in calibration_report["folds"]}
    fold_provenance = {f["heldout_person"]: f for f in calibration_report["folds"]}
    if len(fold_calibrations) != 30:
        raise ValueError(f"calibration report must contain all 30 held-out volunteers; got {len(fold_calibrations)}")
    optical_root = root / "optical raw/rigid_bodies/upper"
    if not optical_root.exists():
        raise FileNotFoundError(optical_root)
    all_rows, summaries, source_rows, geometry_rows, model_folds, rejects = [], [], [], [], [], []
    with StreamExtractor() as extractor:
        for side in "LR":
            real = pp.collect(root / "inertial/upper", side, extractor)
            bags, y, subs, exs, names, real_rejects = real
            lookup = {Path(name).name: i for i, name in enumerate(names)}
            reject_lookup = {Path(row["source"]).name: row["reason"] for row in real_rejects}
            # The model for each held-out volunteer is trained only on other volunteers' measured bags.
            models = {}
            for subject in sorted(set(subs)):
                train = training_mask(subs, subject)
                X, yr, ye, weights = rp.flattened(bags, y, exs, train)
                models[subject] = (rp.fit_model(X, yr, weights), rp.fit_model(X, ye, weights))
            candidates = []
            for p in sorted(optical_root.rglob("*_1.csv")):
                m = PATTERN.match(p.name)
                if not m:
                    continue
                group, number, exercise, quality, _series = m.groups()
                person = f"{group}{int(number):02d}"
                time_s, boards = read_board(p, side)
                optical_records = []
                for segment, (q, pos, valid) in zip(("upper", "forearm"), boards):
                    optical_records.append({"t": time_s, "q": q, "pos": pos, "valid": valid,
                        "meta": {"segment": segment, "optical_path": str(p), "person": person,
                                 "exercise": exercise, "quality": int(quality), "side": side}})
                source_name = f"{person}{exercise}{quality}_{_series}.csv"
                real_index = lookup.get(source_name)
                real_rejection = reject_lookup.get(source_name, "")
                candidates.append({"source_id": len(candidates), "path": p,
                    "source": p.relative_to(root).as_posix(), "person": person,
                    "canonical_source_id": source_name,
                    "exercise": exercise, "label": int(quality),
                    "optical_records": optical_records,
                    "paired_real_status": "retained" if real_index is not None else (real_rejection or "no paired real source")})
            source_cap = config["analysis"].get("source_cap")
            if source_cap is not None:
                candidates = select_sources(candidates, int(source_cap))
            # This optical manifest is the fixed all-171-source denominator, including measured-data rejects.
            people = sorted({row["person"] for row in candidates})
            if not candidates:
                rejects.append({"side": side, "reason": "no optical/inertial common source rows"})
                continue
            if len(people) != 30:
                raise ValueError(f"{side}: placement sweep requires all 30 volunteers, got {len(people)}")
            if len(candidates) != 171:
                raise ValueError(f"{side}: canonical raw cohort must contain 171 paired first-series sources, got {len(candidates)}")
            for subject in people:
                tr = training_mask(subs, subject)
                model_folds.append({"side": side, "heldout_person": subject,
                    "train_people": sorted(set(subs[tr].tolist())),
                    "train_source_ids": [names[i] for i in np.flatnonzero(tr)],
                    "heldout_source_ids": [r["canonical_source_id"] for r in candidates if r["person"] == subject],
                    "n_train_people": int(len(set(subs[tr]))),
                    "n_train_sources": int(np.sum(tr))})
            remount_levels = [float(x) for x in config["geometry"]["remount_rotation_stress_deg"]]
            ids_by_candidate = {(midx, degree): {} for midx in range(len(mounts)) for degree in remount_levels}
            for candidate_index, source in enumerate(candidates):
                row_i = source["source_id"]
                subject, exercise, label = source["person"], source["exercise"], source["label"]
                optical_records = source["optical_records"]
                for mount_i, mount in enumerate(mounts):
                    try:
                        fold_cal = fold_calibrations.get(subject, {})
                        cal = {seg: fold_cal.get(f"{side}|{seg}") for seg in ("upper", "forearm")}
                        if any(cal.get(seg) is None for seg in ("upper", "forearm")):
                            raise ValueError("no train-only fitted calibration for held-out fold")
                        raw = virtual_pair(optical_records, mount, config, calibration=cal)
                        if mount["upper_fraction"] == mount["forearm_fraction"] == .5:
                            for geometry_scale in (.8, 1.2):
                                for surface_delta in (-15., 15.):
                                    stressed_geometry = virtual_pair(optical_records, mount, config,
                                        geometry_scale=geometry_scale, surface_delta=surface_delta,
                                        calibration=cal)
                                    geometry_rows.append({"side": side, "source": source["source"],
                                        "subject": subject, "candidate": mount_i,
                                        "geometry_scale": geometry_scale, "surface_delta_deg": surface_delta,
                                        **signal_metrics(stressed_geometry)})
                        qm, em = models[subject]
                        for degree in remount_levels:
                            seed_text = f"{side}|{source['source']}|{mount_i}|{degree}".encode()
                            seed = int.from_bytes(hashlib.sha256(seed_text).digest()[:4], "little")
                            stressed = rotation_stress(raw, degree, seed)
                            try:
                                features = extractor(np.clip(stressed, -3., 3.))
                                if len(features) < 3:
                                    raise ValueError("fewer than 3 causal C features")
                                qprob = float(rp.series_probs(qm, features)[1])
                                eprob = rp.series_probs(em, features)
                                qpred = int(qprob >= .5)
                                epred = str(em.classes_[int(np.argmax(eprob))])
                                ids_by_candidate[mount_i, degree][row_i] = (qpred, epred, len(features))
                                rejection = ""
                            except (ValueError, FloatingPointError) as exc:
                                ids_by_candidate[mount_i, degree][row_i] = None
                                qpred, qprob, epred, features, rejection = "abstain", "", "abstain", [], str(exc)
                            finite = np.isfinite(stressed).all(axis=1)
                            if finite.any():
                                good = stressed[finite]
                                dyn = good - np.median(good, axis=0)
                            else:
                                dyn = np.empty((0, 6))
                            source_rows.append(dict(side=side, source=source["source"], subject=subject,
                                exercise=exercise, quality_label=label, paired_real_status=source["paired_real_status"], candidate=mount_i,
                                remount_rotation_deg=degree, quality_prediction=qpred, quality_probability=qprob,
                                exercise_prediction=epred, feature_count=len(features),
                                clip_fraction=float(np.mean(np.abs(stressed[finite]) >= 3)) if finite.any() else "",
                                valid_fraction=float(finite.mean()),
                                dynamic_rms_g=float(np.sqrt(np.mean(dyn**2))) if len(dyn) else "",
                                rejection=rejection))
                    except (ValueError, FloatingPointError) as exc:
                        for degree in remount_levels:
                            ids_by_candidate[mount_i, degree][row_i] = None
                            source_rows.append(dict(side=side, source=source["source"], subject=subject,
                                exercise=exercise, quality_label=label, candidate=mount_i,
                                remount_rotation_deg=degree, quality_prediction="abstain", quality_probability="",
                                exercise_prediction="abstain", feature_count=0, clip_fraction="",
                                valid_fraction="", dynamic_rms_g="", rejection=str(exc)))
                if candidate_index % 25 == 0:
                    print(f"{side}: replayed {candidate_index+1}/{len(candidates)} optical sources", flush=True)

            for mount_i, mount in enumerate(mounts):
              for degree in remount_levels:
                decisions = ids_by_candidate[mount_i, degree]
                eligible = [row["source_id"] for row in candidates]
                source_by_id = {row["source_id"]: row for row in candidates}
                qright = eright = 0
                covered = 0
                qfloor = efloor = 0
                per_fold = []
                # A missing optical source remains a failed decision in the fixed side cohort.
                for i in eligible:
                    decision = decisions.get(i)
                    if decision is not None:
                        covered += 1
                        qright += int(decision[0] == source_by_id[i]["label"])
                        eright += int(decision[1] == source_by_id[i]["exercise"])
                for subject in people:
                    ix = [i for i in eligible if source_by_id[i]["person"] == subject]
                    tr = training_mask(subs, subject)
                    qmaj = int(np.mean(y[tr]) >= .5)
                    ec, counts = np.unique(exs[tr], return_counts=True)
                    emaj = str(ec[np.argmax(counts)])
                    qfloor += sum(int(source_by_id[i]["label"] == qmaj) for i in ix)
                    efloor += sum(int(source_by_id[i]["exercise"] == emaj) for i in ix)
                    cal_fold = fold_provenance.get(subject, {})
                    cal_params = {seg: cal_fold.get("params_by_sensor", {}).get(f"{side}|{seg}")
                                  for seg in ("upper", "forearm")}
                    per_fold.append({"heldout_person": subject, "n_eligible": len(ix),
                        "n_covered": sum(decisions.get(i) is not None for i in ix),
                        "train_people": int(len(set(subs[tr]))), "train_source_count": int(np.sum(tr))})
                    per_fold[-1]["train_calibration"] = {
                        seg: ({"fit_success": p.get("fit_success"), "fit_rmse_g": p.get("fit_rmse_g"),
                               "jacobian_rank": p.get("jacobian_rank"), "bound_hits": p.get("bound_hits"),
                               "fit_records": p.get("fit_records")} if p else None)
                        for seg, p in cal_params.items()}
                denom = len(eligible)
                by_exercise = {}
                for exercise in sorted({source_by_id[i]["exercise"] for i in eligible}):
                    eids = [i for i in eligible if source_by_id[i]["exercise"] == exercise]
                    ecov = sum(decisions.get(i) is not None for i in eids)
                    eqright = sum(decisions[i][0] == source_by_id[i]["label"]
                                  for i in eids if decisions.get(i) is not None)
                    eeright = sum(decisions[i][1] == exercise
                                  for i in eids if decisions.get(i) is not None)
                    by_exercise[exercise] = {"eligible_series": len(eids), "covered": ecov,
                        "coverage": ecov / len(eids) if eids else 0.,
                        "quality_series_label_agreement_all_denominator": eqright / len(eids) if eids else 0.,
                        "exercise_series_label_agreement_all_denominator": eeright / len(eids) if eids else 0.}
                summary = {"side": side, "candidate": mount_i, "remount_rotation_deg": degree, **mount,
                    "eligible_series": denom, "subjects": len(people), "covered": covered,
                    "coverage": covered / denom if denom else 0,
                    "quality_series_label_agreement_all_denominator": qright / denom if denom else 0,
                    "exercise_series_label_agreement_all_denominator": eright / denom if denom else 0,
                    "quality_majority_floor_all_denominator": qfloor / denom if denom else 0,
                    "exercise_majority_floor_all_denominator": efloor / denom if denom else 0,
                    "quality_conditional_agreement": qright / covered if covered else None,
                    "exercise_conditional_agreement": eright / covered if covered else None,
                    "by_exercise": by_exercise,
                    "folds": per_fold}
                summaries.append(summary)
                all_rows.append(summary)
            print(f"{side}: finished {len(mounts)} candidate sites", flush=True)

    gate = calibration_report.get("calibration_gate", {"passed": False, "reasons": ["calibration report has no gate result"]})
    stress_summary = []
    for side in "LR":
        for candidate in range(len(mounts)):
            rows = [r for r in geometry_rows if r["side"] == side and r["candidate"] == candidate]
            if not rows:
                continue
            for geometry_scale in (.8, 1.2):
                for surface_delta in (-15., 15.):
                    group = [r for r in rows if r["geometry_scale"] == geometry_scale and r["surface_delta_deg"] == surface_delta]
                    if group:
                        stress_summary.append({"side": side, "candidate": candidate,
                            "geometry_scale": geometry_scale, "surface_delta_deg": surface_delta,
                            "n_sources": len(group),
                            "valid_fraction_median": float(np.median([r["valid_fraction"] for r in group])),
                            "clip_fraction_median": float(np.median([r["clip_fraction"] for r in group if r["clip_fraction"] is not None])),
                            "dynamic_rms_g_p10_p50_p90": np.percentile([r["dynamic_rms_g"] for r in group if r["dynamic_rms_g"] is not None], [10, 50, 90]).tolist()})
    report = {"protocol": config["protocol_id"], "config": config,
        "source": "simulated optical board-pose replay scored by real-data C causal models",
        "calibration_gate": gate, "interpretation": "Diagnostic model response and series-label agreement only. These are not patient-placement accuracy, validated placement scores, or a placement ranking.",
        "calibration_source": str(calibration_path),
        "n_candidates": len(mounts), "candidate_grid": mounts, "rows": summaries,
        "model_folds": model_folds,
        "geometry_surface_stress": {"scope": "central fraction .50/.50 slice; signal feasibility only, no classifier scoring",
            "rows": stress_summary, "per_source_csv": str(out_path.with_name(out_path.stem + "-geometry-stress.csv"))},
        "input_subjects_per_side": {s: sorted({r["subject"] for r in source_rows if r["side"] == s}) for s in "LR"},
        "rejected": rejects, "assumptions": ["optical rigid-body board poses are replayed at assumed anatomical offsets", "board-to-chip origin and transform are unknown", "optical/IMU clocks are not shared", "whole-series labels are inherited for diagnostic agreement only", "±3 g clipping is a rig approximation", "no held-out test data used in model training or calibration"]}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    detail_path = out_path.with_name(out_path.stem + "-sources.csv")
    if source_rows:
        with detail_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in source_rows for k in row)), lineterminator="\n")
            writer.writeheader(); writer.writerows(source_rows)
    if geometry_rows:
        with out_path.with_name(out_path.stem + "-geometry-stress.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(geometry_rows[0]), lineterminator="\n")
            writer.writeheader(); writer.writerows(geometry_rows)
    print(json.dumps({"summary": str(out_path), "per_source": str(detail_path), "candidates": len(mounts), "rows": len(summaries), "calibration_gate_passed": gate["passed"]}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/phytmo"))
    parser.add_argument("--config", type=Path, default=Path("configs/placement-search.json"))
    parser.add_argument("--out", type=Path, default=Path("docs/runs/phase4/placement-sweep.json"))
    parser.add_argument("--calibration", type=Path, default=Path("docs/runs/phase4/calibration.json"))
    args = parser.parse_args()
    run(args.root, args.config, args.out, args.calibration)


if __name__ == "__main__":
    main()
