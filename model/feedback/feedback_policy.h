#ifndef FEEDBACK_POLICY_H
#define FEEDBACK_POLICY_H
#include <stdint.h>
#include "feedback.h"
#ifdef __cplusplus
extern "C" {
#endif
#define FEEDBACK_PERSISTENCE 2
#define FEEDBACK_COOLDOWN_MS 5000u
typedef struct {
    FeedbackCue pending;
    unsigned consecutive;
    uint32_t last_cue_ms;
    int emitted;
} FeedbackPolicy;
void feedback_policy_reset(FeedbackPolicy *s);
/* Two consecutive eligible measurements, then at most one cue per 5 seconds.
   Returns an event, not a latched message; caller clears displayed cues on faults/pause.
   ms is a monotonic active-set clock. Borrowed provenance must outlive the result. */
FeedbackResult feedback_policy_update(FeedbackPolicy *s, const FeedbackConfig *config,
                                      const FeedbackMeasurement *measurement, uint32_t ms);
const char *feedback_cue_text(FeedbackCue cue);
#ifdef __cplusplus
}
#endif
#endif
