#ifndef FORM_STREAM_H
#define FORM_STREAM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FORM_STREAM_AXES 3
#define FORM_STREAM_FEATURES 31
#define FORM_STREAM_BASELINE_SAMPLES 201
#define FORM_STREAM_MIN_SAMPLES 120
#define FORM_STREAM_MAX_SAMPLES 500
#define FORM_STREAM_DEADBAND_SAMPLES 20

/* Caller-owned state; allocate statically on small boards. No allocation or
 * mutable global state. All samples are accelerometer g at exactly 100 Hz.
 *
 * Worst-case sample storage: 500 * 3 * sizeof(float) plus 201 * sizeof(float)
 * for the trailing baseline, and 31 * sizeof(float) for one pending result.
 * With 4-byte floats these arrays reserve 6928 bytes, plus scalar state and
 * ABI padding (measure sizeof(form_stream) on the target). A segment closes
 * at 500 samples; storage never grows. Caller output adds 31 floats; function
 * stack and the model's flash/stack are additional to this state budget.
 * The gate is max(0.005 g, 0.35 * peak_ema); confirmed local maxima of the
 * absolute detrended magnitude update peak_ema with weight 0.1. Init clears
 * calibration as well as samples. There is no file/global-percentile input.
 *
 * Fields are exposed for allocation and diagnostics; only peak_ema and
 * peak_initialized may be copied after init to retain a user's calibration
 * across separate recordings. Do not modify other fields while streaming.
 */
typedef struct form_stream {
    float segment[FORM_STREAM_MAX_SAMPLES][FORM_STREAM_AXES];
    float baseline[FORM_STREAM_BASELINE_SAMPLES];
    float pending_x[FORM_STREAM_FEATURES];
    float baseline_sum;
    float peak_ema;
    float previous_abs;
    float before_previous_abs;
    uint32_t sample_index;
    uint32_t segment_start;
    uint32_t pending_start;
    uint32_t pending_end;
    uint16_t baseline_head;
    uint16_t baseline_count;
    uint16_t segment_length;
    uint16_t below_count;
    uint16_t max_segment_length;
    uint8_t peak_initialized;
    uint8_t active;
    uint8_t pending;
    uint8_t pending_forced;
    uint8_t error;
} form_stream;

void form_stream_init(form_stream *s);

/* Trailing mean includes the current sample and uses available samples during
 * startup. No artificial padding/flush is applied at end of recording.
 * Poll after every push. One completed vector may wait for poll; a second
 * completion before consumption latches an error instead of overwriting it.
 * Non-finite input, arithmetic overflow or sample counter exhaustion likewise
 * latch an error: poll returns -1 until init. Invalid samples are not accepted.
 */
void form_stream_push(form_stream *s, float ax, float ay, float az);

/* Returns 1 once per completed repetition, 0 if none, -1 on error (including
 * null arguments). The vector is duration_s, then statistic-major x/y/z for
 * mean, population std, min, max, range, rms, skew, excess kurtosis, energy,
 * and zcr about the mean (including transitions to/from exactly zero).
 * On success *p_wrong = form_rep_predict(out_x); verdict is >= 0.5.
 * pending_start/end remain available after poll, in [start,end) sample units;
 * pending_forced distinguishes the sample cap from deadband closure. The 20
 * below-threshold samples belong to the segment; segments <120 are discarded.
 * End-of-recording active segments are deliberately left incomplete.
 */
int form_stream_poll(form_stream *s, float out_x[FORM_STREAM_FEATURES],
                     float *p_wrong);

#ifdef __cplusplus
}
#endif
#endif
