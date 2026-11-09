"""Early-gyro clock fit, independent late-gyro check and frozen-lag acceleration diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.signal import correlate, correlation_lags
from scipy.spatial.transform import Rotation

from calibrated_replay import load_record, aligned_waveforms


def validate_config(cfg):
    keys=('early_fraction','late_start_fraction','relative_search_seconds','minimum_overlap_seconds',
          'minimum_overlap_fraction','separate_peak_seconds','screen_minimum_correlation',
          'screen_minimum_peak_margin','screen_maximum_lag_disagreement_seconds')
    if cfg.get('version')!=1 or not np.isfinite([cfg[k] for k in keys]).all():
        raise ValueError('invalid clock audit configuration')
    if not (0<cfg['early_fraction']<cfg['late_start_fraction']<1
        and cfg['relative_search_seconds']>0 and cfg['minimum_overlap_seconds']>0
        and 0<cfg['minimum_overlap_fraction']<=1 and cfg['separate_peak_seconds']>0
        and 0<cfg['screen_minimum_correlation']<=1 and 0<=cfg['screen_minimum_peak_margin']<=2
        and cfg['screen_maximum_lag_disagreement_seconds']>=0):
        raise ValueError('clock audit thresholds outside bounds')


def sample_spans(t, values, grid):
    """Linear interpolation within finite contiguous runs only, with no endpoint extrapolation."""
    t, values, grid = (np.asarray(x, float) for x in (t, values, grid))
    if t.ndim != 1 or values.shape != t.shape or grid.ndim != 1 or len(t) < 2:
        raise ValueError('expected >=2 timestamped scalar values and a 1D target grid')
    if not np.isfinite(t).all() or not np.isfinite(grid).all() or np.any(np.diff(t) <= 0):
        raise ValueError('timestamps must be finite and strictly increasing')
    dt = float(np.median(np.diff(t)))
    ix = np.flatnonzero(np.isfinite(values))
    cut = np.flatnonzero((np.diff(ix)>1) | (np.diff(t[ix])>1.5*dt))+1
    result = np.full(len(grid), np.nan)
    for run in np.split(ix, cut):
        if len(run)<2:
            continue
        take=(grid>=t[run[0]]) & (grid<=t[run[-1]])
        result[take]=np.interp(grid[take],t[run],values[run])
    return result


def gyro_series(record):
    t=np.asarray(record['t'],float)
    q=np.asarray(record['q'],float)
    valid=np.asarray(record['valid'],bool).copy()
    valid &= np.isfinite(q).all(axis=1) & (np.linalg.norm(q,axis=1)>.5)
    valid_pair=valid[:-1] & valid[1:] & np.isclose(np.diff(t),.01,atol=1e-5)
    values=np.full(len(t)-1,np.nan)
    qa=q[:-1][valid_pair];qb=q[1:][valid_pair]
    qa=qa/np.linalg.norm(qa,axis=1,keepdims=True);qb=qb/np.linalg.norm(qb,axis=1,keepdims=True)
    values[valid_pair]=np.linalg.norm((Rotation.from_quat(qa).inv()*Rotation.from_quat(qb)).as_rotvec(),axis=1)/np.diff(t)[valid_pair]
    imu_t=np.asarray(record['meta']['imu_t'],float)
    measured=np.linalg.norm(record['real6'][:,:3],axis=1)*np.pi/180
    return (t[:-1]+t[1:])/2,values,imu_t,measured


def estimate_window_lag(ot,ow,it,iw,window,cfg):
    start,stop=window
    if not np.isfinite([start,stop]).all() or stop<=start:
        raise ValueError('invalid optical window')
    og=np.arange(ot[0],ot[-1]+1e-7,.01)
    ig=np.arange(it[0],it[-1]+1e-7,.01)
    x=sample_spans(ot,ow,og);y=sample_spans(it,iw,ig)
    mx=np.isfinite(x)&(og>=start)&(og<=stop);my=np.isfinite(y)
    minimum=max(int(cfg['minimum_overlap_seconds']*100),int(np.ceil(cfg['minimum_overlap_fraction']*mx.sum())))
    if mx.sum()<minimum:
        return dict(lag_s=None,reason='insufficient optical gyro coverage',available_samples=int(mx.sum()))
    # Center each full input for numerical stability, then remove overlap-specific means below.
    x=np.where(mx,x-np.nanmean(x[mx]),0.);y=np.where(my,y-np.nanmean(y[my]),0.)
    mx=mx.astype(float);my=my.astype(float)
    def cc(a,b):return correlate(a,b,mode='full',method='fft')
    count=np.maximum(cc(my,mx),0.)
    sx=cc(my,x);sy=cc(y,mx)
    cross=cc(y,x)-sx*sy/np.maximum(count,1.)
    vx=np.maximum(cc(my,x*x)-sx*sx/np.maximum(count,1.),0.)
    vy=np.maximum(cc(y*y,mx)-sy*sy/np.maximum(count,1.),0.)
    denominator=np.sqrt(vx*vy)
    lags=correlation_lags(len(y),len(x))
    allowed=(count>=minimum-.01)&(np.abs(lags)<=round(cfg['relative_search_seconds']*100))&(denominator>1e-8)
    if not allowed.any():return dict(lag_s=None,reason='no variable sufficient-overlap candidate')
    scores=np.divide(cross,denominator,out=np.full(len(cross),-np.inf),where=denominator>1e-8)
    scores[allowed]=np.clip(scores[allowed],-1.,1.)
    candidates=np.flatnonzero(allowed);peak=int(candidates[np.argmax(scores[candidates])])
    separate=allowed&(np.abs(lags-lags[peak])>=round(cfg['separate_peak_seconds']*100))
    second=float(np.max(scores[separate])) if separate.any() else None
    return dict(lag_s=float(ig[0]-og[0]+lags[peak]*.01),peak_correlation=float(scores[peak]),
                peak_margin=float(scores[peak]-second) if second is not None else None,
                overlap_samples=int(round(count[peak])),available_samples=int(mx.sum()),
                reason='reference-assisted window estimate')


def fixed_lag_check(ot,ow,it,iw,window,lag):
    grid=np.arange(window[0],window[1]+1e-7,.01)
    x=sample_spans(ot,ow,grid);y=sample_spans(it,iw,grid+lag)
    available=np.isfinite(x);good=available&np.isfinite(y)
    x,y=x[good],y[good]
    correlation=None
    if len(x)>=2 and np.std(x)>1e-8 and np.std(y)>1e-8:
        correlation=float(np.corrcoef(x,y)[0,1])
    return dict(correlation=correlation,overlap_samples=int(good.sum()),
                coverage=float(good.sum()/max(available.sum(),1)))


def passes_screen(early,late,check,cfg):
    if early['lag_s'] is None or late['lag_s'] is None or check.get('correlation') is None:
        return False
    return bool(early['peak_correlation']>=cfg['screen_minimum_correlation']
        and early.get('peak_margin') is not None and early['peak_margin']>=cfg['screen_minimum_peak_margin']
        and check['correlation']>=cfg['screen_minimum_correlation']
        and check['coverage']>=cfg['minimum_overlap_fraction']
        and abs(late['lag_s']-early['lag_s'])<=cfg['screen_maximum_lag_disagreement_seconds']+1e-8)


def metric_pair(data,late_start):
    take=data['time_s']>=late_start
    if take.sum()<200:raise ValueError('fewer than two seconds of late acceleration overlap')
    real=data['real_g'][take];result={}
    for key in ('baseline_g','calibrated_g'):
        pred=data[key][take];error=pred-real
        xd=pred-pred.mean(axis=0);yd=real-real.mean(axis=0)
        result[key]=dict(rmse_g=float(np.sqrt(np.mean(error**2))),rmse_xyz_g=np.sqrt(np.mean(error**2,axis=0)).tolist(),
            bias_xyz_g=error.mean(axis=0).tolist(),dynamic_rmse_g=float(np.sqrt(np.mean((xd-yd)**2))))
    return dict(n_samples=int(take.sum()),measured_dynamic_rms_g=float(np.sqrt(np.mean((real-real.mean(axis=0))**2))),**result)


def run(root,prior_path,cfg_path,out):
    cfg=json.loads(cfg_path.read_text());prior=json.loads(prior_path.read_text())
    validate_config(cfg)
    rows=[];failures=[]
    for fold in prior['folds']:
        for original in fold['rows']:
            sid=original['source_id'];path,side,segment=sid.split('|')
            row=dict(source_id=sid,person=original['person'],side=side,segment=segment,
                     exercise=original['exercise'],quality=original['quality'])
            try:
                rec=load_record(Path(path),root/'inertial/upper',side,segment)
                ot,ow,it,iw=gyro_series(rec);duration=ot[-1]-ot[0]
                early_window=(ot[0],ot[0]+duration*cfg['early_fraction'])
                late_window=(ot[0]+duration*cfg['late_start_fraction'],ot[-1])
                early=estimate_window_lag(ot,ow,it,iw,early_window,cfg)
                late=estimate_window_lag(ot,ow,it,iw,late_window,cfg)
                check=fixed_lag_check(ot,ow,it,iw,late_window,early['lag_s']) if early['lag_s'] is not None else {}
                row.update(early_window_s=early_window,late_window_s=late_window,early=early,late_independent_diagnostic=late,
                    late_at_frozen_early_lag=check,passes_descriptive_screen=passes_screen(early,late,check,cfg),
                    lag_difference_s=late['lag_s']-early['lag_s'] if late['lag_s'] is not None and early['lag_s'] is not None else None)
                if early['lag_s'] is not None:
                    try:
                        params=fold['params_by_sensor'][side+'|'+segment]
                        waves=aligned_waveforms(rec,early['lag_s'],params)
                        row['late_waveform']=metric_pair(waves,late_window[0]+early['lag_s'])
                    except (ValueError,IndexError) as exc:row['waveform_error']=str(exc)
            except (ValueError,OSError) as exc:
                row['error']=str(exc);row['passes_descriptive_screen']=False;failures.append(sid)
            rows.append(row)
        print(f"{fold['heldout_person']}: audited {len(rows)}/653 sensor records",flush=True)
    passed=[r for r in rows if r['passes_descriptive_screen']]
    summary=dict(people=len({r['person'] for r in rows}),sensor_records=len(rows),processing_errors=len(failures),
                 screened_sensor_records=len(passed),screened_people=len({r['person'] for r in passed}),
                 waveform_records=sum('late_waveform' in r for r in rows))
    for label,subset in [('all_available_late',rows),('screened_late',passed)]:
        eligible=[r['late_waveform'] for r in subset if 'late_waveform' in r]
        summary[label]=dict(records=len(eligible),baseline_median_total_rmse_g=float(np.median([r['baseline_g']['rmse_g'] for r in eligible])) if eligible else None,
            calibrated_median_total_rmse_g=float(np.median([r['calibrated_g']['rmse_g'] for r in eligible])) if eligible else None)
    result=dict(protocol=cfg,summary=summary,rows=rows,inherited_phase4_rejected=prior['rejected'],
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        prior_calibration_sha256=hashlib.sha256(prior_path.read_bytes()).hexdigest(),
        interpretation='Reference-assisted early/late timing diagnostic only. Same held-out volunteer gyro informs timing, never acceleration. Physical corrections are frozen historical Phase 4 training-only fits, not refitted under the new clock policy. This does not pass/replace the Phase 4 simulator gate or establish anatomical location.')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path('data/phytmo'))
    ap.add_argument('--prior',type=Path,default=Path('docs/runs/phase4/calibration.json'))
    ap.add_argument('--config',type=Path,default=Path('configs/clock-reconstruction-audit.json'))
    ap.add_argument('--out',type=Path,default=Path('docs/runs/phase5/clock-reconstruction.json'))
    args=ap.parse_args();run(args.root,args.prior,args.config,args.out)


if __name__=='__main__':main()
