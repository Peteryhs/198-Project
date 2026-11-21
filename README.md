# Telly

[![Android 10+](https://img.shields.io/badge/Android-10%2B-26372C?logo=android&logoColor=white)](App/)
[![Kotlin](https://img.shields.io/badge/Kotlin-26372C?logo=kotlin&logoColor=white)](App/)
[![ESP32](https://img.shields.io/badge/ESP32-26372C?logo=espressif&logoColor=white)](Firmware/TallyFirmwareV2/)
[![Python](https://img.shields.io/badge/Python-26372C?logo=python&logoColor=white)](Model/)

**A clear record of movement.**

Telly is a prototype that helps older adults track arm exercises at home. An ESP32 streams motion from two accelerometers, one on the upper arm and one on the forearm, to an Android phone over Wi-Fi. After each set, the app estimates rep count and movement quality, saves the result, and lets you export it as CSV.

## Get started

- **Android app:** Open [`App/`](App/) in Android Studio with JDK 21 and Android SDK 37. Run on an ARM64 device with Android 10 or later, or build a debug APK with `./gradlew assembleDebug` from `App/`.
- **ESP32 firmware:** Open [`Firmware/TallyFirmwareV2/`](Firmware/TallyFirmwareV2/) in PlatformIO. Follow the [sensor wiring guide](App/docs/FIRMWARE-HANDOFF.md#hardware), then build and upload for the `esp32doit-devkit-v1` board.

## Learn more

[Data flow](App/docs/LINK.md) · [Scoring model](Model/README.md) · [Research notes](MISC/docs/README.md)

## Makers

Raghav, Sasvin, Jeevan, and Peter

*ECE 198 Design Project · University of Waterloo*
