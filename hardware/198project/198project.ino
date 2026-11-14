#include "accelerometer_reading.h"
#include <Arduino.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Existing wiring: two ADXL335 units on analog inputs A0..A2 and A3..A5.
// These pin numbers and the conversion constants in accelerometer_reading.cpp
// are inherited from the original sketch; verify them for the actual board.
Accelerometer accelerometer1(A0, A1, A2);
Accelerometer accelerometer2(A3, A4, A5);

static const unsigned long SAMPLE_PERIOD_US = 10000UL;
static const unsigned long MAX_SAMPLES = 60000UL; // parser limit; 10 minutes at 100 Hz
static const unsigned long VERDICT_TIMEOUT_MS = 30000UL;
static const unsigned long SERIAL_BAUD = 115200UL;

static bool collecting = false;
static bool awaitingVerdict = false;
static char selectedSide = 'L';
static unsigned long nextSampleUs = 0;
static unsigned long sampleCount = 0;
static unsigned long setStartMs = 0;
static unsigned long verdictWaitStartMs = 0;
static bool verdictTimeoutReported = false;
static char inputLine[40];
static size_t inputLength = 0;
static bool discardInputLine = false;
static char replyInputLine[40];
static size_t replyInputLength = 0;
static bool discardReplyLine = false;
static char verdictLine[40];

static void note(const __FlashStringHelper *message) {
  Serial.print(F("# "));
  Serial.println(message);
}

static void endSet(const char *reason) {
  Serial1.print(F("E "));
  Serial1.println(reason);
  collecting = false;
  awaitingVerdict = true;
  verdictLine[0] = '\0';
  verdictWaitStartMs = millis();
  verdictTimeoutReported = false;
}

static void beginSet(char side) {
  if (collecting || awaitingVerdict) {
    note(F("BUSY: wait for verdict; after timeout restart Python and reset board"));
    return;
  }
  selectedSide = side;
  sampleCount = 0;
  Serial1.print(F("#TALLY2 fs=100 unit=g range=3 side="));
  Serial1.println(selectedSide);
  setStartMs = millis();
  nextSampleUs = micros();
  collecting = true;
}

static void processUSBCommand(char *line) {
  if (strcmp(line, "STOP") == 0 || strcmp(line, "ABORT") == 0) {
    if (collecting) endSet(strcmp(line, "STOP") == 0 ? "done" : "aborted");
    else note(F("no active set"));
    return;
  }
  if (strlen(line) == 7 && strncmp(line, "START ", 6) == 0 &&
      (line[6] == 'L' || line[6] == 'R')) {
    beginSet(line[6]);
    return;
  }
  if (line[0] != '\0') note(F("commands: START L, START R, STOP, ABORT"));
}

static void serviceSerialInput() {
  // Bound USB command work per loop so a noisy console cannot starve sampling.
  for (uint8_t processed = 0; processed < 16 && Serial.available() > 0; ++processed) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!discardInputLine) {
        inputLine[inputLength] = '\0';
        processUSBCommand(inputLine);
      }
      inputLength = 0;
      discardInputLine = false;
    } else if (discardInputLine) {
      continue;
    } else if (inputLength + 1 < sizeof(inputLine)) {
      inputLine[inputLength++] = c;
    } else {
      inputLength = 0;
      discardInputLine = true;
      note(F("input line too long; discarded"));
    }
  }
}

static void processVerdict(char *line) {
  char tag[4] = {0}, verdict[16] = {0}, probability[16] = {0},
       exercise[16] = {0}, trailing = '\0';
  char *end = NULL;
  bool shapeOk = sscanf(line, "%3s %15s %15s %15s %c", tag, verdict,
                        probability, exercise, &trailing) == 4 &&
    strcmp(tag, "V") == 0 &&
    (strcmp(verdict, "correct") == 0 || strcmp(verdict, "wrong") == 0 ||
     strcmp(verdict, "unknown") == 0);
  bool probabilityOk = false;
  bool exerciseOk = shapeOk && (strcmp(exercise, "EAH") == 0 ||
                    strcmp(exercise, "EFE") == 0 || strcmp(exercise, "SQZ") == 0);
  if (shapeOk && strcmp(verdict, "unknown") == 0) {
    probabilityOk = strcmp(probability, "nan") == 0 && strcmp(exercise, "-") == 0;
  } else if (shapeOk) {
    double p = strtod(probability, &end);
    probabilityOk = end != probability && *end == '\0' && isfinite(p) &&
                    p >= 0.0 && p <= 1.0 && exerciseOk;
  }
  if (shapeOk && probabilityOk && awaitingVerdict) {
    strncpy(verdictLine, line, sizeof(verdictLine) - 1);
    verdictLine[sizeof(verdictLine) - 1] = '\0';
    awaitingVerdict = false;
    Serial.print(F("# "));
    Serial.println(verdictLine);
  } else {
    note(F("ignored invalid or unsolicited verdict"));
  }
}

static void serviceVerdictInput() {
  // The tally script's reply arrives on the same UART that carries samples.
  // Bound work per loop and discard overlong lines through their newline.
  for (uint8_t processed = 0; processed < 16 && Serial1.available() > 0; ++processed) {
    char c = (char)Serial1.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!discardReplyLine) {
        replyInputLine[replyInputLength] = '\0';
        if (replyInputLength > 0) processVerdict(replyInputLine);
      }
      replyInputLength = 0;
      discardReplyLine = false;
    } else if (discardReplyLine) {
      continue;
    } else if (replyInputLength + 1 < sizeof(replyInputLine)) {
      replyInputLine[replyInputLength++] = c;
    } else {
      replyInputLength = 0;
      discardReplyLine = true;
      note(F("reply line too long; discarded"));
    }
  }
}

static void printSample(unsigned long seq, unsigned long tMs,
                        float ux, float uy, float uz,
                        float fx, float fy, float fz) {
  Serial1.print(F("S "));
  Serial1.print(seq);
  Serial1.print(' ');
  Serial1.print(tMs);
  Serial1.print(' ');
  if (ux >= 0) Serial1.print('+');
  Serial1.print(ux, 8); Serial1.print(' ');
  if (uy >= 0) Serial1.print('+');
  Serial1.print(uy, 8); Serial1.print(' ');
  if (uz >= 0) Serial1.print('+');
  Serial1.print(uz, 8); Serial1.print(' ');
  if (fx >= 0) Serial1.print('+');
  Serial1.print(fx, 8); Serial1.print(' ');
  if (fy >= 0) Serial1.print('+');
  Serial1.print(fy, 8); Serial1.print(' ');
  if (fz >= 0) Serial1.print('+');
  Serial1.print(fz, 8); Serial1.println();
}

static void sampleIfDue() {
  if (!collecting) return;
  unsigned long nowUs = micros();
  long lateness = (long)(nowUs - nextSampleUs);
  if (lateness < 0) return;
  // Do not assign idealized timestamps to missed acquisitions. A long delay
  // invalidates the set so the parser cannot score a fabricated 100 Hz stream.
  if ((unsigned long)lateness >= SAMPLE_PERIOD_US) {
    endSet("aborted");
    note(F("sampling deadline missed; set rejected"));
    return;
  }
  if (sampleCount >= MAX_SAMPLES) {
    endSet("overflow");
    return;
  }
  unsigned long tMs = millis() - setStartMs;
  float ux = accelerometer1.convertX();
  float uy = accelerometer1.convertY();
  float uz = accelerometer1.convertZ();
  float fx = accelerometer2.convertX();
  float fy = accelerometer2.convertY();
  float fz = accelerometer2.convertZ();
  if (!isfinite(ux) || !isfinite(uy) || !isfinite(uz) ||
      !isfinite(fx) || !isfinite(fy) || !isfinite(fz)) {
    endSet("aborted");
    note(F("non-finite sensor reading; set rejected"));
    return;
  }
  printSample(sampleCount, tMs, ux, uy, uz, fx, fy, fz);
  ++sampleCount;
  nextSampleUs += SAMPLE_PERIOD_US;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  Serial1.begin(SERIAL_BAUD);
  // Explicitly retain the 10-bit ADC scale used by the existing 338/0.0148
  // conversion constants on Arduino cores that expose this setting.
#if defined(ARDUINO_ARCH_RENESAS_UNO)
  analogReadResolution(10);
#endif
  note(F("ready; send START L or START R, then STOP to end"));
}

void loop() {
  serviceSerialInput();
  serviceVerdictInput();
  sampleIfDue();
  if (awaitingVerdict && !verdictTimeoutReported &&
      millis() - verdictWaitStartMs >= VERDICT_TIMEOUT_MS) {
    verdictTimeoutReported = true;
    note(F("verdict timeout; START locked. Restart Python and reset board to recover"));
  }
}
