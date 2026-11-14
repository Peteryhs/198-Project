# Paired firmware host lifecycle check

This isolated host check compiles the sketch against a minimal Arduino serial/clock stub and
exercises the stream header/sample framing, STOP and ABORT endings, reply gating, invalid reply
rejection, missed-deadline abort, and timeout lock. It does not verify actual Arduino core
compatibility, UART throughput, ADC wiring, or sensor calibration.

From the repository root:

```sh
g++ -std=c++11 -Wall -Wextra -Itests/paired_firmware tests/paired_firmware/lifecycle.cpp hardware/198project/accelerometer_reading.cpp -o /tmp/paired-firmware-check && /tmp/paired-firmware-check
```
