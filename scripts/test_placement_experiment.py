import numpy as np
from placement_experiment import rotate_mounts,common_data

def main():
    x=np.random.default_rng(0).normal(size=(100,6))
    a=rotate_mounts(x,'A01','L',30);b=rotate_mounts(x,'A01','L',30)
    assert np.array_equal(a,b) and np.allclose(rotate_mounts(x,'A01','L',0),x)
    assert np.allclose(np.linalg.norm(a.reshape(-1,2,3),axis=2),np.linalg.norm(x.reshape(-1,2,3),axis=2))
    left=([np.ones((3,61))]*2,np.array([0,1]),np.array(['A01','A02']),np.array(['EAH','EFE']),['L/a.csv','L/b.csv'],[])
    right=([np.ones((3,61))],np.array([1]),np.array(['A02']),np.array(['EFE']),['R/b.csv'],[])
    d=common_data(left,right);assert d['L'][4]==['L/b.csv'] and len(d['R'][0])==1
    print('deterministic independent mount rotations preserve norms before clipping; common-cohort association passed')
if __name__=='__main__':main()
