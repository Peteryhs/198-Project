"""Freestanding Cortex-M4F object/state/stack measurements, never a board timing claim."""
from __future__ import annotations
import json,shlex,subprocess,tempfile
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def run(cmd):
    print('$',shlex.join(map(str,cmd)))
    return subprocess.check_output(list(map(str,cmd)),text=True)


def sections(obj):
    detail=run(['llvm-size','-A',obj]);print(detail)
    summary=run(['llvm-size',obj]);print(summary)
    text,data,bss=map(int,summary.strip().splitlines()[-1].split()[:3])
    return dict(text_rodata_exidx_bytes=text,data_bytes=data,bss_bytes=bss,allocated_object_bytes=text+data+bss,object_file_bytes=obj.stat().st_size,sections=detail)


def main():
    models=sorted((ROOT/'model').glob('paired-synchronized-*/*/realtime_model.h'))+sorted((ROOT/'model/placement-controls').glob('*/realtime_model.h'))
    result=[]
    with tempfile.TemporaryDirectory(prefix='tally-arm-') as td:
        temp=Path(td);(temp/'math.h').write_text('float sqrtf(float);float fminf(float,float);float fmaxf(float,float);float expf(float);\n#define isfinite(x) __builtin_isfinite(x)\n#define INFINITY __builtin_inff()\n')
        flags=['clang','--target=arm-none-eabi','-mcpu=cortex-m4','-mthumb','-mfpu=fpv4-sp-d16','-mfloat-abi=hard','-Oz','-ffreestanding','-fno-builtin','-fdata-sections','-ffunction-sections','-fstack-usage','-I',str(temp),'-I',str(ROOT/'model/streaming')]
        shared=temp/'features.o'
        print(run(flags+['-c',str(ROOT/'model/streaming/paired_stream.c'),'-o',str(shared)]))
        feature_sizes=sections(shared)
        stacks={}
        probe=temp/'probe.c';probe.write_text('#include "paired_runtime.h"\nPairRuntime live;\nfloat result[4];\nint ingest(unsigned ms,const float x[6]){return pair_push(&live,ms,x,result,&result[3]);}\nint finish(void){return pair_series(&live,result,&result[3]);}\n')
        probe_obj=temp/'probe.o';print(run(flags+['-c',str(probe),'-o',str(probe_obj)]))
        symbols=run(['llvm-nm','-S',probe_obj]);print(symbols)
        state_bytes=int(next(l.split()[1] for l in symbols.splitlines() if l.split()[-1]=='live'),16)
        output_bytes=int(next(l.split()[1] for l in symbols.splitlines() if l.split()[-1]=='result'),16)
        for i,header in enumerate(models):
            directory=header.parent;prefix=f'model{i}';model=np.load(directory/'realtime_model.npz')
            wrapper=temp/(prefix+'.c');wrapper.write_text('#include "realtime_model.h"\nint predict(float*x,float*e,float*q){return rt_predict_rep(x,e,q);}\n')
            classifier=temp/(prefix+'.o');print(run(flags+['-I',str(directory),'-c',str(wrapper),'-o',str(classifier)]))
            row=dict(model=str(directory.relative_to(ROOT)),parameter_bytes=sum(model[k].nbytes for k in model.files if k!='exercise_classes'),classifier=sections(classifier))
            if 'offline' not in str(directory):
                runtime=temp/(prefix+'-runtime.o')
                extra=['-DPAIR_FOREARM_ONLY'] if directory.name.endswith('forearm') else []
                print(run(flags+['-I',str(directory),*extra,'-c',str(ROOT/'model/streaming/paired_runtime.c'),'-o',str(runtime)]))
                whole=temp/(prefix+'-pipeline.o')
                unity=temp/(prefix+'-unity.c')
                unity.write_text('#include \"'+str(ROOT/'model/streaming/paired_stream.c')+'\"\n#include \"'+str(ROOT/'model/streaming/paired_runtime.c')+'\"\n#include \"'+str(probe)+'\"\n')
                print(run(flags+['-I',str(directory),*extra,'-c',str(unity),'-o',str(whole)]))
                row['full_causal_pipeline']=sections(whole)
                row['unresolved']=run(['llvm-nm','-u',whole]);print(row['unresolved'])
            else:row['deployment']='offline comparison only; noncausal detector not ported; use separately trained causal counterpart'
            result.append(row)
        for path in sorted(temp.glob('*.su')):stacks[path.name]=path.read_text();print(path.name,stacks[path.name])
    static=state_bytes+output_bytes
    report=dict(target='arm-none-eabi cortex-m4 fpv4-sp-d16 hard-float -Oz',models=result,feature_detector_object=feature_sizes,target_runtime_state_bytes=state_bytes,target_output_bytes=output_bytes,stack_usage_files=stacks,
                allocation_estimates=dict(static_bytes=static,stack_reserve=4096,core_reserve=4096,oled_reserve=1024,interrupt_reserve=1024,total=static+4096+4096+1024+1024,headroom_of_32768=32768-static-4096-4096-1024-1024),
                feature_arithmetic=dict(max_samples=600,axes=6,buffer_bytes=600*6*4,axis_sample_visits_per_cycle=2*600*6,approx_multiplications_before_scalar_normalization=4*600*6,approx_add_sub_before_scalar_normalization=6*600*6,square_roots_per_cycle_features=12,classifier_mac_per_pair_cycle=4*61,classifier_expf_per_cycle=4),
                latency=dict(confirmation_component_s=20/100,ema_time_constant_s=float(-.01/np.log(.8)),true_repetition_end_to_display='not measured; unknown anatomical boundary, hysteresis wait, refractoriness, MCU feature/libm/ADC/display timing',mid_repetition='not validated'),
                two_pair_float_state_plus_core_estimate=2*state_bytes+4096,
                scope='unlinked target objects; includes actual feature/detector code and causal runtime; excludes resolved libm/compiler helpers, Arduino core/linker, acquisition/display; .su compiler frame estimates exclude unknown library/interrupt stack; all reserves estimates')
    Path('docs/runs/round2/target-size.json').write_text(json.dumps(report,indent=2)+'\n')
    print('| model | parameters B | classifier text/rodata/exidx B | complete causal text/rodata/exidx B | complete causal BSS B |')
    for r in result:
        f=r.get('full_causal_pipeline',{})
        print(f"| {r['model']} | {r['parameter_bytes']} | {r['classifier']['text_rodata_exidx_bytes']} | {f.get('text_rodata_exidx_bytes','offline control')} | {f.get('bss_bytes','offline control')} |")
    print('STATE / ESTIMATES / COST / LATENCY:',json.dumps({k:v for k,v in report.items() if k not in {'models','feature_detector_object','stack_usage_files'}},indent=2))
if __name__=='__main__':main()
