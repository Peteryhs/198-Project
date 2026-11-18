# Android demo mode and connection

Turn on **Demo data (debug)** on the home screen, then start a set and choose **Connect demo device**. No ESP32, Wi-Fi permission or password is needed in demo mode. Recording shows a synthetic trace, then a canned scoring result. You can stop or abort, explore results and provenance, export a CSV rep summary, and try simulated calibration. Repeated sets vary the canned verdict and exercise. These are fixtures, not model predictions or sensor measurements.

The switch is available in the app without rebuilding. Its setting survives app restarts. Demo history and calibration stay in memory and disappear when the process ends; they never enter real device storage. Mode changes return to home and are disabled while a set is recording or scoring. The real backend is disconnected before switching, and its saved history and calibration remain intact.

## Real hardware

Turn demo mode off. On Connect, enter the ESP32's WPA2 password, or leave the field blank if the device's Wi-Fi is open. A blank field asks Android for an open `Tally-*` network; a non-blank one asks for WPA2 and must be 8 to 63 plain ASCII characters, checked by the app with a readable message. Current firmware (`firmware/TallyFirmwareV2/src/wifi_ap.c`) runs WPA2, so enter its `TALLY_AP_PASSPHRASE`. If the join fails, the message names which kind of network was requested and the likely mismatch. The password is held in memory for the app session, not saved by Tally. Android asks for Wi-Fi permission/network selection as needed. If the device still holds an unfinished set from a lost link or app restart, Start set aborts it and starts fresh.

**Documented:** `docs/FIRMWARE-HANDOFF.md` and `docs/ESP32-WIRE-V1.md` remain the transport authority. Firmware sends raw millivolts. Nominal calibration means fallback conversion constants, not prerecorded sensor readings. Real pose capture reads the connected ESP32; saving all poses replaces the fallback for future sets. Python still runs only after a real set ends, with no live model inference or rep count.

## Verification limits

**Measured:** `org.junit.runner.JUnitCore` passed the fake backend, calibration copy, app import boundary and demo CSV tests after compilation with cached `org.jetbrains.kotlin.cli.jvm.K2JVMCompiler`. These host checks use cached JVM dependencies, not the project's full Gradle/Android toolchain. XML parsing and source assertions checked launcher resource references, the no-title-bar theme and explicit slide transitions; `git diff --check` passed.

These changes were inspected without a connected phone or ESP32. Launcher appearance, navigation motion, Wi-Fi joining, real calibration and Android CSV sharing need hardware verification. Local source checks or JVM checks do not establish that the Android app runs successfully.

## Diagnostics: the app log
A set start, a Wi-Fi join, a link loss and every failure on the start path are written to `filesDir/tally.log` (last 1,500 lines in memory, 256 KiB on disk). An uncaught exception is written to `filesDir/tally-crash.log` before the process dies. **Home -> Diagnostics** shows both and **Copy** puts them on the clipboard, so no adb or computer is needed. Nothing is uploaded anywhere.
