"""Train the same pair heads from the actual C causal detector/feature extractor."""
from __future__ import annotations
import argparse,ctypes,subprocess,tempfile
from pathlib import Path
import numpy as np
import paired_pipeline as pp

ROOT=Path(__file__).resolve().parents[1]

class StreamExtractor:
    def __init__(self):
        self.temp=tempfile.TemporaryDirectory()
        wrapper=Path(self.temp.name)/'wrapper.c'
        wrapper.write_text('#include "paired_stream.h"\n#include <stddef.h>\n'
            'unsigned state_bytes(void){return sizeof(PairStream);}\n'
            'int replay(const float *x,unsigned n,float *out,unsigned *ends,unsigned *overflows){\n'
            'PairStream s={0};unsigned count=0;float f[61];\n'
            'for(unsigned i=0;i<n;i++){if(stream_push(&s,i*10,x+i*6,f)==1){\n'
            'for(unsigned k=0;k<61;k++){out[count*61+k]=f[k];}ends[count++]=i+1;}}\n'
            '*overflows=s.overflows;return count;}\n')
        so=Path(self.temp.name)/'stream.so'
        subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-I',str(ROOT/'model/streaming'),str(wrapper),str(ROOT/'model/streaming/paired_stream.c'),'-lm','-o',str(so)],check=True)
        self.lib=ctypes.CDLL(str(so));self.ptr=ctypes.POINTER(ctypes.c_float);self.uptr=ctypes.POINTER(ctypes.c_uint)
        self.lib.replay.argtypes=[self.ptr,ctypes.c_uint,self.ptr,self.uptr,self.uptr]
        self.lib.stream_push.argtypes=[ctypes.c_void_p,ctypes.c_uint,self.ptr,self.ptr]
        self.lib.stream_reset.argtypes=[ctypes.c_void_p]
        self.lib.stream_features.argtypes=[self.ptr,ctypes.c_uint,self.ptr]
        self.overflows=0
    def __call__(self,x):
        x=np.ascontiguousarray(x,np.float32);f=np.empty((len(x)//120+2,61),np.float32);ends=np.empty(len(f),np.uint32);overflow=ctypes.c_uint()
        n=self.lib.replay(x.ctypes.data_as(self.ptr),len(x),f.ctypes.data_as(self.ptr),ends.ctypes.data_as(self.uptr),ctypes.byref(overflow))
        self.ends=ends[:n];self.overflows+=overflow.value
        return f[:n].copy()
    def __enter__(self):return self
    def __exit__(self,*args):self.temp.cleanup()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--out',type=Path,default=Path('model/paired-synchronized-causal'));args=ap.parse_args()
    with StreamExtractor() as ex:
        for side in 'LR':
            pp.evaluate(pp.collect(args.root,side,ex),args.out/side,f'real recordings; {side} pair; ±3 g; actual C causal detector + features')
        print('C buffer overflows (cycles discarded):',ex.overflows)
if __name__=='__main__':main()
