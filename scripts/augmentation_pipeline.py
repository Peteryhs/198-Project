"""Raw acceleration augmentation and matched volunteer-held-out evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from modelling_environment import check_environment
check_environment()

import numpy as np
from scipy.spatial.transform import Rotation
from scipy.signal import butter, sosfilt, sosfilt_zi
import sklearn
import scipy

import paired_pipeline as pp
import realtime_pipeline as rp
from streaming_pipeline import StreamExtractor


VERSION = 1
DATASET_VERSION = "PHYTMO Zenodo 6319979"
DEFAULT_CONFIG = {
    "version": VERSION,
    "seed": 0,
    "augmentation_count": 1,
    "sample_rate_hz": 100.0,
    "bias_g": [0.0, 0.0, 0.0],
    "gain": [1.0, 1.0, 1.0],
    "noise_std_g": 0.0,
    "lowpass_hz": 20.0,
    "orientation": {"max_degrees": 0.0},
    "quantization_step_g": None,
    "clip_g": 3.0,
}


def _triple(value, key, positive=False):
    if any(isinstance(v, (bool, np.bool_)) for v in np.asarray(value, dtype=object).flat):
        raise ValueError(f"{key} must be numeric, not boolean")
    a = np.asarray(value)
    if a.dtype.kind == "b":
        raise ValueError(f"{key} must be numeric, not boolean")
    try: a = a.astype(float)
    except (TypeError, ValueError): raise ValueError(f"{key} must be numeric") from None
    if a.ndim == 0:
        a = np.repeat(a, 3)
    if a.shape != (3,) or not np.isfinite(a).all() or (positive and np.any(a <= 0)):
        raise ValueError(f"{key} must be a finite scalar or three values" + (" > 0" if positive else ""))
    return a.tolist()


def validate_config(config: dict) -> dict:
    """Validate and return a normalized, self-contained versioned config."""
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    allowed = set(DEFAULT_CONFIG)
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"unsupported config fields: {sorted(unknown)}")
    out = {**DEFAULT_CONFIG, **config}
    if type(out["version"]) is not int or out["version"] != VERSION:
        raise ValueError(f"unsupported augmentation config version: {out['version']}")
    if not isinstance(out["seed"], int) or isinstance(out["seed"], bool) or out["seed"] < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not isinstance(out["augmentation_count"], int) or isinstance(out["augmentation_count"], bool) or not 1 <= out["augmentation_count"] <= 100:
        raise ValueError("augmentation_count must be an integer from 1 to 100")
    for k in ("sample_rate_hz", "noise_std_g", "clip_g"):
        if isinstance(out[k], bool):
            raise ValueError(f"{k} must be numeric, not boolean")
        try: value = float(out[k])
        except (TypeError, ValueError): raise ValueError(f"{k} must be numeric") from None
        if not np.isfinite(value) or value < 0 or (k != "noise_std_g" and value == 0):
            raise ValueError(f"{k} must be finite and " + ("nonnegative" if k == "noise_std_g" else "positive"))
        out[k] = value
    if not np.isclose(out["sample_rate_hz"], 100.0):
        raise ValueError("sample_rate_hz must be 100 Hz for the paired C feature pipeline")
    out["bias_g"] = _triple(out["bias_g"], "bias_g")
    out["gain"] = _triple(out["gain"], "gain", positive=True)
    if out["lowpass_hz"] is not None:
        if isinstance(out["lowpass_hz"], bool):
            raise ValueError("lowpass_hz must be numeric or null, not boolean")
        try: out["lowpass_hz"] = float(out["lowpass_hz"])
        except (TypeError, ValueError): raise ValueError("lowpass_hz must be numeric or null") from None
        if not np.isfinite(out["lowpass_hz"]) or not 0 < out["lowpass_hz"] < out["sample_rate_hz"] / 2:
            raise ValueError("lowpass_hz must be null or between 0 and Nyquist")
    orient = out["orientation"]
    if not isinstance(orient, dict) or set(orient) != {"max_degrees"}:
        raise ValueError("orientation must contain only max_degrees")
    angle = orient["max_degrees"]
    if isinstance(angle, bool):
        raise ValueError("orientation.max_degrees must be numeric, not boolean")
    try: angle = float(angle)
    except (TypeError, ValueError): raise ValueError("orientation.max_degrees must be numeric") from None
    if not np.isfinite(angle) or not 0 <= angle <= 180:
        raise ValueError("orientation.max_degrees must be between 0 and 180")
    out["orientation"] = {"max_degrees": angle}
    step = out["quantization_step_g"]
    if step is not None:
        if isinstance(step, bool):
            raise ValueError("quantization_step_g must be numeric or null, not boolean")
        try: step = float(step)
        except (TypeError, ValueError): raise ValueError("quantization_step_g must be numeric or null") from None
        if not np.isfinite(step) or step <= 0:
            raise ValueError("quantization_step_g must be null or positive")
        out["quantization_step_g"] = step
    return out


def loso_indices(subjects, held_out):
    """Return a disjoint train/test partition for one held-out volunteer."""
    subjects = np.asarray(subjects)
    train = np.flatnonzero(subjects != held_out)
    test = np.flatnonzero(subjects == held_out)
    if not len(test) or set(subjects[train]) & {held_out}:
        raise ValueError("LOSO partition leaks held-out subject or has no held-out rows")
    return train, test


def _transform_details(x, config: dict, seed: int):
    c = validate_config(config)
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or x.shape[1] not in (3, 6) or len(x) < 12 or not np.isfinite(x).all():
        raise ValueError("x must be finite (n>=12, 3) or (n>=12, 6) acceleration in g")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    rng = np.random.default_rng(seed)
    out = x.copy(); orientations = []
    for j in range(0, x.shape[1], 3):
        v = out[:, j:j + 3]
        angle = np.deg2rad(c["orientation"]["max_degrees"])
        matrix = np.eye(3)
        if angle:
            axis = rng.normal(size=3)
            axis /= np.linalg.norm(axis)
            rotation = Rotation.from_rotvec(axis * rng.uniform(-angle, angle))
            matrix = rotation.as_matrix()
            v = rotation.apply(v)
        orientations.append(matrix.tolist())
        v = v * c["gain"] + c["bias_g"]
        if c["lowpass_hz"] is not None:
            sos = butter(1, c["lowpass_hz"], btype="lowpass", fs=c["sample_rate_hz"], output="sos")
            v, _ = sosfilt(sos, v, axis=0, zi=sosfilt_zi(sos)[:, :, None] * v[0][None, None, :])
        if c["noise_std_g"]:
            v += rng.normal(0.0, c["noise_std_g"], v.shape)
        step = c["quantization_step_g"]
        if step is not None:
            v = np.round(v / step) * step
        out[:, j:j + 3] = np.clip(v, -c["clip_g"], c["clip_g"])
    if not np.isfinite(out).all():
        raise ValueError("augmentation produced nonfinite values")
    return out, {"seed": int(seed), "orientation_matrices": orientations,
                 "bias_g": c["bias_g"], "gain": c["gain"], "noise_std_g": c["noise_std_g"]}


def transform(x, config: dict, seed: int) -> np.ndarray:
    """Transform an (n, 3) or paired (n, 6) acceleration matrix, in g."""
    return _transform_details(x, config, seed)[0]


def transform_with_provenance(x, config: dict, seed: int):
    """Return transformed acceleration and exact sampled transformation parameters."""
    return _transform_details(x, config, seed)


def config_hash(config: dict) -> str:
    raw = json.dumps(validate_config(config), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _seed(config, source, variant):
    raw = f"{config['seed']}|{source}|{variant}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "little")


def load_side(root: Path, side: str, clip_g: float):
    data, rejected, seen, expected = [], [], set(), {}
    for path, meta, x, error in pp.records(root, side):
        name = path.relative_to(root).as_posix()
        if meta:
            seen.add(meta[0])
            expected[meta[0]] = expected.get(meta[0], 0) + 1
        if error:
            rejected.append({"source_id": name, "reason": error})
            continue
        counterpart = name.replace(f"/{side}arm/", f"/{side}forearm/")
        counterpart_path = path.parent.parent / f"{side}forearm" / path.name
        data.append({"source_id": name, "counterpart_id": counterpart, "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "counterpart_sha256": hashlib.sha256(counterpart_path.read_bytes()).hexdigest(),
                     "subject": meta[0], "exercise": meta[1], "label": meta[3], "raw": x, "clip_g": clip_g})
    if len(seen) != 30:
        raise ValueError(f"LOSO requires all 30 source volunteers; saw {len(seen)}")
    return data, rejected, expected


def _features(record, x, extractor):
    f = extractor(np.ascontiguousarray(np.clip(x, -record["clip_g"], record["clip_g"]), dtype=np.float32))
    return f if len(f) >= 3 else None


def _generate(records, extractor, config, out):
    generated_dir = out / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    manifest, variants, transformed_lineage, preview = [], [], [], None
    cfg_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    cohort_subjects = sorted({r["subject"] for r in records})
    for r in records:
        raw_bytes = np.asarray(r["raw"], dtype="<f8").tobytes()
        aligned_hash = hashlib.sha256(raw_bytes).hexdigest()
        row_variants = []
        for vi in range(config["augmentation_count"]):
            seed = _seed(config, r["source_id"], vi)
            x, details = _transform_details(r["raw"], config, seed)
            # Feature coverage is meaningful only at the paired pipeline's fixed ±3 g contract.
            f = _features(r, x, extractor) if config["clip_g"] == 3.0 else None
            time_s = np.arange(len(x), dtype=float) / config["sample_rate_hz"]
            checks = {"finite": bool(np.isfinite(x).all()),
                      "sample_count_preserved": len(x) == len(r["raw"]),
                      "time_step_100hz": bool(np.allclose(np.diff(time_s), 0.01)),
                      "clip_respected": bool(np.max(np.abs(x)) <= config["clip_g"] + 1e-12),
                      "c_feature_coverage": int(len(f)) if f is not None else None,
                      "feature_coverage_status": "fixed ±3 g C diagnostic" if config["clip_g"] == 3.0 else "not evaluated; clip differs from fixed C contract"}
            token = hashlib.sha256(r["source_id"].encode()).hexdigest()[:16]
            artifact = generated_dir / f"{token}-v{vi:02d}.npz"
            provenance = {"source_id": r["source_id"], "counterpart_id": r["counterpart_id"],
                          "source_sha256": r["source_sha256"], "counterpart_sha256": r["counterpart_sha256"],
                          "aligned_pair_sha256": aligned_hash, "hash_scope": "raw CSV bytes for source/counterpart; aligned float64 paired acceleration for aligned_pair_sha256",
                          "subject": r["subject"], "exercise": r["exercise"],
                          "label": r["label"], "label_origin": "measured series label inherited by transformed copy",
                          "status": "transformed", "variant": vi, "dataset_version": DATASET_VERSION,
                          "pipeline_version": VERSION, "config_version": config["version"],
                          "validation_status": "implementation checks only; physical transfer unvalidated; no downstream benefit established",
                          "config_sha256": config_hash(config),
                          **details, "validation": checks}
            np.savez_compressed(artifact, time_s=time_s, original_g=r["raw"], augmented_g=x,
                                config_json=np.asarray(cfg_json), provenance_json=np.asarray(json.dumps(provenance, sort_keys=True)))
            item = {**provenance, "artifact": str(artifact),
                    "status": "transformed" if f is not None else ("generated_only" if config["clip_g"] != 3.0 else "transformed_rejected"),
                    "training_only": bool(f is not None and config["clip_g"] == 3.0),
                    "training_fold_held_out_subjects": [s for s in cohort_subjects if s != r["subject"]] if f is not None else []}
            manifest.append(item); transformed_lineage.append(item); row_variants.append((f, x, details))
            if preview is None:
                ends = [] if f is None else [float(k / config["sample_rate_hz"]) for k in extractor.ends]
                preview = (r, x, ends, vi, provenance)
        variants.append(row_variants)
    with (out / "augmentation-manifest.jsonl").open("w") as f:
        for item in manifest:
            f.write(json.dumps(item, sort_keys=True) + "\n")
    return variants, transformed_lineage, preview


def _fit_predict(records, real_bags, variants, config):
    subjects = sorted({r["subject"] for r in records})
    pred = np.full(len(records), -1, dtype=int)
    epred = np.full(len(records), "abstain", dtype=object)
    folds, transformed_rejects = [], []
    for held in subjects:
        tr, te = loso_indices([r["subject"] for r in records], held)
        tr, te = tr.tolist(), te.tolist()
        tbags, ty, tx, bag_sources = [], [], [], []
        for i in tr:
            r = records[i]
            bag_variants = [(real_bags[i], None, None), *variants[i]]
            for vi, (f, _x, _details) in enumerate(bag_variants):
                if f is None:
                    if vi:
                        transformed_rejects.append({"source_id": r["source_id"], "variant": vi - 1,
                                                   "reason": "fewer than 3 C cycles"})
                    continue
                tbags.append(f); ty.append(r["label"]); tx.append(r["exercise"]); bag_sources.append(r["source_id"])
        if not tbags:
            raise ValueError(f"empty training fold for held-out subject {held}")
        X = np.vstack(tbags)
        # Every original source series contributes total weight 1; its copies split that same weight.
        source_counts = {s: bag_sources.count(s) for s in set(bag_sources)}
        weights = np.concatenate([np.full(len(b), 1.0 / (len(b) * source_counts[source]))
                                  for b, source in zip(tbags, bag_sources)])
        qmodel = rp.fit_model(X, np.concatenate([np.full(len(b), y) for b, y in zip(tbags, ty)]), weights)
        # For exercise head, match the same flattening used by round-two paired LOSO.
        yex = np.concatenate([np.full(len(b), e) for b, e in zip(tbags, tx)])
        emodel = rp.fit_model(X, yex, weights)
        for i in te:
            r = records[i]
            f = real_bags[i]
            pred[i] = int(rp.series_probs(qmodel, f)[1] >= .5)
            ep = rp.series_probs(emodel, f)
            epred[i] = emodel.classes_[np.argmax(ep)]
        fold_train_subjects = sorted({records[i]["subject"] for i in tr})
        fold_test_subjects = sorted({records[i]["subject"] for i in te})
        if held in fold_train_subjects or fold_test_subjects != [held] or set(fold_train_subjects) & set(fold_test_subjects):
            raise ValueError(f"LOSO subject leakage in fold {held}")
        folds.append({"subject": held, "train_subjects": fold_train_subjects, "test_subjects": fold_test_subjects,
                      "n_series": len(te), "test_source_ids": [records[i]["source_id"] for i in te],
                      "quality_accuracy": float(np.mean(pred[te] == [records[i]["label"] for i in te])),
                      "quality_train_majority_floor": float(np.mean([records[i]["label"] == int(np.mean([records[j]["label"] for j in tr]) >= .5) for i in te])),
                      "exercise_accuracy": float(np.mean(epred[te] == [records[i]["exercise"] for i in te])),
                      "exercise_train_majority_floor": float(np.mean([records[i]["exercise"] == max(sorted({records[j]["exercise"] for j in tr}), key=lambda e: sum(records[j]["exercise"] == e for j in tr)) for i in te]))})
    return pred, epred, folds, transformed_rejects


def _percentile_subject_interval(correct_a, correct_b, subjects, seed):
    people = np.unique(subjects); rng = np.random.default_rng(seed); scores = []
    difference = correct_b.astype(float) - correct_a.astype(float)
    for _ in range(2000):
        selected = rng.choice(people, len(people), replace=True)
        ix = np.concatenate([np.flatnonzero(subjects == s) for s in selected])
        scores.append(float(difference[ix].mean()))
    return [float(x) for x in np.percentile(scores, [2.5, 97.5])]


def evaluate_side(root: Path, side: str, config: dict, out: Path):
    config = validate_config(config)
    if config["clip_g"] != 3.0:
        raise ValueError("paired LOSO evaluation requires the fixed ±3 g C pipeline contract; use --generate-only for other clip settings")
    data, rejected, expected_by_subject = load_side(root, side, config["clip_g"])
    with StreamExtractor() as extractor:
        # Retain only source series with valid real features. Both arms and held-out sides share this cohort.
        records, real_bags = [], []
        for r in data:
            f = _features(r, r["raw"], extractor)
            if f is None:
                rejected.append({"source_id": r["source_id"], "reason": "fewer than 3 C cycles"})
            else:
                records.append(r); real_bags.append(f)
        subjects = np.asarray([r["subject"] for r in records]); labels = np.asarray([r["label"] for r in records])
        exercises = np.asarray([r["exercise"] for r in records])
        if len(set(subjects)) != 30:
            raise ValueError("retained cohort no longer covers all 30 volunteers")
        # Use one fixed set of C features and folds for the real-only arm.
        folds = sorted(set(subjects)); real_pred = np.full(len(records), -1, int); real_epred = np.full(len(records), "abstain", object)
        for held in folds:
            tr = subjects != held; te = ~tr
            X, yr, ye, w = rp.flattened(real_bags, labels, exercises, tr)
            qm, em = rp.fit_model(X, yr, w), rp.fit_model(X, ye, w)
            for i in np.flatnonzero(te):
                real_pred[i] = int(rp.series_probs(qm, real_bags[i])[1] >= .5)
                ep = rp.series_probs(em, real_bags[i]); real_epred[i] = em.classes_[np.argmax(ep)]
        variants, trans_lineage, preview = _generate(records, extractor, config, out)
        aug_pred, aug_epred, aug_folds, trans_rej = _fit_predict(records, real_bags, variants, config)
    out.mkdir(parents=True, exist_ok=True)
    real_q = real_pred == labels; aug_q = aug_pred == labels
    real_e = real_epred == exercises; aug_e = aug_epred == exercises
    qfloor = float(np.unique(labels, return_counts=True)[1].max() / len(labels))
    efloor = float(np.unique(exercises, return_counts=True)[1].max() / len(exercises))
    qtrain = float(np.average([f["quality_train_majority_floor"] for f in aug_folds], weights=[f["n_series"] for f in aug_folds]))
    etrain = float(np.average([f["exercise_train_majority_floor"] for f in aug_folds], weights=[f["n_series"] for f in aug_folds]))
    retained_by_subject = {s: int(sum(r["subject"] == s for r in records)) for s in sorted(expected_by_subject)}
    report = {
        "source": "real PHYTMO recordings; paired accelerations; augmentation applied to training subjects only",
        "dataset_version": DATASET_VERSION, "pipeline_version": VERSION,
        "side": side, "subjects": len(set(subjects)), "series": len(records), "cycles": int(sum(map(len, real_bags))),
        "quality_majority_class_floor": qfloor, "exercise_majority_class_floor": efloor,
        "training_fold_majority_floors": {"quality": qtrain, "exercise": etrain},
        "coverage": {"source_series_seen": int(sum(expected_by_subject.values())), "retained": len(records),
                     "retention_fraction": float(len(records) / sum(expected_by_subject.values())),
                     "subjects_seen": len(expected_by_subject),
                     "retained_by_subject": {s: {"seen": int(expected_by_subject[s]), "retained": retained_by_subject[s]} for s in sorted(expected_by_subject)}},
        "real_only": {"quality_accuracy": float(real_q.mean()), "exercise_accuracy": float(real_e.mean())},
        "augmented_train_only": {"quality_accuracy": float(aug_q.mean()), "exercise_accuracy": float(aug_e.mean()),
                                 "quality_subject_bootstrap_95_difference_interval": _percentile_subject_interval(real_q, aug_q, subjects, config["seed"]),
                                 "exercise_subject_bootstrap_95_difference_interval": _percentile_subject_interval(real_e, aug_e, subjects, config["seed"] + 1)},
        "config": config, "config_sha256": config_hash(config),
        "training": "fixed C=1 paired C pipeline, LOSO; each source series total weight 1, divided over its original and successfully transformed copies; transformed copies use training subjects only",
        "held_out": "unaltered measured real series only; no tuning on held-out scores",
        "split_audit": {"method": "LOSO by source volunteer", "fold_count": len(aug_folds),
                        "all_30_subjects_tested": len(aug_folds) == 30,
                        "train_test_subject_overlap": [], "training_subject_count_per_fold": len(set(subjects)) - 1},
        "rejected_source_ids": rejected, "transformed_training_rejections": trans_rej,
        "folds": aug_folds, "lineage": ([{"source_id": r["source_id"], "counterpart_id": r["counterpart_id"],
            "source_sha256": r["source_sha256"], "counterpart_sha256": r["counterpart_sha256"],
            "subject": r["subject"], "exercise": r["exercise"], "label": r["label"],
            "label_origin": "measured series label", "dataset_version": DATASET_VERSION,
            "status": "measured", "transformed": False} for r in records] + trans_lineage),
        "validation": "series-level pseudo-labels only; no repetition ground truth; no anatomical or clinical error labels",
        "provenance": {"argv": sys.argv, "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__, "seed": config["seed"]},
    }
    if preview:
        r, x, ends, variant, provenance = preview
        preview_obj = {"time_s": [float(i / config["sample_rate_hz"]) for i in range(len(x))],
                       "original_g": r["raw"].tolist(), "augmented_g": x.tolist(), "boundaries_s": ends,
                       "provenance": provenance, "config": config, "config_sha256": config_hash(config)}
        (out / "example.json").write_text(json.dumps(preview_obj, separators=(",", ":")) + "\n")
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    import csv
    with (out / "predictions.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["source_id", "subject", "exercise", "label", "real_quality_prediction", "augmented_quality_prediction", "real_exercise_prediction", "augmented_exercise_prediction", "status"])
        w.writerows((r["source_id"], r["subject"], r["exercise"], r["label"], int(real_pred[i]), int(aug_pred[i]), str(real_epred[i]), str(aug_epred[i]), "measured held-out") for i, r in enumerate(records))
    print(json.dumps({k: v for k, v in report.items() if k not in {"folds", "lineage", "rejected_source_ids", "transformed_training_rejections", "coverage"}}, indent=2))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="PHYTMO raw inertial root")
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("data/phase3-augmentation"))
    ap.add_argument("--generate-only", action="store_true", help="write transformed raw series without fitting; permits configurable clipping")
    args = ap.parse_args()
    config = validate_config(json.loads(args.config.read_text()))
    for side in "LR":
        out = args.out / args.config.stem / side
        if args.generate_only:
            records, rejected, _expected = load_side(args.root, side, config["clip_g"])
            with StreamExtractor() as extractor:
                variants, lineage, preview = _generate(records, extractor, config, out)
            if preview:
                r, x, ends, variant, provenance = preview
                preview_obj = {"time_s": [float(i / config["sample_rate_hz"]) for i in range(len(x))],
                               "original_g": r["raw"].tolist(), "augmented_g": x.tolist(), "boundaries_s": ends,
                               "provenance": provenance, "config": config, "config_sha256": config_hash(config)}
                (out / "example.json").write_text(json.dumps(preview_obj, separators=(",", ":")) + "\n")
            (out / "generation.json").write_text(json.dumps({"config": config, "config_sha256": config_hash(config),
                "generated": len(lineage), "rejected_source_ids": rejected, "status": "generation only; no model fitting"}, indent=2) + "\n")
        else:
            evaluate_side(args.root, side, config, out)


if __name__ == "__main__":
    main()
