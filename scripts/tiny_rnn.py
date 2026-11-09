"""Fixed tiny GRU versus accepted paired classifier, on matched real LOSO recordings."""
import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence

from modelling_environment import check_environment
from rnn_data import load_side

CLASSES=np.array(['EAH','EFE','SQZ'])
DATA=None
CFG=None
OUT=None


def check_runtime():
    pins=check_environment()
    if torch.__version__!='2.9.1+cpu':raise RuntimeError('isolated torch==2.9.1+cpu environment required')
    torch.set_num_threads(1)
    return dict(python=os.sys.version.split()[0],numerical_pins=pins,torch=torch.__version__)


class TinyGRU(nn.Module):
    def __init__(self,hidden=8):
        super().__init__()
        self.gru=nn.GRU(6,hidden,batch_first=True)
        self.head=nn.Linear(hidden+1,4)

    def forward(self,x,lengths,duration):
        packed=pack_padded_sequence(x,lengths.cpu(),batch_first=True,enforce_sorted=False)
        _,h=self.gru(packed)
        return self.head(torch.cat([h[0],duration[:,None]],dim=1))


def normalize_train(data,train):
    selected=np.flatnonzero(train)
    if len(selected)==0:raise ValueError('no training sources')
    # Equal source weight, irrespective of recording length/cycle count.
    moments=[]
    for i in selected:
        x=np.concatenate(data['sequences'][i]).astype(np.float64)
        moments.append((x.mean(axis=0),(x*x).mean(axis=0)))
    mean=np.mean([m[0] for m in moments],axis=0)
    var=np.maximum(np.mean([m[1] for m in moments],axis=0)-mean*mean,0.)
    scale=np.sqrt(var);scale[scale<1e-6]=1.
    counts=np.array([len(b) for b in data['sequences']]);offsets=np.r_[0,np.cumsum(counts)]
    durations=[data['durations'][offsets[i]:offsets[i+1]].astype(float) for i in selected]
    dm=float(np.mean([d.mean() for d in durations]))
    ds=float(np.sqrt(max(np.mean([np.mean(d*d) for d in durations])-dm*dm,0.)))
    return dict(input_mean=mean.astype(np.float32),input_scale=scale.astype(np.float32),
                duration_mean=np.float32(dm),duration_scale=np.float32(ds if ds>=1e-6 else 1.))


def prepare(data,norm):
    seq=[s for b in data['sequences'] for s in b]
    counts=np.array([len(b) for b in data['sequences']]);owners=np.repeat(np.arange(len(counts)),counts)
    lengths=np.array([len(s) for s in seq])
    if np.any(lengths<1) or np.any(lengths>150):raise ValueError('sequence outside fixed 600-source-sample cap')
    x=np.zeros((len(seq),150,6),np.float32)
    for i,s in enumerate(seq):x[i,:len(s)]=(s-norm['input_mean'])/norm['input_scale']
    dur=(data['durations']-norm['duration_mean'])/norm['duration_scale']
    ex=np.array([int(np.flatnonzero(CLASSES==e)[0]) for e in data['exs']])
    return dict(x=torch.from_numpy(x),lengths=torch.from_numpy(lengths),duration=torch.from_numpy(dur.astype(np.float32)),
                quality=torch.from_numpy(data['y'][owners].astype(np.float32)),
                exercise=torch.from_numpy(ex[owners].astype(np.int64)),owners=owners,counts=counts)


def fit_fold(data,heldout,cfg):
    train=data['subs']!=heldout
    if len(set(data['subs'][train]))!=29 or heldout in set(data['subs'][train]):raise ValueError('LOSO train split must exclude one of 30 people')
    norm=normalize_train(data,train);tensors=prepare(data,norm)
    indices=np.flatnonzero(train[tensors['owners']])
    weights=np.zeros(len(tensors['owners']),np.float32)
    weights[indices]=len(indices)/(train.sum()*tensors['counts'][tensors['owners'][indices]])
    assert np.isclose(weights[indices].mean(),1.)
    seed=cfg['seed']+int(data['side']=='R')*1000+sorted(set(data['subs'])).index(heldout)
    torch.manual_seed(seed);torch.use_deterministic_algorithms(True)
    rng=np.random.default_rng(seed)
    model=TinyGRU(cfg['hidden_size'])
    optimizer=torch.optim.Adam(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
    trace=[];start=time.monotonic()
    for epoch in range(cfg['epochs']):
        model.train();sums=np.zeros(3);denom=0
        order=rng.permutation(indices)
        for first in range(0,len(order),cfg['batch_cycles']):
            ix=order[first:first+cfg['batch_cycles']]
            optimizer.zero_grad(set_to_none=True)
            logits=model(tensors['x'][ix],tensors['lengths'][ix],tensors['duration'][ix])
            q=nn.functional.binary_cross_entropy_with_logits(logits[:,0],tensors['quality'][ix],reduction='none')
            e=nn.functional.cross_entropy(logits[:,1:],tensors['exercise'][ix],reduction='none')
            w=torch.from_numpy(weights[ix]);loss=(w*(q*cfg['quality_loss_weight']+e*cfg['exercise_loss_weight'])).mean()
            if not torch.isfinite(loss):raise FloatingPointError('nonfinite training loss')
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),cfg['gradient_norm_clip']);optimizer.step()
            sums+=np.array([float((w*q).sum().detach()),float((w*e).sum().detach()),float(loss.detach())*len(ix)])
            denom+=len(ix)
        trace.append(dict(epoch=epoch+1,quality_loss=float(sums[0]/denom),exercise_loss=float(sums[1]/denom),total_loss=float(sums[2]/denom)))
    model.eval();test=np.flatnonzero(~train[tensors['owners']]);probs=[]
    with torch.no_grad():
        for first in range(0,len(test),cfg['batch_cycles']):
            ix=test[first:first+cfg['batch_cycles']]
            logits=model(tensors['x'][ix],tensors['lengths'][ix],tensors['duration'][ix])
            probs.append(torch.cat([logits[:,:1].sigmoid(),logits[:,1:].softmax(dim=1)],dim=1).numpy())
    probs=np.concatenate(probs)
    rows=[]
    for i in np.flatnonzero(~train):
        p=probs[tensors['owners'][test]==i].mean(axis=0)
        rows.append(dict(source=data['names'][i],subject=str(heldout),exercise=str(data['exs'][i]),quality=int(data['y'][i]),
            quality_prediction=int(p[0]>=.5),exercise_prediction=str(CLASSES[int(np.argmax(p[1:]))]),
            quality_wrong_probability=float(p[0]),exercise_probabilities=p[1:].tolist(),cycles=int(tensors['counts'][i])))
    summary=dict(heldout_person=str(heldout),train_people=sorted(set(data['subs'][train].tolist())),
        train_source_ids=[data['names'][i] for i in np.flatnonzero(train)],test_source_ids=[r['source'] for r in rows],
        seed=seed,train_cycles=len(indices),test_cycles=len(test),training_seconds=time.monotonic()-start,loss_trace=trace,
        normalization={k:np.asarray(v).tolist() for k,v in norm.items()},rows=rows)
    weights={k:v.detach().numpy() for k,v in model.gru.state_dict().items()}
    weights.update(head_weight=model.head.weight.detach().numpy(),head_bias=model.head.bias.detach().numpy(),**norm)
    return summary,weights


def worker(heldout):
    summary,weights=fit_fold(DATA,heldout,CFG)
    target=OUT/f'fold-{DATA["side"]}-{heldout}.json';target.write_text(json.dumps(summary,indent=2)+'\n')
    if heldout==sorted(set(DATA['subs']))[0]:np.savez(OUT/f'example-fold-{DATA["side"]}-{heldout}.npz',**weights)
    return dict(person=str(heldout),seconds=summary['training_seconds'])


def paired_ci(rows,baseline,key,draws,seed):
    people=sorted({r['subject'] for r in rows})
    stats=[]
    truth='quality' if key=='quality_prediction' else 'exercise'
    for person in people:
        subset=[r for r in rows if r['subject']==person]
        difference=sum(int(r[key]==r[truth])-int(baseline[r['source']][key]==r[truth]) for r in subset)
        stats.append([difference,len(subset)])
    stats=np.array(stats);rng=np.random.default_rng(seed)
    chosen=rng.integers(0,len(stats),(draws,len(stats)))
    totals=stats[chosen].sum(axis=1);values=100*totals[:,0]/totals[:,1]
    return np.percentile(values,[2.5,97.5]).tolist()


def summarize(data,folds,cfg):
    rows=[r for f in folds for r in f['rows']]
    raw=list(csv.DictReader((Path('model/paired-synchronized-causal')/data['side']/'predictions.csv').open()))
    baseline={r['source']:{**r,'quality':int(r['quality']),'quality_prediction':int(r['quality_prediction'])} for r in raw}
    assert {r['source'] for r in rows}==set(baseline)==set(data['names'])
    assert len(rows)==len(baseline)
    for row in rows:
        other=baseline[row['source']]
        assert (row['subject'],row['quality'],row['exercise'])==(other['subject'],other['quality'],other['exercise'])
    metrics={}
    for label,key,truth in [('quality','quality_prediction','quality'),('exercise','exercise_prediction','exercise')]:
        current=np.mean([r[key]==r[truth] for r in rows]);old=np.mean([baseline[r['source']][key]==r[truth] for r in rows])
        vals=[r[truth] for r in rows];_,counts=np.unique(vals,return_counts=True)
        metrics[label]=dict(rnn_agreement=float(current),accepted_baseline_agreement=float(old),
            difference_percentage_points=float(100*(current-old)),paired_subject_bootstrap_95_percent_pp=paired_ci(rows,baseline,key,cfg['bootstrap_draws'],cfg['seed']),
            majority_floor=float(counts.max()/len(vals)))
    by_exercise={}
    for ex in CLASSES:
        subset=[r for r in rows if r['exercise']==ex]
        by_exercise[str(ex)]=dict(series=len(subset),quality_agreement=float(np.mean([r['quality']==r['quality_prediction'] for r in subset])),
                                 exercise_agreement=float(np.mean([r['exercise']==r['exercise_prediction'] for r in subset])))
    return dict(side=data['side'],people=30,retained_series=len(rows),available_series=len(rows)+len(data['rejected']),
        cycles=sum(r['cycles'] for r in rows),metrics=metrics,by_exercise=by_exercise,rejected=data['rejected'],
        folds=folds,raw_hashes=data['raw_hashes'],config=cfg,
        parameter_count=424,parameter_bytes_float32=1696,normalization_bytes_float32=56,
        interpretation='One fixed single-seed GRU baseline on matched real recordings. Whole-series labels only; per-cycle probabilities are weakly supervised. No error categories, per-repetition accuracy, patient benefit or hardware timing established.')


def main():
    global DATA,CFG,OUT
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path('data/phytmo/inertial/upper'))
    ap.add_argument('--config',type=Path,default=Path('configs/tiny-rnn.json'))
    ap.add_argument('--out',type=Path,default=Path('docs/runs/phase6-rnn'))
    args=ap.parse_args();runtime=check_runtime();CFG=json.loads(args.config.read_text());OUT=args.out;OUT.mkdir(parents=True,exist_ok=True)
    if CFG['version']!=1 or CFG['hidden_size']!=8 or CFG['epochs']<1 or CFG['workers']<1:raise ValueError('invalid fixed experiment config')
    for side in 'LR':
        DATA=load_side(args.root,side)
        people=sorted(set(DATA['subs']));assert len(people)==30
        print(f'{side}: {len(DATA["names"])} sources, {sum(map(len,DATA["sequences"]))} cycles; starting 30 folds',flush=True)
        with ProcessPoolExecutor(max_workers=CFG['workers'],mp_context=mp.get_context('fork')) as pool:
            futures=[pool.submit(worker,p) for p in people]
            for done in as_completed(futures):print(side,json.dumps(done.result()),flush=True)
        folds=[json.loads((OUT/f'fold-{side}-{p}.json').read_text()) for p in people]
        result=summarize(DATA,folds,CFG);result['runtime']=runtime
        result['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        result['config_sha256']=hashlib.sha256(args.config.read_bytes()).hexdigest()
        (OUT/f'results-{side}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(side,json.dumps(result['metrics']),flush=True)


if __name__=='__main__':main()
