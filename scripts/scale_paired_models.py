"""Capacity sweeps and numeric-only inference export for paired-series models."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

SEED = 0


@dataclass(frozen=True)
class Config:
    name: str
    kind: str
    options: tuple


def model_configs():
    configs = [Config(f"hgb-leaves{leaf}-iter{it}", "hgb", (leaf, it, .1))
               for leaf in (15, 31, 63) for it in (50, 200)]
    configs += [Config("mlp-" + "-".join(map(str,dims)), "mlp", (dims, .0001, 300))
                for dims in ((64,), (128, 64), (256, 128))]
    configs += [Config("extratrees-32-leaves256", "extratrees", (32, 256))]
    return configs


def _flatten(bags, labels, exercises, mask):
    ix = np.flatnonzero(mask)
    X = np.vstack([bags[i] for i in ix]).astype(np.float32, copy=False)
    yq = np.concatenate([np.full(len(bags[i]), labels[i]) for i in ix])
    ye = np.concatenate([np.full(len(bags[i]), exercises[i]) for i in ix])
    w = np.concatenate([np.full(len(bags[i]), 1.0 / len(bags[i])) for i in ix])
    w = np.asarray(w, dtype=np.float64) * (len(w) / w.sum())
    return X, yq, ye, w


def _fit_one(X, y, weights, config):
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if config.kind == "hgb":
        leaves, iters, lr = config.options
        model = HistGradientBoostingClassifier(max_leaf_nodes=leaves, max_iter=iters,
                                                learning_rate=lr, early_stopping=False,
                                                random_state=SEED)
        return model.fit(X, y, sample_weight=weights)
    if config.kind == "mlp":
        hidden, alpha, iters = config.options
        model = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=hidden,
                          alpha=alpha, max_iter=iters, early_stopping=False,
                          random_state=SEED, solver="adam"))
        model.fit(X, y, standardscaler__sample_weight=weights,
                  mlpclassifier__sample_weight=weights)
        return model
    if config.kind == "extratrees":
        trees, leaves = config.options
        return ExtraTreesClassifier(n_estimators=trees, max_leaf_nodes=leaves,
                                    n_jobs=1, random_state=SEED).fit(X, y, sample_weight=weights)
    raise ValueError(f"unknown model kind: {config.kind}")


def fit_pair(X, y_quality, y_exercise, weights, config):
    """Fit the two series-label heads on the same training rows and weights."""
    return (_fit_one(X, y_quality, weights, config),
            _fit_one(X, y_exercise, weights, config))


def _prob(model, X):
    return model.predict_proba(X)


def evaluate_config(bags, y, subjects, exercises, config):
    """Run one complete leave-one-subject-out configuration."""
    from threadpoolctl import threadpool_limits
    import time, warnings
    y = np.asarray(y); subjects = np.asarray(subjects); exercises = np.asarray(exercises)
    qpred = np.zeros(len(y), dtype=int)
    epred = np.empty(len(y), dtype=exercises.dtype)
    fold_rows=[]; warning_rows=[]; train_seconds=0.; predict_seconds=0.
    with threadpool_limits(limits=1):
        for subject in sorted(set(subjects)):
            test = subjects == subject
            X, yq, ye, weights = _flatten(bags, y, exercises, ~test)
            start=time.perf_counter()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                qm, em = fit_pair(X, yq, ye, weights, config)
            train_seconds += time.perf_counter()-start
            warning_rows.extend(str(w.message) for w in caught)
            pred_start=time.perf_counter()
            for i in np.flatnonzero(test):
                qp = _prob(qm, bags[i]); ep = _prob(em, bags[i])
                qmean, emean = qp.mean(axis=0), ep.mean(axis=0)
                qpred[i] = 1 if len(qm.classes_) == 2 and qmean[1] >= .5 else qm.classes_[np.argmax(qmean)]
                epred[i] = em.classes_[np.argmax(emean)]
            predict_seconds += time.perf_counter()-pred_start
            ix=np.flatnonzero(test)
            fold_rows.append({"subject":str(subject),"n_series":len(ix),
                "quality_accuracy":float(np.mean(qpred[ix]==y[ix])),
                "exercise_accuracy":float(np.mean(epred[ix]==exercises[ix]))})
    return {"config": config.name, "config_spec":asdict(config),
            "quality_prediction": qpred, "exercise_prediction": epred,
            "quality_accuracy": float(np.mean(qpred == y)),
            "exercise_accuracy": float(np.mean(epred == exercises)),
            "folds": fold_rows, "train_seconds":train_seconds,
            "inference_seconds":predict_seconds,"warnings":sorted(set(warning_rows))}


def evaluate_variant(bags, y, subjects, exercises, config):
    """Public resumable single-variant LOSO entry point."""
    return evaluate_config(bags,y,subjects,exercises,config)


def evaluate_sweep(bags, y, subjects, exercises, configs=None, progress=print):
    results = []
    for cfg in model_configs() if configs is None else configs:
        if progress:
            progress(f"starting {cfg.name}", flush=True)
        results.append(evaluate_config(bags, y, subjects, exercises, cfg))
        if progress:
            progress(f"finished {cfg.name}: quality={results[-1]['quality_accuracy']:.4f}, exercise={results[-1]['exercise_accuracy']:.4f}", flush=True)
    return results


def _tree_arrays(trees, classes, hgb=False):
    left=[]; right=[]; feature=[]; threshold=[]; values=[]; leaves=[]; offsets=[0]
    for tree in trees:
        lo=len(left)
        if hgb:
            n=tree.nodes
            l=np.asarray(n["left"],dtype=np.int64); r=np.asarray(n["right"],dtype=np.int64)
            f=np.asarray(n["feature_idx"],dtype=np.int64); leaf=np.asarray(n["is_leaf"],dtype=bool)
            left.extend(np.where(~leaf,l+lo,l)); right.extend(np.where(~leaf,r+lo,r)); feature.extend(f); leaves.extend(leaf)
            threshold.extend(n["num_threshold"]); values.extend(n["value"])
        else:
            t=tree.tree_
            f=np.asarray(t.feature,dtype=np.int64); leaf=f<0
            left.extend(np.where(~leaf,t.children_left+lo,t.children_left));
            right.extend(np.where(~leaf,t.children_right+lo,t.children_right)); feature.extend(f); leaves.extend(leaf)
            threshold.extend(t.threshold)
            val=t.value[:,0,:]
            if val.shape[1] != len(classes):
                expanded=np.zeros((len(val),len(classes)))
                expanded[:, :val.shape[1]]=val
                val=expanded
            if not hgb:
                sums=val.sum(axis=1,keepdims=True)
                val=np.divide(val,sums,out=np.zeros_like(val),where=sums != 0)
            values.extend(val.ravel() if hgb else val)
        offsets.append(len(left))
    return {"left":np.asarray(left,dtype=np.int32), "right":np.asarray(right,dtype=np.int32),
            "feature":np.asarray(feature,dtype=np.int32), "threshold":np.asarray(threshold,dtype=np.float64),
            "value":np.asarray(values,dtype=np.float64).reshape(-1), "leaf":np.asarray(leaves,dtype=np.bool_),
            "offsets":np.asarray(offsets,dtype=np.int32)}


def _encode(model, prefix, out):
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    classes=np.asarray(model.classes_)
    out[prefix+"_feature_count"]=np.asarray([model.n_features_in_],np.int32)
    if hasattr(model, "named_steps"):
        scaler=model.named_steps["standardscaler"]; clf=model.named_steps["mlpclassifier"]
        out[prefix+"_kind"]=np.asarray([1],np.int8)
        out[prefix+"_mean"]=scaler.mean_.astype(np.float64); out[prefix+"_scale"]=scaler.scale_.astype(np.float64)
        out[prefix+"_classes"]=classes
        out[prefix+"_layers"]=np.asarray([len(clf.coefs_)],np.int32)
        for i,(w,b) in enumerate(zip(clf.coefs_,clf.intercepts_)):
            out[f"{prefix}_w{i}"]=w.astype(np.float64); out[f"{prefix}_b{i}"]=b.astype(np.float64)
        return
    out[prefix+"_classes"]=classes
    if isinstance(model, HistGradientBoostingClassifier):
        trees=[t for stage in model._predictors for t in stage]
        state=_tree_arrays(trees,classes,hgb=True)
        out[prefix+"_kind"]=np.asarray([2],np.int8)
        for k,v in state.items(): out[prefix+"_"+k]=v
        out[prefix+"_base"]=model._baseline_prediction.reshape(-1).astype(np.float64)
        out[prefix+"_iterations"]=np.asarray([len(model._predictors)],np.int32)
        out[prefix+"_learning_rate"]=np.asarray([model.learning_rate],np.float64)
        out[prefix+"_classes_per_iter"]=np.asarray([len(model._predictors[0])],np.int32)
        return
    if isinstance(model,(ExtraTreesClassifier,RandomForestClassifier)):
        state=_tree_arrays(model.estimators_,classes)
        out[prefix+"_kind"]=np.asarray([3],np.int8)
        for k,v in state.items(): out[prefix+"_"+k]=v
        return
    raise TypeError(f"unsupported export type {type(model).__name__}")


def export_pair(path, qmodel, emodel):
    """Write both heads as compressed numeric arrays; validate numpy parity."""
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    data={}; _encode(qmodel,"quality",data); _encode(emodel,"exercise",data)
    np.savez_compressed(path,**data)
    loaded=load_numeric(path)
    for prefix,model in (("quality",qmodel),("exercise",emodel)):
        probe=np.zeros((2,int(model.n_features_in_)),dtype=np.float64)
        probe[1]=np.linspace(-1,1,probe.shape[1])
        if not np.allclose(predict_numpy(loaded,prefix,probe),model.predict_proba(probe),rtol=2e-5,atol=2e-6):
            raise AssertionError(f"numeric export parity failed: {prefix}")
    return sum(v.nbytes for v in data.values())


def load_numeric(path):
    with np.load(path,allow_pickle=False) as z:
        state={k:z[k] for k in z.files}
    if any(v.dtype.hasobject for v in state.values()):
        raise ValueError("object arrays are forbidden in numeric model exports")
    if any(v.dtype.kind in "fiu" and not np.isfinite(v).all() for v in state.values()):
        raise ValueError("model export contains non-finite numeric state")
    return state


def predict_numpy(state, prefix, X):
    """Pure NumPy predict_proba for states produced by export_pair."""
    X=np.asarray(X,dtype=np.float64)
    if X.ndim != 2 or X.shape[1] != int(state[prefix+"_feature_count"][0]) or not np.isfinite(X).all():
        raise ValueError("X must be a finite matrix with the model's feature count")
    kind=int(state[prefix+"_kind"][0]); classes=state[prefix+"_classes"]
    if kind == 1:
        a=(X-state[prefix+"_mean"])/state[prefix+"_scale"]
        for i in range(int(state[prefix+"_layers"][0])):
            a=a@state[f"{prefix}_w{i}"]+state[f"{prefix}_b{i}"]
            if i+1 < int(state[prefix+"_layers"][0]): a=np.maximum(a,0)
        if len(classes)==2 and a.shape[1]==1:
            p=1/(1+np.exp(-np.clip(a[:,0],-700,700))); return np.column_stack((1-p,p))
        a=np.exp(a-a.max(axis=1,keepdims=True)); return a/a.sum(axis=1,keepdims=True)
    left=state[prefix+"_left"]; right=state[prefix+"_right"]; feature=state[prefix+"_feature"]
    threshold=state[prefix+"_threshold"]; val=state[prefix+"_value"]; leaves=state[prefix+"_leaf"]; offsets=state[prefix+"_offsets"]
    if kind==3:
        ans=np.zeros((len(X),len(classes)))
        for lo in offsets[:-1]:
            nodes=np.full(len(X),lo,dtype=np.int32)
            while True:
                active=np.flatnonzero(~leaves[nodes])
                if not len(active): break
                current=nodes[active]; split=feature[current]
                go_left=X[active,split]<=threshold[current]
                nodes[active]=np.where(go_left,left[current],right[current])
            ans+=val.reshape(-1,len(classes))[nodes]
        return ans/(len(offsets)-1)
    if kind==2:
        raw=np.tile(state[prefix+"_base"],(len(X),1)); per=int(state[prefix+"_classes_per_iter"][0])
        for ti,(lo,hi) in enumerate(zip(offsets[:-1],offsets[1:])):
            nodes=np.full(len(X),lo,dtype=np.int32)
            while True:
                active=np.flatnonzero(~leaves[nodes])
                if not len(active): break
                current=nodes[active]; split=feature[current]
                go_left=X[active,split]<=threshold[current]
                nodes[active]=np.where(go_left,left[current],right[current])
            raw[:,ti%per]+=val[nodes]
        if raw.shape[1]==1:
            p=1/(1+np.exp(-np.clip(raw[:,0],-700,700))); return np.column_stack((1-p,p))
        raw-=raw.max(axis=1,keepdims=True); p=np.exp(raw); return p/p.sum(axis=1,keepdims=True)
    raise ValueError(f"unknown serialized model kind {kind}")


def benchmark(model, X, repeats=3):
    import time
    X=np.asarray(X)
    start=time.perf_counter()
    for _ in range(repeats): model.predict_proba(X)
    return {"rows":len(X),"repeats":repeats,"seconds":(time.perf_counter()-start)/repeats}
