"""Validate domain before diagnostic model responses; never train on simulated error labels."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from scipy.signal import welch
from scipy.stats import wasserstein_distance
import paired_pipeline as pp
import realtime_pipeline as rp
from streaming_pipeline import StreamExtractor
from limb_simulation import simulate


def statistics(x,extractor):
    f=extractor(x);ends=extractor.ends.copy()
    values=[]
    for segment in range(2):
        xyz=x[:,segment*3:segment*3+3];mag=np.linalg.norm(xyz,axis=1)
        hz,power=welch(mag,fs=100,nperseg=min(len(x),1000));band=(hz>=.15)&(hz<=3)
        _,axis_power=welch(xyz,fs=100,nperseg=min(len(x),1000),axis=0)
        axis_power=axis_power.sum(axis=1);hf=axis_power[(hz>=5)&(hz<=40)].sum()/max(axis_power[hz>0].sum(),1e-20)
        peaks=[mag[max(0,int(end-round(row[0]*100))):end].max() for row,end in zip(f,ends)]
        values.append(dict(envelope_g=float(np.percentile(mag,95)-np.percentile(mag,5)),
                           dominant_hz=float(hz[band][np.argmax(power[band])]),
                           peak_p50_g=float(np.median(peaks)) if peaks else 0.,peak_p90_g=float(np.percentile(peaks,90)) if peaks else 0.,
                           duration_p50_s=float(np.median(f[:,0])) if len(f) else 0.,duration_p90_s=float(np.percentile(f[:,0],90)) if len(f) else 0.,hf_fraction=float(hf)))
    return values,f


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--out',type=Path,default=Path('docs/runs/round2/simulation.json'));args=ap.parse_args()
    validation=[];responses=[];pending=[]
    with StreamExtractor() as extractor:
        for side in 'LR':
            data=pp.collect(args.root,side,extractor);bags,y,subs,exs,names,_=data
            real={}
            for p,meta,x,error in pp.records(args.root,side):
                if error or meta[3]!=0 or p.relative_to(args.root).as_posix() not in names:continue
                stats,_=statistics(np.clip(x,-3,3),extractor)
                real[p.relative_to(args.root).as_posix()]=stats
            for s in sorted(set(subs)):
                train=subs!=s
                X,yr,ye,w=rp.flattened(bags,y,exs,train)
                qm,em=rp.fit_model(X,yr,w),rp.fit_model(X,ye,w)
                for ex in sorted(set(exs)):
                    ids=np.flatnonzero(train&(exs==ex)&(y==0))
                    period=float(np.median([np.median(bags[i][:,0]) for i in ids]))
                    for variant in ['nominal','shallow','fast','weak','misaligned','stall']:
                        x=simulate(ex,period,variant,n=2000)
                        stats,f=statistics(x,extractor)
                        if variant=='nominal':
                            for i in np.flatnonzero((subs==s)&(exs==ex)&(y==0)):
                                if names[i] in real:
                                    for seg in range(2):
                                        validation.append(dict(subject=str(s),exercise=str(ex),side=side,segment=seg,real=real[names[i]][seg],simulation=stats[seg]))
                        response=dict(source='simulation; diagnostic only; no clinical error truth',held_out_subject_model=str(s),exercise=str(ex),side=side,scenario=variant,period_from_other_29=period,cycles=len(f))
                        responses.append(response);pending.append((response,f,qm,em))
                print('simulation held-out model',side,s,'complete',flush=True)
    gates=[]
    for side in 'LR':
        for ex in ['EAH','EFE','SQZ']:
            for seg in range(2):
                rows=[r for r in validation if r['side']==side and r['exercise']==ex and r['segment']==seg]
                for key in rows[0]['real']:
                    real=np.array([r['real'][key] for r in rows]);sim=np.array([r['simulation'][key] for r in rows])
                    ratio=float(np.median(sim)/max(np.median(real),1e-9))
                    scale=max(np.ptp(np.percentile(real,[25,75])),.05*np.median(real),1e-6)
                    distance=float(wasserstein_distance(real,sim)/scale)
                    gates.append(dict(side=side,exercise=ex,segment=seg,statistic=key,n=len(real),real_p10_p50_p90=np.percentile(real,[10,50,90]).tolist(),simulation_p10_p50_p90=np.percentile(sim,[10,50,90]).tolist(),median_ratio=ratio,normalized_wasserstein=distance,passed=bool(.75<=ratio<=1.33 and distance<=.5)))
    print('Domain gate evaluated before classifier responses:',all(r['passed'] for r in gates),flush=True)
    # Failed-gate outputs remain explicit diagnostics, never reported as accuracy.
    for response,f,qm,em in pending:
        response['wrong_probability']=float(rp.series_probs(qm,f)[1]) if len(f) else None
        response['intended_exercise_probability']=float(rp.series_probs(em,f)[list(em.classes_).index(response['exercise'])]) if len(f) else None
    out=dict(source='simulation validation against real recordings; nominal correct-series distribution only',gate='all median ratios [0.75,1.33], all normalized Wasserstein <=0.5; predeclared before code',gate_passed=all(r['passed'] for r in gates),passed_statistics=sum(r['passed'] for r in gates),total_statistics=len(gates),comparisons=gates,responses=responses,
             interpretation='failed domain gate prohibits accuracy/clinical inference; model probabilities are diagnostic sensitivities, never evidence of a real error mechanism',limits=['illustrative planar rigid links, not patients','unknown placement extrinsics','no force/effort or pain model','no soft tissue, band slip, ADC skew or real saturation recovery','wrong trajectories are constructed scenarios, not clinical labels','C cycle durations are detector proxies, not repetition truth'])
    args.out.write_text(json.dumps(out,indent=2)+'\n')
    print('Validation gate:',out['gate_passed'],'passed',out['passed_statistics'],'/',len(gates))
    print('| Side/exercise/segment/statistic | real p10/p50/p90 | simulation p10/p50/p90 | ratio | normalized distance | pass |')
    for r in gates:
        print(f"| {r['side']}/{r['exercise']}/{r['segment']}/{r['statistic']} | {np.round(r['real_p10_p50_p90'],4).tolist()} | {np.round(r['simulation_p10_p50_p90'],4).tolist()} | {r['median_ratio']:.4f} | {r['normalized_wasserstein']:.4f} | {r['passed']} |")
    print('| Simulation scenario (failed-domain diagnostic) | mean wrong probability | mean exercise probability | abstaining series |')
    for v in ['nominal','shallow','fast','weak','misaligned','stall']:
        rows=[r for r in responses if r['scenario']==v]
        print(f"| {v} | {np.mean([r['wrong_probability'] for r in rows if r['cycles']]):.6f} | {np.mean([r['intended_exercise_probability'] for r in rows if r['cycles']]):.6f} | {sum(not r['cycles'] for r in rows)} |")
if __name__=='__main__':main()
