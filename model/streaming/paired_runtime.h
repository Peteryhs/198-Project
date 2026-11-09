#ifndef PAIRED_RUNTIME_H
#define PAIRED_RUNTIME_H
#include "paired_stream.h"
typedef struct {
    PairStream stream;
    float quality_sum, exercise_sum[3];
    uint32_t count;
} PairRuntime;
void pair_reset(PairRuntime *s);
/* Output is provisional per cycle. Only series-level pooling has held-subject validation. */
int pair_push(PairRuntime *s,uint32_t ms,const float x[6],float exercise[3],float *quality);
/* Caller marks the series end. Returns 0 (abstain) without completed cycles. */
int pair_series(const PairRuntime *s,float exercise[3],float *quality);
#endif
