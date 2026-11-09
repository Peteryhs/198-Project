"""Record-relative timestamp-aligned two-sensor series experiment; no per-repetition ground truth."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from harness import parse_name, read_inertial, window_features
import realtime_pipeline as rp


def aligned_pair(a, b):
    arrays = []
    for sig in (a, b):
        if sig.ndim != 2 or sig.shape[1] != 10 or not np.isfinite(sig).all():
            raise ValueError('invalid matrix')
        dt = np.diff(sig[:, 0])
        if len(dt) == 0 or np.any(dt < 0) or dt.max() > .05 or not .008 <= np.median(dt) <= .012:
            raise ValueError('timestamps not near 100 Hz, reversed or gap >50 ms')
        t, ix, counts = np.unique(sig[:, 0], return_index=True, return_counts=True)
        values = np.add.reduceat(sig[:, 4:7], ix, axis=0) / counts[:, None]
        arrays.append((t-t[0], values))
    start, stop = max(x[0][0] for x in arrays), min(x[0][-1] for x in arrays)
    if stop - start < 3.6:
        raise ValueError('shared interval <3.6 s')
    grid = start + np.arange(int(np.floor((stop-start)*100+1e-6))+1) / 100
    return np.column_stack([np.interp(grid, t, v[:, k]) for t, v in arrays for k in range(3)])


def records(root, side):
    for p in sorted(root.glob(f'*/{side}arm/*.csv')):
        meta = parse_name(str(p))
        if meta is None or meta[1] not in {'EAH','EFE','SQZ'}:
            continue
        q = p.parent.parent / f'{side}forearm' / p.name
        if not q.exists():
            yield p, meta, None, 'missing counterpart'
            continue
        try:
            x = aligned_pair(read_inertial(str(p)), read_inertial(str(q)))
            yield p, meta, x, None
        except ValueError as e:
            yield p, meta, None, str(e)


def offline_features(x):
    from reps import find_peaks
    sig = np.zeros((len(x), 10)); sig[:, 4:7] = x[:, 3:]
    peaks = find_peaks(sig)
    if len(peaks) < 2:
        return np.empty((0,61), np.float32)
    bounds = [0, *((peaks[1:]+peaks[:-1])//2), len(x)]
    rows = []
    for a,b in zip(bounds[:-1],bounds[1:]):
        if b-a >= 10:
            rows.append(np.r_[(b-a)/100, window_features(x[None,a:b,:3])[0], window_features(x[None,a:b,3:])[0]])
    return np.asarray(rows,dtype=np.float32)


def collect(root, side, extractor=offline_features, transform=None):
    bags=[]; y=[]; subs=[]; exs=[]; names=[]; rejected=[]
    for p, meta, x, error in records(root, side):
        name = p.relative_to(root).as_posix()
        if error:
            rejected.append({'source':name,'reason':error}); continue
        if transform is not None:
            x = transform(x, meta)
        rows = extractor(np.clip(x,-3,3))
        if len(rows)<3:
            rejected.append({'source':name,'reason':'fewer than 3 detected cycles'}); continue
        bags.append(rows); y.append(meta[3]); subs.append(meta[0]); exs.append(meta[1]); names.append(name)
    if len(set(subs)) != 30:
        raise ValueError(f'LOSO requires 30 subjects, got {len(set(subs))}')
    return bags,np.asarray(y),np.asarray(subs),np.asarray(exs),names,rejected


def export(bags,y,subs,exs,out):
    X,yr,ye,w=rp.flattened(bags,y,exs,np.ones(len(y),bool))
    qm,em=rp.fit_model(X,yr,w),rp.fit_model(X,ye,w)
    rp.export_c_header(out/'realtime_model.h',qm[0].mean_,qm[0].scale_,em,qm)
    data={}
    for prefix,m in [('quality',qm),('exercise',em)]:
        c=m[1].coef_/m[0].scale_
        data[prefix+'_coef']=c.astype(np.float32)
        data[prefix+'_intercept']=(m[1].intercept_-c@m[0].mean_).astype(np.float32)
    data['exercise_classes']=em.classes_
    (out/'metadata.json').write_text(json.dumps(dict(feature_count=X.shape[1],time_contract='authors synchronized recording starts; interpolate relative timestamps, not device uptime',feature_order=('duration, upper statistic-major mean/std/min/max/range/rms/skew/kurtosis/energy/zcr xyz, then forearm same' if X.shape[1]==61 else 'duration, selected sensor statistic-major mean/std/min/max/range/rms/skew/kurtosis/energy/zcr xyz'),exercise_classes=em.classes_.tolist(),input='two synchronized accelerometers, g, ±3 g, 100 Hz',labels='series-level only; per-cycle pseudo-labels',error_category='not enough evidence to say'),indent=2)+'\n')
    np.savez_compressed(out/'realtime_model.npz',**data)
    return sum(data[k].nbytes for k in data if k!='exercise_classes')


def evaluate(data,out,source):
    bags,y,subs,exs,names,rejected=data
    pred,epred=rp.fold_predictions(bags,y,subs,exs)
    folds=[]
    for s in sorted(set(subs)):
        te=subs==s;tr=~te
        ec,counts=np.unique(exs[tr],return_counts=True)
        folds.append(dict(subject=s,n=int(te.sum()),quality=float(np.mean(pred[te]==y[te])),
                          quality_train_majority=float(np.mean(y[te]==int(y[tr].mean()>=.5))),
                          exercise=float(np.mean(epred[te]==exs[te])),
                          exercise_train_majority=float(np.mean(exs[te]==ec[counts.argmax()]))))
    out.mkdir(parents=True,exist_ok=True)
    report=dict(source=source,subjects=len(set(subs)),series=len(y),cycles=sum(map(len,bags)),features=bags[0].shape[1],
                quality_accuracy=float(np.mean(pred==y)),quality_majority_floor=float(np.unique(y,return_counts=True)[1].max()/len(y)),
                exercise_accuracy=float(np.mean(epred==exs)),exercise_majority_floor=float(np.unique(exs,return_counts=True)[1].max()/len(y)),
                quality_train_majority=float(np.average([f['quality_train_majority'] for f in folds],weights=[f['n'] for f in folds])),
                exercise_train_majority=float(np.average([f['exercise_train_majority'] for f in folds],weights=[f['n'] for f in folds])),
                parameter_bytes=export(bags,y,subs,exs,out),folds=folds,rejected=rejected,
                protocol='fixed C=1; weighted per series; LOSO; series-level labels only; no held-out tuning')
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    import csv
    with (out/'predictions.csv').open('w') as f:
        wr=csv.writer(f);wr.writerow(['source','subject','exercise','quality','quality_prediction','exercise_prediction'])
        wr.writerows(zip(names,subs,exs,y,pred,epred))
    print(json.dumps({k:v for k,v in report.items() if k not in {'folds','rejected'}},indent=2))
    print('rejected:',len(rejected))
    return report


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--out',type=Path,default=Path('model/paired-synchronized-offline'))
    args=ap.parse_args()
    for side in 'LR':
        evaluate(collect(args.root,side),args.out/side,f'real recordings; {side} upper arm + forearm; ±3 g; offline common boundaries')

if __name__=='__main__':main()
