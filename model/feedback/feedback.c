#include "feedback.h"

#include <math.h>

static int present(const char *value) { return value && value[0] != '\0'; }

FeedbackResult feedback_evaluate(const FeedbackConfig *config,
                                 const FeedbackMeasurement *measurement) {
    FeedbackResult result = {0};
    result.cue = FEEDBACK_ABSTAIN;
    result.message = "No tempo feedback.";
    if (!config || !measurement) {
        result.reason = FEEDBACK_REASON_INVALID_CONFIG;
        return result;
    }
    if (config->category != FEEDBACK_TEMPO || measurement->category != FEEDBACK_TEMPO) {
        result.reason = FEEDBACK_REASON_UNSUPPORTED_CATEGORY;
        return result;
    }
    if (!config->target_is_prescribed || !present(config->prescription_id) ||
        config->exercise_id < FEEDBACK_EAH || config->exercise_id > FEEDBACK_SQZ ||
        !isfinite(config->target_seconds) || !isfinite(config->min_seconds) ||
        !isfinite(config->max_seconds) || config->min_seconds <= 0.0f ||
        config->target_seconds <= 0.0f || config->min_seconds > config->target_seconds ||
        config->target_seconds > config->max_seconds) {
        result.reason = FEEDBACK_REASON_INVALID_CONFIG;
        return result;
    }
    result.target_applies = 1;
    result.target_seconds = config->target_seconds;
    result.target_min_seconds = config->min_seconds;
    result.target_max_seconds = config->max_seconds;
    result.exercise_id = config->exercise_id;
    result.prescription_id = config->prescription_id;
    if (measurement->exercise_id < FEEDBACK_EAH || measurement->exercise_id > FEEDBACK_SQZ ||
        config->exercise_id != measurement->exercise_id) {
        result.target_applies = 0;
        result.reason = FEEDBACK_REASON_TARGET_NOT_APPLICABLE;
        return result;
    }
    if (!measurement->measurement_is_valid || !isfinite(measurement->measured_seconds) ||
        measurement->measured_seconds <= 0.0f) {
        result.reason = FEEDBACK_REASON_INVALID_MEASUREMENT;
        return result;
    }
    result.measured_seconds = measurement->measured_seconds;
    result.boundary_evidence_id = measurement->boundary_evidence_id;
    result.boundary_evidence_scope = measurement->boundary_evidence_scope;
    if (!measurement->repetition_boundary_independently_validated) {
        result.reason = FEEDBACK_REASON_BOUNDARY_UNVALIDATED;
        return result;
    }
    if (!present(measurement->boundary_evidence_id) ||
        !present(measurement->boundary_evidence_scope)) {
        result.reason = FEEDBACK_REASON_MISSING_EVIDENCE;
        return result;
    }
    result.reason = FEEDBACK_REASON_NONE;
    if (measurement->measured_seconds < config->min_seconds) {
        result.cue = FEEDBACK_TOO_FAST;
        result.message = "Measured repetition duration is below your prescribed range.";
    } else if (measurement->measured_seconds > config->max_seconds) {
        result.cue = FEEDBACK_TOO_SLOW;
        result.message = "Measured repetition duration is above your prescribed range.";
    } else {
        result.cue = FEEDBACK_ON_TARGET;
        result.message = "Measured repetition duration is within your prescribed range.";
    }
    return result;
}
