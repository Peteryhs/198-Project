"""Descriptive train-only reference deviations; refuses mechanism identification."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from paired_pipeline import records
from streaming_pipeline import StreamExtractor

FEATURES=['cycle_duration_s','upper_envelope_g','forearm_envelope_g','magnitude_correlation']

def reference(training):
    med=np.median(training,axis=0);scale=np.maximum(1.4826*np.median(abs(training-med),axis=0),[.05,.01,.01,.05])
    return med,scale


def evidence(values,training):
    med,scale=reference(training);z=(values-med)/scale
    return dict(error_category='not enough evidence to say',measurements=dict(zip(FEATURES,map(float,values))),
                training_reference_median=dict(zip(FEATURES,map(float,med))),training_reference_scale=dict(zip(FEATURES,map(float,scale))),
                robust_z=dict(zip(FEATURES,map(float,z))),deviation_flags=dict(zip(FEATURES,map(bool,abs(z)>3))),
                interpretation='exploratory physical-quantity deviations; not prescribed targets, range of motion, muscle effort or named errors')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();raw=[];out=[];summary=[]
    with StreamExtractor() as extractor:
        for side in 'LR':
            for p,meta,x,error in records(args.root,side):
                if error:continue
                x=np.clip(x,-3,3);f=extractor(x)
                if len(f)<3:continue
                mag=np.linalg.norm(x.reshape(-1,2,3),axis=2)
                env=np.percentile(mag,95,axis=0)-np.percentile(mag,5,axis=0)
                corr=np.corrcoef(mag.T)[0,1] if np.all(mag.std(axis=0)>0) else 0.
                raw.append(dict(source=p.relative_to(args.root).as_posix(),subject=meta[0],exercise=meta[1],label=meta[3],side=side,values=[float(np.median(f[:,0])),*map(float,env),float(corr)]))
    for row in raw:
        training=np.array([r['values'] for r in raw if r['side']==row['side'] and r['exercise']==row['exercise'] and r['subject']!=row['subject'] and r['label']==0])
        out.append({**row,**evidence(np.array(row['values']),training)})
    for label in [0,1]:
        rows=[r for r in out if r['label']==label]
        flags=np.array([list(r['deviation_flags'].values()) for r in rows])
        summary.append(dict(source='real recordings; descriptive deviations, not mechanism accuracy',series_label=label,series=len(rows),feature_flag_fraction=dict(zip(FEATURES,flags.mean(axis=0).tolist())),any_flag_fraction=float(flags.any(axis=1).mean()),multiple_flags_fraction=float((flags.sum(axis=1)>1).mean())))
    result=dict(protocol='other-subject same-exercise correct references; robust-z >3 fixed before analysis; all 30 volunteers; no error labels invented',summary=summary,evidence=out,
                planning_estimates=dict(people=12,exercises=3,conditions=5,repetitions=8,total_repetitions=12*3*5*8,collection_hours=12*45/60,rater_hours=2*12*3*5*8*10/3600))
    Path('docs/runs/round2/error-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,planning_estimates=result['planning_estimates']),indent=2))
    print('Example evidence (not a diagnosis):',json.dumps(out[0],indent=2))
    print('Mechanism accuracy: unavailable; zero mechanism ground-truth labels; no mechanism classifier exported.')
if __name__=='__main__':main()
