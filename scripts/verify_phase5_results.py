"""Cross-check corrected Phase 5 source versions, cohorts, screens and reported aggregates."""
import hashlib
import json
from pathlib import Path

import numpy as np

BASE=Path('docs/runs/phase5')


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    old=read('docs/runs/phase4/calibration.json')
    corrected=read(BASE/'calibration-corrected.json')
    assert corrected['runtime']['calibration_script_sha256']==sha('scripts/calibrated_replay.py')
    assert corrected['runtime']['config_sha256']==sha('configs/replay-calibration.json')
    before={r['source_id']:r for f in old['folds'] for r in f['rows']}
    after={r['source_id']:r for f in corrected['folds'] for r in f['rows']}
    assert len(before)==len(after)==653 and before.keys()==after.keys()
    assert old['rejected']==corrected['rejected'] and len(corrected['rejected'])==31
    for sid,row in after.items():
        prior=before[sid]
        assert row['person']==prior['person'] and row['train_median_lag_s']==prior['train_median_lag_s']
        for track in ['primary_train_mapped','oracle_diagnostic']:
            assert row[track].get('baseline')==prior[track].get('baseline')
            if row[track].get('baseline') and row[track].get('calibrated'):
                assert row[track]['baseline']['n_samples']==row[track]['calibrated']['n_samples']
    assert len(corrected['folds'])==30
    for fold in corrected['folds']:
        assert fold['heldout_person'] not in fold['train_people'] and len(set(fold['train_people']))==29
        assert set(fold['train_source_ids']).isdisjoint(fold['heldout_source_ids'])
    timing=read(BASE/'clock-reconstruction-corrected.json');cfg=timing['protocol']
    assert timing['source_sha256']==sha('scripts/clock_reconstruction_audit.py')
    assert timing['prior_calibration_sha256']==sha(BASE/'calibration-corrected.json')
    assert {r['source_id'] for r in timing['rows']}==after.keys()
    passed=[]
    for row in timing['rows']:
        e,l,c=row['early'],row['late_independent_diagnostic'],row['late_at_frozen_early_lag']
        good=(e['lag_s'] is not None and l['lag_s'] is not None and c.get('correlation') is not None
              and e['peak_correlation']>=cfg['screen_minimum_correlation']
              and e.get('peak_margin') is not None and e['peak_margin']>=cfg['screen_minimum_peak_margin']
              and c['correlation']>=cfg['screen_minimum_correlation'] and c['coverage']>=cfg['minimum_overlap_fraction']
              and abs(l['lag_s']-e['lag_s'])<=cfg['screen_maximum_lag_disagreement_seconds']+1e-8)
        assert row['passes_descriptive_screen']==good
        if good:passed.append(row)
    assert len(passed)==timing['summary']['screened_sensor_records']==20
    assert len({r['person'] for r in passed})==timing['summary']['screened_people']==6
    for label,rows in [('all_available_late',timing['rows']),('screened_late',passed)]:
        rows=[r for r in rows if 'late_waveform' in r]
        saved=timing['summary'][label];assert saved['records']==len(rows)
        for field,key in [('baseline_g','baseline_median_total_rmse_g'),('calibrated_g','calibrated_median_total_rmse_g')]:
            expected=np.median([r['late_waveform'][field]['rmse_g'] for r in rows])
            assert np.isclose(saved[key],expected,rtol=1e-12,atol=1e-12)
    # Rebuild an actual late comparison from the raw source; calculate errors without metric_pair.
    from calibrated_replay import load_record,aligned_waveforms
    sample=passed[0];path,side,seg=sample['source_id'].split('|')
    fold=next(f for f in corrected['folds'] if f['heldout_person']==sample['person'])
    rec=load_record(Path(path),Path('data/phytmo/inertial/upper'),side,seg)
    waves=aligned_waveforms(rec,sample['early']['lag_s'],fold['params_by_sensor'][side+'|'+seg])
    take=waves['time_s']>=sample['late_window_s'][0]+sample['early']['lag_s']
    assert int(take.sum())==sample['late_waveform']['n_samples']
    for field in ['baseline_g','calibrated_g']:
        x=waves[field][take];y=waves['real_g'][take];saved=sample['late_waveform'][field]
        assert np.allclose(np.sqrt(np.mean((x-y)**2,axis=0)),saved['rmse_xyz_g'],atol=1e-12)
        assert np.allclose(np.mean(x-y,axis=0),saved['bias_xyz_g'],atol=1e-12)
        assert np.isclose(np.sqrt(np.mean((x-y)**2)),saved['rmse_g'],atol=1e-12)
    audit=read(BASE/'reporting-audit.json')
    assert audit['calibration']['fit_input_alignment']['max_boundary_discrepancy_g']<1e-10
    assert audit['corrected_calibration']['report_sha256']==sha(BASE/'calibration-corrected.json')
    anatomy=read(BASE/'location-followup.json')
    assert len(anatomy['rows'])==60 and len(anatomy['rejected'])==0
    assert anatomy['summary']['declared_stability_passes']==0
    assert corrected['calibration_gate']['passed'] is False
    result=dict(source_versions='matched',matched_baseline_and_cohorts='unchanged',fold_exclusion='passed',
                timing_screens_and_summary='independently reproduced',late_raw_source_metrics='reproduced',
                fit_score_boundary_max_error_g=audit['calibration']['fit_input_alignment']['max_boundary_discrepancy_g'],
                physical_validation='still failed',accepted_models='verified separately by verify_round2.py')
    (BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
