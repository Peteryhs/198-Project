"""Independently check saved scores, lineage, folds and sampled augmentation artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from augmentation_pipeline import config_hash, transform_with_provenance
from harness import parse_name, read_inertial
from paired_pipeline import aligned_pair

ROOT = Path(__file__).resolve().parents[1]


def verify(root, output, side):
    directory = output / side
    report = json.loads((directory / "results.json").read_text())
    assert report == json.loads((ROOT / f"docs/runs/phase3/augmentation-{side}.json").read_text())
    config = report["config"]
    assert config_hash(config) == report["config_sha256"]
    with (directory / "predictions.csv").open() as handle:
        predictions = list(csv.DictReader(handle))
    with (ROOT / f"model/paired-synchronized-causal/{side}/predictions.csv").open() as handle:
        prior = {row["source"]: row for row in csv.DictReader(handle)}
    names = {row["source_id"] for row in predictions}
    subjects = {row["subject"] for row in predictions}
    assert len(predictions) == len(names) == report["series"]
    assert len(subjects) == 30 and names == set(prior)
    for row in predictions:
        name = row["source_id"]
        meta = parse_name(name)
        assert (row["subject"], row["exercise"], int(row["label"])) == (meta[0], meta[1], meta[3])
        assert row["real_quality_prediction"] == prior[name]["quality_prediction"]
        assert row["real_exercise_prediction"] == prior[name]["exercise_prediction"]
    for arm, prefix in [("real_only", "real"), ("augmented_train_only", "augmented")]:
        for task, truth in [("quality", "label"), ("exercise", "exercise")]:
            value = sum(row[f"{prefix}_{task}_prediction"] == row[truth] for row in predictions) / len(predictions)
            assert value == report[arm][f"{task}_accuracy"]
    rejects = {row["source_id"] for row in report["rejected_source_ids"]}
    assert not names & rejects
    assert len(names) + len(rejects) == report["coverage"]["source_series_seen"]
    for fold in report["folds"]:
        held = fold["subject"]
        assert set(fold["train_subjects"]) == subjects - {held}
        assert set(fold["test_subjects"]) == {held}
        assert set(fold["test_source_ids"]) == {row["source_id"] for row in predictions if row["subject"] == held}
    assert {fold["subject"] for fold in report["folds"]} == subjects
    originals = {row["source_id"]: row for row in report["lineage"] if row["status"] == "measured"}
    manifest = [json.loads(line) for line in (directory / "augmentation-manifest.jsonl").read_text().splitlines()]
    assert len(manifest) == len(names) * config["augmentation_count"]
    for row in manifest:
        original = originals[row["source_id"]]
        for field in ["subject", "exercise", "label", "source_sha256", "counterpart_sha256"]:
            assert row[field] == original[field]
        assert set(row["training_fold_held_out_subjects"]) == subjects - {row["subject"]}
        assert row["config_sha256"] == report["config_sha256"]
        assert row["status"] == "transformed" and row["validation"]["c_feature_coverage"] >= 3
        assert row["config_version"] == config["version"] and row["dataset_version"]
        assert "unvalidated" in row["validation_status"]
    for original in originals.values():
        for name_key, hash_key in [("source_id", "source_sha256"), ("counterpart_id", "counterpart_sha256")]:
            assert hashlib.sha256((root / original[name_key]).read_bytes()).hexdigest() == original[hash_key]
    for row in [manifest[0], manifest[-1]]:
        artifact = Path(row["artifact"])
        if not artifact.is_absolute():
            artifact = ROOT / artifact
        with np.load(artifact, allow_pickle=False) as saved:
            source = aligned_pair(read_inertial(str(root / row["source_id"])),
                                  read_inertial(str(root / row["counterpart_id"])))
            assert np.array_equal(source, saved["original_g"])
            regenerated, parameters = transform_with_provenance(source, config, row["seed"])
            assert np.array_equal(regenerated, saved["augmented_g"])
            assert parameters["orientation_matrices"] == row["orientation_matrices"]
            assert np.allclose(np.diff(saved["time_s"]), .01)
            assert hashlib.sha256(np.asarray(source, dtype="<f8").tobytes()).hexdigest() == row["aligned_pair_sha256"]
    print(f"{side}: scores independently recomputed; {len(names)} matched baseline sources, {len(rejects)} rejected, 30 disjoint folds; {len(manifest)} variants retain volunteer/labels/hashes/version; four-task saved decisions checked; sampled NPZ replay bit-identical")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/phytmo/inertial/upper")
    parser.add_argument("--output", type=Path, default=ROOT / "data/phase3-augmentation/augmentation-example")
    args = parser.parse_args()
    for side in "LR":
        verify(args.root, args.output, side)
    optical = json.loads((ROOT / "docs/runs/phase3/simulation-placement.json").read_text())
    for summary in optical["candidate_summaries"]:
        matched = [row for row in optical["rows"] if row["candidate"] == summary["candidate"]
                   and row["segment"] == summary["segment"]
                   and row["geometry_error_fraction"] == summary["geometry_error_fraction"]
                   and row["surface_error_deg"] == summary["surface_error_deg"]
                   and row["measured_inertial"] is not None]
        assert len(matched) == summary["n_measured_pairs"]
        assert np.array_equal(np.percentile([row["dynamic_rms_g"] for row in matched], [10, 50, 90]),
                              summary["matched_optical_dynamic_rms_g_p10_p50_p90"])
    print("Optical reference summaries use identical source cohorts for virtual and measured RMS; missing calibration remains explicit")


if __name__ == "__main__":
    main()
