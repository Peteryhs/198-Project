# Paired accelerometer firmware

`198project.ino` sends the line protocol consumed by `scripts/tally_paired_stream.py`.
Connect to the board's existing serial interface at **115200 baud** and use newline
terminated commands:

- `START L` or `START R` starts a set and chooses the side recorded in the stream header.
- `STOP` ends the current set as `E done`, which allows scoring. `ABORT` ends it as
  `E aborted`, which the parser records as rejected.
- The tally script returns `V <verdict> <probability> <exercise>`. Firmware reads this
  without blocking and displays a validated reply as a `#` comment. It will not accept a new
  set until the reply arrives. If none arrives within 30 seconds, it remains locked; restart Python and reset the board before starting another set. This prevents a delayed reply from being
  assigned to a later set.

USB `Serial` at 115200 baud carries commands and status. `Serial1` at 115200 baud carries the
sample stream and receives the tally script's verdict. This matches the intended Yun layout where
the Linux serial endpoint (`/dev/ttyATH0`) is wired to the MCU's hardware UART; confirm that
mapping on the target board.

During a set, the firmware emits one paired sample every 10 ms in this format:

```text
#TALLY2 fs=100 unit=g range=3 side=L
S <seq> <t_ms> <ux> <uy> <uz> <fx> <fy> <fz>
E done
```

The side selection only labels the stream for the corresponding side-specific model; it does
not identify or verify which body side the sensors are physically attached to. A missed sample
deadline aborts the set rather than filling in synthetic timestamps. At 60,000 samples the
firmware ends with `E overflow`, which the parser rejects. The parser also rejects aborted sets
and streams whose measured rate falls outside 95–105 Hz.

## Wiring and calibration

The sketch retains the existing mapping of sensor 1 to A0–A2 and sensor 2 to A3–A5. The
conversion still uses `(ADC - 338) * 0.0148` for each axis. Those constants assume the original
5 V Arduino / ADXL335 setup and are not calibrated or confirmed for a particular board, sensor,
reference voltage, orientation, or mounting. Verify wiring and calibrate each axis on the actual
hardware before treating the reported values as accurate acceleration in g. The `range=3` header
is the expected ADXL335 range metadata; it is not a hardware measurement.

No Arduino build toolchain is configured in this repository environment. The sketch should be
built for the actual Arduino-compatible board, after confirming its analog pin naming and serial
connection.

## Host check (without hardware)

From the repository root:

```sh
g++ -std=c++11 -Wall -Wextra -Itests/paired_firmware \
  tests/paired_firmware/lifecycle.cpp hardware/198project/accelerometer_reading.cpp \
  -o /tmp/paired-firmware-check
/tmp/paired-firmware-check
```

This uses Arduino stubs to check sample order, set controls, reply validation, and timeout locking.
It does not verify Arduino-core compilation, UART throughput, ADC timing, or physical sensor readings.
