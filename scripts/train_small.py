"""Budgeted form classifiers; run from the repository root with the pinned venv."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from harness import parse_name, read_inertial, window_features, windows
from reps import ACC, FS, find_peaks

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'data/phytmo/inertial/upper'
CACHE = REPO / 'tmp/small-data.npz'
STATS = ['mean', 'std', 'min', 'max', 'range', 'rms', 'skew', 'kurtosis', 'energy', 'zcr']
FEATURES = [f'{stat}_{axis}' for stat in STATS for axis in 'xyz']


def load_data(root=ROOT, cache=CACHE):
    """Extract both original feature contracts in one CSV pass; no pickle cache."""
    root, cache = Path(root).resolve(), Path(cache)
    paths = sorted(root.rglob('*.csv'))
    if not paths:
        raise ValueError(f'no CSV files under {root}')
    # Validate cache identity against the raw file inventory, sizes and mtimes.
    import hashlib
    identity = hashlib.sha256('\n'.join(f'{p.relative_to(root)}:{p.stat().st_size}:{p.stat().st_mtime_ns}' for p in paths).encode()).hexdigest()
    if cache.exists():
        with np.load(cache, allow_pickle=False) as z:
            if str(z['identity']) == identity and str(z['root']) == str(root):
                return {k: z[k] for k in z.files}
    bags, sy, ss, se, sources = [], [], [], [], []
    wx, wy, ws, we = [], [], [], []
    for path in paths:
        meta = parse_name(str(path))
        if meta is None:
            continue
        subject, exercise, _, label, _ = meta
        sig = read_inertial(str(path))
        w = windows(sig[:, ACC], 300, .5)
        if len(w):
            wx.append(window_features(w)); wy.extend([label]*len(w))
            ws.extend([subject]*len(w)); we.extend([exercise]*len(w))
        peaks = find_peaks(sig)
        if len(peaks) < 2:
            continue
        bounds = [0] + list((peaks[1:] + peaks[:-1]) // 2) + [len(sig)]
        rows = [np.r_[[(b-a)/FS], window_features(sig[a:b, ACC][None, :, :])[0]]
                for a, b in zip(bounds[:-1], bounds[1:]) if b-a >= 10]
        if len(rows) < 3:
            continue
        bags.append(np.vstack(rows)); sy.append(label); ss.append(subject)
        se.append(exercise); sources.append(str(path.relative_to(root)))
    lens = np.array([len(b) for b in bags])
    data = dict(rep_X=np.vstack(bags), rep_y=np.repeat(sy, lens),
                rep_subject=np.repeat(ss, lens), rep_exercise=np.repeat(se, lens),
                rep_starts=np.r_[0, np.cumsum(lens)], series_y=np.array(sy),
                series_subject=np.array(ss), series_exercise=np.array(se),
                series_source=np.array(sources), window_X=np.vstack(wx),
                window_y=np.array(wy), window_subject=np.array(ws), window_exercise=np.array(we),
                identity=np.array(identity), root=np.array(str(root)), csv_count=np.array(len(paths)))
    for prefix in ('rep', 'window'):
        assert np.isfinite(data[prefix+'_X']).all()
        assert len(np.unique(data[prefix+'_subject'])) == 30
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **data)
    return data


def score(y, pred, exercises):
    return {'accuracy': float(np.mean(pred == y)), 'correct': int(np.sum(pred == y)),
            'count': len(y), 'per_exercise': {
                str(ex): {'accuracy': float(np.mean(pred[exercises == ex] == y[exercises == ex])),
                          'correct': int(np.sum(pred[exercises == ex] == y[exercises == ex])),
                          'count': int(np.sum(exercises == ex))}
                for ex in np.unique(exercises)}}


def evaluate(data, kind, make):
    X, y, subjects = (data[kind+'_'+s] for s in ('X', 'y', 'subject'))
    probabilities = np.empty(len(y))
    for subject in np.unique(subjects):
        te = subjects == subject
        model = make().fit(X[~te], y[~te])
        probabilities[te] = model.predict_proba(X[te])[:, 1]
    if kind == 'rep':
        starts = data['rep_starts']
        probabilities = np.add.reduceat(probabilities, starts[:-1]) / np.diff(starts)
        y, ex = data['series_y'], data['series_exercise']
    else:
        ex = data['window_exercise']
    pred = (probabilities >= .5).astype(int)
    return score(y, pred, ex), probabilities


def baselines(data, output):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from scipy.stats import binomtest
    results = {}
    predictions = {}
    for name, kind, make in [
        ('rep_logreg', 'rep', lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0))),
        ('rep_rf80', 'rep', lambda: RandomForestClassifier(n_estimators=80, min_samples_leaf=8, max_depth=14, n_jobs=3, random_state=0)),
        ('window_rf80', 'window', lambda: RandomForestClassifier(n_estimators=80, min_samples_leaf=8, max_depth=14, n_jobs=3, random_state=0))]:
        results[name], predictions[name] = evaluate(data, kind, make)
        print(name, json.dumps(results[name]), flush=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2)+'\n')
        np.savez_compressed(output.with_suffix('.npz'), **predictions)
    y = data['series_y']
    a, b = predictions['rep_rf80'] >= .5, predictions['rep_logreg'] >= .5
    ac, bc = int(((a == y) & (b != y)).sum()), int(((a != y) & (b == y)).sum())
    results['mcnemar'] = dict(forest_only_correct=ac, logreg_only_correct=bc, p=float(binomtest(ac, ac+bc).pvalue))
    output.write_text(json.dumps(results, indent=2)+'\n')


def fit_small(data, output, budget_bytes=120000, node_budget=10000):
    """Evaluate deployment float32 inputs, refit all subjects, gate before export."""
    import joblib
    import sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    from small_export import emit, check_budget
    from verify_small_export import verify
    from scipy.stats import binomtest
    # Use the same finite float32 input grid as the C API in every fold.
    data = dict(data)
    for kind in ('rep', 'window'):
        data[kind+'_X'] = data[kind+'_X'].astype(np.float32)
    models, sources, results, predictions = {}, {}, {}, {}
    for kind, iterations in [('rep', 50), ('window', 100)]:
        params = dict(max_iter=iterations, max_leaf_nodes=15, learning_rate=.15,
                      l2_regularization=0., early_stopping=False, random_state=0)
        make = lambda: HistGradientBoostingClassifier(**params)
        result, predictions[kind] = evaluate(data, kind, make)
        result['hyperparameters'] = params
        floor = .873 if kind == 'rep' else .809
        if result['accuracy'] < floor:
            raise ValueError(f'{kind} accuracy {result["accuracy"]} below {floor}; no exports written')
        model = make().fit(data[kind+'_X'], data[kind+'_y'])
        name = 'form_'+kind
        models[name] = model
        sources[name] = emit(model, name, data[kind+'_X'].shape[1])
        result['export'] = sources[name][2]
        results[kind] = result
        print(kind, json.dumps(result), flush=True)
    budget = check_budget(sources, budget_bytes, node_budget)
    # Verify a temporary complete export before replacing any deliverable.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='small-export-') as tempdir:
        temp = Path(tempdir)
        for name, (source, header, _) in sources.items():
            (temp/(name+'.c')).write_text(source)
            (temp/(name+'.h')).write_text(header)
            joblib.dump(models[name], temp/(name+'.joblib'), compress=3)
        parity = verify(temp, data)
        golden = {}
        for kind in ('rep', 'window'):
            indices = np.linspace(0, len(data[kind+'_X'])-1, 8, dtype=int)
            rows = data[kind+'_X'][indices]
            golden[kind+'_X'] = rows
            golden[kind+'_probability'] = models['form_'+kind].predict_proba(rows)[:, 1]
            golden[kind+'_row_index'] = indices
        output.mkdir(parents=True, exist_ok=True)
        import shutil
        for path in temp.iterdir():
            shutil.copyfile(path, output/path.name)
        np.savez_compressed(output/'golden.npz', **golden)
    baseline_path = REPO/'docs/runs/small-model/baselines.json'
    comparison = {}
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text())
        for kind in ('rep', 'window'):
            old = baseline.get(kind+'_rf80')
            if old:
                comparison[kind] = {'loss_percentage_points': 100*(old['accuracy']-results[kind]['accuracy']),
                    'per_exercise_loss_percentage_points': {ex: 100*(old['per_exercise'][ex]['accuracy']-results[kind]['per_exercise'][ex]['accuracy']) for ex in old['per_exercise']}}
        bp = np.load(baseline_path.with_suffix('.npz'), allow_pickle=False)
        if 'rep_logreg' in bp:
            y = data['series_y']; a = predictions['rep'] >= .5; b = bp['rep_logreg'] >= .5
            ac = int(((a == y) & (b != y)).sum()); bc = int(((a != y) & (b == y)).sum())
            comparison['rep_vs_logreg'] = {'gain_percentage_points': 100*(results['rep']['accuracy']-baseline['rep_logreg']['accuracy']),
                'small_only_correct': ac, 'logreg_only_correct': bc,
                'mcnemar_exact_p': float(binomtest(ac, ac+bc).pvalue) if ac+bc else 1.}
    report = {'command': 'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .venv/bin/python scripts/train_small.py --fit',
              'sklearn': sklearn.__version__, 'dataset_identity': str(data['identity']),
              'csv_count': int(data['csv_count']), 'series': len(data['series_y']), 'subjects': 30,
              'rep_rows': len(data['rep_X']), 'window_rows': len(data['window_X']),
              'chance_floor': float(max(np.mean(data['series_y']), 1-np.mean(data['series_y']))),
              'protocol': 'all 30 leave-one-subject-out; all training rows; rep mean probabilities then >=0.5; windows scored per row',
              'models': results, 'budget': budget, 'comparison': comparison, 'parity': parity,
              'acceptance': {'rep': .873, 'window': .809, 'note': 'stricter explicit window hard floor overrides 0.799 tolerance'},
              'precision': 'Every LOSO fit and full refit uses float32 feature inputs, matching C; probability accumulation is float32 in C.',
              'refit': 'all 30 subjects; no training accuracy used for acceptance'}
    run_dir = REPO/'docs/runs/small-model'
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir/'fit.json').write_text(json.dumps(report, indent=2)+'\n')
    np.savez_compressed(run_dir/'predictions.npz', **predictions, series_y=data['series_y'],
                        series_subject=data['series_subject'], series_exercise=data['series_exercise'],
                        window_y=data['window_y'], window_subject=data['window_subject'], window_exercise=data['window_exercise'])
    metadata_path = REPO/'model/metadata.json'
    metadata = json.loads(metadata_path.read_text())
    # Legacy artefacts/contracts stay recorded; additive deployment metadata is explicit.
    metadata['small_models'] = {
        'library': 'scikit-learn HistGradientBoostingClassifier', 'evaluation': report,
        'files': {'rep': 'small/form_rep.c + .h + .joblib', 'window': 'small/form_window.c + .h + .joblib'},
        'feature_order': {'rep': ['duration_s']+FEATURES, 'window': FEATURES},
        'input_contract': {'sampling_hz': 100, 'channels': ['accel_x', 'accel_y', 'accel_z'], 'units': 'g',
            'precision': 'finite IEEE float32', 'window_samples': 300, 'window_overlap': .5,
            'labels': {'0': 'correct', '1': 'wrong'}, 'pooling': 'series mean of per-repetition P(wrong); verdict >=0.5',
            'supervision': 'whole-series labels only; no bad-repetition or error-type claims',
            'c_api': 'P(wrong) or -1 on nonfinite input; no allocation; expf from libm'},
        'feature_implementation': 'harness.window_features is statistic-major, axes x/y/z inside each statistic; preceding legacy wording features_per_axis lists statistics only',
        'resource_scope': 'See docs/runs/small-model/target.json for measured objects and real linked resource probe; current paired firmware not rewired.'}
    metadata_path.write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps({'budget': budget, 'comparison': comparison, 'parity': parity}, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--cache', type=Path, default=CACHE)
    ap.add_argument('--baselines', action='store_true')
    ap.add_argument('--fit', action='store_true', help='LOSO, refit all subjects, gate, verify, export')
    ap.add_argument('--output', type=Path, default=REPO/'model/small')
    ap.add_argument('--budget-bytes', type=int, default=120000)
    ap.add_argument('--node-budget', type=int, default=10000)
    args = ap.parse_args()
    if not 0 < args.budget_bytes <= 120000 or not 0 < args.node_budget < 65536:
        ap.error('require 0 < budget bytes <= 120000 and 0 < node budget < 65536')
    data = load_data(args.root, args.cache)
    print({k: data[k].shape for k in ('rep_X', 'window_X', 'series_y')}, flush=True)
    if args.baselines:
        baselines(data, REPO/'docs/runs/small-model/baselines.json')
    if args.fit or not args.baselines:
        fit_small(data, args.output, args.budget_bytes, args.node_budget)

if __name__ == '__main__':
    main()
