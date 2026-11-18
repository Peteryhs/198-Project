# ESP32 firmware handoff

All processing happens on the phone: millivolts → g, cycle segmentation, the 61 features, the model, the
set verdict. The board is a sensor pipe — sample six channels, send them, infer nothing. The frozen wire
format is `docs/ESP32-WIRE-V1.md`; what follows is what the sender must get right.

## Hardware
One ESP32-WROOM-32, Wi-Fi only. Two ADXL335 analog accelerometers (upper arm, forearm), six channels, all on
ADC1 because ADC2 is unusable while Wi-Fi is on.

| Ch | Signal | Pin |
|---|---|---|
| 0 | upper x | GPIO36 |
| 1 | upper y | GPIO39 |
| 2 | upper z | GPIO34 |
| 3 | forearm x | GPIO35 |
| 4 | forearm y | GPIO32 |
| 5 | forearm z | GPIO33 |

Those six are every free ADC1 pin, so battery-voltage telemetry has nowhere to live; do not invent a
channel for it. At 3.3 V supply a ±3 g ADXL335 output spans 0.66–2.64 V and the ESP32 ADC is accurate only
to about 2.45 V; a 3.0 V sensor supply (1.5 V ± 0.9 V) keeps it inside that window. That is an owner
decision, not a firmware change.

## Sampling contract
The phone's model was validated against exactly this. Breaking a rule raises no error — it yields a
plausible wrong verdict.

- **100 Hz, one sample every 10 ms**, all six channels on the same `esp_timer` tick. One clock for both
  sensors; the phone never aligns two devices.
- **Millivolts, not g**: `u16 mv[6]`. The phone owns the calibration.
- **No filtering, smoothing or averaging** beyond what the ADC read needs.
- **No gap filling.** A tick later than 15 ms ends the set with `SET_END timing`; a ring overrun ends it
  with `ring_overrun`. A set with a hole is rejected, not repaired.
- **Contiguous sequence numbers.** A break rejects the whole set.
- **Cap at 60,000 samples** (600 s), then `SET_END overflow`.

## Wire behaviour
SoftAP at `192.168.4.1`, TCP port `5198`, one station; the app joins with `WifiNetworkSpecifier` and binds
its socket to that network. Little-endian, CRC32 IEEE over bytes `[2, 6+n)`. The board sends `HELLO` on
accept, `SET_STARTED`, `SAMPLES`, `SET_END` with a reason code, and a 1 Hz `HEARTBEAT`; it receives
`START`, `STOP`, `ABORT` and `RESUME`. Each sample is `u32 t_us` + `u16 mv[6]`, batched up to 10 per frame,
so a `SAMPLES` frame goes out about every 100 ms — 179 bytes for ten samples, roughly 1.79 kB/s.

If a `RESUME` asks for a sequence already dropped from the ring, end with `ring_overrun` rather than
skipping samples.

## Out of scope
Rep counting, features, scoring, any judgement about the set, and any model on the board. Those are frozen
on the phone.

See also `docs/PLAN.md` §2 for why SoftAP over hotspot, TCP over UDP, and the 30 s ring.
