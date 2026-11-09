"""Independent arithmetic and presentation audit of saved Phase 4 outputs."""
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = Path("docs/runs/phase4")


def close(a, b, tol=1e-10):
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def calibration_audit(path=BASE / "calibration.json"):
    report = json.loads(path.read_text())
    all_rows = [row for fold in report["folds"] for row in fold["rows"]]
    all_ids = {row["source_id"] for row in all_rows}
    for fold in report["folds"]:
        heldout = fold["heldout_person"]
        assert all(row["person"] == heldout for row in fold["rows"])
        assert heldout not in fold["train_people"] and len(set(fold["train_people"])) == 29
        assert set(fold["train_source_ids"]).isdisjoint(fold["heldout_source_ids"])
        assert set(fold["train_source_ids"]) == {r["source_id"] for r in all_rows if r["person"] != heldout}
    tracks = {}
    for track in ("primary_train_mapped", "oracle_diagnostic"):
        rows = [row for fold in report["folds"] for row in fold["rows"]
                if row.get(track, {}).get("baseline") and row[track].get("calibrated")]
        pairs = [(r[track]["baseline"], r[track]["calibrated"]) for r in rows]
        assert all(a["n_samples"] == b["n_samples"] and a["duration_s"] == b["duration_s"] for a, b in pairs)
        active = [(a, b) for a, b in pairs if b["measured_dynamic_rms_g"] >= .05]
        quiet = len(pairs) - len(active)
        baseline_mean = statistics.fmean(a["dynamic_rmse_g"] for a, _ in active)
        calibrated_mean = statistics.fmean(b["dynamic_rmse_g"] for _, b in active)
        median_total = [statistics.median(a["rmse_g"] for a, _ in pairs),
                        statistics.median(b["rmse_g"] for _, b in pairs)]
        max_axis_bias = max(abs(v) for _, b in pairs for v in b["bias_g"])
        metrics = {
            "matched": len(pairs), "active_measured_rms_ge_0_05g": len(active), "quiet": quiet,
            "mean_active_dynamic_rmse_baseline_g": baseline_mean,
            "mean_active_dynamic_rmse_calibrated_g": calibrated_mean,
            "active_dynamic_rmse_reduction_percent": 100 * (1 - calibrated_mean / baseline_mean),
            "median_total_rmse_baseline_calibrated_g": median_total,
            "max_abs_calibrated_axis_bias_g_all_matched": max_axis_bias,
            "dynamic_correlation_median_active": statistics.median(b["dynamic_correlation"] for _, b in active),
            "dynamic_nrmse_median_active": statistics.median(b["dynamic_nrmse"] for _, b in active),
            "per_axis_median_correlation_baseline": [statistics.median(a["correlation_xyz"][i] for a, _ in pairs) for i in range(3)],
            "per_axis_median_correlation_calibrated": [statistics.median(b["correlation_xyz"][i] for _, b in pairs) for i in range(3)],
        }
        tracks[track] = metrics
    gate = report["calibration_gate"]
    primary = tracks["primary_train_mapped"]
    saved = gate["matched_waveform"]
    assert primary["matched"] == saved["n_matched_records"]
    assert primary["active_measured_rms_ge_0_05g"] == saved["n_dynamic_active_records"]
    assert close(primary["mean_active_dynamic_rmse_baseline_g"], saved["baseline_dynamic_rmse_g_mean"])
    assert close(primary["mean_active_dynamic_rmse_calibrated_g"], saved["calibrated_dynamic_rmse_g_mean"])
    assert close(primary["max_abs_calibrated_axis_bias_g_all_matched"], saved["max_axis_bias_abs_g"])
    # The gate's correlation and NRMSE are active-only, while its bias maximum includes quiet matches.
    expected_clock_coverage = sum(row["clock_residual_s"] is not None for f in report["folds"] for row in f["rows"])
    expected_clock_coverage /= sum(len(f["rows"]) for f in report["folds"])
    assert close(expected_clock_coverage, gate["clock"]["heldout_lag_coverage"])
    cache_row = next(row for fold in report["folds"] for row in fold["rows"] if row.get("cache"))
    with np.load(cache_row["cache"], allow_pickle=False) as cache:
        real = cache["real_g"]
        golden = {}
        for field, name in (("baseline_g", "baseline"), ("calibrated_g", "calibrated")):
            pred = cache[field]
            err = pred - real
            yd = real - real.mean(axis=0)
            xd = pred - pred.mean(axis=0)
            saved = cache_row["primary_train_mapped"][name]
            golden[name] = {
                "n_samples": int(len(pred)),
                "rmse_g": float(np.sqrt(np.mean(err ** 2))),
                "bias_g": err.mean(axis=0).tolist(),
                "correlation_xyz": [float(np.corrcoef(pred[:, i], real[:, i])[0, 1]) for i in range(3)],
                "dynamic_rmse_g": float(np.sqrt(np.mean((xd - yd) ** 2))),
                "dynamic_nrmse": float(np.linalg.norm(xd - yd) / np.linalg.norm(yd)),
                "dynamic_correlation": float(np.sum(xd * yd) / (np.linalg.norm(xd) * np.linalg.norm(yd))),
                "measured_dynamic_rms_g": float(np.sqrt(np.mean(yd ** 2))),
            }
            for key, value in golden[name].items():
                assert np.allclose(value, saved[key], rtol=1e-10, atol=1e-10), (name, key)
    fit_alignment = fit_input_alignment_audit(report)
    return {"report_path": str(path), "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "tracks": tracks, "clock_coverage": expected_clock_coverage,
            "transform_count": sum(len(f["params_by_sensor"]) for f in report["folds"]),
            "folds": len(report["folds"]), "gate_passed": gate["passed"],
            "cache_numpy_golden_metrics": golden, "fit_input_alignment": fit_alignment}


def fit_input_alignment_audit(report):
    # Compare optimizer preprocessing inputs with independent baseline replay on real records.
    from calibrated_replay import _prepare_fit_record, _resample_pair, load_record
    rows = [row for fold in report["folds"] for row in fold["rows"]
            if row.get("primary_train_mapped", {}).get("baseline")][:24]
    errors = []
    for row in rows:
        optical, side, segment = row["source_id"].split("|")
        record = load_record(Path(optical), Path("data/phytmo/inertial/upper"), side, segment)
        lag = .0037
        prepared = _prepare_fit_record(record, lag)
        if prepared is None:
            continue
        x, _, _ = _resample_pair(record, lag, include_time=True)
        delta = np.max(np.abs(prepared[0] - x), axis=1)
        errors.append({"max_abs_g": float(delta.max()), "mean_abs_g": float(delta.mean()),
                       "different_grid_samples": int(np.count_nonzero(delta > 1e-8)),
                       "samples": int(len(delta))})
    assert errors
    return {"records_checked": len(errors), "lag_s": .0037,
            "max_boundary_discrepancy_g": max(x["max_abs_g"] for x in errors),
            "median_record_max_discrepancy_g": float(np.median([x["max_abs_g"] for x in errors])),
            "mean_fraction_of_samples_differing": float(np.mean([x["different_grid_samples"] / x["samples"] for x in errors])),
            "interpretation": "Fit/scoring interpolation differences are measured directly; values above 1e-8 g indicate inconsistency. The pre-fix snapshot is retained separately."}


def placement_audit():
    report = json.loads((BASE / "placement-sweep.json").read_text())
    groups = defaultdict(list)
    with (BASE / "placement-sweep-sources.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["side"], int(row["candidate"]), float(row["remount_rotation_deg"]))
            groups[key].append(row)
    assert len(groups) == len(report["rows"]) == 486
    assert sum(map(len, groups.values())) == 83106
    for fold in report["model_folds"]:
        assert len(fold["train_people"]) == 29 and fold["heldout_person"] not in fold["train_people"]
        assert set(fold["train_source_ids"]).isdisjoint(fold["heldout_source_ids"])
        assert all(not Path(source).name.startswith(fold["heldout_person"]) for source in fold["train_source_ids"])
    for saved in report["rows"]:
        key = (saved["side"], saved["candidate"], saved["remount_rotation_deg"])
        rows = groups[key]
        denom = len(rows)
        covered = sum(r["quality_prediction"] != "abstain" for r in rows)
        qcorrect = sum(r["quality_prediction"] == r["quality_label"] for r in rows)
        ecorrect = sum(r["exercise_prediction"] == r["exercise"] for r in rows)
        assert denom == saved["eligible_series"] == 171
        assert covered == saved["covered"]
        assert close(covered / denom, saved["coverage"])
        assert close(qcorrect / denom, saved["quality_series_label_agreement_all_denominator"])
        assert close(ecorrect / denom, saved["exercise_series_label_agreement_all_denominator"])
    zero = [r for r in report["rows"] if r["remount_rotation_deg"] == 0]
    result = {}
    for side in "LR":
        side_rows = [r for r in zero if r["side"] == side]
        result[side] = {k: [min(r[k] for r in side_rows), max(r[k] for r in side_rows)]
                        for k in ("quality_series_label_agreement_all_denominator", "exercise_series_label_agreement_all_denominator", "coverage")}
    return {"scenarios": len(groups), "source_decisions": sum(map(len, groups.values())),
            "all_summaries_match_source_csv": True, "zero_rotation_ranges": result,
            "calibration_gate_passed": report["calibration_gate"]["passed"]}


def known_value_checks():
    # Independent edge checks: fixed all-eligible denominator keeps abstention as a miss.
    labels = ["1", "0", "1", "0"]
    preds = ["1", "abstain", "0", "0"]
    assert sum(a == b for a, b in zip(labels, preds)) / len(labels) == .5
    assert sum(a == b for a, b in zip(labels, preds) if b != "abstain") / sum(p != "abstain" for p in preds) == 2 / 3
    baseline, calibrated = [0.2, 0.4, 0.6], [0.1, 0.3, 0.5]
    assert close(100 * (1 - statistics.fmean(calibrated) / statistics.fmean(baseline)), 25)
    assert close(statistics.median([0.01, 0.08, 0.3]), .08)
    return True


def main():
    known_value_checks()
    result = {"scope": "internal reporting and pipeline arithmetic consistency only; not physical validation",
              "known_value_checks": "passed", "calibration": calibration_audit(), "placement": placement_audit(),
              "physical_correctness": "not established; clock and waveform calibration gates fail, virtual geometry and sensor registration remain assumptions"}
    corrected=Path('docs/runs/phase5/calibration-corrected.json')
    if corrected.exists():
        fresh=json.loads(corrected.read_text())
        assert fresh['runtime']['calibration_script_sha256']==hashlib.sha256(Path('scripts/calibrated_replay.py').read_bytes()).hexdigest()
        result['corrected_calibration']=calibration_audit(corrected)
    out = Path("docs/runs/phase5/reporting-audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
