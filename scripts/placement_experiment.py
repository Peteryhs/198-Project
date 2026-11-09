"""Common-cohort recorded-side comparison and held-out synthetic remount stress."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import paired_pipeline as pp
import realtime_pipeline as rp
from streaming_pipeline import StreamExtractor
from limb_simulation import simulate


def rotate_mounts(x,subject,side,degrees):
    rng=np.random.default_rng(int.from_bytes(hashlib.sha256((subject+side).encode()).digest()[:4],'little'))
    out=x.copy()
    for seg in range(2):
        axis=rng.normal(size=3);axis/=np.linalg.norm(axis)
        out[:,seg*3:seg*3+3]=Rotation.from_rotvec(axis*np.deg2rad(degrees)).apply(x[:,seg*3:seg*3+3])
    return out


def common_data(left,right):
    keys=sorted(set(Path(n).name for n in left[4])&set(Path(n).name for n in right[4]))
    result={}
    for side,data in [('L',left),('R',right)]:
        lookup={Path(n).name:i for i,n in enumerate(data[4])};ix=[lookup[k] for k in keys]
        result[side]=([data[0][i] for i in ix],*[data[j][ix] for j in [1,2,3]],[data[4][i] for i in ix],[])
    assert np.array_equal(result['L'][1],result['R'][1]) and np.array_equal(result['L'][2],result['R'][2])
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();rows=[];models={};predictions={};details=[]
    with StreamExtractor() as extractor:
        data=common_data(pp.collect(args.root,'L',extractor),pp.collect(args.root,'R',extractor))
        assert len(set(data['L'][2]))==30, 'common cohort must retain 30 volunteers'
        for side in 'LR':
            for config in ['pair','upper','forearm']:
                bags,y,subs,exs,names,rejected=data[side]
                if config=='upper':bags=[b[:,:31] for b in bags]
                if config=='forearm':bags=[np.c_[b[:,0],b[:,31:]] for b in bags]
                report=pp.evaluate((bags,y,subs,exs,names,rejected),Path('model/placement-controls')/f'{side}-{config}',f'real recordings; common cohort; {side}-{config}; common C boundaries')
                rows.append({k:v for k,v in report.items() if k not in {'folds','rejected'}})
            bags,y,subs,exs,names,_=data[side]
            for s in sorted(set(subs)):
                tr=subs!=s;X,yr,ye,w=rp.flattened(bags,y,exs,tr)
                models[side,s]=(rp.fit_model(X,yr,w),rp.fit_model(X,ye,w))
            for angle in [0,15,30,60]:
                qpred=np.full(len(y),-1);epred=np.full(len(y),'abstain',dtype=object);cycles=np.zeros(len(y),int)
                lookup={Path(n).name:i for i,n in enumerate(names)}
                for p,meta,x,error in pp.records(args.root,side):
                    if error or p.name not in lookup:continue
                    i=lookup[p.name];f=extractor(np.clip(rotate_mounts(x,meta[0],side,angle),-3,3));cycles[i]=len(f)
                    if len(f)<3:continue
                    qm,em=models[side,meta[0]];qpred[i]=int(rp.series_probs(qm,f)[1]>=.5);epred[i]=em.classes_[rp.series_probs(em,f).argmax()]
                scored=qpred>=0
                qfloor=float(np.unique(y,return_counts=True)[1].max()/len(y));efloor=float(np.unique(exs,return_counts=True)[1].max()/len(y))
                rows.append(dict(source='real recordings' if angle==0 else 'simulation: mount rotation applied to held-out real recordings',side=side,degrees=angle,series=len(y),subjects=len(set(subs)),coverage=float(scored.mean()),quality_accuracy=float(np.mean(qpred==y)),quality_majority_floor=qfloor,exercise_accuracy=float(np.mean(epred==exs)),exercise_majority_floor=efloor,quality_conditional_accuracy=float(np.mean(qpred[scored]==y[scored])),exercise_conditional_accuracy=float(np.mean(epred[scored]==exs[scored])),denominator='all matched series; abstention counts as failure'))
                if angle==0:predictions[side]=(qpred==y,epred==exs)
                for i in range(len(y)):details.append(dict(source=names[i],subject=str(subs[i]),side=side,degrees=angle,cycles=int(cycles[i]),quality_label=int(y[i]),quality_prediction=int(qpred[i]),exercise=str(exs[i]),exercise_prediction=str(epred[i])))
                print('held-out remount',side,angle,'complete',flush=True)
        subs=data['L'][2];rng=np.random.default_rng(0);people=np.unique(subs);diffs={}
        for j,task in enumerate(['quality','exercise']):
            difference=predictions['L'][j].astype(float)-predictions['R'][j]
            estimates=[]
            for _ in range(2000):
                selected=rng.choice(people,len(people),replace=True);ids=np.concatenate([np.flatnonzero(subs==s) for s in selected]);estimates.append(difference[ids].mean())
            diffs[task]=dict(left_minus_right=float(difference.mean()),subject_bootstrap_95_interval=np.percentile(estimates,[2.5,97.5]).tolist(),interpretation='exploratory side comparison; no model selection or tuning')
    offsets=[]
    for ex in ['EAH','EFE','SQZ']:
        base=simulate(ex,2,n=2000)
        for shift in [-.05,.05]:
            changed=simulate(ex,2,n=2000,offset=shift)
            offsets.append(dict(source='simulation; failed-domain mechanical diagnostic',exercise=ex,offset_m=shift,rms_change_g=float(np.sqrt(np.mean((changed-base)**2))),peak_change_g=float(np.max(abs(changed-base)))))
    result=dict(rows=rows,side_difference=diffs,offset_diagnostics=offsets,predictions=details,protocol='fixed model and perturbations; training on clean other 29; shared cohort; no test-fold tuning',decision='no supported cm/tightness optimum; use indexed exterior-lateral upper+forearm placements as a proposal pending patient remount validation')
    Path('docs/runs/round2/placement.json').write_text(json.dumps(result,indent=2)+'\n')
    print('| Source / configuration | series | quality accuracy / majority floor | exercise accuracy / majority floor | coverage |')
    for r in rows:
        name=r['source']+(f" {r['side']} {r['degrees']}deg" if 'degrees' in r else '')
        print(f"| {name} | {r['series']} | {r['quality_accuracy']:.6f} / {r['quality_majority_floor']:.6f} | {r['exercise_accuracy']:.6f} / {r['exercise_majority_floor']:.6f} | {r.get('coverage',1):.6f} |")
    print('Subject-block bootstrap:',json.dumps(diffs,indent=2))
    print('SIMULATED position offsets (cannot rank patient placements):',json.dumps(offsets,indent=2))
if __name__=='__main__':main()
