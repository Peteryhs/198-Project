"""Bounded, reproducible repetition-feature baseline and tiny linear export.

Example: python scripts/realtime_pipeline.py training-data --features-root
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from modelling_environment import check_environment
check_environment()

import numpy as np

SEED = 0
FILE_RE = re.compile(r"^([A-E]\d{2})([A-Z]{3})([LR]?)([01])_([12])\.csv$")


def extract_raw(root: Path, clip_g: float | None, sensor: str = "all") -> tuple[list[np.ndarray], np.ndarray, np.ndarray, np.ndarray, list[str]]:
    from harness import parse_name, read_inertial
    from mil import rep_features
    bags, labels, subjects, exercises, names = [], [], [], [], []
    duplicate_times, max_gap = 0, 0.0
    for path in sorted(root.rglob("*.csv")):
        if sensor != "all" and path.parent.name != sensor:
            continue
        meta = parse_name(str(path))
        if meta is None:
            continue
        subject, ex, _side, label, _series = meta
        if ex not in {"EAH", "EFE", "SQZ"}:
            continue
        sig = read_inertial(str(path))
        if sig.ndim != 2 or sig.shape[1] != 10 or len(sig) < 2 or not np.isfinite(sig).all():
            raise ValueError(f"invalid PHYTMO sensor matrix: {path}")
        dt = np.diff(sig[:, 0])
        if np.any(dt < 0) or np.mean(dt == 0) > .01 or not .008 <= np.median(dt) <= .012:
            raise ValueError(f"expected near-100 Hz nondecreasing timestamps: {path}")
        duplicate_times += int(np.sum(dt == 0))
        max_gap = max(max_gap, float(dt.max()))
        if clip_g is not None:
            sig[:, 4:7] = np.clip(sig[:, 4:7], -clip_g, clip_g)
        rows = rep_features(sig)
        if len(rows) < 3:
            continue
        bags.append(rows.astype(np.float32)); labels.append(label); subjects.append(subject)
        exercises.append(ex); names.append(path.relative_to(root).as_posix())
    if not bags:
        raise ValueError(f"no usable series under {root}")
    print(f"raw timestamps: duplicates={duplicate_times}, maximum gap={max_gap:.9g} s; nominal 100 Hz, no resampling")
    return bags, np.asarray(labels), np.asarray(subjects), np.asarray(exercises), names


def load_cache(root: Path, sensor="all"):
    z = np.load(root / "reps_features_acc.npz", allow_pickle=True)
    bags = [np.asarray(b, dtype=np.float32) for b in z["bags"]]
    y, subs, exs = z["y"], z["subject"].astype(str), z["exercise"].astype(str)
    rows = []
    with (root / "manifest.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    if len(bags) != len(y) or len(y) != len(subs) or len(y) != len(exs):
        raise ValueError("cache arrays have inconsistent lengths")
    if any(b.ndim != 2 or b.shape[1] != 31 or not len(b) or not np.isfinite(b).all() for b in bags):
        raise ValueError("cache bags must be nonempty finite (n_reps, 31) matrices")
    if len(rows) != len(bags):
        raise ValueError(f"manifest/cache length mismatch: {len(rows)} vs {len(bags)}")
    keep = []
    for i, row in enumerate(rows):
        if not FILE_RE.match(Path(row["file"]).name) or (row["subject"], row["exercise"], int(row["label"])) != (subs[i], exs[i], int(y[i])):
            raise ValueError(f"cache/manifest row association mismatch at row {i}: {row['file']}")
        if len(bags[i]) != int(row["reps_detected"]):
            raise ValueError(f"cache/manifest repetition count mismatch: {row['file']}")
        if sensor == "all" or Path(row["file"]).parts[-2] == sensor:
            keep.append(i)
    if not keep:
        raise ValueError(f"no cache rows for sensor {sensor}")
    return [bags[i] for i in keep], y[keep].astype(int), subs[keep], exs[keep], [rows[i]["file"] for i in keep]


def flattened(bags, y, exs, train_mask, duration_only=False):
    indices = np.flatnonzero(train_mask)
    X = np.vstack([bags[i] for i in indices])
    if duration_only:
        X = X[:, :1]
    yr = np.concatenate([np.full(len(bags[i]), y[i]) for i in indices])
    ye = np.concatenate([np.full(len(bags[i]), exs[i]) for i in indices])
    weights = np.concatenate([np.full(len(bags[i]), 1.0 / len(bags[i])) for i in indices])
    return X, yr, ye, weights


def fit_model(X, y, weights):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    weights = np.asarray(weights, dtype=np.float64) * (len(weights) / weights.sum())
    scaler.fit(X, sample_weight=weights)
    clf = LogisticRegression(C=1.0, max_iter=3000, random_state=SEED).fit(scaler.transform(X), y, sample_weight=weights)
    return Pipeline([("standardscaler", scaler), ("logisticregression", clf)])


def series_probs(model, bag):
    return model.predict_proba(bag).mean(axis=0)


def fold_predictions(bags, y, subjects, exercises, duration_only=False, weighted=True, folds=None):
    preds = np.zeros(len(y), dtype=int)
    ex_preds = np.empty(len(y), dtype=object)
    groups = sorted(set(subjects)) if folds is None else list(folds)
    for subject in groups:
        te = subjects == subject; tr = ~te
        X, yr, ye, weights = flattened(bags, y, exercises, tr, duration_only)
        if not weighted:
            weights = np.ones(len(weights))
        qmodel, emodel = fit_model(X, yr, weights), fit_model(X, ye, weights)
        for i in np.flatnonzero(te):
            xi = bags[i][:, :1] if duration_only else bags[i]
            preds[i] = int(series_probs(qmodel, xi)[1] >= .5)
            if not duration_only:
                probs = series_probs(emodel, bags[i]); ex_preds[i] = emodel.classes_[np.argmax(probs)]
    return preds, ex_preds


def fit_export(bags, y, subjects, exercises, outdir: Path, feature_metadata=None):
    X, yr, ye, weights = flattened(bags, y, exercises, np.ones(len(y), dtype=bool))
    qm, em = fit_model(X, yr, weights), fit_model(X, ye, weights)
    scaler = qm.named_steps["standardscaler"]
    logreg = qm.named_steps["logisticregression"]
    means = scaler.mean_; scales = scaler.scale_
    # Separate exercise scaler is expected to match quality scaler (same weighted examples).
    ecoef = em.named_steps["logisticregression"].coef_ / scales
    np.savez_compressed(outdir / "realtime_model.npz",
                        exercise_coef=ecoef.astype(np.float32),
                        exercise_intercept=(em.named_steps["logisticregression"].intercept_ - ecoef @ means).astype(np.float32),
                        quality_coef=(logreg.coef_[0] / scales).astype(np.float32),
                        quality_intercept=np.float32(logreg.intercept_[0] - (logreg.coef_[0] / scales) @ means),
                        exercise_classes=em.named_steps["logisticregression"].classes_)
    meta = {"format":"affine_linear_float32_raw_features", "seed":SEED, "feature_count":31,
            "feature_order":"duration_s, then statistic-major mean/std/min/max/range/rms/skew/kurtosis/energy/zcr, each x/y/z",
            "exercise_classes":em.named_steps["logisticregression"].classes_.tolist(), "quality_classes":[0,1],
            "training":"repetition-label propagation: each repetition inherits its source series label; sample weights make each series contribute equal total weight",
            "pooling":"mean repetition probabilities; series threshold 0.5", "repetition_labels":"inherited pseudo-label; not per-rep ground truth",
            "runtime_status":"offline noncausal segmentation; no runtime or hardware validation",
            "sampling_hz":100, "sensor_channels":["accel_x", "accel_y", "accel_z"], "units":"g",
            "memory_budget":{"coefficient_bytes":512,"coefficient_float_count":128,"scratch_bytes_target":256,"tflm":False},
            "model_files":["realtime_model.npz","realtime_model.h"]}
    meta["feature_preprocessing"] = feature_metadata or {"status":"unspecified"}
    (outdir / "realtime_metadata.json").write_text(json.dumps(meta, indent=2)+"\n")
    # Fold scaling into coefficients so C consumes the raw feature vector.
    export_c_header(outdir / "realtime_model.h", means, scales, em, qm)
    return qm, em


def export_c_header(path, means, scales, em, qm):
    e = em.named_steps["logisticregression"]; q = qm.named_steps["logisticregression"]
    ecoef = e.coef_ / scales
    eint = e.intercept_ - ecoef @ means
    qcoef = q.coef_[0] / scales
    qint = q.intercept_[0] - qcoef @ means
    def lit(x):
        s = f"{float(x):.9g}"
        if "." not in s and "e" not in s: s += ".0"
        return s + "f"
    def arr(v): return ", ".join(lit(x) for x in np.asarray(v).ravel())
    nf = len(means)
    content = (f"/* Generated float32 affine coefficients; inputs are {nf} repetition features. */\n#ifndef REALTIME_MODEL_H\n#define REALTIME_MODEL_H\n#include <math.h>\n"
        f"static const int RT_N_FEATURES={nf}, RT_N_EXERCISES={len(e.classes_)};\n"
        f"static const float rt_exercise_coef[{len(e.classes_)*nf}]={{{arr(ecoef)}}};\n"
        f"static const float rt_exercise_intercept[{len(e.classes_)}]={{{arr(eint)}}};\n"
        f"static const float rt_quality_coef[{nf}]={{{arr(qcoef)}}};\nstatic const float rt_quality_intercept={lit(qint)};\n"
        "static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}\n"
        "static inline const char *rt_error_category(void){return \"not enough evidence to say\";}\n"
        f"static inline int rt_predict_rep(const float x[{nf}], float ex[RT_N_EXERCISES], float *quality){{\n"
        " for(int k=0;k<RT_N_FEATURES;k++)if(!isfinite(x[k]))return 0;\n"
        " float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;\n"
        " for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<RT_N_FEATURES;k++)z[j]+=rt_exercise_coef[j*RT_N_FEATURES+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}\n"
        " for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;\n"
        " float q=rt_quality_intercept; for(int k=0;k<RT_N_FEATURES;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}\n#endif\n")
    path.write_text(content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset_root", type=Path, help="raw PHYTMO root, or training-data when --features-root")
    ap.add_argument("--features-root", action="store_true", help="load training-data feature cache; clipping unavailable")
    ap.add_argument("--sensor", default="all", help="sensor folder to use (default all; e.g. Larm)")
    ap.add_argument("--smoke-test", action="store_true", help="mark sample-sized data as smoke-test only")
    ap.add_argument("--clip-g", type=float, default=None)
    ap.add_argument("--unclipped", action="store_true", help="raw-data control arm; otherwise raw input defaults to clipping at 3 g")
    ap.add_argument("--out", type=Path, default=Path("realtime-results"))
    args = ap.parse_args()
    if args.clip_g is not None and (not np.isfinite(args.clip_g) or args.clip_g <= 0): ap.error("--clip-g must be finite and positive")
    if args.clip_g is not None and args.unclipped: ap.error("choose --clip-g or --unclipped")
    if args.features_root:
        if args.clip_g is not None or args.unclipped: ap.error("raw range options cannot be applied to cached features; clipping must happen before segmentation")
        bags,y,subs,exs,names=load_cache(args.dataset_root,args.sensor)
        source="cached features (clipping cannot be reconstructed)"
        metadata_path = args.dataset_root/"feature_metadata.json"
        feature_metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {"clip_g":"not declared by input cache"}
    else:
        clip_g = None if args.unclipped else 3.0 if args.clip_g is None else args.clip_g
        bags,y,subs,exs,names=extract_raw(args.dataset_root,clip_g,args.sensor)
        source="raw CSV without clipping" if clip_g is None else f"raw CSV clipped at ±{clip_g:g} g before offline segmentation"
        feature_metadata = {"clip_g":clip_g, "range_operation":"per-axis hard clipping before segmentation", "source_root":str(args.dataset_root.resolve())}
    feature_metadata = {**feature_metadata, "selected_sensor":args.sensor, "sensor_fusion":False,
                        "segmentation":"offline centered detrending, whole-series prominence and future peaks",
                        "sampling_hz_nominal":100, "channels":["accel_x","accel_y","accel_z"], "units":"g"}
    args.out.mkdir(parents=True,exist_ok=True)
    if args.smoke_test and len(set(subs)) < 2:
        ap.error("smoke test requires at least 2 volunteers")
    if not args.smoke_test and len(set(subs)) != 30:
        ap.error(f"benchmark mode requires all 30 volunteers; found {len(set(subs))}. Pass --smoke-test for a non-benchmark run")
    if set(y) != {0,1} or set(exs) != {"EAH","EFE","SQZ"}:
        ap.error("expected both quality labels and exactly EAH/EFE/SQZ")
    pred, epred=fold_predictions(bags,y,subs,exs)
    duration,_=fold_predictions(bags,y,subs,exs,duration_only=True)
    unweighted,_=fold_predictions(bags,y,subs,exs,weighted=False)
    folds=[]
    for s in sorted(set(subs)):
        ix=np.flatnonzero(subs==s)
        tr=subs!=s
        qfloor=float(np.mean(y[ix] == (np.mean(y[tr]) >= .5)))
        eclasses,e_counts=np.unique(exs[tr],return_counts=True)
        efloor=float(np.mean(exs[ix] == eclasses[np.argmax(e_counts)]))
        folds.append({"subject":str(s),"n_series":len(ix),
                      "quality_accuracy":float(np.mean(pred[ix]==y[ix])),"duration_only_accuracy":float(np.mean(duration[ix]==y[ix])),
                      "unweighted_quality_accuracy":float(np.mean(unweighted[ix]==y[ix])),
                      "quality_train_majority_floor":qfloor,"exercise_accuracy":float(np.mean(epred[ix]==exs[ix])),
                      "exercise_train_majority_floor":efloor})
    learning=[]
    for s in sorted(set(subs)):
        others=np.array([x for x in sorted(set(subs)) if x != s]); np.random.default_rng(SEED).shuffle(others)
        for ntrain in sorted({min(n,len(others)) for n in (10,20,29)}):
            chosen=set(others[:ntrain]); tr=np.isin(subs,list(chosen)); te=subs==s
            X,yr,_,w=flattened(bags,y,exs,tr); qm=fit_model(X,yr,w)
            vals=[int(series_probs(qm,bags[i])[1]>=.5)==int(y[i]) for i in np.flatnonzero(te)]
            floor=float(np.mean(y[te] == (np.mean(y[tr]) >= .5)))
            learning.append({"test_subject":str(s),"train_subjects":ntrain,"n_series":int(np.sum(te)),"accuracy":float(np.mean(vals)),"quality_train_majority_floor":floor})
    fit_export(bags,y,subs,exs,args.out,feature_metadata)
    (args.out/"feature_metadata.json").write_text(json.dumps(feature_metadata,indent=2)+"\n")
    if not args.features_root:
        np.savez_compressed(args.out / "reps_features_acc.npz", bags=np.array(bags,dtype=object), y=y,
                            subject=subs, exercise=exs, source=np.asarray(names))
        with (args.out/"manifest.csv").open("w",newline="") as f:
            w = csv.writer(f)
            w.writerow(["file","subject","exercise","label","reps_detected"])
            w.writerows((name,str(s),str(ex),int(label),len(bag)) for name,s,ex,label,bag in zip(names,subs,exs,y,bags))
    with (args.out/"loso_folds.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=folds[0].keys()); w.writeheader(); w.writerows(folds)
    with (args.out/"loso_predictions.csv").open("w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["source","subject","exercise","quality_label","quality_prediction","unweighted_quality_prediction","duration_quality_prediction","exercise_prediction"])
        w.writerows(zip(names,subs,exs,y,pred,unweighted,duration,epred))
    results={"source":source,"n_series":len(y),"n_repetitions":int(sum(map(len,bags))),"subjects":len(set(subs)),
             "quality_loso_accuracy":float(np.mean(pred==y)),"quality_test_fold_majority_floor":float(np.average([x["quality_train_majority_floor"] for x in folds],weights=[x["n_series"] for x in folds])),
             "exercise_loso_accuracy":float(np.mean(epred==exs)),"exercise_train_majority_floor":float(np.average([x["exercise_train_majority_floor"] for x in folds],weights=[x["n_series"] for x in folds])),
             "duration_only_accuracy":float(np.mean(duration==y)),"unweighted_quality_accuracy":float(np.mean(unweighted==y)),
             "exercise_filename_accuracy":float(np.mean(epred==exs)),"folds":folds,"learning_curve":learning,
             "training_method":"repetition-label propagation with equal total series weights; labels are inherited pseudo-labels, not per-rep ground truth",
             "rep_errors":"not evaluated: no repetition-level ground truth; always report not enough evidence",
             "segmentation":"find_peaks-based offline noncausal segmentation; not an embedded runtime pipeline",
             "sampling_contract":"nominal 100 Hz features; raw CSV timestamp jitter/gaps are reported but samples are not resampled",
             "benchmark_status":"smoke-test only" if args.smoke_test else "full-dataset protocol"}
    results["quality_majority_class_floor"] = float(np.unique(y,return_counts=True)[1].max()/len(y))
    results["exercise_majority_class_floor"] = float(np.unique(exs,return_counts=True)[1].max()/len(exs))
    results["per_exercise_quality"] = [{"exercise":str(ex), "n_series":int(np.sum(exs==ex)),
                                         "accuracy":float(np.mean(pred[exs==ex]==y[exs==ex])),
                                         "majority_class_floor":float(np.unique(y[exs==ex],return_counts=True)[1].max()/np.sum(exs==ex))}
                                        for ex in sorted(set(exs))]
    import scipy, sklearn
    results["provenance"] = {"argv":sys.argv, "seed":SEED, "sensor":args.sensor,
                             "python":sys.version.split()[0], "numpy":np.__version__,
                             "scipy":scipy.__version__, "scikit-learn":sklearn.__version__}
    if args.features_root:
        results["provenance"]["input_sha256"] = {name:hashlib.sha256((args.dataset_root/name).read_bytes()).hexdigest()
                                                for name in ("reps_features_acc.npz", "manifest.csv")}
    (args.out/"results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(f"status={results['benchmark_status']}; source={source}; series={len(y)} repetitions={sum(map(len,bags))} subjects={len(set(subs))}; sensor={args.sensor}; seed={SEED}")
    qfloor = results["quality_test_fold_majority_floor"]
    print("| Task / approach (recording-level LOSO) | Accuracy | Majority-class floor | Train-majority baseline |")
    print("| --- | ---: | ---: | ---: |")
    for name, acc, floor, baseline in (("Quality / weighted linear", results["quality_loso_accuracy"], results["quality_majority_class_floor"], qfloor),
                             ("Quality / original unweighted linear", results["unweighted_quality_accuracy"], results["quality_majority_class_floor"], qfloor),
                             ("Quality / duration only", results["duration_only_accuracy"], results["quality_majority_class_floor"], qfloor),
                             ("Exercise / weighted linear", results["exercise_loso_accuracy"], results["exercise_majority_class_floor"], results["exercise_train_majority_floor"])):
        print(f"| {name} | {acc:.6f} | {floor:.6f} | {baseline:.6f} |")
    print("| Exercise / quality | Accuracy | Majority-class floor |")
    print("| --- | ---: | ---: |")
    for row in results["per_exercise_quality"]:
        print(f"| {row['exercise']} | {row['accuracy']:.6f} | {row['majority_class_floor']:.6f} |")
    print("| Held subject | Quality accuracy | Quality floor | Exercise accuracy | Exercise floor |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for row in folds:
        print(f"| {row['subject']} | {row['quality_accuracy']:.6f} | {row['quality_train_majority_floor']:.6f} | {row['exercise_accuracy']:.6f} | {row['exercise_train_majority_floor']:.6f} |")
    print("| Training subjects / quality learning curve | Accuracy | Train-majority floor |")
    print("| --- | ---: | ---: |")
    for ntrain in sorted({row["train_subjects"] for row in learning}):
        rows = [row for row in learning if row["train_subjects"] == ntrain]
        w = [row["n_series"] for row in rows]
        print(f"| {ntrain} | {np.average([row['accuracy'] for row in rows],weights=w):.6f} | {np.average([row['quality_train_majority_floor'] for row in rows],weights=w):.6f} |")
    print(f"Exported bounded linear model and fold results to {args.out}")


if __name__ == "__main__": main()
