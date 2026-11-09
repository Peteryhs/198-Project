"""Fresh-fit and host-C checks for paired exports (not a new accuracy benchmark)."""
import argparse,ctypes,json,subprocess,tempfile
from pathlib import Path
import numpy as np
import paired_pipeline as pp
import realtime_pipeline as rp


def verify(data,model_dir):
    bags,y,subs,exs,*_=data
    X,yr,ye,w=rp.flattened(bags,y,exs,np.ones(len(y),bool))
    qm,em=rp.fit_model(X,yr,w),rp.fit_model(X,ye,w)
    saved=np.load(model_dir/'realtime_model.npz');errors={}
    for prefix,m in [('quality',qm),('exercise',em)]:
        c=m[1].coef_/m[0].scale_;intercept=m[1].intercept_-c@m[0].mean_
        for suffix,values in [('coef',c),('intercept',intercept)]:
            key=prefix+'_'+suffix;errors[key]=float(np.max(np.abs(saved[key]-values.astype(np.float32))))
    assert max(errors.values())==0,errors
    with tempfile.TemporaryDirectory() as td:
        src=Path(td)/'wrapper.c';so=Path(td)/'wrapper.so'
        src.write_text('#include "realtime_model.h"\nint predict(float*x,float*e,float*q){return rt_predict_rep(x,e,q);}\n')
        subprocess.run(['cc','-shared','-fPIC','-O2','-I',str(model_dir),str(src),'-lm','-o',str(so)],check=True)
        lib=ctypes.CDLL(str(so));f=lib.predict;ptr=ctypes.POINTER(ctypes.c_float);f.argtypes=[ptr]*3
        expected_e=em.predict_proba(X);expected_q=qm.predict_proba(X)[:,1];maxerr=0.;cq=[];ce=[]
        for row,pe,pq in zip(X,expected_e,expected_q):
            row=np.ascontiguousarray(row,np.float32);e=np.zeros(3,np.float32);q=np.zeros(1,np.float32)
            assert f(row.ctypes.data_as(ptr),e.ctypes.data_as(ptr),q.ctypes.data_as(ptr))==1
            maxerr=max(maxerr,float(np.max(abs(e-pe))),float(abs(q[0]-pq)));cq.append(q[0]);ce.append(e)
        assert maxerr<3e-5,maxerr
        offset=0;diff=0
        for bag in bags:
            n=len(bag);sl=slice(offset,offset+n)
            diff+=int((np.mean(cq[sl])>=.5)!=(np.mean(expected_q[sl])>=.5))
            diff+=int(np.argmax(np.mean(ce[sl],axis=0))!=np.argmax(np.mean(expected_e[sl],axis=0)))
            offset+=n
        assert diff==0,diff
        row[:]=np.nan
        assert f(row.ctypes.data_as(ptr),e.ctypes.data_as(ptr),q.ctypes.data_as(ptr))==0
    print(json.dumps(dict(model=str(model_dir),coefficient_errors=errors,max_probability_error=maxerr,series_decision_differences=diff),indent=2))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--model',type=Path,default=Path('model/paired-synchronized-offline'));ap.add_argument('--causal',action='store_true');args=ap.parse_args()
    if args.causal:
        from streaming_pipeline import StreamExtractor
        with StreamExtractor() as extractor:
            for side in 'LR':verify(pp.collect(args.root,side,extractor),args.model/side)
    else:
        for side in 'LR':verify(pp.collect(args.root,side),args.model/side)
if __name__=='__main__':main()
