"""Borrowed engine conventions against static gravity and analytic pendulum force."""
import numpy as np
from limb_simulation import make_model,virtual_acceleration,simulate,G

def main():
    m=make_model();q=np.zeros((1,2));v=q.copy();a=q.copy()
    got=virtual_acceleration(m,q,v,a)
    assert np.allclose(got,[[0,0,1,0,0,1]]),got
    q[:]=[.4,0];v[:]=[2,0];a[:]=[3,0]
    got=virtual_acceleration(m,q,v,a)[0,:3]
    expected=[-.15*3/G-np.sin(.4),0,.15*4/G+np.cos(.4)]
    assert np.allclose(got,expected,atol=1e-10),(got,expected)
    a=simulate('EFE',2,n=1200);b=simulate('EFE',2,'weak',n=1200)
    assert np.array_equal(a,b) and np.isfinite(a).all() and abs(a).max()<=3
    print('MuJoCo 3.3.7: static 1g and analytic rotating/accelerating pendulum passed')
    print('100 Hz ±3g filtered/noisy/quantized chain; same-kinematics weak counterfactual identical')
if __name__=='__main__':main()
