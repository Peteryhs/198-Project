"""Independent timing evidence only; gyroscopes never become model inputs."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.signal import correlate,correlation_lags
from harness import read_inertial

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();result={}
    for side in 'LR':
        rows=[]
        for p in sorted(args.root.glob(f'*/{side}arm/*EAH*.csv')):
            a=read_inertial(str(p));b=read_inertial(str(p.parent.parent/f'{side}forearm'/p.name));n=min(len(a),len(b))
            u=np.linalg.norm(a[:n,1:4],axis=1);v=np.linalg.norm(b[:n,1:4],axis=1);u-=u.mean();v-=v.mean()
            c=correlate(u,v);lags=correlation_lags(n,n);mask=abs(lags)<=200
            rows.append([a[0,0]-b[0,0],(a[-1,0]-a[0,0])-(b[-1,0]-b[0,0]),lags[mask][np.argmax(c[mask])]/100,np.corrcoef(u,v)[0,1]])
        rows=np.array(rows)
        result[side]=dict(eah_pairs=len(rows),median_absolute_uptime_start_offset_s=float(np.median(abs(rows[:,0]))),median_absolute_relative_duration_difference_s=float(np.median(abs(rows[:,1]))),median_absolute_relative_grid_gyro_lag_s=float(np.median(abs(rows[:,2]))),median_relative_grid_gyro_correlation=float(np.median(rows[:,3])))
    print(json.dumps(result,indent=2))
    print('Clock decision: use author-synchronized recording starts and within-file relative timestamps, never raw device uptime. No per-record lag fitting or gyro model features.')
if __name__=='__main__':main()
