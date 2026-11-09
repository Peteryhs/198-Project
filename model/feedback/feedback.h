#ifndef FEEDBACK_H
#define FEEDBACK_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    FEEDBACK_TEMPO = 1,
    FEEDBACK_RANGE_OF_MOTION = 2,
    FEEDBACK_POSTURE = 3,
    FEEDBACK_EFFORT = 4,
    FEEDBACK_GRIP = 5
} FeedbackCategory;

typedef enum {
    FEEDBACK_EAH = 1,
    FEEDBACK_EFE = 2,
    FEEDBACK_SQZ = 3
} FeedbackExercise;

typedef enum {
    FEEDBACK_ABSTAIN = 0,
    FEEDBACK_ON_TARGET = 1,
    FEEDBACK_TOO_FAST = 2,
    FEEDBACK_TOO_SLOW = 3
} FeedbackCue;

typedef enum {
    FEEDBACK_REASON_NONE = 0,
    FEEDBACK_REASON_UNSUPPORTED_CATEGORY = 1,
    FEEDBACK_REASON_INVALID_CONFIG = 2,
    FEEDBACK_REASON_TARGET_NOT_APPLICABLE = 3,
    FEEDBACK_REASON_INVALID_MEASUREMENT = 4,
    FEEDBACK_REASON_BOUNDARY_UNVALIDATED = 5,
    FEEDBACK_REASON_MISSING_EVIDENCE = 6
} FeedbackReason;

typedef struct {
    FeedbackCategory category;
    float target_seconds;
    float min_seconds;
    float max_seconds;
    int target_is_prescribed;
    FeedbackExercise exercise_id;
    const char *prescription_id;
} FeedbackConfig;

typedef struct {
    FeedbackCategory category;
    FeedbackExercise exercise_id;
    float measured_seconds;
    int measurement_is_valid;
    int repetition_boundary_independently_validated;
    const char *boundary_evidence_id;
    const char *boundary_evidence_scope;
} FeedbackMeasurement;

typedef struct {
    FeedbackCue cue;
    FeedbackReason reason;
    int target_applies;
    float target_seconds;
    float target_min_seconds;
    float target_max_seconds;
    float measured_seconds;
    FeedbackExercise exercise_id;
    const char *prescription_id;
    const char *boundary_evidence_id;
    const char *boundary_evidence_scope;
    const char *message;
} FeedbackResult;

/* Duration-only heuristic. Boundary provenance is caller-asserted and is not
   established by the existing causal detector. */
FeedbackResult feedback_evaluate(const FeedbackConfig *config,
                                 const FeedbackMeasurement *measurement);

#ifdef __cplusplus
}
#endif
#endif
