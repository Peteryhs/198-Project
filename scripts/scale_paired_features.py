"""Rebuild paired feature bags and align them with the accepted LOSO baseline."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

import paired_pipeline as pp
import realtime_pipeline as rp

ROOT = Path(__file__).resolve().parents[1]


def flatten_train(data, train_mask, duration_only=False):
    """Flatten selected training series using the baseline equal-series weights."""
    return rp.flattened(data["bags"], data["y"], data["exercises"], train_mask, duration_only)


def series_probabilities(model, bag):
    """Pool repetition probabilities exactly as the paired baseline does."""
    return rp.series_probs(model, bag)


def save_dataset(data, path: Path):
    """Store numeric bags and source-aligned baseline decisions without pickle."""
    path.parent.mkdir(parents=True, exist_ok=True)
    offsets = np.r_[0, np.cumsum([len(b) for b in data["bags"]])].astype(np.int64)
    features = np.concatenate(data["bags"], axis=0).astype(np.float32, copy=False)
    rows = [data["baseline_predictions"][s] for s in data["sources"]]
    np.savez_compressed(path, features=features, offsets=offsets, y=data["y"],
                        subjects=np.asarray(data["subjects"], dtype="U3"),
                        exercises=np.asarray(data["exercises"], dtype="U3"),
                        sources=np.asarray(data["sources"], dtype="U128"),
                        baseline_quality=np.asarray([int(r["quality_prediction"]) for r in rows]),
                        baseline_exercise=np.asarray([r["exercise_prediction"] for r in rows], dtype="U3"))


def load_dataset(path: Path):
    """Load a saved cache into the same dictionary shape as ``build_dataset``."""
    with np.load(path, allow_pickle=False) as z:
        features, offsets = z["features"], z["offsets"]
        y, subjects, exercises = z["y"], z["subjects"].astype(str), z["exercises"].astype(str)
        sources = z["sources"].astype(str).tolist()
        qpred, epred = z["baseline_quality"], z["baseline_exercise"].astype(str)
        n = len(sources)
        if features.ndim != 2 or features.shape[1] != 61 or not np.isfinite(features).all():
            raise ValueError(f"features must be a finite (n_cycles, 61) matrix in {path}")
        if offsets.ndim != 1 or len(offsets) != n + 1 or not len(offsets) or offsets[0] != 0 or offsets[-1] != len(features) or np.any(np.diff(offsets) <= 0):
            raise ValueError(f"invalid feature offsets in {path}")
        arrays = (y, subjects, exercises, qpred, epred)
        if any(a.ndim != 1 or len(a) != n for a in arrays) or len(set(sources)) != n:
            raise ValueError(f"cache series metadata lengths or source keys are invalid in {path}")
        if set(np.unique(qpred)) - {0, 1}:
            raise ValueError(f"invalid cached baseline quality predictions in {path}")
        bags = [features[a:b].copy() for a, b in zip(offsets[:-1], offsets[1:])]
        baseline_predictions = {s: {"quality_prediction": str(q), "exercise_prediction": str(e)}
                               for s, q, e in zip(sources, qpred, epred)}
        return {"bags": bags, "y": y.copy(), "subjects": subjects,
                "exercises": exercises, "sources": sources,
                "baseline_predictions": baseline_predictions, "cycles": int(len(features))}


def _baseline(mode: str, side: str, baseline_root: Path):
    directory = baseline_root / side
    report = json.loads((directory / "results.json").read_text())
    with (directory / "predictions.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != report["series"]:
        raise ValueError(f"{directory}: prediction rows do not match reported series count")
    keyed = {row["source"]: row for row in rows}
    if len(keyed) != len(rows):
        raise ValueError(f"{directory}: duplicate baseline source")
    return report, keyed


def build_dataset(root: Path, side: str, mode: str,
                  baseline_root: Path | None = None, validate: bool = True) -> dict:
    """Rebuild one side/mode dataset and attach baseline predictions by source.

    ``mode`` is ``offline`` or ``causal``. Extraction is imported from the
    established paired pipelines; this module only validates and packages it.
    """
    if side not in {"L", "R"}:
        raise ValueError("side must be L or R")
    if mode not in {"offline", "causal"}:
        raise ValueError("mode must be offline or causal")
    baseline_root = baseline_root or ROOT / f"model/paired-synchronized-{mode}"
    if mode == "causal":
        from streaming_pipeline import StreamExtractor
        with StreamExtractor() as extractor:
            bags, y, subjects, exercises, sources, rejected = pp.collect(root, side, extractor)
    else:
        bags, y, subjects, exercises, sources, rejected = pp.collect(root, side)

    report, baseline_predictions = _baseline(mode, side, baseline_root)
    expected_rejected = {row["source"]: row["reason"] for row in report.get("rejected", [])}
    actual_rejected = {row["source"]: row["reason"] for row in rejected}
    if actual_rejected != expected_rejected:
        raise ValueError(f"rejected source set differs from baseline (actual={len(actual_rejected)}, expected={len(expected_rejected)})")
    if len(set(subjects)) != 30:
        raise ValueError(f"expected 30 subjects, found {len(set(subjects))}")
    if len(set(sources)) != len(sources):
        raise ValueError("rebuilt dataset contains duplicate sources")
    if set(sources) != set(baseline_predictions):
        missing = sorted(set(baseline_predictions) - set(sources))
        extra = sorted(set(sources) - set(baseline_predictions))
        raise ValueError(f"source cohort differs from baseline (missing={missing[:3]}, extra={extra[:3]})")

    pred_by_source = {source: baseline_predictions[source] for source in sources}
    cycles = int(sum(map(len, bags)))
    if validate:
        checks = {
            "series": len(sources),
            "subjects": len(set(subjects)),
            "cycles": cycles,
            "features": bags[0].shape[1] if bags else 0,
        }
        for field, actual in checks.items():
            if actual != report[field]:
                raise ValueError(f"{side}/{mode} {field} mismatch: rebuilt {actual}, baseline {report[field]}")
        for i, source in enumerate(sources):
            row = pred_by_source[source]
            actual = (str(subjects[i]), str(exercises[i]), int(y[i]))
            expected = (row["subject"], row["exercise"], int(row["quality"]))
            if actual != expected:
                raise ValueError(f"{source}: rebuilt subject/exercise/label {actual} != baseline {expected}")

    return {"bags": bags, "y": y, "subjects": subjects, "exercises": exercises,
            "sources": sources, "baseline_predictions": pred_by_source,
            "mode": mode, "side": side, "cycles": cycles,
            "rejected": rejected, "baseline_report": report}


def self_check(root: Path = ROOT / "data/phytmo/inertial/upper"):
    for mode in ("offline", "causal"):
        for side in "LR":
            data = build_dataset(root, side, mode)
            pred, epred = rp.fold_predictions(data["bags"], data["y"], data["subjects"], data["exercises"])
            mismatch = []
            for i, source in enumerate(data["sources"]):
                row = data["baseline_predictions"][source]
                if int(pred[i]) != int(row["quality_prediction"]) or str(epred[i]) != row["exercise_prediction"]:
                    mismatch.append(source)
            feature_hash = hashlib.sha256(np.concatenate(data["bags"], axis=0).astype("<f4", copy=False).tobytes()).hexdigest()
            input_hash = hashlib.sha256()
            for source in data["sources"]:
                source_path = root / source
                counter_path = source_path.parent.parent / f"{side}forearm" / source_path.name
                for input_path in (source_path, counter_path):
                    input_hash.update(input_path.relative_to(root).as_posix().encode())
                    input_hash.update(input_path.read_bytes())
            audit = {"side": side, "mode": mode, "series": len(data["sources"]), "cycles": data["cycles"],
                     "quality_prediction_mismatches": int(sum(int(pred[i]) != int(data["baseline_predictions"][s]["quality_prediction"]) for i, s in enumerate(data["sources"]))),
                     "exercise_prediction_mismatches": int(sum(str(epred[i]) != data["baseline_predictions"][s]["exercise_prediction"] for i, s in enumerate(data["sources"]))),
                     "feature_sha256": feature_hash, "input_pair_sha256": input_hash.hexdigest()}
            if mismatch:
                raise AssertionError(f"{side}/{mode}: {len(mismatch)} fresh LOSO predictions differ from baseline; e.g. {mismatch[:3]}")
            cache = ROOT / "output/scale/cache" / f"{side}-{mode}.npz"
            save_dataset(data, cache)
            (cache.with_suffix(".json")).write_text(json.dumps(audit, indent=2) + "\n")
            print(f"{side}/{mode}: {len(data['sources'])} series, {data['cycles']} cycles, "
                  f"{len(set(data['subjects']))} subjects, source-aligned baseline; saved {cache}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/phytmo/inertial/upper")
    parser.add_argument("--side", choices=("L", "R"))
    parser.add_argument("--mode", choices=("offline", "causal"))
    args = parser.parse_args()
    if (args.side is None) != (args.mode is None):
        parser.error("--side and --mode must be supplied together")
    if args.side is None:
        self_check(args.root)
    else:
        data = build_dataset(args.root, args.side, args.mode)
        print(f"{args.side}/{args.mode}: {len(data['sources'])} series, {data['cycles']} cycles; validated")


if __name__ == "__main__":
    main()
