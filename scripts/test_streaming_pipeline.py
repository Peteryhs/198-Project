"""C statistics, prefix causality, invalid-input/reset and bounded idle behavior."""
import ctypes
import numpy as np
from harness import window_features
from streaming_pipeline import StreamExtractor

def main():
    with StreamExtractor() as ex:
        rng=np.random.default_rng(4)
        x=np.clip(rng.normal(size=(250,6)),-3,3).astype(np.float32)
        out=np.empty(61,np.float32)
        ex.lib.stream_features(x.ctypes.data_as(ex.ptr),len(x),out.ctypes.data_as(ex.ptr))
        expected=np.r_[2.5,window_features(x[None,:,:3].astype(float))[0],window_features(x[None,:,3:].astype(float))[0]]
        assert np.allclose(out,expected,atol=2e-5),np.max(abs(out-expected))
        for value in [0., .1, 3.]:
            constant=np.full((600,6),value,np.float32)
            ex.lib.stream_features(constant.ctypes.data_as(ex.ptr),len(constant),out.ctypes.data_as(ex.ptr))
            expected=np.r_[6.,window_features(constant[None,:,:3].astype(float))[0],window_features(constant[None,:,3:].astype(float))[0]]
            assert np.allclose(out,expected,atol=2e-5),('constant-axis statistics',value,out,expected)
        t=np.arange(2400)/100
        x=np.tile((1+.4*np.sin(2*np.pi*t/2))[:,None],(1,6))
        full=ex(x);ends=ex.ends.copy();short=ex(x[:1550]);shortends=ex.ends.copy()
        assert len(full)>4 and np.array_equal(short,full[ends<=1550])
        assert np.array_equal(shortends,ends[ends<=1550])
        assert len(ex(np.ones((2000,6))))==0 and ex.overflows>0
        state=ctypes.create_string_buffer(ex.lib.state_bytes());ex.lib.stream_reset(state)
        v=np.ones(6,np.float32);out=np.empty(61,np.float32)
        assert ex.lib.stream_push(state,0,v.ctypes.data_as(ex.ptr),out.ctypes.data_as(ex.ptr))==0
        assert ex.lib.stream_push(state,40,v.ctypes.data_as(ex.ptr),out.ctypes.data_as(ex.ptr))==-1
        v[0]=np.nan
        assert ex.lib.stream_push(state,50,v.ctypes.data_as(ex.ptr),out.ctypes.data_as(ex.ptr))==-1
        print('C/Python 61-statistic parity, prefix causality, idle overflow, timestamp gap and NaN rejection passed')
        print('sizeof(PairStream) host bytes:',ex.lib.state_bytes())
if __name__=='__main__':main()
