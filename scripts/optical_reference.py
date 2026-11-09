"""Deterministic CRC-checked optical subset; unaligned virtual-sensor reference, not accuracy."""
from __future__ import annotations
import argparse,csv,json,re,zipfile,zlib
from pathlib import Path
import numpy as np
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation
from fetch_upper_range import RangeReader,URL
from harness import read_inertial
from paired_pipeline import aligned_pair
from streaming_pipeline import StreamExtractor
from simulation_experiment import statistics


def select(names):
    pattern=re.compile(r'^optical interp/rigid_bodies/upper/([A-E])/([A-E]\d{2})(EAH|EFE|SQZ)([01])_1_interp\.csv$')
    selected=[]
    for group in 'ABCDE':
        for ex in ['EAH','EFE','SQZ']:
            for label in [0,1]:
                candidates=[name for name in names if (m:=pattern.match(name)) and m[1]==group and m[3]==ex and int(m[4])==label]
                if candidates:selected.append(sorted(candidates)[0])
    return selected


def optical_pair(path,side):
    with path.open() as f:
        rows=list(csv.reader(next(f) for _ in range(7)))
    blocks=[];cols=[1]
    for body in (('thigh2','shin2') if side=='L' else ('thigh','shin')):
        block=[i for i,(kind,name) in enumerate(zip(rows[2],rows[3])) if kind=='Rigid Body' and name==body]
        if len(block)!=7:raise ValueError(f'{body} lacks quaternion+position block')
        blocks.append(block);cols.extend(block)
    data=np.genfromtxt(path,delimiter=',',skip_header=7,usecols=cols)
    valid=np.isfinite(data).all(axis=1)
    for start in [1,8]:valid&=np.linalg.norm(data[:,start:start+4],axis=1)>.5
    runs=np.split(np.arange(len(data)),np.flatnonzero(valid[1:]!=valid[:-1])+1)
    good=[r for r in runs if valid[r[0]]]
    if not good:raise ValueError('no finite optical span')
    span=max(good,key=len)
    if len(span)<1200:raise ValueError('no >=12 second continuous optical span')
    data=data[span];dt=np.diff(data[:,0])
    if not np.allclose(dt,.01,atol=1e-5):raise ValueError('optical rate is not 100 Hz')
    result=[]
    for start in [1,8]:
        quat=data[:,start:start+4];pos=data[:,start+4:start+7]
        acceleration=savgol_filter(pos,11,3,deriv=2,delta=.01,axis=0)
        # Descriptor Fig. 1 defines optical Y-up; board-to-chip position remains unmeasured.
        specific=acceleration-np.array([0,-9.80665,0])
        result.append(Rotation.from_quat(quat).inv().apply(specific)/9.80665)
    return np.column_stack(result)[50:-50],dict(total_frames=len(valid),continuous_frames=len(span),finite_fraction=float(valid.mean()))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('data/phytmo'));args=ap.parse_args()
    r=RangeReader(URL);manifest=[]
    with zipfile.ZipFile(r) as z:
        for name in select(z.namelist()):
            info=z.getinfo(name);p=args.root/name
            if not p.exists() or zlib.crc32(p.read_bytes())!=info.CRC:
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(info))
            manifest.append(dict(member=name,bytes=info.file_size,crc32=f'{info.CRC:08x}'))
            print('CRC-checked',name,flush=True)
    comparisons=[];rejected=[]
    with StreamExtractor() as extractor:
        for row in manifest:
            p=args.root/row['member'];base=p.name.replace('_interp','');group=base[0]
            for side in 'LR':
                try:
                    optical,scope=optical_pair(p,side)
                    inertial=aligned_pair(read_inertial(str(args.root/'inertial/upper'/group/f'{side}arm'/base)),read_inertial(str(args.root/'inertial/upper'/group/f'{side}forearm'/base)))
                    real,_=statistics(np.clip(inertial,-3,3),extractor)
                    sim,_=statistics(np.clip(optical,-3,3),extractor)
                    comparisons.append(dict(source='optical-derived simulation vs real recordings; clocks/extrinsics unverified',member=row['member'],side=side,scope=scope,real=real,optical_virtual=sim))
                except (ValueError,OSError) as e:rejected.append(dict(member=row['member'],side=side,reason=str(e)))
    report=dict(selected_files=len(manifest),comparisons=len(comparisons),rejected=rejected,http_bytes=r.downloaded,manifest=manifest,rows=comparisons,
                interpretation='not synchronized; Y-up and origin at board rather than chip; derivative filtering attenuates high frequency; reference diagnostics only, no model accuracy or angle validation')
    Path('docs/runs/round2/optical-reference.json').write_text(json.dumps(report,indent=2)+'\n')
    print('selected optical files',len(manifest),'usable side comparisons',len(comparisons),'rejected',len(rejected),'HTTP bytes',r.downloaded)
    print('| Unaligned optical-derived simulation / real median ratio | upper | forearm |')
    for key in ['envelope_g','dominant_hz','peak_p50_g','peak_p90_g','duration_p50_s','duration_p90_s','hf_fraction']:
        ratios=[np.median([v['optical_virtual'][seg][key]/max(v['real'][seg][key],1e-9) for v in comparisons]) for seg in range(2)]
        print(f'| {key} | {ratios[0]:.4f} | {ratios[1]:.4f} |')
if __name__=='__main__':main()
