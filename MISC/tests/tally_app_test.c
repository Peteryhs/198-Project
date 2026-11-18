#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "tally_app.h"

static const TallyConfig config = {{FEEDBACK_TEMPO, 2, 1.8f, 2.2f, 1, FEEDBACK_EAH,
                                   "SYNTHETIC-TEST-ONLY"}, 10};
static void sample(unsigned i, float x[6]) {
    for (unsigned k = 0; k < 6; k++) x[k] = 1 + .4f * sinf(6.283185307f * i / 200);
}
static void policy_tests(void) {
    FeedbackPolicy p = {0};
    FeedbackMeasurement m = {FEEDBACK_TEMPO, FEEDBACK_EAH, 1, 1, 1,
        "fixture-known-timing", "synthetic-duration-not-human-evidence"};
    const float values[] = {1, 3, 2, 1.8f, 2.2f};
    const FeedbackCue expected[] = {FEEDBACK_TOO_FAST, FEEDBACK_TOO_SLOW, FEEDBACK_ON_TARGET,
                                    FEEDBACK_ON_TARGET, FEEDBACK_ON_TARGET};
    for (unsigned i = 0; i < 5; i++) {
        feedback_policy_reset(&p); m.measured_seconds = values[i];
        assert(feedback_policy_update(&p, &config.timing, &m, 0).cue == FEEDBACK_ABSTAIN);
        FeedbackResult r = feedback_policy_update(&p, &config.timing, &m, 1000);
        assert(r.cue == expected[i]);
        printf("synthetic duration=%.3f cue=%s (fixture only)\n", values[i], r.message);
        assert(feedback_policy_update(&p, &config.timing, &m, 5999).cue == FEEDBACK_ABSTAIN);
        assert(feedback_policy_update(&p, &config.timing, &m, 6000).cue == expected[i]);
    }
    feedback_policy_reset(&p); m.measured_seconds = 1;
    assert(feedback_policy_update(&p, &config.timing, &m, 0).cue == 0);
    m.measured_seconds = 3;
    assert(feedback_policy_update(&p, &config.timing, &m, 1000).cue == 0);
    m.repetition_boundary_independently_validated = 0;
    assert(feedback_policy_update(&p, &config.timing, &m, 2000).reason == FEEDBACK_REASON_BOUNDARY_UNVALIDATED);
    m.repetition_boundary_independently_validated = 1;
    assert(feedback_policy_update(&p, &config.timing, &m, 3000).cue == 0);
    assert(feedback_policy_update(&p, &config.timing, &m, 4000).cue == FEEDBACK_TOO_SLOW);
    m.measurement_is_valid = 0;
    assert(feedback_policy_update(&p, &config.timing, &m, 10000).cue == 0);
    m.measurement_is_valid = 1;
    m.boundary_evidence_id = NULL;
    assert(feedback_policy_update(&p, &config.timing, &m, 10000).reason == FEEDBACK_REASON_MISSING_EVIDENCE);
    m.boundary_evidence_id = "fixture";
    feedback_policy_reset(&p);
    feedback_policy_update(&p, &config.timing, &m, UINT32_MAX-1000);
    assert(feedback_policy_update(&p, &config.timing, &m, UINT32_MAX-1000).cue != 0);
    assert(feedback_policy_update(&p, &config.timing, &m, 3998).cue == 0);
    assert(feedback_policy_update(&p, &config.timing, &m, 3999).cue != 0);
    assert(!strcmp(feedback_cue_text(FEEDBACK_TOO_FAST), "Faster than target"));
}
static void configuration_tests(void) {
    TallyApp s = {0}; TallyConfig c = config;
    assert(!tally_start(&s, 0)); assert(!tally_configure(&s, NULL));
    c.target_count = 0; assert(!tally_configure(&s, &c)); c = config;
    c.timing.prescription_id = NULL; assert(!tally_configure(&s, &c)); c = config;
    c.timing.target_is_prescribed = 0; assert(!tally_configure(&s, &c)); c = config;
    c.timing.min_seconds = NAN; assert(!tally_configure(&s, &c)); c = config;
    c.timing.max_seconds = 1; assert(!tally_configure(&s, &c)); c = config;
    c.timing.exercise_id = 0; assert(!tally_configure(&s, &c)); c = config;
    assert(tally_configure(&s, &c)); assert(!tally_resume(&s, 0)); assert(!tally_finish(&s, 0));
    assert(tally_start(&s, 0)); assert(!tally_start(&s, 0)); assert(!tally_configure(&s, &c));
    assert(tally_pause(&s, 100)); assert(!tally_pause(&s, 110)); assert(!tally_configure(&s, &c));
    assert(tally_push(&s, 200, NULL) == -1); assert(s.output.faults == 0);
    assert(tally_resume(&s, 1000)); assert(tally_finish(&s, 1100));
    assert(s.output.active_ms == 200); assert(!s.output.assessment_available);
    assert(!tally_finish(&s, 1200)); assert(tally_start(&s, 2000));
    assert(!s.output.cycles && !s.output.active_ms && !s.output.faults);
}
static void parity_and_duration_tests(void) {
    const unsigned steps[] = {8, 10, 12, 0}; /* 0 alternates 8/12 ms. */
    for (unsigned mode = 0; mode < 4; mode++) {
        unsigned step = steps[mode];
        TallyApp s = {0}; PairRuntime direct = {0}; float x[6], ex[3], q;
        unsigned cues = 0, cycles = 0; uint32_t prior_boundary = 0;
        assert(tally_configure(&s, &config)); assert(tally_start(&s, 0));
        for (unsigned i = 0; i < 2400; i++) {
            sample(i, x);
            uint32_t ms = step ? i*step : i*10-(i%2)*2;
            uint32_t events = direct.stream.events;
            int a = tally_push(&s, ms, x), b = pair_push(&direct, ms, x, ex, &q);
            assert(a == b && a >= 0); cues += s.output.cue != 0;
            if (a == 1) {
                cycles++;
                assert(s.output.duration_available);
                assert(fabsf(s.output.cycle_seconds - (ms-prior_boundary)*.001f) < 1e-6f);
                assert(s.output.timing_reason == FEEDBACK_REASON_BOUNDARY_UNVALIDATED);
            }
            if (direct.stream.events != events) prior_boundary = ms;
            if (s.output.cycles >= s.output.target_count) assert(s.output.state == TALLY_RUNNING);
        }
        assert(tally_finish(&s, step ? 2399*step : 23988)); assert(!cues && cycles >= 3);
        assert(s.output.cycles == direct.count && s.output.assessment_available);
        assert(s.output.cycles > s.output.target_count); /* Requested count does not auto-finish unvalidated reps. */
        assert(pair_series(&direct, ex, &q));
        assert(q == s.output.mean_quality_probability);
        for (unsigned k = 0; k < 3; k++) assert(ex[k] == s.output.exercise_probability[k]);
        printf("app/direct parity: cadence mode=%u (0=alternating 8/12 ms) cycles=%u quality=%g no real timing cues\n", step, cycles, q);
    }
}
static void pause_and_partial_tests(void) {
    TallyApp s = {0}; float x[6];
    tally_configure(&s, &config); tally_start(&s, 0);
    for (unsigned i = 0; i < 100; i++) { sample(i, x); tally_push(&s, i*10, x); }
    assert(!s.output.cycles); tally_pause(&s, 1000);
    assert(s.runtime.stream.n == 0); assert(!s.output.duration_available);
    tally_resume(&s, 10000);
    for (unsigned i = 0; i < 100; i++) { sample(i, x); tally_push(&s, 10000+i*10, x); }
    tally_finish(&s, 11000);
    assert(!s.output.cycles && !s.output.assessment_available && s.output.active_ms == 2000);
    tally_start(&s, 0);
    for (unsigned i = 0; i < 650; i++) { sample(i, x); tally_push(&s, i*10, x); }
    assert(s.output.cycles > 0 && s.output.cycles < 3);
    tally_finish(&s, 6490); assert(!s.output.assessment_available);
    tally_start(&s, 0);
    for (unsigned i = 0; i < 1200; i++) { sample(i, x); tally_push(&s, i*10, x); }
    unsigned before = s.output.cycles; float sum = s.runtime.quality_sum;
    tally_pause(&s, 12000); assert(s.runtime.quality_sum == sum);
    tally_resume(&s, 20000);
    for (unsigned i = 0; i < 1200; i++) { sample(i, x); tally_push(&s, 20000+i*10, x); }
    tally_finish(&s, 32000);
    assert(s.output.cycles == before*2 && s.output.assessment_available && s.output.active_ms == 24000);
}
static void fault_tests(void) {
    TallyApp s = {0}; float x[6] = {1,1,1,1,1,1};
    tally_configure(&s, &config); tally_start(&s, 0);
    tally_push(&s, 0, x); assert(tally_push(&s, 40, x) == -1);
    assert(s.output.faults & TALLY_TIMING_GAP); assert(!s.runtime.count);
    tally_finish(&s, 40); assert(!s.output.assessment_available);
    const float bad[] = {NAN, INFINITY, -INFINITY};
    for (unsigned j = 0; j < 3; j++) {
        tally_start(&s, 0); x[0] = bad[j]; assert(tally_push(&s, 0, x) == -1);
        assert(s.output.faults & TALLY_BAD_SAMPLE); tally_finish(&s, 0);
    }
    tally_start(&s, 0); assert(tally_push(&s, 0, NULL) == -1); tally_finish(&s, 0);
    for (unsigned j = 0; j < 4; j++) {
        const float clipped[] = {-4,-3,3,4};
        tally_start(&s, 0); x[0] = clipped[j]; tally_push(&s, 0, x);
        assert(s.output.faults & TALLY_CLIPPED); assert(s.runtime.stream.samples[0][0] == fmaxf(-3,fminf(3,x[0])));
        assert(!s.output.duration_available && !s.output.cue); tally_finish(&s, 0);
    }
    x[0] = 1; tally_start(&s, 0);
    for (unsigned i = 0; i <= 600; i++) tally_push(&s, i*10, x);
    assert((s.output.faults & TALLY_OVERFLOW) && s.runtime.stream.n == 1);
    tally_finish(&s, 6000); assert(!s.output.assessment_available);
    tally_start(&s, UINT32_MAX-99); tally_push(&s, UINT32_MAX-99, x); tally_push(&s, UINT32_MAX-89, x);
    tally_pause(&s, UINT32_MAX-79); tally_resume(&s, 100); tally_finish(&s, 120);
    assert(s.output.active_ms == 40);
    tally_start(&s, 100); assert(tally_push(&s, 99, x) == -1); tally_finish(&s, 100);
    assert(s.output.faults & TALLY_TIMING_GAP);
    tally_start(&s, 0); s.output.active_ms = UINT32_MAX-5;
    assert(tally_push(&s, 10, x) == -1); assert(s.output.faults & TALLY_TIMING_GAP);
    puts("lifecycle, partial cycles, insufficient cycles, pause pooling, reset, faults and clock wrap passed");
}
int main(void) {
    policy_tests(); configuration_tests(); parity_and_duration_tests(); pause_and_partial_tests(); fault_tests();
    puts("All Tally application tests passed.");
}
