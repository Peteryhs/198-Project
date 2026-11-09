"""Print the report's measured tables directly from retained result artifacts."""
import json
from pathlib import Path


def load(path):return json.loads(Path(path).read_text())

def main():
    base=load('model/realtime-linear/results.json')
    print('Accepted historical baseline, read only (not rerun):',json.dumps({k:base[k] for k in ['n_series','quality_loso_accuracy','quality_majority_class_floor','exercise_loso_accuracy','exercise_majority_class_floor']}))
    print('| Source / configuration | series | quality accuracy / majority floor | exercise accuracy / majority floor |')
    print('| --- | ---: | ---: | ---: |')
    for mode in ['offline','causal']:
        for side in 'LR':
            r=load(f'model/paired-synchronized-{mode}/{side}/results.json')
            print(f"| REAL recordings / {side} paired {mode} | {r['series']} | {r['quality_accuracy']*100:.2f}% / {r['quality_majority_floor']*100:.2f}% | {r['exercise_accuracy']*100:.2f}% / {r['exercise_majority_floor']*100:.2f}% |")
            from collections import Counter
            print(f"retention {mode}/{side}: {r['series']}/{r['series']+len(r['rejected'])} = {r['series']/(r['series']+len(r['rejected'])):.6f}; rejected reasons: {dict(Counter(x['reason'] for x in r['rejected']))}")
    place=load('docs/runs/round2/placement.json')
    for r in place['rows']:
        name=r['source']+(f" {r['side']} {r['degrees']}deg" if 'degrees' in r else '')
        print(f"| {name} | {r['series']} | {r['quality_accuracy']*100:.2f}% / {r['quality_majority_floor']*100:.2f}% | {r['exercise_accuracy']*100:.2f}% / {r['exercise_majority_floor']*100:.2f}% |")
    full=load('model/paired-synchronized-causal/L/results.json')
    print('Common-cohort retained fraction:',place['rows'][0]['series']/(full['series']+len(full['rejected'])))
    print('Side difference/subject-bootstrap intervals:',json.dumps(place['side_difference']))
    sim=load('docs/runs/round2/simulation.json')
    print('Simulation empirical gate:',sim['gate_passed'],'passed',sim['passed_statistics'],'of',sim['total_statistics'])
    print('| Source: real vs SIMULATION / left forearm | real p10/p50/p90 | simulation p10/p50/p90 |')
    print('| --- | --- | --- |')
    for r in sim['comparisons']:
        if r['side']=='L' and r['segment']==1:
            print(f"| {r['exercise']} {r['statistic']} | {', '.join(f'{x:.4f}' for x in r['real_p10_p50_p90'])} | {', '.join(f'{x:.4f}' for x in r['simulation_p10_p50_p90'])} |")
    print('Optical reference:',json.dumps({k:load('docs/runs/round2/optical-reference.json')[k] for k in ['selected_files','comparisons','interpretation']}))
    err=load('docs/runs/round2/error-evidence.json')
    print('Physical deviation summaries (NOT mechanism accuracy):',json.dumps(err['summary']))
    print('Annotation planning ESTIMATES:',json.dumps(err['planning_estimates']))
    target=load('docs/runs/round2/target-size.json')
    print('| Model | parameter B | classifier allocated text B | complete causal allocated text B | causal BSS B |')
    print('| --- | ---: | ---: | ---: | ---: |')
    for r in target['models']:
        p=r.get('full_causal_pipeline',{})
        print(f"| {r['model']} | {r['parameter_bytes']} | {r['classifier']['text_rodata_exidx_bytes']} | {p.get('text_rodata_exidx_bytes','offline control')} | {p.get('bss_bytes','offline control')} |")
    print('Target state/reserves ESTIMATES:',json.dumps(target['allocation_estimates']))
    print('Actual feature arithmetic contract:',json.dumps(target['feature_arithmetic']))
    print('Latency components / limits:',json.dumps(target['latency']))
    print('Two runtime states plus core reserve ESTIMATE:',target['two_pair_float_state_plus_core_estimate'])
    assert len(target['models'])==10 and not sim['gate_passed']
if __name__=='__main__':main()
