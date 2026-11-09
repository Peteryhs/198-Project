"""Independently audit tiny-GRU LOSO outputs, joins, metrics, and lineage hashes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SIDES = ("L", "R")
CLASSES = ("EAH", "EFE", "SQZ")
BASELINE_FILES = (
    "predictions.csv",
    "results.json",
    "metadata.json",
    "realtime_model.h",
    "realtime_model.npz",
)
TRAIN_FILES = (
    "configs/tiny-rnn.json",
    "scripts/tiny_rnn.py",
    "scripts/rnn_data.py",
    "scripts/paired_pipeline.py",
    "model/streaming/paired_stream.c",
    "model/streaming/paired_stream.h",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def git_bytes(revision: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:{relative}"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def baseline_rows(side: str):
    path = ROOT / "model/paired-synchronized-causal" / side / "predictions.csv"
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    result = {}
    for row in rows:
        source = row["source"]
        if source in result:
            raise AssertionError(f"duplicate accepted-baseline source: {side} {source}")
        row["quality"] = int(row["quality"])
        row["quality_prediction"] = int(row["quality_prediction"])
        result[source] = row
    return result


def exact_percentile_ci(rows, baseline, key, draws, seed):
    truth = "quality" if key == "quality_prediction" else "exercise"
    people = sorted({row["subject"] for row in rows})
    stats = []
    for person in people:
        subset = [row for row in rows if row["subject"] == person]
        diff = sum(
            int(row[key] == row[truth])
            - int(baseline[row["source"]][key] == row[truth])
            for row in subset
        )
        stats.append((diff, len(subset)))
    stat = np.asarray(stats)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(stat), (draws, len(stat)))
    values = 100 * stat[picks].sum(axis=1)[:, 0] / stat[picks].sum(axis=1)[:, 1]
    return np.percentile(values, [2.5, 97.5]).tolist()


def verify_side(side: str, baseline_revision: str):
    run = ROOT / "docs/runs/phase6-rnn"
    result_path = run / f"results-{side}.json"
    if not result_path.exists():
        raise FileNotFoundError(f"training result not present yet: {result_path}")
    result = read_json(result_path)
    manifest_path = run / f"data-{side}.json"
    manifest = read_json(manifest_path)
    config_path = ROOT / "configs/tiny-rnn.json"
    config = read_json(config_path)
    base = baseline_rows(side)
    names = set(manifest["names"])
    assert result["side"] == side and manifest["side"] == side
    assert len(names) == len(manifest["names"])
    assert names == set(base), f"{side}: RNN cohort differs from accepted baseline cohort"
    assert result["raw_hashes"] == manifest["raw_hashes"], f"{side}: raw-input hashes differ"
    assert result["config"] == config, f"{side}: saved config differs from current config"
    assert result["config_sha256"] == sha256(config_path.read_bytes()), f"{side}: config hash mismatch"
    trainer = ROOT / "scripts/tiny_rnn.py"
    assert result["script_sha256"] == sha256(trainer.read_bytes()), f"{side}: training script hash mismatch"
    for relative, expected in manifest["pipeline_hashes"].items():
        assert sha256((ROOT / relative).read_bytes()) == expected, f"{side}: data pipeline hash mismatch for {relative}"
    assert result["parameter_count"] == 424 and result["parameter_bytes_float32"] == 1696

    folds = result["folds"]
    assert len(folds) == 30, f"{side}: expected 30 folds, got {len(folds)}"
    people = {row["subject"] for row in base.values()}
    assert len(people) == 30, f"{side}: expected 30 source subjects"
    seen_test, seen_folds = [], []
    all_rows = []
    fold_hashes = {}
    for fold in folds:
        held = str(fold["heldout_person"])
        fold_path = run / f"fold-{side}-{held}.json"
        saved_fold = read_json(fold_path)
        assert saved_fold == fold, f"{side}/{held}: embedded fold differs from saved fold file"
        fold_hashes[fold_path.name] = sha256(fold_path.read_bytes())
        trace = fold["loss_trace"]
        assert len(trace) == config["epochs"] and [row["epoch"] for row in trace] == list(range(1, config["epochs"] + 1))
        assert all(np.isfinite([row["quality_loss"], row["exercise_loss"], row["total_loss"]]).all()
                   for row in trace), f"{side}/{held}: nonfinite loss trace"
        seen_folds.append(held)
        train_people = {str(value) for value in fold["train_people"]}
        assert held not in train_people and train_people == people - {held}, f"{side}/{held}: bad LOSO subject exclusion"
        train_sources = set(fold["train_source_ids"])
        test_sources = set(fold["test_source_ids"])
        assert not train_sources.intersection(test_sources), f"{side}/{held}: source leakage across train/test"
        assert train_sources | test_sources == names, f"{side}/{held}: source cohort mismatch"
        assert train_sources == {s for s in names if base[s]["subject"] != held}
        assert test_sources == {s for s in names if base[s]["subject"] == held}
        assert len(fold["rows"]) == len(test_sources)
        assert {row["source"] for row in fold["rows"]} == test_sources
        for row in fold["rows"]:
            source = row["source"]
            other = base[source]
            assert str(row["subject"]) == held == other["subject"]
            assert int(row["quality"]) == other["quality"]
            assert str(row["exercise"]) == other["exercise"]
            assert int(row["quality_prediction"]) == int(float(row["quality_wrong_probability"]) >= 0.5)
            probs = row["exercise_probabilities"]
            assert len(probs) == 3 and np.isfinite(probs).all()
            assert abs(sum(probs) - 1.0) < 1e-5
            assert row["exercise_prediction"] == CLASSES[int(np.argmax(probs))]
            all_rows.append(row)
            seen_test.append(source)
    assert len(set(seen_folds)) == 30 and set(seen_folds) == people
    assert len(seen_test) == len(names) and set(seen_test) == names

    recomputed = {}
    for label, key, truth in (
        ("quality", "quality_prediction", "quality"),
        ("exercise", "exercise_prediction", "exercise"),
    ):
        current = np.mean([row[key] == row[truth] for row in all_rows])
        old = np.mean([base[row["source"]][key] == row[truth] for row in all_rows])
        values = [row[truth] for row in all_rows]
        _, counts = np.unique(values, return_counts=True)
        actual = result["metrics"][label]
        assert abs(current - actual["rnn_agreement"]) < 1e-12
        assert abs(old - actual["accepted_baseline_agreement"]) < 1e-12
        assert abs(100 * (current - old) - actual["difference_percentage_points"]) < 1e-10
        assert np.allclose(exact_percentile_ci(all_rows, base, key, config["bootstrap_draws"], config["seed"]),
                           actual["paired_subject_bootstrap_95_percent_pp"], atol=1e-10)
        assert abs(counts.max() / len(values) - actual["majority_floor"]) < 1e-12
        recomputed[label] = dict(rnn_agreement=float(current), baseline_agreement=float(old),
                                 difference_percentage_points=float(100 * (current - old)),
                                 majority_floor=float(counts.max() / len(values)))

    assert result["retained_series"] == len(names)
    assert result["available_series"] == len(names) + len(result["rejected"])
    assert result["cycles"] == sum(int(row["cycles"]) for row in all_rows)

    lineage = {
        "result": {"path": result_path.relative_to(ROOT).as_posix(), "sha256": sha256(result_path.read_bytes())},
        "data_manifest": {"path": manifest_path.relative_to(ROOT).as_posix(), "sha256": sha256(manifest_path.read_bytes())},
        "raw_sources": {
            "file_count": len(manifest["raw_hashes"]),
            "path_to_sha256_map_sha256": sha256(json.dumps(manifest["raw_hashes"], sort_keys=True, separators=(",", ":")).encode()),
        },
        "pipeline_hashes": manifest["pipeline_hashes"],
        "config": {"path": "configs/tiny-rnn.json", "sha256": sha256(config_path.read_bytes())},
        "training_code": {},
        "fold_files": fold_hashes,
        "accepted_baseline": {},
    }
    for relative in TRAIN_FILES:
        path = ROOT / relative
        lineage["training_code"][relative] = sha256(path.read_bytes())
    for filename in BASELINE_FILES:
        relative = f"model/paired-synchronized-causal/{side}/{filename}"
        path = ROOT / relative
        committed = git_bytes(baseline_revision, relative)
        working = path.read_bytes()
        assert working == committed, f"accepted baseline file changed from {baseline_revision}: {relative}"
        lineage["accepted_baseline"][filename] = {
            "sha256": sha256(working),
            "matches_git_revision": working == committed,
            "git_revision": baseline_revision,
            "git_blob_oid": subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", f"{baseline_revision}:{relative}"],
                check=True, text=True, stdout=subprocess.PIPE,
            ).stdout.strip(),
        }
    return dict(side=side, result_hash_matches_current_code=True,
                exact_source_join=True, folds_exclude_heldout_subject=True,
                metrics=recomputed, lineage=lineage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-revision", default="61ede24",
                        help="Git revision that defines the accepted causal baseline (default: 61ede24)")
    parser.add_argument("--out", type=Path, help="optional JSON report path; stdout is always emitted")
    args = parser.parse_args()
    report = {
        "verifier": "independent read-only audit; recomputes joins, fold exclusions and paired metrics",
        "baseline_revision": args.baseline_revision,
        "sides": [verify_side(side, args.baseline_revision) for side in SIDES],
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, FileNotFoundError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
