#include "Arduino.h"
FakeSerial Serial, Serial1;
#include "../../hardware/198project/198project.ino"
#include <cassert>
#include <iostream>
int main() {
  setup(); Serial.clear(); Serial1.clear();
  Serial.inject("START L\n"); loop();
  assert(collecting && Serial1.out.find("#TALLY2 fs=100 unit=g range=3 side=L\n") != std::string::npos);
  loop(); assert(Serial1.out.find("S 0 0 +0.00000000 +0.00000000") != std::string::npos);
  fakeClock() += SAMPLE_PERIOD_US; loop();
  assert(sampleCount == 2 && Serial1.out.find("S 1 10 +0.00000000") != std::string::npos);
  Serial.inject("STOP\n"); loop();
  assert(!collecting && awaitingVerdict && Serial1.out.find("E done\n") != std::string::npos);
  Serial.inject("START R\n"); loop(); assert(!collecting);
  Serial1.inject("V invalid\n"); loop(); assert(awaitingVerdict);
  Serial1.inject("V correct 0.125 EFE\n"); loop(); loop(); assert(!awaitingVerdict);
  Serial.inject("START R\n"); loop(); assert(collecting && Serial1.out.find("side=R\n") != std::string::npos);
  Serial.inject("ABORT\n"); loop(); assert(awaitingVerdict && Serial1.out.find("E aborted\n") != std::string::npos);
  Serial1.inject("V unknown nan -\n"); loop(); loop(); assert(!awaitingVerdict);
  Serial.inject("START L\n"); loop();
  fakeClock() = nextSampleUs + SAMPLE_PERIOD_US;
  loop(); assert(!collecting && awaitingVerdict && Serial1.out.find("E aborted\n") != std::string::npos);
  fakeClock() = verdictWaitStartMs * 1000UL + VERDICT_TIMEOUT_MS * 1000UL;
  loop(); assert(awaitingVerdict && verdictTimeoutReported);
  Serial.inject("START L\n"); loop(); assert(!collecting && awaitingVerdict);
  std::cout << "firmware lifecycle host checks passed\n";
}
