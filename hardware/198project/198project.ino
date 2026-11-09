#include <Arduino.h>
#include <stdlib.h>
#include <string.h>
#include "../../model/application/tally_app.h"

/* One left upper-arm/forearm pair. No ADC calibration or display driver exists yet.
   Replay g values must never be sent through analogRead or converted as voltages. */
static TallyApp app;
static char line[160], prescription[48];
static unsigned used;
static bool discarding;

static void displayOutput() {
  const TallyOutput *o = &app.output;
  Serial.print("state="); Serial.print((int)o->state);
  Serial.print(" detected_cycles="); Serial.print(o->cycles);
  Serial.print(" requested_count="); Serial.print(o->target_count);
  Serial.print(" active_ms="); Serial.print(o->active_ms);
  Serial.print(" faults="); Serial.print(o->faults);
  Serial.print(" timing_reason="); Serial.println((int)o->timing_reason);
  if (o->cue != FEEDBACK_ABSTAIN) Serial.println(feedback_cue_text(o->cue));
  if (o->state == TALLY_FINISHED) {
    if (o->assessment_available) {
      Serial.println(o->mean_quality_probability >= .5f ? "Model series label: incorrect" : "Model series label: correct");
      Serial.print("Mean model P(study class 1/incorrect); not percent incorrect reps: ");
      Serial.println(o->mean_quality_probability, 6);
      Serial.print("Exercise probabilities EAH/EFE/SQZ: ");
      for (unsigned i = 0; i < 3; ++i) { Serial.print(o->exercise_probability[i], 6); Serial.print(' '); }
      Serial.println();
      Serial.println("Error explanation: not enough evidence to say");
    } else Serial.println("Session assessment unavailable (insufficient cycles or data faults).");
  }
}

/* Acquisition hook: a calibrated, synchronized six-channel frame uses this same API.
   It must use the set's timestamp clock and satisfy 100 Hz cadence/skew measurements.
   shortcut: physical ADC acquisition is unavailable, implement after calibration/bench tests. */
int submitAccelerationG(uint32_t ms, const float g[6]) {
  uint32_t faults = app.output.faults;
  int status = tally_push(&app, ms, g);
  if (status == 1 || app.output.faults != faults) displayOutput();
  return status;
}

static unsigned split(char *text, char delimiter, char *tokens[], unsigned capacity) {
  unsigned n = 0;
  while (*text) {
    if (delimiter == ' ') { while (*text == ' ') ++text; if (!*text) break; }
    if (n == capacity || *text == delimiter) return 0;
    tokens[n++] = text;
    while (*text && *text != delimiter) ++text;
    if (*text) { *text++ = '\0'; if (!*text && delimiter == ',') return 0; }
  }
  return n;
}
static bool unsignedValue(const char *text, uint32_t *out) {
  uint32_t value = 0;
  if (!*text) return false;
  while (*text) {
    if (*text < '0' || *text > '9') return false;
    unsigned digit = (unsigned)(*text++ - '0');
    if (value > (UINT32_MAX - digit) / 10) return false;
    value = value * 10 + digit;
  }
  *out = value;
  return true;
}
static bool floatValue(const char *text, float *out) {
  char *end;
  *out = strtof(text, &end);
  return end != text && *end == '\0'; // Application checks nonfinite values too.
}
static void rejectInput() {
  if (app.output.state == TALLY_RUNNING) tally_push(&app, app.tick_ms, NULL);
  Serial.println("Rejected input.");
  displayOutput();
}
static void processLine() {
  char *token[9];
  // CSV data and commands are separate transports into the same application.
  bool csv = line[0] >= '0' && line[0] <= '9';
  unsigned n = split(line, csv ? ',' : ' ', token, 9);
  uint32_t ms = 0;
  bool ok = false;
  if (csv && n == 7) {
    float g[6];
    ok = unsignedValue(token[0], &ms);
    for (unsigned k = 0; k < 6; ++k) ok = floatValue(token[k+1], g+k) && ok;
    if (ok) {
      if (app.output.state != TALLY_RUNNING) { rejectInput(); return; }
      submitAccelerationG(ms, g); return;
    }
  } else if (n == 8 && !strcmp(token[0], "C")) {
    uint32_t exercise, count, prescribed;
    float lo, target, hi;
    // prescribed=1 is an explicit caller attestation, never inferred from numbers.
    if (unsignedValue(token[1], &exercise) && unsignedValue(token[2], &count) &&
        floatValue(token[3], &lo) && floatValue(token[4], &target) && floatValue(token[5], &hi) &&
        unsignedValue(token[6], &prescribed) && prescribed == 1 && strlen(token[7]) < sizeof(prescription)) {
      TallyConfig c = {{FEEDBACK_TEMPO, target, lo, hi, 1, (FeedbackExercise)exercise, token[7]}, count};
      ok = tally_configure(&app, &c);
      if (ok) { strcpy(prescription, token[7]); app.config.timing.prescription_id = prescription; }
    }
  } else if (n == 2 && unsignedValue(token[1], &ms)) {
    if (!strcmp(token[0], "S")) ok = tally_start(&app, ms);
    else if (!strcmp(token[0], "P")) ok = tally_pause(&app, ms);
    else if (!strcmp(token[0], "R")) ok = tally_resume(&app, ms);
    else if (!strcmp(token[0], "F")) ok = tally_finish(&app, ms);
  }
  if (!ok) { rejectInput(); return; }
  displayOutput();
}

void setup() {
  Serial.begin(115200);
  Serial.println("Tally one-pair scaffold; cycles are not validated anatomical repetitions.");
  Serial.println("Supply C exercise count min target max prescribed(1) prescription-id, then S/P/R/F time_ms.");
  Serial.println("No default targets; prescription approval is caller-attested. Manual F ends the set.");
  Serial.println("Replay rows: time_ms,upper_ax_g,upper_ay_g,upper_az_g,forearm_ax_g,forearm_ay_g,forearm_az_g");
}
void loop() {
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      if (!discarding) { line[used] = '\0'; processLine(); }
      else rejectInput();
      used = 0; discarding = false;
    } else if (!discarding) {
      if ((unsigned char)ch < 32 || (unsigned char)ch > 126) discarding = true;
      else if (used + 1 < sizeof(line)) line[used++] = ch;
      else {
        discarding = true;

      }
    }
  }
}
