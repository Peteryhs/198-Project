"""Independently audit saved Phase 4 lineage, matched metrics and placement decisions."""
import csv
import argparse
import hashlib
import json
import re
import subprocess
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

BASE = Path('docs/runs/phase4')


def read(name):
    return json.loads((BASE / (name + '.json')).read_text())


def verify_data():
    counts = {}
    total = 0
    for kind in ('raw', 'interp'):
        manifest = read('data-' + kind + '-archive')
        rows = manifest['categories'][kind]['first_series_with_local_inertial_counterpart_members']
        cal = read('data-' + kind + '-calibration')['upper_calibration'][kind]['members']
        assert len(rows) == 171 and len(cal) == 30
        assert len({r['normalized_person'] for r in rows}) == 30
        for row in rows + cal:
            path = Path('data/phytmo') / row['member']
            payload = path.read_bytes()
            assert len(payload) == row['bytes'], path
            assert zlib.crc32(payload) == int(row['crc32'], 16), path
            total += len(payload)
        counts[kind] = dict(exercise_files=len(rows), calibration_files=len(cal))
    assert total == 2465165313
    return dict(files=402, uncompressed_bytes=total, counts=counts, crc_and_size='all passed')


def verify_calibration(source_ref=None):
    report = read('calibration')
    cfg = json.loads(Path('configs/replay-calibration.json').read_text())
    source = (subprocess.check_output(['git','show',source_ref+':scripts/calibrated_replay.py'])
              if source_ref else Path('scripts/calibrated_replay.py').read_bytes())
    assert report['runtime']['calibration_script_sha256'] == hashlib.sha256(source).hexdigest()
    assert report['runtime']['config_sha256'] == hashlib.sha256(Path('configs/replay-calibration.json').read_bytes()).hexdigest()
    folds = report['folds']
    assert len(folds) == 30 and report['cohort']['n_records'] == 653
    assert len(report['rejected']) == 31
    rows = [r for f in folds for r in f['rows']]
    assert len(rows) == 653 and len({r['source_id'] for r in rows}) == 653
    by_id = {r['source_id']: r for r in rows}
    params = []
    for fold in folds:
        who = fold['heldout_person']
        assert who not in fold['train_people'] and len(set(fold['train_people'])) == 29
        assert set(fold['train_source_ids']).isdisjoint(fold['heldout_source_ids'])
        assert set(fold['train_source_ids']) == {r['source_id'] for r in rows if r['person'] != who}
        assert all(r['person'] == who for r in fold['rows'])
        for key, lag in fold['train_lag_medians_s'].items():
            side, seg = key.split('|')
            eligible = [by_id[s]['heldout_gyro_oracle_lag'] for s in fold['train_source_ids']
                        if by_id[s]['side'] == side and by_id[s]['segment'] == seg]
            values = [r['lag_s'] for r in eligible if r['lag_s'] is not None
                      and r['peak_correlation'] >= cfg['timing']['minimum_gyro_magnitude_correlation']
                      and r['peak_margin'] >= cfg['timing']['minimum_peak_margin']]
            assert lag == float(np.median(values))
            assert all(r['train_median_lag_s'] == lag for r in fold['rows'] if r['side'] == side and r['segment'] == seg)
        params.extend(fold['params_by_sensor'].values())
    assert len(params) == 120 and all(p['fit_success'] and p['jacobian_rank'] == 12 for p in params)
    tracks = {}
    for track in ('primary_train_mapped', 'oracle_diagnostic'):
        paired = [(r, r[track]['baseline'], r[track]['calibrated']) for r in rows
                  if r.get(track, {}).get('baseline') and r[track].get('calibrated')]
        assert all(a['n_samples'] == b['n_samples'] and a['duration_s'] == b['duration_s'] for _, a, b in paired)
        active = [(r, a, b) for r, a, b in paired if b['measured_dynamic_rms_g'] >= .05]
        base = np.mean([a['dynamic_rmse_g'] for _, a, _ in active])
        fitted = np.mean([b['dynamic_rmse_g'] for _, _, b in active])
        tracks[track] = dict(matched=len(paired), active=len(active), mean_dynamic_rmse_baseline_g=float(base),
            mean_dynamic_rmse_calibrated_g=float(fitted), dynamic_rmse_reduction_percent=float(100*(1-fitted/base)),
            median_total_rmse_baseline_g=float(np.median([a['rmse_g'] for _, a, _ in paired])),
            median_total_rmse_calibrated_g=float(np.median([b['rmse_g'] for _, _, b in paired])))
        if track == 'primary_train_mapped':
            gate = report['calibration_gate']['matched_waveform']
            assert np.isclose(gate['baseline_dynamic_rmse_g_mean'], base)
            assert np.isclose(gate['calibrated_dynamic_rmse_g_mean'], fitted)
            # Resample people, carrying all their matched active sensor recordings together.
            people = sorted({r['person'] for r, _, _ in active})
            sums = np.array([[sum(a['dynamic_rmse_g'] for r,a,b in active if r['person']==p),
                              sum(b['dynamic_rmse_g'] for r,a,b in active if r['person']==p)] for p in people])
            draw = np.random.default_rng(20261107).integers(0,len(people),(2000,len(people)))
            totals = sums[draw].sum(axis=1)
            tracks[track]['subject_bootstrap_reduction_percent_p025_p975'] = np.percentile(100*(1-totals[:,1]/totals[:,0]),[2.5,97.5]).tolist()
    # Reproduce the plotted held-out cache directly from the saved physical fit.
    from calibrated_replay import load_record, aligned_waveforms
    example = next(r for r in rows if r.get('cache'))
    fold = next(f for f in folds if f['heldout_person'] == example['person'])
    path, side, segment = example['source_id'].split('|')
    record = load_record(Path(path), Path('data/phytmo/inertial/upper'), side, segment)
    rebuilt = aligned_waveforms(record, example['train_median_lag_s'], fold['params_by_sensor'][side+'|'+segment])
    with np.load(example['cache'], allow_pickle=False) as cache:
        for field in ('time_s', 'real_g', 'baseline_g', 'calibrated_g'):
            assert np.array_equal(cache[field], rebuilt[field], equal_nan=True), field
    return dict(folds=30, accepted_sensor_records=653, rejected_sensor_records=31, fitted_transforms=120,
                transforms_with_bound_hits=sum(bool(p['bound_hits']) for p in params), tracks=tracks,
                lineage_train_clock_and_cache='passed', gate_passed=report['calibration_gate']['passed'])


def verify_placements():
    report = read('placement-sweep')
    groups = defaultdict(list)
    with (BASE/'placement-sweep-sources.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            groups[row['side'],int(row['candidate']),float(row['remount_rotation_deg'])].append(row)
    assert len(report['rows']) == len(groups) == 486
    assert sum(map(len, groups.values())) == 83106
    for fold in report['model_folds']:
        assert len(fold['train_people']) == fold['n_train_people'] == 29
        assert fold['heldout_person'] not in fold['train_people']
        assert set(fold['train_source_ids']).isdisjoint(fold['heldout_source_ids'])
        assert all(not Path(p).name.startswith(fold['heldout_person']) for p in fold['train_source_ids'])
    assert len(report['model_folds']) == 60
    majority = {}
    for fold in report['model_folds']:
        labels = [re.search(r'(EAH|EFE|SQZ)([01])_[12]\.csv$', Path(p).name).groups()
                  for p in fold['train_source_ids']]
        qmaj = str(int(np.mean([int(q) for e,q in labels]) >= .5))
        # np.unique in the evaluator sorts ties alphabetically.
        counts = Counter(e for e,q in labels)
        emaj = min(counts, key=lambda e: (-counts[e],e))
        majority[fold['side'],fold['heldout_person']] = (qmaj,emaj)
    summary = {}
    for saved in report['rows']:
        rows = groups[saved['side'], saved['candidate'], saved['remount_rotation_deg']]
        assert len(rows) == len({r['source'] for r in rows}) == saved['eligible_series'] == 171
        assert len({r['subject'] for r in rows}) == 30
        covered = sum(r['quality_prediction'] != 'abstain' for r in rows)
        qr = sum(r['quality_prediction'] == r['quality_label'] for r in rows)
        er = sum(r['exercise_prediction'] == r['exercise'] for r in rows)
        assert covered == saved['covered']
        for key, value in [('coverage',covered/171), ('quality_series_label_agreement_all_denominator',qr/171),
                           ('exercise_series_label_agreement_all_denominator',er/171)]:
            assert np.isclose(saved[key],value), key
        qfloor = sum(r['quality_label'] == majority[r['side'],r['subject']][0] for r in rows)/171
        efloor = sum(r['exercise'] == majority[r['side'],r['subject']][1] for r in rows)/171
        assert np.isclose(saved['quality_majority_floor_all_denominator'],qfloor)
        assert np.isclose(saved['exercise_majority_floor_all_denominator'],efloor)
        for exercise, result in saved['by_exercise'].items():
            subset = [r for r in rows if r['exercise']==exercise]
            assert len(subset) == result['eligible_series']
            assert sum(r['quality_prediction']!='abstain' for r in subset) == result['covered']
            assert np.isclose(sum(r['quality_prediction']==r['quality_label'] for r in subset)/len(subset),
                              result['quality_series_label_agreement_all_denominator'])
    for side in 'LR':
        example = groups[side,0,0.]
        quality_counts = Counter(r['quality_label'] for r in example)
        exercise_counts = Counter(r['exercise'] for r in example)
        selected = [r for r in report['rows'] if r['side']==side and r['remount_rotation_deg']==0]
        def bounds(key):
            return [min(r[key] for r in selected),max(r[key] for r in selected)]
        summary[side] = dict(sources=171, people=30, global_quality_majority_floor=max(quality_counts.values())/171,
            global_exercise_majority_floor=max(exercise_counts.values())/171,
            training_quality_majority_predictor=selected[0]['quality_majority_floor_all_denominator'],
            training_exercise_majority_predictor=selected[0]['exercise_majority_floor_all_denominator'],
            coverage_range=bounds('coverage'), quality_agreement_range=bounds('quality_series_label_agreement_all_denominator'),
            exercise_agreement_range=bounds('exercise_series_label_agreement_all_denominator'),
            median_clip_fraction=float(np.median([float(r['clip_fraction']) for r in example if r['clip_fraction']!=''])))
    assert report['calibration_gate']['passed'] is False
    return dict(scenarios=486, per_source_decisions=83106, model_folds=60, recomputed_decisions='passed', sides=summary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration-source-ref',help='explicit historical Git revision for the unchanged Phase 4 report source hash')
    args=parser.parse_args()
    result = dict(data=verify_data(), calibration=verify_calibration(args.calibration_source_ref), placements=verify_placements())
    (BASE/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
