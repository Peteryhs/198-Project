#include "tally_app.h"
#include <math.h>

static void quiet(TallyApp *s) {
    s->output.cue = FEEDBACK_ABSTAIN;
    s->output.duration_available = 0;
    s->output.cycle_seconds = 0;
    s->output.timing_reason = FEEDBACK_REASON_BOUNDARY_UNVALIDATED;
    feedback_policy_reset(&s->policy);
}
static int tick(TallyApp *s, uint32_t ms) {
    uint32_t delta = ms - s->tick_ms;
    if (delta > 0x7fffffffu || delta > UINT32_MAX - s->output.active_ms) return 0;
    s->output.active_ms += delta;
    s->tick_ms = ms;
    return 1;
}
int tally_configure(TallyApp *s, const TallyConfig *config) {
    if (!s || !config || s->output.state == TALLY_RUNNING || s->output.state == TALLY_PAUSED ||
        !config->target_count) return 0;
    FeedbackMeasurement probe = {FEEDBACK_TEMPO, config->timing.exercise_id, 1, 1, 0, 0, 0};
    FeedbackResult r = feedback_evaluate(&config->timing, &probe);
    if (r.reason != FEEDBACK_REASON_BOUNDARY_UNVALIDATED) return 0;
    TallyConfig copy = *config;
    *s = (TallyApp){0};
    s->config = copy;
    s->output.state = TALLY_READY;
    s->output.target_count = copy.target_count;
    quiet(s);
    return 1;
}
int tally_start(TallyApp *s, uint32_t ms) {
    if (!s || (s->output.state != TALLY_READY && s->output.state != TALLY_FINISHED)) return 0;
    pair_reset(&s->runtime);
    s->output = (TallyOutput){0};
    s->output.state = TALLY_RUNNING;
    s->output.target_count = s->config.target_count;
    s->tick_ms = ms;
    quiet(s);
    return 1;
}
int tally_pause(TallyApp *s, uint32_t ms) {
    if (!s || s->output.state != TALLY_RUNNING || !tick(s, ms)) return 0;
    s->output.state = TALLY_PAUSED;
    stream_reset(&s->runtime.stream); /* Discard partial cycle, preserve series pooling. */
    quiet(s);
    return 1;
}
int tally_resume(TallyApp *s, uint32_t ms) {
    if (!s || s->output.state != TALLY_PAUSED || ms - s->tick_ms > 0x7fffffffu) return 0;
    s->tick_ms = ms;
    s->output.state = TALLY_RUNNING;
    quiet(s);
    return 1;
}
int tally_finish(TallyApp *s, uint32_t ms) {
    if (!s || (s->output.state != TALLY_RUNNING && s->output.state != TALLY_PAUSED)) return 0;
    if (s->output.state == TALLY_RUNNING && !tick(s, ms)) return 0;
    if (s->output.state == TALLY_PAUSED && ms - s->tick_ms > 0x7fffffffu) return 0;
    quiet(s);
    s->output.state = TALLY_FINISHED;
    int available = pair_series(&s->runtime, s->output.exercise_probability,
                                &s->output.mean_quality_probability);
    s->output.assessment_available = available && s->runtime.count >= 3 && !s->output.faults;
    return 1;
}
static int reject(TallyApp *s, unsigned fault) {
    s->output.faults |= fault;
    pair_reset(&s->runtime);
    quiet(s);
    s->output.timing_reason = FEEDBACK_REASON_INVALID_MEASUREMENT;
    return -1;
}
int tally_push(TallyApp *s, uint32_t ms, const float x[6]) {
    if (!s || s->output.state != TALLY_RUNNING) return -1;
    s->output.cue = FEEDBACK_ABSTAIN;
    if (!tick(s, ms)) return reject(s, TALLY_TIMING_GAP);
    if (!x) return reject(s, TALLY_BAD_SAMPLE);
    for (unsigned k = 0; k < 6; k++)
        if (!isfinite(x[k])) return reject(s, TALLY_BAD_SAMPLE);
    PairStream *stream = &s->runtime.stream;
    if (stream->started && (ms - stream->last_ms < 8 || ms - stream->last_ms > 12))
        return reject(s, TALLY_TIMING_GAP);
    for (unsigned k = 0; k < 6; k++)
        if (x[k] <= -3 || x[k] >= 3) {
            s->output.faults |= TALLY_CLIPPED;
            quiet(s); /* Keep the classifier's existing clipping behavior. */
        }
    uint32_t events = stream->events;
    uint32_t overflows = stream->overflows;
    float ex[3], q;
    int status = pair_push(&s->runtime, ms, x, ex, &q);
    if (status < 0) return reject(s, TALLY_MODEL_ERROR);
    if (stream->overflows != overflows) {
        s->output.faults |= TALLY_OVERFLOW;
        quiet(s);
        s->output.timing_reason = FEEDBACK_REASON_INVALID_MEASUREMENT;
    }
    if (status == 1) {
        s->output.cycles++;
        s->output.cycle_seconds = (ms - s->boundary_ms) * .001f;
        s->output.duration_available = !s->output.faults;
        FeedbackMeasurement m = {FEEDBACK_TEMPO, s->config.timing.exercise_id,
            s->output.cycle_seconds, s->output.duration_available, 0, 0, 0};
        FeedbackResult r = feedback_policy_update(&s->policy, &s->config.timing, &m,
                                                   s->output.active_ms);
        s->output.cue = r.cue;
        s->output.timing_reason = r.reason;
    }
    if (stream->events != events) s->boundary_ms = ms;
    return status;
}
