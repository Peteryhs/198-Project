# ECE 198: Home Exercise Monitoring

Sensors for older adults who exercise at home alone. The device counts repetitions and keeps the pace honest.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Peteryhs/198-Project/main/assets/data-flow-dark.svg">
  <img src="https://raw.githubusercontent.com/Peteryhs/198-Project/main/assets/data-flow-light.svg" alt="Data path: four ADXL335 accelerometers on one matched pair of limbs feed an Arduino UNO R4 Minima, which counts repetitions and drives an OLED screen. A planned Python model on a host computer scores each session." width="100%">
</picture>

## What the project does

CCCARE (Centre for Community, Clinical and Applied Research Excellence) runs supervised exercise programs for older adults at the University of Waterloo. One instructor supervises up to 30 participants in one session. When a participant goes home, no one measures the exercises.

This project measures those exercises. Four accelerometers sit on one pair of limbs. An Arduino UNO R4 Minima reads the sensors, counts each repetition, and shows the count and the pace on a small screen. A Python model on a host computer scores the quality of the session and writes a summary for the instructor.

## Status

The repository holds a scaffold. No part of the system runs yet.

| Part | State |
| --- | --- |
| `hardware/198project/` | Sketch entry point and an `Accelerometer` class header. The sketch is a stub. |
| `model/model.py` | Empty file. |
| Data transfer | Not started. `data_transfer.h` and `data_transfer.cpp` are placeholders. |
| WiFi path | Under evaluation with the Arduino Yún shield. |
| Bill of materials | Drafted. No parts are ordered. |

## How it works

The UNO R4 Minima has six analog inputs. The design uses four of them, one for each sensor, on pins A0 to A3. Two inputs stay free.

Two sensors on one limb measure the angle between its segments. One sensor on a limb shows only that the limb moved. The pair is the reason the device can tell a full repetition from a shallow one.

A repetition is a shape in the signal. The limb rises, it returns, and a counter passes its threshold. A hysteresis band stops the same motion from counting twice.

The screen shows the count and the pace during the session. Three buttons start a session, calibrate the sensors, and reset the count.

The host model reads the samples, scores each repetition, and writes one summary for the instructor.

## Hardware

| Part | Qty | Role |
| --- | --- | --- |
| Arduino UNO R4 Minima (`ABX00080`) | 1 | Reads four analog channels and counts repetitions. RA4M1 at 48 MHz, 5 V logic, 256 kB flash. |
| ADXL335 3-axis accelerometer | 4 | Two per limb on one matched pair. Analog output on three axes, sensor range ±3 g. |
| Arduino Yún shield | 1 | WiFi 802.11 b/g/n and a LAN port, for the link to the host model. Under evaluation. |
| OLED display | 1 | Shows the repetition count and the pace. |
| Pushbutton | 3 | Start, calibrate, reset. |
| Armband | 4 | Holds each sensor in the same position on every session. |

Datasheets for the board and the shield are in `hardware/resources/`.

## Design targets

| Measure | Target |
| --- | --- |
| Counting error | At most 1 error per 10 repetitions |
| Samples recorded | 95% or more of the session |
| Continuous run | 60 minutes without a reset |

These numbers are requirements, not results. No measurement exists yet.
