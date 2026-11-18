#include "paired_stream.h"
#include <math.h>
void stream_reset(PairStream *s) { *s=(PairStream){0}; }
void stream_features(const float samples[][6], unsigned n, float out[61]) {
    out[0]=n*.01f;
    for(unsigned k=0;k<6;k++) {
        float sum=0, sq=0, mn=3, mx=-3;
        for(unsigned i=0;i<n;i++) {
            float v=samples[i][k]; sum+=v; sq+=v*v;
            if(v<mn)mn=v;
            if(v>mx)mx=v;
        }
        /* Constant axes need an exact mean to avoid roundoff becoming unit skew. */
        float mean=mn==mx?mn:sum/n, m2=0,m3=0,m4=0;
        unsigned zcr=0; int prev=0;
        for(unsigned i=0;i<n;i++) {
            float d=samples[i][k]-mean, d2=d*d;
            m2+=d2; m3+=d2*d; m4+=d2*d2;
            int sign=(d>0)-(d<0);
            if(i && sign!=prev)zcr++;
            prev=sign;
        }
        float var=m2/n, sd=sqrtf(var), norm=sd>0?sd:1;
        unsigned base=1+(k/3)*30+k%3;
        out[base]=mean; out[base+3]=sd; out[base+6]=mn; out[base+9]=mx;
        out[base+12]=mx-mn; out[base+15]=sqrtf(sq/n);
        out[base+18]=(m3/n)/(norm*norm*norm);
        out[base+21]=(m4/n)/(norm*norm*norm*norm)-3;
        out[base+24]=sq/n; out[base+27]=(float)zcr/n;
    }
}
int stream_push(PairStream *s,uint32_t ms,const float input[6],float out[61]) {
    float x[6];
    for(unsigned k=0;k<6;k++) {
        if(!isfinite(input[k])) {stream_reset(s);s->invalid=1;return -1;}
        x[k]=fminf(3,fmaxf(-3,input[k]));
    }
    if(s->started && (ms-s->last_ms<8 || ms-s->last_ms>12)) {
        stream_reset(s);s->invalid=1;return -1;
    }
    float mag=sqrtf(x[3]*x[3]+x[4]*x[4]+x[5]*x[5]);
    if(!s->started) {s->smooth=mag;s->peak=mag;s->trough=mag;s->started=1;}
    s->last_ms=ms;
    s->smooth+=.2f*(mag-s->smooth);
    s->elapsed++;
    if(s->n==STREAM_CAP) {s->overflows++;s->n=0;s->boundary=0;}
    for(unsigned k=0;k<6;k++)s->samples[s->n][k]=x[k];
    s->n++;
    if(!s->armed) {
        if(s->smooth<s->trough)s->trough=s->smooth;
        if(s->smooth-s->trough>=.04f) {s->armed=1;s->peak=s->smooth;}
    }
    if(s->smooth>s->peak) {s->peak=s->smooth;s->fall=0;}
    else if(s->armed && s->peak-s->smooth>=.04f)s->fall++;
    else s->fall=0;
    if(s->armed && s->fall>=20 && s->elapsed>=120) {
        int ready=s->boundary && s->n>=120;
        if(ready)stream_features(s->samples,s->n,out);
        s->events++;s->boundary=1;s->n=0;s->elapsed=0;s->fall=0;s->armed=0;
        s->peak=s->trough=s->smooth;
        return ready;
    }
    return 0;
}
