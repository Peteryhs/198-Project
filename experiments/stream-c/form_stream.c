#include "form_stream.h"
#include "form_rep.h"

#include <math.h>
#include <string.h>

/* EMA of abs(detrended) local peaks; gate at 35% of that peak, floored at 0.005 g. */
#define FORM_STREAM_PEAK_ALPHA 0.1f
#define FORM_STREAM_THRESHOLD_FRACTION 0.35f
#define FORM_STREAM_THRESHOLD_FLOOR 0.005f

static int stream_finite(float x)
{
    return x == x && fabsf(x) <= 3.402823466e38f;
}

static void close_segment(form_stream *s, uint32_t end, int forced)
{
    unsigned n = s->segment_length;
    unsigned axis, i;

    s->segment_length = 0;
    s->below_count = 0;
    s->active = 0;
    if (n > s->max_segment_length) s->max_segment_length = (uint16_t)n;
    if (n < FORM_STREAM_MIN_SAMPLES) return;
    if (s->pending) {
        s->error = 1;
        return;
    }
    s->pending_start = s->segment_start;
    s->pending_end = end;
    s->pending_forced = (uint8_t)(forced != 0);

    s->pending_x[0] = (float)n * 0.01f;
    for (axis = 0; axis < FORM_STREAM_AXES; ++axis) {
        const float reference = s->segment[0][axis];
        float delta_sum = 0.0f, mean, m2 = 0.0f, m3 = 0.0f, m4 = 0.0f;
        float mn = reference, mx = reference, square_sum = 0.0f;
        unsigned crossings = 0;
        float previous_sign = 0.0f;

        for (i = 0; i < n; ++i) {
            float v = s->segment[i][axis];
            delta_sum += v - reference;
            if (v < mn) mn = v;
            if (v > mx) mx = v;
            square_sum += v * v;
            if (!stream_finite(delta_sum) || !stream_finite(square_sum)) {
                s->error = 1;
                return;
            }
        }
        mean = reference + delta_sum / (float)n;
        /* Central powers match training while avoiding raw-moment cancellation. */
        for (i = 0; i < n; ++i) {
            float d = s->segment[i][axis] - mean;
            float d2 = d * d;
            m2 += d2;
            m3 += d2 * d;
            m4 += d2 * d2;
            if (!stream_finite(m2) || !stream_finite(m3) || !stream_finite(m4)) {
                s->error = 1;
                return;
            }
            d = d < 0.0f ? -1.0f : (d > 0.0f ? 1.0f : 0.0f);
            if (i && d != previous_sign) ++crossings;
            previous_sign = d;
        }
        {
            float variance = m2 / (float)n;
            float sd = (float)sqrt(variance);
            float skew = 0.0f, kurt = -3.0f;
            float rms = (float)sqrt(square_sum / (float)n);
            if (sd > 0.0f) {
                float sd2 = sd * sd;
                skew = (m3 / (float)n) / (sd2 * sd);
                kurt = (m4 / (float)n) / (sd2 * sd2) - 3.0f;
            }
            s->pending_x[1u + 0u * 3u + axis] = mean;
            s->pending_x[1u + 1u * 3u + axis] = sd;
            s->pending_x[1u + 2u * 3u + axis] = mn;
            s->pending_x[1u + 3u * 3u + axis] = mx;
            s->pending_x[1u + 4u * 3u + axis] = mx - mn;
            s->pending_x[1u + 5u * 3u + axis] = rms;
            s->pending_x[1u + 6u * 3u + axis] = skew;
            s->pending_x[1u + 7u * 3u + axis] = kurt;
            s->pending_x[1u + 8u * 3u + axis] = square_sum / (float)n;
            s->pending_x[1u + 9u * 3u + axis] = (float)crossings / (float)n;
            if (!stream_finite(mean) || !stream_finite(sd) || !stream_finite(rms) ||
                !stream_finite(skew) || !stream_finite(kurt) ||
                !stream_finite(s->pending_x[1u + 4u * 3u + axis]) ||
                !stream_finite(s->pending_x[1u + 8u * 3u + axis])) {
                s->error = 1;
                return;
            }
        }
    }
    s->pending = 1;
}

void form_stream_init(form_stream *s)
{
    if (s) memset(s, 0, sizeof(*s));
}

void form_stream_push(form_stream *s, float ax, float ay, float az)
{
    float mag, baseline, detrended, abs_value, threshold;
    float values[FORM_STREAM_AXES];
    uint32_t index;
    unsigned i;

    if (!s || s->error) return;
    if (!stream_finite(ax) || !stream_finite(ay) || !stream_finite(az) ||
        s->sample_index == UINT32_MAX) {
        s->error = 1;
        return;
    }
    values[0] = ax; values[1] = ay; values[2] = az;
    mag = (float)sqrt(ax * ax + ay * ay + az * az);
    if (!stream_finite(mag)) { s->error = 1; return; }

    if (s->baseline_count < FORM_STREAM_BASELINE_SAMPLES) {
        unsigned slot = (s->baseline_head + s->baseline_count) % FORM_STREAM_BASELINE_SAMPLES;
        s->baseline[slot] = mag;
        s->baseline_sum += mag;
        ++s->baseline_count;
    } else {
        s->baseline_sum -= s->baseline[s->baseline_head];
        s->baseline[s->baseline_head] = mag;
        s->baseline_sum += mag;
        s->baseline_head = (uint16_t)((s->baseline_head + 1u) % FORM_STREAM_BASELINE_SAMPLES);
    }
    if (!stream_finite(s->baseline_sum)) { s->error = 1; return; }
    baseline = s->baseline_sum / (float)s->baseline_count;
    detrended = mag - baseline;
    abs_value = fabsf(detrended);
    if (!stream_finite(abs_value)) { s->error = 1; return; }

    threshold = s->peak_initialized ?
        s->peak_ema * FORM_STREAM_THRESHOLD_FRACTION : FORM_STREAM_THRESHOLD_FLOOR;
    if (threshold < FORM_STREAM_THRESHOLD_FLOOR) threshold = FORM_STREAM_THRESHOLD_FLOOR;
    index = s->sample_index;
    if (!s->active && abs_value > threshold && abs_value > s->previous_abs) {
        s->active = 1;
        s->segment_start = index;
        s->segment_length = 0;
        s->below_count = 0;
    }
    if (s->active) {
        if (s->segment_length >= FORM_STREAM_MAX_SAMPLES) { s->error = 1; return; }
        for (i = 0; i < FORM_STREAM_AXES; ++i)
            s->segment[s->segment_length][i] = values[i];
        ++s->segment_length;
        if (s->segment_length > s->max_segment_length)
            s->max_segment_length = s->segment_length;
        if (abs_value < threshold) {
            if (s->below_count < UINT16_MAX) ++s->below_count;
        } else {
            s->below_count = 0;
        }
    }

    /* A peak is confirmed one sample after it occurs; this keeps only scalar history. */
    if (s->sample_index >= 2u && s->previous_abs > s->before_previous_abs &&
        s->previous_abs >= abs_value) {
        if (!s->peak_initialized) {
            s->peak_ema = s->previous_abs;
            s->peak_initialized = 1;
        } else {
            s->peak_ema += FORM_STREAM_PEAK_ALPHA * (s->previous_abs - s->peak_ema);
        }
        if (!stream_finite(s->peak_ema)) { s->error = 1; return; }
    }
    s->before_previous_abs = s->previous_abs;
    s->previous_abs = abs_value;

    ++s->sample_index;
    if (s->active && s->segment_length >= FORM_STREAM_MAX_SAMPLES) {
        close_segment(s, s->sample_index, 1);
    } else if (s->active && s->below_count >= FORM_STREAM_DEADBAND_SAMPLES) {
        close_segment(s, s->sample_index, 0);
    }
}

int form_stream_poll(form_stream *s, float out_x[FORM_STREAM_FEATURES], float *p_wrong)
{
    float probability;
    unsigned i;
    if (!s || !out_x || !p_wrong) return -1;
    if (s->error) return -1;
    if (!s->pending) return 0;
    for (i = 0; i < FORM_STREAM_FEATURES; ++i) out_x[i] = s->pending_x[i];
    probability = form_rep_predict(out_x);
    if (!stream_finite(probability) || probability < 0.0f || probability > 1.0f) {
        s->error = 1;
        return -1;
    }
    *p_wrong = probability;
    s->pending = 0;
    return 1;
}
