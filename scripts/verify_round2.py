"""Recheck stored predictions, exact refits and C parity for every valid round-two model."""
import csv,json
from pathlib import Path
import numpy as np
import paired_pipeline as pp
import realtime_pipeline as rp
from streaming_pipeline import StreamExtractor
from placement_experiment import common_data
from verify_paired_export import verify


def check(data,path):
    verify(data,path)
    bags,y,subs,exs,names,_=data
    q,e=rp.fold_predictions(bags,y,subs,exs)
    with (path/'predictions.csv').open() as f:prior={r['source']:r for r in csv.DictReader(f)}
    assert len(prior)==len(names)
    assert all(int(prior[name]['quality_prediction'])==qp and prior[name]['exercise_prediction']==ep for name,qp,ep in zip(names,q,e))
    r=json.loads((path/'results.json').read_text())
    assert r['quality_accuracy']==float(np.mean(q==y)) and r['exercise_accuracy']==float(np.mean(e==exs))
    print(f"stored LOSO predictions unchanged {path}: quality={r['quality_accuracy']:.6f} / majority={r['quality_majority_floor']:.6f}; exercise={r['exercise_accuracy']:.6f} / majority={r['exercise_majority_floor']:.6f}")


def main():
    root=Path('data/phytmo/inertial/upper')
    for side in 'LR':check(pp.collect(root,side),Path('model/paired-synchronized-offline')/side)
    with StreamExtractor() as extractor:
        data={side:pp.collect(root,side,extractor) for side in 'LR'}
        for side in 'LR':check(data[side],Path('model/paired-synchronized-causal')/side)
        common=common_data(data['L'],data['R'])
        for side in 'LR':
            for config in ['pair','upper','forearm']:
                bags,y,subs,exs,names,rejected=common[side]
                if config=='upper':bags=[b[:,:31] for b in bags]
                if config=='forearm':bags=[np.c_[b[:,0],b[:,31:]] for b in bags]
                check((bags,y,subs,exs,names,rejected),Path('model/placement-controls')/f'{side}-{config}')
    print('All 10 valid models: exact saved coefficients, C probability parity and every LOSO series decision verified.')
if __name__=='__main__':main()
