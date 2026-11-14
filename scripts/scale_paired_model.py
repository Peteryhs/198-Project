"""Capacity-only paired LOSO experiment. Run with .venv/bin/python; no baseline is written."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import warnings

import numpy as np
from scipy.stats import binomtest
from threadpoolctl import threadpool_limits

import scale_paired_features as features
import scale_paired_models as models

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "docs/runs/scale"
CACHE = ROOT / "output/scale/cache"


def write_json(path, value):
    def convert(v):
        if isinstance(v, np.ndarray): return v.tolist()
        if isinstance(v, np.generic): return v.item()
        raise TypeError(type(v).__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, default=convert, allow_nan=False) + "\n")
    temp.replace(path)


def milestone(message):
    line = time.strftime("%Y-%m-%dT%H:%M:%S%z ") + message
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / "progress.log").open("a") as handle: handle.write(line + "\n")
    try:
        with Path("/home/peter/work/198-scale/progress.log").open("a") as handle: handle.write(line + "\n")
    except OSError:
        pass  # This session mounts the requested external log read-only; local log records milestones.
    print(line, flush=True)


def load_cohort(mode, side):
    data = features.load_dataset(CACHE / f"{side}-{mode}.npz")
    baseline = ROOT / f"model/paired-synchronized-{mode}" / side / "results.json"
    data.update(mode=mode, side=side, baseline_report=json.loads(baseline.read_text()))
    audit = json.loads((CACHE / f"{side}-{mode}.json").read_text())
    matrix = np.concatenate(data["bags"])
    assert matrix.shape == (audit["cycles"], 61) and matrix.dtype == np.float32 and np.isfinite(matrix).all()
    assert hashlib.sha256(matrix.astype("<f4", copy=False).tobytes()).hexdigest() == audit["feature_sha256"]
    assert len(data["y"]) == audit["series"] and len(set(data["subjects"])) == 30
    qbase = np.array([int(data["baseline_predictions"][s]["quality_prediction"]) for s in data["sources"]])
    ebase = np.array([data["baseline_predictions"][s]["exercise_prediction"] for s in data["sources"]])
    assert float(np.mean(qbase == data["y"])) == data["baseline_report"]["quality_accuracy"]
    assert float(np.mean(ebase == data["exercises"])) == data["baseline_report"]["exercise_accuracy"]
    return data


def comparison(data, row):
    y = data["y"]
    baseline = np.array([int(data["baseline_predictions"][s]["quality_prediction"]) for s in data["sources"]])
    correct = np.asarray(row["quality_prediction"]) == y
    base_correct = baseline == y
    gains = int(np.sum(correct & ~base_correct)); losses = int(np.sum(~correct & base_correct))
    folds = []
    for subject in sorted(set(data["subjects"])):
        mask = data["subjects"] == subject
        folds.append(dict(subject=str(subject), n=int(mask.sum()),
                          baseline=float(base_correct[mask].mean()), quality=float(correct[mask].mean()),
                          delta_correct=int(correct[mask].sum() - base_correct[mask].sum())))
    # Resample subjects, retaining each subject's series as a block.
    rng = np.random.default_rng(0)
    draws = rng.integers(0, len(folds), (20000, len(folds)))
    differences = np.array([f["delta_correct"] for f in folds])
    counts = np.array([f["n"] for f in folds])
    delta = differences[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return dict(gained_series=gains, lost_series=losses,
                mcnemar_exact_two_sided_p=float(binomtest(gains, gains + losses, .5).pvalue) if gains + losses else 1.,
                subject_bootstrap_delta_95_interval=np.quantile(delta, [.025, .975]).tolist(),
                bootstrap_resamples=20000, bootstrap_seed=0,
                subjects_won=sum(f["delta_correct"] > 0 for f in folds),
                subjects_lost=sum(f["delta_correct"] < 0 for f in folds),
                subjects_tied=sum(f["delta_correct"] == 0 for f in folds),
                fold_quality_min=min(f["quality"] for f in folds),
                fold_quality_max=max(f["quality"] for f in folds), folds=folds)


def run_cohort(mode, side):
    data = load_cohort(mode, side)
    feature_hash = json.loads((CACHE / f"{side}-{mode}.json").read_text())["feature_sha256"]
    for config in models.model_configs():
        destination = RUN / f"{mode}-{side}" / f"{config.name}.json"
        if destination.exists():
            old = json.loads(destination.read_text())
            if old["config_spec"] != json.loads(json.dumps(asdict(config))):
                raise ValueError(f"stale configuration checkpoint: {destination}")
            if old.get("feature_sha256", feature_hash) != feature_hash:
                raise ValueError(f"feature matrix changed; remove stale checkpoint: {destination}")
            continue
        milestone(f"start {mode}/{side}/{config.name}")
        with threadpool_limits(limits=1):
            row = models.evaluate_variant(data["bags"], data["y"], data["subjects"], data["exercises"], config)
        row.update(mode=mode, side=side, feature_sha256=feature_hash)
        base = data["baseline_report"]
        row["quality_delta_pp"] = 100 * (row["quality_accuracy"] - base["quality_accuracy"])
        row["exercise_delta_pp"] = 100 * (row["exercise_accuracy"] - base["exercise_accuracy"])
        write_json(destination, row)
        milestone(f"finished {mode}/{side}/{config.name}: quality={row['quality_accuracy']:.6f}, exercise={row['exercise_accuracy']:.6f}")


def measure_full(data, config, row):
    X, yq, ye, weights = features.flatten_train(data, np.ones(len(data["y"]), bool))
    weights *= len(weights) / weights.sum()
    with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        start = time.perf_counter()
        qm, em = models.fit_pair(X, yq, ye, weights, config)
        row["full_fit_seconds"] = time.perf_counter() - start
        target = ROOT / "output/scale/models" / f"{data['mode']}-{data['side']}" / f"{config.name}.npz"
        row["parameter_bytes"] = models.export_pair(target, qm, em)
        row["parameter_delta_bytes"] = row["parameter_bytes"] - data["baseline_report"]["parameter_bytes"]
        row["npz_file_bytes"] = target.stat().st_size
        state = models.load_numeric(target)
        max_error = 0.
        # All rebuilt cycles, plus synthetic probes from export_pair, exercise both numeric loaders.
        for prefix, model in (("quality", qm), ("exercise", em)):
            expected = model.predict_proba(X)
            actual = models.predict_numpy(state, prefix, X)
            max_error = max(max_error, float(np.max(np.abs(expected - actual))))
            np.testing.assert_allclose(actual, expected, atol=2e-6, rtol=2e-5)
            for a, b in zip(np.split(actual, np.cumsum([len(b) for b in data["bags"]])[:-1]),
                            np.split(expected, np.cumsum([len(b) for b in data["bags"]])[:-1])):
                if prefix == "quality":
                    assert (a.mean(axis=0)[1] >= .5) == (b.mean(axis=0)[1] >= .5)
                else:
                    assert np.argmax(a.mean(axis=0)) == np.argmax(b.mean(axis=0))
        row["export_max_probability_error"] = max_error
        # Costs include both heads; use existing cycle matrices and report median warm timings.
        sample = X[:256]
        def predict(z):
            return models.predict_numpy(state, "quality", z), models.predict_numpy(state, "exercise", z)
        predict(sample)
        batch = []; single = []
        for _ in range(5):
            start = time.perf_counter(); predict(sample); batch.append((time.perf_counter() - start) / len(sample))
            start = time.perf_counter(); predict(sample[:1]); single.append(time.perf_counter() - start)
        row["numpy_batch_us_per_cycle"] = float(np.median(batch) * 1e6)
        row["numpy_single_cycle_us"] = float(np.median(single) * 1e6)
        row["full_fit_warnings"] = sorted(set(str(w.message) for w in caught))
        row["total_tree_nodes"] = sum(len(v) for k, v in state.items() if k.endswith("_left"))
        if config.kind == "extratrees":
            assert 5000 <= row["total_tree_nodes"] <= 50000
    return target


def finalize():
    import scipy, sklearn
    tables = []; selections = []; audits = []
    for mode in ("causal", "offline"):
        for side in "LR":
            data = load_cohort(mode, side)
            audit = json.loads((CACHE / f"{side}-{mode}.json").read_text()); audits.append(audit)
            rows = []
            for config in models.model_configs():
                path = RUN / f"{mode}-{side}" / f"{config.name}.json"
                row = json.loads(path.read_text())
                assert len(row["quality_prediction"]) == len(row["exercise_prediction"]) == len(data["y"])
                assert row["quality_accuracy"] == float(np.mean(np.asarray(row["quality_prediction"]) == data["y"]))
                assert row["exercise_accuracy"] == float(np.mean(np.asarray(row["exercise_prediction"]) == data["exercises"]))
                assert {f["subject"] for f in row["folds"]} == set(data["subjects"])
                assert sum(f["n_series"] for f in row["folds"]) == len(data["y"])
                row["feature_sha256"] = audit["feature_sha256"]
                if "parameter_bytes" not in row:
                    measure_full(data, config, row); write_json(path, row)
                    milestone(f"measured full fit/export/inference {mode}/{side}/{config.name}")
                rows.append(row)
            best = min(rows, key=lambda r: (-r["quality_accuracy"], r["parameter_bytes"]))
            stats = comparison(data, best)
            base = data["baseline_report"]
            worthwhile = (stats["subject_bootstrap_delta_95_interval"][0] > 0 and stats["subjects_lost"] == 0
                          and best["exercise_accuracy"] >= base["exercise_accuracy"])
            selected = dict(mode=mode, side=side, best=best["config"], comparison=stats,
                            deploy=bool(worthwhile and mode == "causal"), baseline=base,
                            series=len(data["y"]), cycles=data["cycles"])
            selections.append(selected); tables.extend(rows)
            if selected["deploy"]:
                export = ROOT / "model/paired-scaled" / side; export.mkdir(parents=True, exist_ok=True)
                source = ROOT / "output/scale/models" / f"{mode}-{side}" / f"{best['config']}.npz"
                shutil.copyfile(source, export / "model.npz")
                metadata = json.loads((ROOT / f"model/paired-synchronized-{mode}" / side / "metadata.json").read_text())
                metadata.update(model_type=best["config_spec"]["kind"], hyperparameters=best["config_spec"],
                                pooling="mean cycle probabilities; quality >= 0.5; exercise argmax",
                                loader="scripts.scale_paired_models.load_numeric; predict_numpy(state, head, X)")
                write_json(export / "metadata.json", metadata)
                write_json(export / "results.json", dict(variants=rows, selection=selected))
    provenance = dict(command=sys.argv, python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                      sklearn=sklearn.__version__, host=platform.platform(),
                      cpu=next((line.split(":",1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                                if line.startswith("model name")), platform.processor()),
                      threads_per_worker=1, numerical_export="float64 state, int32 tree indices; includes both heads and state metadata",
                      source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in [Path(__file__), Path(features.__file__), Path(models.__file__)]})
    write_json(RUN / "results.json", dict(provenance=provenance, audits=audits, selections=selections,
                                         variants=[{k:v for k,v in r.items() if k not in {"quality_prediction", "exercise_prediction", "folds"}} for r in tables]))
    report(tables, selections, audits)
    milestone("report and deployment decision complete")


def report(rows, selections, audits):
    lines = ["# Paired model capacity experiment", "", "Recommendation: **keep the existing affine deployment models**." if not any(s["deploy"] for s in selections) else "Recommendation: adopt the exported causal candidate(s) listed below, subject to the stated evidence limits.", "",
             "All scores are series-level subject-held-out LOSO on the baseline's retained recordings within each side/mode and the same 61 float32 features. Cycle labels remain inherited pseudo-labels. Pairing, boundaries, clipping, features, equal total series weights, probability pooling, and folds are unchanged. Fresh affine refits reproduced every stored decision for both heads in all four cohorts (see `results.json` audits). Left/right cohorts differ, so this is not a matched side comparison.", "",
             "| Baseline | Side | Series | Cycles | Quality % | Exercise % | Parameter B |", "|---|---|---:|---:|---:|---:|---:|"]
    if all(s["comparison"]["subject_bootstrap_delta_95_interval"][0] <= 0 for s in selections):
        lines[4:4] = ["No selected variant establishes a quality gain beyond subject-fold noise: every exploratory subject-block interval includes zero or favors the baseline.", ""]
    for s in selections:
        b=s["baseline"]
        lines.append(f"| synchronized-{s['mode']} | {s['side']} | {b['series']} | {b['cycles']} | {100*b['quality_accuracy']:.2f} | {100*b['exercise_accuracy']:.2f} | {b['parameter_bytes']} |")
    lines += ["", "Capacity grid fixed before reading scores: HGB leaves 15/31/63 × iterations 50/200, learning rate 0.1, no early stopping; MLP ReLU hidden layers 64, 128–64, 256–128, Adam, alpha=0.0001, max_iter=300, no validation split, training-fold weighted standardisation; ExtraTrees 32 trees/head, max_leaf_nodes=256. Seed 0 for every estimator. Other estimator defaults are scikit-learn 1.7.2. Full settings and convergence warnings are in the per-variant JSON files.", "",
              "| Cohort | Side | Variant | Quality % | Δ pp | Exercise % | Δ pp | State B | LOSO train s | Full fit s | NumPy batch µs/cycle | NumPy single µs |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['mode']} | {r['side']} | {r['config']} | {100*r['quality_accuracy']:.2f} | {r['quality_delta_pp']:+.2f} | {100*r['exercise_accuracy']:.2f} | {r['exercise_delta_pp']:+.2f} | {r['parameter_bytes']} | {r['train_seconds']:.2f} | {r['full_fit_seconds']:.2f} | {r['numpy_batch_us_per_cycle']:.2f} | {r['numpy_single_cycle_us']:.2f} |")
    lines += ["", "Measured ExtraTrees full-model nodes (both heads): " + "; ".join(
        f"{r['mode']}/{r['side']} {r['total_tree_nodes']}" for r in rows if r["config_spec"]["kind"] == "extratrees") + "."]
    lines += ["", "Training costs are measured host wall time for both heads: LOSO sums the held-out fits; full fit trains on all retained data. Sweep workers may contend for CPU; full fits and inference benchmarks run sequentially with one library thread. Inference is the exported NumPy loader, median of five warm runs on 256 cycles (batch) or one cycle (single), excluding feature extraction, loading, and pooling. State bytes are the uncompressed NPZ array payload including scaling, topology and classes, not Python process RAM; compressed file bytes and actual ensemble node counts are in JSON. The affine baseline's 992 B counts float32 coefficients/intercepts; larger exports use float64 values and int32 indices and count their full array state. These are x86 host measurements, not AR9331 estimates; CPU/compiler details are in `host.json`.", ""]
    if any(r.get("warnings") or r.get("full_fit_warnings") for r in rows):
        lines += ["Some MLP fits reached the fixed iteration limit without convergence. Their scores describe that fixed training budget; no extra iterations or hyperparameter tuning were selected from these folds.", ""]
    for s in selections:
        c=s["comparison"]; lo,hi=c["subject_bootstrap_delta_95_interval"]
        lines += [f"**{s['mode']}/{s['side']} best: {s['best']}.** Fold quality range {100*c['fold_quality_min']:.2f}–{100*c['fold_quality_max']:.2f}%; subjects won/tied/lost {c['subjects_won']}/{c['subjects_tied']}/{c['subjects_lost']}. Paired series gains/losses {c['gained_series']}/{c['lost_series']}; exact two-sided McNemar p={c['mcnemar_exact_two_sided_p']:.6g}. Subject-block bootstrap 95% interval for the aggregate quality change: [{100*lo:+.2f}, {100*hi:+.2f}] pp.", ""]
        lines += [(f"Deploy the exported causal candidate in `model/paired-scaled/{s['side']}/`." if s["deploy"] else
                   "Retain the affine model on this side." if s["mode"] == "causal" else "Offline segmentation control only."), ""]
        moved = [f"{f['subject']} {100*f['baseline']:.1f}→{100*f['quality']:.1f}% ({f['delta_correct']:+d}/{f['n']})" for f in c["folds"] if f["delta_correct"]]
        lines += ["Changed subject folds: " + ("; ".join(moved) if moved else "none") + ".", ""]
        if c["subjects_lost"]:
            lines += ["This candidate regresses on the listed losing subjects, including when its aggregate mean rises.", ""]
    lines += ["Variants were selected on these same folds: McNemar p-values and bootstrap intervals are **descriptive, not confirmatory**. McNemar treats series as paired units despite within-subject dependence; the subject-block interval better reflects fold spread, but remains exploratory after selection. No gain is established beyond fold noise when its interval includes zero.", "",
              "Deployment gate: positive lower subject-bootstrap bound, no losing subject, and no exercise-accuracy regression; causal candidates only. Offline models are segmentation controls. A failed gate retains affine deployment and produces no `model/paired-scaled/{L,R}` artifact. Full numeric candidate states remain in ignored `output/scale/models/`; load with `load_numeric(path)` and `predict_numpy(state, 'quality' or 'exercise', X)` from `scripts/scale_paired_models.py`. Exports were checked against scikit-learn on every rebuilt cycle, including pooled decisions; no pickle or C header is needed. The deployment gate is conservative; failure is not proof that all larger models are inferior.", "",
              "Reproduce: `.venv/bin/python scripts/scale_paired_model.py --rebuild --jobs 4`. Checkpoints resume completed variants; delete only `docs/runs/scale/{causal,offline}-{L,R}/` and ignored `output/scale/` to force a fresh sweep. Feature audits include input and matrix hashes. `commands.log` records the executed commands.", "",
              "Not tested: no board, no live sampling, no patient data, no anatomical repetition labels, no new features/detectors, no remount robustness, no named error mechanisms, no nested selection or independent confirmatory cohort, no AR9331 Python/package/RAM/latency integration. Volunteer series labels do not validate per-repetition correctness or patient safety."]
    (RUN / "REPORT.md").write_text("\n".join(lines) + "\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--jobs", type=int, default=1, choices=(1, 2, 4))
    parser.add_argument("--mode", choices=("causal", "offline"))
    parser.add_argument("--side", choices=("L", "R"))
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args=parser.parse_args()
    RUN.mkdir(parents=True,exist_ok=True)
    with (RUN/"commands.log").open("a") as f: f.write(json.dumps([sys.executable,*sys.argv])+"\n")
    if args.self_check:
        toy = dict(y=np.array([0,1,0,1,0,1]), subjects=np.array(["a","a","b","b","c","c"]),
                   sources=list("123456"), baseline_predictions={k:{"quality_prediction":v}
                   for k,v in zip("123456",[1,1,0,1,0,1])})
        stats = comparison(toy, {"quality_prediction":[0,1,0,0,0,1]})
        assert [stats[k] for k in ("gained_series","lost_series","subjects_won","subjects_lost","subjects_tied")] == [1,1,1,1,1]
        assert stats["mcnemar_exact_two_sided_p"] == 1
        for mode in ("causal","offline"):
            for side in "LR": load_cohort(mode,side)
        milestone("paired statistics, cohort counts, cache hashes, baseline accuracies self-check passed")
        return
    if args.rebuild:
        subprocess.run([sys.executable,str(ROOT/"scripts/scale_paired_features.py")],check=True)
        milestone("rebuilt all matrices and reproduced baseline predictions")
    if args.finalize: finalize(); return
    if args.side or args.mode:
        if not (args.side and args.mode): parser.error("--side and --mode must be supplied together")
        run_cohort(args.mode,args.side); return
    from concurrent.futures import ThreadPoolExecutor
    def worker(pair):
        mode,side=pair
        env=dict(os.environ,OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1")
        log=RUN/f"{mode}-{side}.log"
        with log.open("a") as f:
            subprocess.run([sys.executable,__file__,"--mode",mode,"--side",side],stdout=f,stderr=subprocess.STDOUT,env=env,check=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(worker,[(mode,side) for mode in ("causal","offline") for side in "LR"]))
    finalize()


if __name__ == "__main__": main()
