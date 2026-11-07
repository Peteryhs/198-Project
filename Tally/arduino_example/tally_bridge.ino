/*
  Tally plug example: UNO R4 Minima + candidate Yun shield / Bridge transport.
  Board/shield compatibility has NOT been verified. Check the exact Bridge library
  and wiring for this board. This is a transport example, not calibrated firmware.

  Three analog outputs from ONE accelerometer connect to A0, A1, A2. This differs
  from the ECE 198 proposal of four sensors with one measured axis per sensor.
  ADXL335 IC supply is 1.8–3.6 V: verify your breakout's regulator and input rating.
  Samples below are raw 12-bit ADC counts, not m/s². Calibrate before converting.

  Advertise metadata once on each accepted connection. No sensor Kotlin class is
  required. Example additional scalar: append ,temp:1:scalar:degC:Temperature
  then send D,temp,23.5 only after reading actual hardware (never synthetic data).
*/
#include <Bridge.h>
#include <YunServer.h>
#include <YunClient.h>

const int SERVER_PORT = 5555;
const unsigned long SEND_INTERVAL_MS = 20;
YunServer server(SERVER_PORT);
YunClient client;
unsigned long lastSend = 0;

void setup() {
  analogReadResolution(12);
  Bridge.begin();
  server.noListenOnLocalhost();
  server.begin();
}

void loop() {
  if (!client.connected()) {
    client = server.accept();
    if (client.connected()) {
      client.println("PLUGS,accel:3:vector:ADC counts:Accelerometer:x|y|z:0:4095:motion");
      lastSend = millis();
    }
    return;
  }
  const unsigned long now = millis();
  if (now - lastSend < SEND_INTERVAL_MS) return;
  lastSend = now;
  client.print("D,accel,");
  client.print(analogRead(A0)); client.print(',');
  client.print(analogRead(A1)); client.print(',');
  client.println(analogRead(A2));
}
