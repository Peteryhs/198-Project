#include "feedback_policy.h"
void feedback_policy_reset(FeedbackPolicy *s) { *s = (FeedbackPolicy){0}; }
const char *feedback_cue_text(FeedbackCue cue) {
    switch (cue) {
    case FEEDBACK_ON_TARGET: return "Pace on target";
    case FEEDBACK_TOO_FAST: return "Faster than target";
    case FEEDBACK_TOO_SLOW: return "Slower than target";
    default: return "Timing feedback unavailable";
    }
}
FeedbackResult feedback_policy_update(FeedbackPolicy *s, const FeedbackConfig *config,
                                      const FeedbackMeasurement *measurement, uint32_t ms) {
    FeedbackResult r = feedback_evaluate(config, measurement);
    if (r.cue == FEEDBACK_ABSTAIN) {
        s->pending = FEEDBACK_ABSTAIN;
        s->consecutive = 0;
        return r;
    }
    if (r.cue != s->pending) {
        s->pending = r.cue;
        s->consecutive = 0;
    }
    if (s->consecutive < FEEDBACK_PERSISTENCE) s->consecutive++;
    if (s->consecutive < FEEDBACK_PERSISTENCE ||
        (s->emitted && ms - s->last_cue_ms < FEEDBACK_COOLDOWN_MS)) {
        r.cue = FEEDBACK_ABSTAIN;
        r.message = "Timing cue pending persistence or cooldown.";
    } else {
        s->last_cue_ms = ms;
        s->emitted = 1;
        r.message = feedback_cue_text(r.cue);
    }
    return r;
}
