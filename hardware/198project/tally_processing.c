#define PAIRED_MODEL_HEADER "../paired-synchronized-causal/L/realtime_model.h"
/* Arduino builds sketch-local .c files; compile each portable source exactly once. */
#include "../../model/streaming/paired_stream.c"
#include "../../model/streaming/paired_runtime.c"
#include "../../model/feedback/feedback.c"
#include "../../model/feedback/feedback_policy.c"
#include "../../model/application/tally_app.c"
