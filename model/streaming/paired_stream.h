#ifndef PAIRED_STREAM_H
#define PAIRED_STREAM_H
#include <stdint.h>
#define STREAM_CAP 600
#define STREAM_FEATURES 61
/* Caller calibrates six ADC channels to g and supplies one synchronized sample/10 ms. */
typedef struct {
    float samples[STREAM_CAP][6];
    float smooth, peak, trough;
    uint32_t last_ms, elapsed, events, overflows, invalid;
    unsigned n, fall;
    int started, armed, boundary;
} PairStream;
void stream_reset(PairStream *s);
/* 1: completed causal cycle, 0: no verdict, -1: invalid sample/timing (state reset).
   Output belongs to a peak-confirmation-to-confirmation interval, not labelled rep truth. */
int stream_push(PairStream *s, uint32_t ms, const float x[6], float features[61]);
void stream_features(const float samples[][6], unsigned n, float features[61]);
#endif
