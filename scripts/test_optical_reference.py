"""Optical header selection and derivative physics against a known synthetic translation."""
import csv,tempfile
from pathlib import Path
import numpy as np
from optical_reference import optical_pair,select

def main():
    names=['optical interp/rigid_bodies/upper/A/A01EFE0_1_interp.csv','../evil.csv','optical raw/rigid_bodies/upper/A/A01EFE0_1.csv']
    assert select(names)==names[:1]
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'optical.csv'
        headers=[['metadata'],[],['','Type']+['Rigid Body']*14,['','Name']+['thigh2']*7+['shin2']*7,['','ID']+['x']*14,['','']+['Rotation']*4+['Position']*3+['Rotation']*4+['Position']*3,['Frame','Time']+['X','Y','Z','W','X','Y','Z']*2]
        with p.open('w') as f:
            w=csv.writer(f);w.writerows(headers)
            for i in range(2000):
                t=i/100;body=[0,0,0,1,.1*t*t,1,0];w.writerow([i,t]+body+body)
        x,scope=optical_pair(p,'L')
        assert len(x)==1900 and scope['finite_fraction']==1
        assert np.allclose(x,np.tile([.2/9.80665,1,0],2),atol=1e-7)
    print('optical deterministic selection, XYZW/position parsing, 100 Hz, derivative and gravity checks passed')
if __name__=='__main__':main()
