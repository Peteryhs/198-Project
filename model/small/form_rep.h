#ifndef FORM_REP_H
#define FORM_REP_H
#ifdef __cplusplus
extern "C" {
#endif
/* Stat-major float features; returns P(series-label 1: wrong), or -1 for nonfinite input.
   Repetitions have series-level labels only; average probabilities over the set. */
float form_rep_predict(const float x[31]);
#ifdef __cplusplus
}
#endif
#endif
