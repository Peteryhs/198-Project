"""MuJoCo virtual accelerometers: kinematics prescribed, effort deliberately unidentified."""
from pathlib import Path
import numpy as np
from scipy.signal import lfilter
import mujoco
from modelling_environment import check_environment
check_environment()
if mujoco.__version__!='3.3.7':raise RuntimeError('simulation requires mujoco==3.3.7; uv run --locked --extra simulation ...')
ROOT=Path(__file__).resolve().parents[1]
G=9.80665


def make_model(offset=0.,plane_deg=0.):
    m=mujoco.MjModel.from_xml_path(str(ROOT/'simulation/two_link.xml'))
    m.site_pos[0,2]-=offset;m.site_pos[1,2]-=offset
    angle=np.deg2rad(plane_deg)
    m.jnt_axis[:]=[np.sin(angle),np.cos(angle),0]
    return m


def virtual_acceleration(m,q,v,a):
    d=mujoco.MjData(m);out=[]
    for qi,vi,ai in zip(q,v,a):
        d.qpos[:]=qi;d.qvel[:]=vi;d.qacc[:]=ai
        mujoco.mj_fwdPosition(m,d);mujoco.mj_fwdVelocity(m,d)
        mujoco.mj_sensorAcc(m,d)
        out.append(d.sensordata.copy()/G)
    return np.asarray(out)


def trajectory(ex,period,n,variant='nominal'):
    t=np.arange(n)/100
    if variant=='fast':period*=.6
    phase=2*np.pi*t/period
    amplitudes={'EAH':(1.0,.08),'EFE':(.08,.85),'SQZ':(.45,.55)}[ex]
    q=np.zeros((n,2));v=q.copy();a=q.copy()
    for k,amp in enumerate(amplitudes):
        if variant=='shallow':amp*=.5
        q[:,k]=.5 if k else .8
        for magnitude,omega,shift in [(amp,2*np.pi/period,k*.35),(.12*amp,4*np.pi/period,.3),(.03*amp,2*np.pi/(5*period),.7),(.003,2*np.pi*7,k),(.001,2*np.pi*11,.5)]:
            p=omega*t+shift;q[:,k]+=magnitude*np.sin(p);v[:,k]+=magnitude*omega*np.cos(p);a[:,k]-=magnitude*omega**2*np.sin(p)
    if variant=='stall':
        mid=n//2;q[mid:]=q[mid];v[mid:]=0;a[mid:]=0
    return q,v,a


def sensor_chain(x,seed=0):
    # Illustrative 20 Hz single-pole analog response; discrete equivalent at 100 Hz.
    alpha=1-np.exp(-2*np.pi*20/100)
    filt=np.empty_like(x)
    for k in range(6):
        filt[:,k],_=lfilter([alpha],[1,-(1-alpha)],x[:,k],zi=[(1-alpha)*x[0,k]])
    rng=np.random.default_rng(seed)
    noise=np.tile([150e-6,150e-6,300e-6],2)*np.sqrt(1.6*20)
    filt+=rng.normal(size=x.shape)*noise+np.array([.02,-.02,.01,-.01,.02,-.02])
    step=5/(16383*.300)
    return np.clip(np.round(np.clip(filt,-3,3)/step)*step,-3,3)


def simulate(ex,period,variant='nominal',seed=0,offset=0.,n=4000):
    q,v,a=trajectory(ex,period,n,variant)
    m=make_model(offset,20 if variant=='misaligned' else 0)
    # Weak intentionally shares nominal motion: accelerometers cannot observe effort alone.
    return sensor_chain(virtual_acceleration(m,q,v,a),seed)
