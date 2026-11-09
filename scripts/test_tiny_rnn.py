"""Known-value checks for temporal inputs, masking, source weighting and held-out exclusion."""
import copy
import json
from pathlib import Path

import numpy as np
import torch

from tiny_rnn import TinyGRU,normalize_train,prepare,fit_fold,check_runtime,paired_ci


def fixture():
    rng=np.random.default_rng(5);sequences=[]
    for i in range(30):
        bag=[]
        for k in range(3+i%3):
            x=rng.normal(0,.1,(12+k,6)).astype(np.float32);x[:,0]+=(i%2)*.8
            bag.append(x)
        sequences.append(bag)
    return dict(sequences=sequences,durations=np.array([len(s)/25 for b in sequences for s in b],np.float32),
        y=np.arange(30)%2,subs=np.array([f'S{i:02}' for i in range(30)]),
        exs=np.array(['EAH','EFE','SQZ']*10),names=[f'S{i:02}EAH0_1.csv' for i in range(30)],side='L')


def main():
    check_runtime();torch.manual_seed(8);model=TinyGRU(8).eval()
    assert sum(p.numel() for p in model.parameters())==424
    x=torch.randn(3,15,6);lengths=torch.tensor([7,15,9]);duration=torch.tensor([1.,2.,3.])
    original=model(x,lengths,duration)
    padded=x.clone();padded[0,7:]=1000;padded[2,9:]=-1000
    assert torch.equal(original,model(padded,lengths,duration))
    a=torch.tensor([[[1.,0,0,0,0,0],[0,1,0,0,0,0],[0,0,1,0,0,0]]])
    assert not torch.allclose(model(a,torch.tensor([3]),torch.tensor([1.])),
                              model(a.flip(1),torch.tensor([3]),torch.tensor([1.])),atol=1e-5)
    data=fixture();held='S00';mask=data['subs']!=held
    norm=normalize_train(data,mask);t=prepare(data,norm)
    selected=mask[t['owners']];weights=len(np.flatnonzero(selected))/(mask.sum()*t['counts'][t['owners'][selected]])
    owners=t['owners'][selected]
    assert np.allclose([weights[owners==i].sum() for i in np.flatnonzero(mask)],len(weights)/mask.sum())
    changed=copy.deepcopy(data)
    for seq in changed['sequences'][0]:seq[:]=500
    changed['durations'][:len(changed['sequences'][0])]=100
    changed_norm=normalize_train(changed,mask)
    assert all(np.array_equal(norm[k],changed_norm[k]) for k in norm)
    cfg=json.loads(Path('configs/tiny-rnn.json').read_text());cfg.update(epochs=2,batch_cycles=128)
    torch.manual_seed(cfg['seed']);initial=TinyGRU(cfg['hidden_size'])
    fold,w=fit_fold(data,held,cfg);again,w2=fit_fold(changed,held,cfg)
    assert not np.array_equal(w['weight_ih_l0'],initial.gru.weight_ih_l0.detach().numpy())
    assert all(np.array_equal(w[k],w2[k]) for k in w)
    assert len(fold['train_people'])==29 and held not in fold['train_people']
    assert set(fold['train_source_ids']).isdisjoint(fold['test_source_ids'])
    assert len(fold['loss_trace'])==2 and all(np.isfinite(r['total_loss']) for r in fold['loss_trace'])
    rows=[dict(source='a',subject='A',quality=0,quality_prediction=0),dict(source='b',subject='B',quality=1,quality_prediction=1)]
    base={'a':dict(quality_prediction=1),'b':dict(quality_prediction=0)}
    assert paired_ci(rows,base,'quality_prediction',100,1)==[100.,100.]
    print('Tiny GRU checks passed:424 parameters, sequence order, padding immunity, equal source weights, held-out mutation invariance, deterministic training and paired bootstrap')


if __name__=='__main__':main()
