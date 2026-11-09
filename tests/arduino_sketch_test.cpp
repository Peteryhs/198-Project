#include <cassert>
#include <cstdio>
#include <cmath>
#include "arduino/Arduino.h"
HardwareSerial Serial;
#include "../hardware/198project/198project.ino"
static void send(const std::string &text) {
    Serial.input = text; Serial.cursor = 0; loop();
}
int main() {
    setup();
    size_t initial = Serial.output.size();
    send("0,1,1,1,1,1,1\n");
    assert(Serial.output.size() > initial && app.output.state == TALLY_IDLE);
    send("C 1 10 1.8 2 2.2 0 SYNTHETIC-ONLY\n"); assert(app.output.state == TALLY_IDLE);
    send("C 1 -1 1.8 2 2.2 1 SYNTHETIC-ONLY\n"); assert(app.output.state == TALLY_IDLE);
    send("C 1 4294967296 1.8 2 2.2 1 SYNTHETIC-ONLY\n"); assert(app.output.state == TALLY_IDLE);
    send("C 1 10 1.8 2 2.2 1 SYNTHETIC-ONLY\n"); assert(app.output.state == TALLY_READY);
    assert(!strcmp(app.config.timing.prescription_id, "SYNTHETIC-ONLY"));
    send("S 0\n0,1,1,1,1,1,1\n10,4,1,1,1,1,1\n");
    assert(app.output.faults == TALLY_CLIPPED);
    size_t bytes = Serial.output.size();
    for (unsigned i = 2; i < 100; i++) send(std::to_string(i*10)+",1,1,1,1,1,1\n");
    assert(Serial.output.size() == bytes); // Sticky faults must not flood 100 Hz serial.
    send("P 1000\nR 2000\nF 2100\n"); assert(app.output.state == TALLY_FINISHED);
    assert(app.output.active_ms == 1100 && !app.output.assessment_available);
    send("S 0\n"); assert(!app.output.faults);
    send(std::string("0,1,1,1,1,1,1") + '\0' + "junk\n");
    assert(app.output.faults & TALLY_BAD_SAMPLE); assert(!app.runtime.stream.started);
    send("F 0\nS 0\n" + std::string(200, '9') + "\n");
    assert(app.output.faults & TALLY_BAD_SAMPLE); assert(!app.runtime.stream.started);
    send("F 0\nS 0\n0,1,1,1,1,1,nan\n"); assert(app.output.faults & TALLY_BAD_SAMPLE);
    send("F 0\nS 0\n4294967296,1,1,1,1,1,1\n"); assert(app.output.faults & TALLY_BAD_SAMPLE);
    send("F 0\nS 0\n0,1,1,1,1,1,1,\n"); assert(app.output.faults & TALLY_BAD_SAMPLE);
    send("F 0\nC 1 3 1.8 2 2.2 1 SYNTHETIC-ONLY\nS 0\n");
    TallyApp direct = {};
    TallyConfig c = {{FEEDBACK_TEMPO, 2, 1.8f, 2.2f, 1, FEEDBACK_EAH, "SYNTHETIC-ONLY"}, 3};
    assert(tally_configure(&direct, &c) && tally_start(&direct, 0));
    for (unsigned i = 0; i < 1200; i++) {
        float g[6];
        for (unsigned k = 0; k < 6; k++) g[k] = 1 + .4f*std::sin(6.283185307f*i/200 + k*.1f);
        char row[160];
        std::snprintf(row, sizeof(row), "%u,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g\n", i*10,
                      g[0], g[1], g[2], g[3], g[4], g[5]);
        send(row);
        tally_push(&direct, i*10, g);
        assert(app.output.cycles == direct.output.cycles && app.output.faults == direct.output.faults);
        assert(!app.output.cue && !direct.output.cue);
    }
    send("F 11990\n"); tally_finish(&direct, 11990);
    assert(app.output.assessment_available && direct.output.assessment_available);
    assert(app.output.mean_quality_probability == direct.output.mean_quality_probability);
    for (unsigned k = 0; k < 3; k++) assert(app.output.exercise_probability[k] == direct.output.exercise_probability[k]);
    puts("Serial CSV ingestion matches direct application cycle statuses and pooled probabilities.");
    puts("Arduino declaration-stub host tests: configuration, lifecycle, strict parsing, fault suppression passed (not Arduino core/hardware).");
}
