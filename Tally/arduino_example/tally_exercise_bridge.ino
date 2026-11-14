/*
  Tally exercise example: one upper-arm + forearm pair on an UNO R4 Minima, sent to the
  Tally app over the candidate Yun shield / Bridge transport (compatibility NOT verified).

  Wiring matches hardware/198project/198project.ino: upper-arm ADXL335 on A0/A1/A2,
  forearm ADXL335 on A3/A4/A5. The g conversion below copies that sketch's
  (raw - 338) * 0.0148 for a 10-bit read at 5 V. Calibrate each axis before trusting it.

  What the app reads (one frame per line):

    time_ms,upper_ax_g,upper_ay_g,upper_az_g,forearm_ax_g,forearm_ay_g,forearm_az_g
        The documented replay row, no header. Tally uses it to estimate repetitions
        itself and to measure sample coverage on the board's own clock.

    TALLY,<state>,<cycles>,<target>,<active_ms>,<faults>,<cycle_s>,<duration_available>,
          <cue>,<timing_reason>,<assessment_available>,<p_eah>,<p_efe>,<p_sqz>,<p_incorrect>
        One TallyOutput (model/application/tally_app.h), field for field. Once the
        firmware runs tally_app, send this after every tally_* call that changes the
        output and at least once a second; Tally then logs the board's count instead
        of its own estimate, mirrors Start/Pause/Finish, and keeps the final verdict.

    TALLYCFG,<exercise 1-3>,<count>,<min_s>,<target_s>,<max_s>,<prescribed 0|1>,<prescription_id>
        Echo of the board's C command, so a set started on the board uses its prescription.

    CAL,<1|0>[,<detail>]
        The calibrate button finished (1) or failed (0).

  100 rows a second is about 4.5 kB/s. Whether Bridge sustains that is unmeasured;
  Tally reports the shortfall as sample coverage rather than hiding it.
*/
#include <Bridge.h>
#include <YunServer.h>
#include <YunClient.h>

const int SERVER_PORT = 5555;
const unsigned long SAMPLE_INTERVAL_MS = 10;  // 100 Hz, the model's input contract
YunServer server(SERVER_PORT);
YunClient client;
unsigned long nextSample = 0;

float toG(int raw) { return (raw - 338) * 0.0148f; }

void setup() {
  Bridge.begin();
  server.noListenOnLocalhost();
  server.begin();
}

void sendRow(unsigned long ms) {
  const int pins[6] = {A0, A1, A2, A3, A4, A5};
  client.print(ms);
  for (int i = 0; i < 6; i++) {
    client.print(',');
    client.print(toG(analogRead(pins[i])), 3);
  }
  client.println();
}

/* Call with a TallyOutput's fields once the firmware links model/application/tally_app.c.
   Arduino prints NaN as "nan"; Tally ignores probabilities unless assessment_available is 1. */
void sendTallyStatus(int state, unsigned long cycles, unsigned long target, unsigned long activeMs,
                     unsigned long faults, float cycleSeconds, int durationAvailable, int cue,
                     int timingReason, int assessmentAvailable, const float exercise[3], float pIncorrect) {
  client.print("TALLY,"); client.print(state);
  client.print(','); client.print(cycles);
  client.print(','); client.print(target);
  client.print(','); client.print(activeMs);
  client.print(','); client.print(faults);
  client.print(','); client.print(cycleSeconds, 3);
  client.print(','); client.print(durationAvailable);
  client.print(','); client.print(cue);
  client.print(','); client.print(timingReason);
  client.print(','); client.print(assessmentAvailable);
  for (int i = 0; i < 3; i++) { client.print(','); client.print(exercise[i], 6); }
  client.print(','); client.println(pIncorrect, 6);
}

void loop() {
  if (!client.connected()) {
    client = server.accept();
    nextSample = millis();
    return;
  }
  const unsigned long now = millis();
  if ((long)(now - nextSample) < 0) return;
  nextSample += SAMPLE_INTERVAL_MS;
  sendRow(now);
}
