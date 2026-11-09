"""Actual six-channel C runtime -> pooled probabilities against replay + Python model."""
import ctypes,subprocess,tempfile
from pathlib import Path
import numpy as np
from scipy.special import expit,softmax
from streaming_pipeline import ROOT,StreamExtractor

def main():
    t=np.arange(2400)/100
    x=np.tile((1+.4*np.sin(2*np.pi*t/2))[:,None],(1,6)).astype(np.float32)
    with StreamExtractor() as ex,tempfile.TemporaryDirectory() as td:
        f=ex(x)
        candidates=[(ROOT/'model/paired-synchronized-causal'/side,False) for side in 'LR']
        candidates += [(p,p.name.endswith('forearm')) for p in sorted((ROOT/'model/placement-controls').iterdir())]
        for model,forearm in candidates:
            side=model.name;z=np.load(model/'realtime_model.npz')
            selected=f if z['quality_coef'].shape[1]==61 else np.c_[f[:,0],f[:,31:]] if forearm else f[:,:31]
            expected_q=expit(selected@z['quality_coef'][0]+z['quality_intercept'][0]).mean()
            expected_e=softmax(selected@z['exercise_coef'].T+z['exercise_intercept'],axis=1).mean(axis=0)
            wrapper=Path(td)/'runtime.c';so=Path(td)/f'runtime-{side}.so'
            wrapper.write_text('#include "paired_runtime.h"\n'
                'unsigned bytes(void){return sizeof(PairRuntime);}\n'
                'int run(float*x,unsigned n,float*e,float*q){PairRuntime s={0};float pe[3],pq;\n'
                'if(pair_series(&s,e,q))return -2;\n'
                'for(unsigned i=0;i<n;i++){if(pair_push(&s,i*10,x+i*6,pe,&pq)<0)return -1;}\n'
                'if(!pair_series(&s,e,q))return 0;return s.count;}\n')
            subprocess.run(['cc','-shared','-fPIC','-O2','-I',str(ROOT/'model/streaming'),'-I',str(model),str(wrapper),str(ROOT/'model/streaming/paired_stream.c'),str(ROOT/'model/streaming/paired_runtime.c'),*(['-DPAIR_FOREARM_ONLY'] if forearm else []),'-lm','-o',str(so)],check=True)
            lib=ctypes.CDLL(str(so));lib.run.argtypes=[ex.ptr,ctypes.c_uint,ex.ptr,ex.ptr]
            e=np.empty(3,np.float32);q=np.empty(1,np.float32)
            count=lib.run(x.ctypes.data_as(ex.ptr),len(x),e.ctypes.data_as(ex.ptr),q.ctypes.data_as(ex.ptr))
            assert count==len(f) and np.allclose(e,expected_e,atol=3e-5) and np.allclose(q[0],expected_q,atol=3e-5)
            print(side,'integrated runtime parity passed; cycles',count,'sizeof(PairRuntime)',lib.bytes())
if __name__=='__main__':main()
