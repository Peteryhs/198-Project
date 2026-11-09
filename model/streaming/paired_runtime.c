#include "paired_runtime.h"
#ifndef PAIRED_MODEL_HEADER
#define PAIRED_MODEL_HEADER "realtime_model.h"
#endif
#include PAIRED_MODEL_HEADER
void pair_reset(PairRuntime *s) { *s=(PairRuntime){0}; }
int pair_push(PairRuntime *s,uint32_t ms,const float x[6],float ex[3],float *q) {
    float features[61];
    int status=stream_push(&s->stream,ms,x,features);
    if(status<0) {pair_reset(s);return -1;}
    if(!status)return 0;
#ifdef PAIR_FOREARM_ONLY
    for(unsigned k=1;k<=30;k++)features[k]=features[k+30];
#endif
    if(!rt_predict_rep(features,ex,q)) {pair_reset(s);return -1;}
    s->quality_sum+=*q;
    for(unsigned k=0;k<3;k++)s->exercise_sum[k]+=ex[k];
    s->count++;
    return 1;
}
int pair_series(const PairRuntime *s,float ex[3],float *q) {
    if(!s->count)return 0;
    *q=s->quality_sum/s->count;
    for(unsigned k=0;k<3;k++)ex[k]=s->exercise_sum[k]/s->count;
    return 1;
}
