#include "tiny_gru.h"

#include <math.h>

static float sigmoidf_stable(float x) {
    if (x >= 0.0f) return 1.0f / (1.0f + expf(-x));
    float e = expf(x);
    return e / (1.0f + e);
}

int tiny_gru_predict(const TinyGruModel *m, const float *x, size_t steps,
                     float duration, TinyGruOutput *out) {
    if (!m || !x || !steps || !out || !isfinite(duration) || duration <= 0.0f ||
        !m->weight_ih || !m->weight_hh || !m->bias_ih || !m->bias_hh ||
        !m->head_weight || !m->head_bias || !m->input_mean || !m->input_scale ||
        !isfinite(m->duration_mean) || !isfinite(m->duration_scale) || m->duration_scale <= 0.0f)
        return 0;

    float h[8] = {0};
    for (size_t t = 0; t < steps; ++t) {
        float xn[6], gi[24], gh[24];
        for (int i = 0; i < 6; ++i) {
            float v = x[t * 6 + i];
            if (!isfinite(v) || !isfinite(m->input_mean[i]) ||
                !isfinite(m->input_scale[i]) || m->input_scale[i] <= 0.0f) return 0;
            xn[i] = (v - m->input_mean[i]) / m->input_scale[i];
        }
        for (int g = 0; g < 24; ++g) {
            gi[g] = m->bias_ih[g]; gh[g] = m->bias_hh[g];
            if (!isfinite(gi[g]) || !isfinite(gh[g])) return 0;
            for (int i = 0; i < 6; ++i) gi[g] += m->weight_ih[g * 6 + i] * xn[i];
            for (int j = 0; j < 8; ++j) gh[g] += m->weight_hh[g * 8 + j] * h[j];
        }
        float r[8], z[8], n[8], next[8];
        for (int j = 0; j < 8; ++j) {
            r[j] = sigmoidf_stable(gi[j] + gh[j]);
            z[j] = sigmoidf_stable(gi[8 + j] + gh[8 + j]);
            n[j] = tanhf(gi[16 + j] + r[j] * gh[16 + j]);
            next[j] = (1.0f - z[j]) * n[j] + z[j] * h[j];
        }
        for (int j = 0; j < 8; ++j) h[j] = next[j];
    }

    float logits[4], dn = (duration - m->duration_mean) / m->duration_scale;
    if (!isfinite(dn)) return 0;
    for (int o = 0; o < 4; ++o) {
        logits[o] = m->head_bias[o] + m->head_weight[o * 9 + 8] * dn;
        if (!isfinite(m->head_bias[o]) || !isfinite(m->head_weight[o * 9 + 8])) return 0;
        for (int j = 0; j < 8; ++j) {
            float w = m->head_weight[o * 9 + j];
            if (!isfinite(w)) return 0;
            logits[o] += w * h[j];
        }
        if (!isfinite(logits[o])) return 0;
    }
    float e0 = expf(logits[1] - fmaxf(logits[1], fmaxf(logits[2], logits[3])));
    float e1 = expf(logits[2] - fmaxf(logits[1], fmaxf(logits[2], logits[3])));
    float e2 = expf(logits[3] - fmaxf(logits[1], fmaxf(logits[2], logits[3])));
    float sum = e0 + e1 + e2;
    if (!isfinite(sum) || sum <= 0.0f) return 0;
    out->quality_probability = sigmoidf_stable(logits[0]);
    out->exercise_probability[0] = e0 / sum;
    out->exercise_probability[1] = e1 / sum;
    out->exercise_probability[2] = e2 / sum;
    return 1;
}
