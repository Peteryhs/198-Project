## 2. Wire contract: ESP32 SoftAP + TCP, binary frames, ESP32 timestamps

**Topology.** The ESP32 runs a SoftAP: SSID `Tally-<last 2 MAC bytes hex>`, WPA2, fixed channel, max 1 station. It serves TCP on `192.168.4.1:5198` and accepts one client. The phone joins with `WifiNetworkSpecifier` (API 29+) and binds the socket to `network.socketFactory`, so phone internet stays on cellular.

Rejected alternatives:
- **mDNS discovery**: the address is fixed on the ESP32's own AP, so discovery only adds a way to fail.
- **Phone hotspot with the ESP32 as station**: needs credential provisioning and discovery. Its one advantage is power, because modem sleep works only in station mode [D: ESP-IDF `examples/wifi/power_save`]. M4 decides whether that advantage matters.
- **UDP**: the validated parser rejects the whole set on any sequence break, so loss would mean either a lost set or gap filling the model was never validated on.
- **BLE GATT**: the owner chose WiFi. BLE (about 27 mA [R]) is the fallback if M4 fails.

**Framing.** All fields little-endian. CRC32 IEEE is `esp_rom_crc32_le` on the ESP32 and `java.util.zip.CRC32` on the phone.

```
off  size  field
0    2     magic 0x54 0x59 ("TY")
2    1     version = 1
3    1     type
4    2     payload_len  (≤ 512; larger → protocol error, drop connection)
6    n     payload
6+n  4     crc32 over bytes [2, 6+n)
```

| Type | Dir | Payload |
|---|---|---|
| `0x01 HELLO` | dev→ph, on accept | `u16 fw_version, u8 mac[6], u8 reset_reason (esp_reset_reason()), u32 sample_period_us=10000, u8 n_ch=6, u8 atten, u16 set_cap=60000, u16 ring_cap=3000, u32 active_set_id (0=none), u32 active_next_seq` |
| `0x02 SET_STARTED` | dev→ph | `u32 set_id, u8 side ('L'/'R')` |
| `0x03 SAMPLES` | dev→ph, every 100 ms | `u32 set_id, u32 first_seq, u8 n (1..10)`, then n × `{u32 t_us, u16 mv[6]}` |
| `0x04 SET_END` | dev→ph | `u32 set_id, u8 reason (0 done, 1 aborted, 2 overflow, 3 timing, 4 ring_overrun), u32 sample_count` |
| `0x05 HEARTBEAT` | dev→ph, 1 Hz | `u32 uptime_ms, u16 ring_fill, u16 min_free_heap_kb` |
| `0x81 START` | ph→dev | `u32 set_id, u8 side` |
| `0x82 STOP` / `0x83 ABORT` | ph→dev | `u32 set_id` |
| `0x84 RESUME` | ph→dev, after reconnect | `u32 set_id, u32 next_seq` |

Channel order is fixed: `mv[0..5]` = upper x/y/z on GPIO36/39/34, then forearm x/y/z on GPIO35/32/33.

Sizes:
- A SAMPLES frame with n=10 is 6 + (9 + 160) + 4 = **179 B per 100 ms, so 1,790 B/s** [Δ].
- The same data as `#TALLY2` text is 4,897,833 B / 60,000 = 81.6 B/sample, so 8.2 kB/s [Δ from M].
- One 600 s set is 1,790 × 600 = **1.07 MB on disk** [Δ].
- Holding the whole set on the ESP32 would take 60,000 × 16 = 960 kB, which exceeds 520 kB SRAM [Δ]. That is why the ESP32 keeps only a ring.

**Loss and lateness.**
- TCP makes loss impossible within a connection. A late frame only delays the chart, because scoring happens at set end.
- On disconnect, the ESP32 keeps sampling into a 3,000-sample ring (30 s = 48 kB [Δ]). The phone reconnects and sends `RESUME`, and the ESP32 resends from `next_seq`.
- If `next_seq` has already left the ring, or the link stalls past 30 s, the ESP32 sends `SET_END ring_overrun`. The set is rejected visibly. **No gap filling, ever.**
- The phone declares the link `Lost` after 3 s without any frame.

**Timestamps come from the ESP32**: `t_us = esp_timer_get_time() − set_start`, taken at the sampling tick. The phone converts with `t_ms = t_us / 1000`, which keeps `tally_stdlib`'s strictly-increasing check and its 95–105 Hz rate check meaningful. The phone's receive time is never used as sample time.

**ESP32 obligations**
1. Sample on a 10 ms `esp_timer` in a task pinned to core 1 (WiFi runs on core 0). Read all six channels with `adc_oneshot` (ADC1 only, `ADC_ATTEN_DB_12` in IDF 5 naming = 11 dB) and convert with `adc_cali` line fitting to mV. Whether to oversample depends on M5.
2. If the gap between two ticks exceeds 15 ms, end with `SET_END timing`. This repeats the existing README rule: "a missed sample deadline aborts the set rather than filling in synthetic timestamps".
3. At 60,000 samples, end with `SET_END overflow`.
4. Send one `send()` per SAMPLES frame with `TCP_NODELAY` set.
5. Lower TX power with `esp_wifi_set_max_tx_power`, since the phone is within about 1 m. This cuts current peaks, which cause brownouts; average current is not the problem.
6. Leave the brownout detector enabled and report `reset_reason` in HELLO, so a lost set can be traced to a brownout.
7. **No battery-voltage telemetry.** All six ADC1 pins are taken and ADC2 cannot be used while WiFi is on. Say so in the hardware notes instead of inventing a channel.

**Analog range.** At 3.3 V supply, ±3 g is 0.66–2.64 V. The accurate ceiling of 2.45 V corresponds to (2.45 − 1.65) / 0.33 = **+2.42 g** [Δ]. Powering the ADXL335s from a clean 3.0 V LDO gives 1.5 V ± 3 × 0.30 V = **0.6–2.4 V** [Δ, using the datasheet's typical 300 mV/g at Vs = 3 V, D], which is inside the window. Whether this is required depends on M6. First check whether the breakout boards have their own regulator.

