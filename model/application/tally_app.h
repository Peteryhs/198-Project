#ifndef TALLY_APP_H
#define TALLY_APP_H
#include "../streaming/paired_runtime.h"
#include "../feedback/feedback_policy.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef enum { TALLY_IDLE, TALLY_READY, TALLY_RUNNING, TALLY_PAUSED, TALLY_FINISHED } TallyState;
enum { TALLY_BAD_SAMPLE = 1, TALLY_TIMING_GAP = 2, TALLY_CLIPPED = 4,
       TALLY_OVERFLOW = 8, TALLY_MODEL_ERROR = 16 };
typedef struct {
    FeedbackConfig timing;
    uint32_t target_count;
} TallyConfig;
typedef struct {
    TallyState state;
    uint32_t target_count, cycles, active_ms, faults;
    float cycle_seconds;
    int duration_available;          /* Detector interval only, never validated rep timing. */
    FeedbackCue cue;                 /* Event for this call only. */
    FeedbackReason timing_reason;
    int assessment_available;       /* Only at finish, >=3 cycles, no data faults. */
    float exercise_probability[3], mean_quality_probability; /* Mean P(study class 1: incorrect). */
} TallyOutput;
typedef struct {
    PairRuntime runtime;             /* Only sample buffer in the application. */
    TallyConfig config;
    TallyOutput output;
    FeedbackPolicy policy;
    uint32_t tick_ms, boundary_ms;
} TallyApp;
/* Zero-initialize once. Config can change only outside a running/paused set.
   Missing/invalid timing targets reject configuration; strings are borrowed. */
int tally_configure(TallyApp *s, const TallyConfig *config);
int tally_start(TallyApp *s, uint32_t ms);
int tally_pause(TallyApp *s, uint32_t ms);
int tally_resume(TallyApp *s, uint32_t ms);
int tally_finish(TallyApp *s, uint32_t ms);
/* Same interface for replay and calibrated physical acquisition. Returns cycle status
   (1/0), -1 for rejected/faulted input. Never validates anatomical boundaries. */
int tally_push(TallyApp *s, uint32_t ms, const float acceleration_g[6]);
#ifdef __cplusplus
}
#endif
#endif
