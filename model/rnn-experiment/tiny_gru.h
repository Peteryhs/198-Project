#ifndef TINY_GRU_H
#define TINY_GRU_H

#include <stddef.h>

typedef struct {
    const float *weight_ih;       /* [24, 6], PyTorch gate order r,z,n */
    const float *weight_hh;       /* [24, 8] */
    const float *bias_ih;         /* [24] */
    const float *bias_hh;         /* [24] */
    const float *head_weight;     /* [4, 9] */
    const float *head_bias;       /* [4] */
    const float *input_mean;      /* [6] */
    const float *input_scale;     /* [6] */
    float duration_mean;
    float duration_scale;
} TinyGruModel;

typedef struct {
    float quality_probability;
    float exercise_probability[3]; /* EAH, EFE, SQZ */
} TinyGruOutput;

/* samples are causal four-sample means at 25 Hz, flattened [steps, 6]. */
int tiny_gru_predict(const TinyGruModel *model, const float *samples, size_t steps,
                     float duration_seconds, TinyGruOutput *output);

#endif
