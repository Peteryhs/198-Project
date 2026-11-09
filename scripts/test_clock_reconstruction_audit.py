"""Independent known-value tests for the split-window clock/reconstruction audit."""
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from clock_reconstruction_audit import (sample_spans,estimate_window_lag,fixed_lag_check,
    passes_screen,gyro_series,metric_pair,validate_config)


def main():
    cfg=json.loads(Path('configs/clock-reconstruction-audit.json').read_text())
    t=2.005+np.arange(4000)/100
    # Irregular event spacing avoids manufacturing an unambiguous periodic peak.
    def signal(t):
        return 4+sum(a*np.exp(-((t-c)/w)**2) for c,a,w in [(5,1,.4),(9,3,.6),(13,2,.3),(19,4,.7),(27,3,.4),(34,2,.6),(38,4,.3)])
    lag=7.35;it=np.arange(1,56,.01)
    x=signal(t);y=signal(it-lag)*1.7+13
    early=estimate_window_lag(t,x,it,y,(t[0],t[0]+16),cfg)
    late=estimate_window_lag(t,x,it,y,(t[0]+24,t[-1]),cfg)
    assert abs(early['lag_s']-lag)<.011,early
    assert abs(late['lag_s']-lag)<.011,late
    check=fixed_lag_check(t,x,it,y,(t[0]+24,t[-1]),early['lag_s'])
    assert check['correlation']>.999 and early['peak_correlation']>.999
    assert passes_screen(early,late,check,cfg)
    # Values outside the winning overlap change global means but must not change its Pearson score.
    outside_y=y.copy()
    outside=(it<t[0]+lag-.02)|(it>t[0]+16+lag+.02)
    outside_y[outside]+=200+np.arange(outside.sum())*.03
    local=estimate_window_lag(t,x,it,outside_y,(t[0],t[0]+16),cfg)
    assert abs(local['lag_s']-early['lag_s'])<1e-8
    assert abs(local['peak_correlation']-early['peak_correlation'])<1e-6
    validate_config(cfg)
    for bad in [{**cfg,'minimum_overlap_fraction':2},{**cfg,'early_fraction':float('nan')}]:
        try:validate_config(bad)
        except ValueError:pass
        else:raise AssertionError('invalid clock config accepted')
    # Wrong clock at later times is detected independently of acceleration.
    bad_y=y.copy(); bad_y[it>lag+23]=signal(it[it>lag+23]-lag-.7)*1.7+13
    bad_check=fixed_lag_check(t,x,it,bad_y,(t[0]+24,t[-1]),early['lag_s'])
    bad_late=estimate_window_lag(t,x,it,bad_y,(t[0]+24,t[-1]),cfg)
    assert not passes_screen(early,bad_late,bad_check,cfg)
    assert abs((bad_late['lag_s']-early['lag_s'])-.7)<.021
    periodic=estimate_window_lag(t,np.sin(t*2*np.pi),it,np.sin((it-lag)*2*np.pi),(t[0],t[0]+16),cfg)
    assert periodic['peak_margin']<.05
    # Missing samples and timestamp gaps must remain absent after interpolation.
    q=np.arange(10.)/100;v=q.copy();v[3:6]=np.nan
    z=sample_spans(q,v,np.arange(19)/200)
    assert np.isnan(z[5:12]).all()
    q=np.r_[np.arange(4)/100,1+np.arange(4)/100]
    assert np.isnan(sample_spans(q,q,np.array([.5]))[0])
    for bad in [np.array([0.,0.]),np.array([0.,np.nan])]:
        try:sample_spans(bad,np.ones(2),np.ones(2))
        except ValueError:pass
        else:raise AssertionError('invalid times accepted')
    try:sample_spans(np.array([0.,1.]),np.ones(2),np.array([np.inf]))
    except ValueError:pass
    else:raise AssertionError('invalid target grid accepted')
    # Constant angular velocity about Z is obtained from quaternion increments, in rad/s.
    qt=np.arange(1000)/100
    rec=dict(t=qt,q=Rotation.from_rotvec(np.column_stack((qt*0,qt*0,qt*.6))).as_quat(),valid=np.ones(1000,bool),
        real6=np.tile([0,0,.6*180/np.pi,0,0,0],(1000,1)),meta={'imu_t':qt})
    _,ow,_,iw=gyro_series(rec)
    assert np.allclose(ow,.6,atol=1e-10) and np.allclose(iw,.6,atol=1e-10)
    constant=estimate_window_lag(qt,np.ones(1000),qt,np.ones(1000),(0,9),cfg)
    assert constant['lag_s'] is None
    # Hand-computable three-axis error, with late masking independent of its value.
    real=np.zeros((300,3));pred=np.tile([1.,2.,2.],(300,1))
    metrics=metric_pair(dict(time_s=np.arange(300)/100,real_g=real,baseline_g=pred,calibrated_g=pred*.5),1.)
    assert metrics['n_samples']==200
    assert np.isclose(metrics['baseline_g']['rmse_g'],np.sqrt(3))
    assert metrics['baseline_g']['rmse_xyz_g']==[1,2,2]
    assert metrics['baseline_g']['bias_xyz_g']==[1,2,2]
    assert metrics['baseline_g']['dynamic_rmse_g']==0
    assert np.isclose(metrics['calibrated_g']['rmse_g'],np.sqrt(3)/2)
    print('Split clock checks passed: known offset/origins/crops, local means, future mismatch, periodic ambiguity, gaps, units and golden waveform metrics')


if __name__=='__main__':main()
