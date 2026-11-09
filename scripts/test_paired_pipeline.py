"""Pair association, timestamp interpolation and common feature contract."""
import numpy as np
from paired_pipeline import aligned_pair, offline_features

def main():
    t=np.arange(1000)/100
    a=np.zeros((1000,10));a[:,0]=t;a[:,4:7]=np.c_[np.sin(t*4),np.cos(t*4),1+np.sin(t*4)]
    b=a.copy();b[:,4:7]*=2
    shifted=b.copy();shifted[:,0]+=17
    assert np.allclose(aligned_pair(a,shifted),aligned_pair(a,b))
    x=aligned_pair(a,b)
    assert np.allclose(x[:,3:],2*x[:,:3])
    f=offline_features(x)
    assert len(f)>2 and f.shape[1]==61
    assert np.allclose(f[:,1:4]*2,f[:,31:34])
    dup=np.insert(a,5,a[5],axis=0)
    assert np.allclose(aligned_pair(dup,b),aligned_pair(a,b))
    bad=a.copy();bad[100:,0]+=.2
    try:aligned_pair(bad,b)
    except ValueError:pass
    else:raise AssertionError('gap was accepted')
    print('pair alignment, duplicate averaging, shared boundaries, feature order and gap rejection passed')
if __name__=='__main__':main()
