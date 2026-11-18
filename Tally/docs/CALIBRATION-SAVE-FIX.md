# Calibration save fix

The save path is fixed in source. Direct Kotlin/Compose compilation and the socket-free JVM tests pass. The requested Gradle commands were run but cannot start in this session's sandbox; **no APK containing this fix was built**. The existing APK is stale (details below).

## Cause and evidence

`backend/src/main/kotlin/calib/Calibration.kt:80` is the radius check, previously `if (!sphere.radiusOk) throw IllegalStateException(OnArmMath.MSG_SENSOR_UNCERTAIN)`. `fromBodyHolds` divides by nominal gain, then demanded a fitted gravity radius near unity as though per-device gains were measured. The independent table-rest hold had the same absolute-scale rejection (`Calibration.kt:97`). Either exception returns `Result.failure` from `AndroidTallyBackend.saveBodyCalibration` before `CalibrationStore.save` (`backend/src/main/kotlin/AndroidTallyBackend.kt:429`). The previous calibration therefore stays in use.

There was another independent rejection in `Calibration.kt:28`: the initializer demanded fitted offsets within the legacy interval. Its bare `require` throws `IllegalArgumentException("Failed requirement.")`, so even the existing UI failure handler could not explain which body action needed attention.

The old `usable` predicate (`Calibration.kt:36`) also treated a saved calibration with nominal gains and no reasons as usable, contrary to its own comment. The old JSON writer omitted reasons.

UI contributors were in `app/src/main/kotlin/ui/TallyApp.kt`'s calibration route (now at line 151): captures had no success feedback, progress was owned by the navigation destination, and Save had no busy guard. Fast duplicate Save calls could save successfully, clear the backend map, then replace success feedback with a missing-hold failure. Home had no calibration display. These are code-path findings, not phone observations.

**Evidence boundary:** the owner's failed calibration vectors and exception were not retained. The available CSVs are exercise recordings whose metadata says `nominal`; they cannot prove the owner's actual gains, offsets, postures, or exact exception. The tests prove the deterministic rejection paths and their fixes. They do not establish that a particular device has a gain fault.

## Reproduction inputs

Measured source: `/home/peter/work/tally-research/05-our-data/1183368908.csv`. SHA-256 (measured with `sha256sum`):

```
4e2821b49fe37bc928ef7a291a64232f45514e8d1fd047d6ae0ebfa361a610da
```

`backend/src/test/resources/calibration/recorded-proxies.csv` contains derived means from measured windows. The following sequence ranges are documented by that fixture; window length is derived as inclusive end minus start plus one. Every window has a derived length of 100 samples. Means are in mV, ordered upper arm then forearm.

| Assigned action | Source sequence range | Derived mean vector (mV) |
|---|---|---|
| Hang | 0–99 | 1287.19, 1008.73, 1310.80, 1396.44, 1048.15, 1273.07 |
| Forward, palm up | 400–499 | 1189.04, 1183.07, 1445.56, 1210.35, 1121.40, 1441.73 |
| Side, palm forward | 800–899 | 1330.52, 1047.76, 1231.98, 1370.34, 1044.66, 1355.81 |
| Overhead | 1200–1299 | 1289.06, 1046.02, 1223.58, 1333.22, 1036.64, 1332.52 |
| Table-rest check | 1600–1699 | 1273.43, 1038.87, 1251.90, 1331.11, 1037.93, 1348.17 |
| Repeat hang | 2000–2099 | 1275.10, 1050.48, 1261.39, 1332.90, 1057.16, 1389.19 |
| Repeat forward | 1530–1629 | 1278.48, 1038.13, 1243.18, 1334.19, 1037.64, 1348.58 |

These assignments are exercise proxies, **not measured calibration postures or evidence that each window passes capture stillness**. Replaying them in order overwrites the original reference entries, just like the backend. The documented seven captures deliberately produce five distinct map keys; that is not an incomplete map.

Derived results from `BodyCalibrationTest.recordedExerciseProxiesExposeTheOriginalRadiusRefusal`:

| Mount | Fitted radius at nominal gain | Fitted offsets (mV, rounded) | Table-rest norm at nominal gain |
|---|---|---|---|
| Upper arm | 0.097695617 | 1304.919, 1055.235, 1250.094 | 0.107676789 |
| Forearm | 0.248337180 | 1340.725, 1118.207, 1335.078 | 0.248192549 |

The **first original rejection is the upper-arm radius check**. Neither proxy offset violates the legacy bounds. Both mounts have a nondegenerate fit and accepted anchor separation, so the fixed path saves their results as marginal and retains radius/check diagnostics. This is a save-path regression, not a claim that these exercise proxies are a valid calibration.

The documented original gain assumption is **330 mV/g** (`OnArmMath.MV_PER_G_NOMINAL`); the documented original absolute-radius tolerance is **0.10 g** (`OnArmMath.RADIUS_TOL_G`), and the documented legacy offset interval is **500–2500 mV** (`Calibration.init`). No tolerance was widened: the review and `08-experiments/protocol/on_arm_redesign/LIMITS.md` do not establish a production acceptance tolerance for nominal-gain hardware.

Controlled cases in `BodyCalibrationTest` separate realistic poses from recorded exercise proxies:

- **Derived common-gain scenario:** assumed true gain **400 mV/g**, assumed offsets **1500 mV**, and assumed static gravity directions. The original radius is derived as **400/330 = 1.212121…** and saving throws. The fixed path saves with nominal gains and an explicit unmeasured-scale reason.
- **Derived offset scenario:** assumed offsets **2600 mV**, assumed gain **330 mV/g**, and the same static directions. Radius passes, but the original initializer throws. The fixed body-hold path retains finite fitted offsets, records the failed legacy offset check, and saves marginally. Legacy calibrations still have their original bounds.
- **Derived plausible on-arm scenario:** the replay's derived hang levels supply starting levels, with assumed per-channel gains **[290, 400, 360, 410, 280, 350] mV/g** and assumed hang/forward/side/overhead/table-rest directions. These are plausible synthetic holds, not estimates of actual device gains. Derived fitted radii are **1.122432309** and **1.100104376**; the old radius gate rejects them. The fixed path preserves both frames and marks the calibration marginal.

To regenerate the fixture means from the source (no NumPy needed):

```sh
python3 - <<'PY'
import csv
from pathlib import Path
source = Path('/home/peter/work/tally-research/05-our-data/1183368908.csv')
with source.open() as stream:
    rows = list(csv.DictReader(line for line in stream if not line.startswith('#')))
for first in [0, 400, 800, 1200, 1600, 2000, 1530]:
    window = rows[first:first + 100]
    print(window[0]['seq'], window[-1]['seq'],
          [sum(float(row[key]) for row in window) / len(window) for key in list(rows[0])[4:]])
PY
```

## Changes

- `Calibration.kt`: scale-dependent radius and check-norm failures become retained diagnostics; finite fitted body offsets outside legacy bounds become retained diagnostics. All body calibrations keep `gainSource = "nominal"` and unmeasured gain/absolute-scale reasons. `usable` requires bench gains and no reasons. Missing holds, malformed/nonfinite/out-of-supply readings, singular geometry, and inseparable references still refuse with body-action names. The supply bound is documented by the analog supply in `docs/ESP32-WIRE-V1.md`; frame dimensions and finiteness are validated on construction.
- `CalibrationStore.kt:30`: JSON explicitly records `status = "marginal"` and reasons and reloads them, alongside the existing offsets, gains, frames and id. Atomic-file write behavior is retained. Older JSON without the new diagnostics still loads and cannot become usable merely by omitting reasons when gains are nominal.
- `TallyApp.kt:89`: progress, feedback and busy state follow the backend across navigation. A replacement backend starts fresh; process/activity recreation safely restarts the capture plan instead of restoring a count onto an unknown map. Synchronous guards prevent duplicate capture/save submissions. Capture success and failure both name the instructed body action; save always leaves success or failure feedback.
- `CalibrationScreen.kt`: Save has a busy state, and completed captures offer **Repeat holds** so a geometric refusal is recoverable. No screen redesign.
- `HomeScreen.kt:52` and `Copy.kt`: Home observes the existing calibration flow and immediately names `nominal` or the saved `body-…` id. Body calibrations explicitly say marginal and unmeasured gains/absolute scale. Removed stale six-pose instructions from this flow.
- `BodyCalibrationTest.kt`: recorded proxy replay, plausible unknown per-channel gains, common gain error, out-of-legacy-range offsets, invalid/missing/degenerate holds, reference separation, and serialized JSON round trip. The round trip uses different functional frames for each mount and asserts offsets, gains, both functional frames, gain source, full id/timestamp and reasons survive; restored calibration stays marginal. `CopyTest.kt` checks saved-id copy and body-action wording.

The app id remains `com.tally.app`; this change adds no dependencies, changes no contract API, and leaves the Python scorer and model bytes untouched. The working tree already contained changes when this task started; they were preserved.

Visual contract: mobile calibration task using the existing repo components, typography, density and layout. Preserve the dedicated capture page and action footer; add visible pending/success/failure feedback and Home's current-calibration text. No added visual system. Compose compilation and wording tests ran; rendered inspection needs a physical sensor and human arm for the real capture flow. No emulator, device, or adb was used.

## Commands and actual output

JDK and SDK requested by the owner:

```sh
export JAVA_HOME="$HOME/.jdks/jdk-21.0.12+8"
export ANDROID_HOME="$HOME/Android/Sdk"
```

The first default-cache invocation failed because the wrapper lock under `$HOME/.gradle` is read-only. A writable copy of the already cached distribution and caches was made under `/tmp/tally-gradle` (no project configuration or SDK change). Both requested commands were then run with:

```sh
GRADLE_USER_HOME=/tmp/tally-gradle ./gradlew test
GRADLE_USER_HOME=/tmp/tally-gradle ./gradlew :app:assembleDebug
```

**Measured output of `./gradlew test`, exit status 1:**

```text
FAILURE: Build failed with an exception.

* What went wrong:
Gradle could not start your build.
> Could not create service of type FileLockContentionHandler using BasicGlobalScopeServices.createFileLockContentionHandler().
   > Could not determine a usable wildcard IP for this machine.

* Try:
> Run with --stacktrace option to get the stack trace.
> Run with --info or --debug option to get more log output.
> Run with --scan to get full insights from a Build Scan (powered by Develocity).
> Get more help at https://help.gradle.org.
```

**Measured output of `./gradlew :app:assembleDebug`, exit status 1:**

```text
FAILURE: Build failed with an exception.

* What went wrong:
Gradle could not start your build.
> Could not create service of type FileLockContentionHandler using BasicGlobalScopeServices.createFileLockContentionHandler().
   > Could not determine a usable wildcard IP for this machine.

* Try:
> Run with --stacktrace option to get the stack trace.
> Run with --info or --debug option to get more log output.
> Run with --scan to get full insights from a Build Scan (powered by Develocity).
> Get more help at https://help.gradle.org.
```

Gradle requires a local socket for its lock service, and the sandbox prohibits opening sockets. This is a verification blocker, not a passing build. An additional `--offline --no-daemon` attempt failed with the same error. No permissions or project build settings were weakened.

Direct fallback, using only the cached compiler/dependencies and generated BuildConfig/R artifacts from the existing build:

```sh
python3 /tmp/check-calibration.py > /tmp/calibration-jvm-final.log 2>&1
```

The session script compiles all contract and backend sources/tests and all app sources/tests with the cached Kotlin and Compose compiler, then invokes JUnitCore. Its exact compiler argument files are `/tmp/calibration-jvm/{contract,backend,app}.args`; runtime classpath is `/tmp/calibration-jvm/runtime-classpath`. This verifies source compilation and the socket-free tests; it does not substitute for Android packaging or an app run. These are temporary session artifacts, not new project build tooling. For normal reproducible verification outside the restricted session, use the Gradle commands above.

**Measured direct-check output (exit status 0):**

```text
Compiling contract
Compiling backend
backend/src/main/kotlin/AndroidTallyBackend.kt:226:133: warning: 'when' is exhaustive so 'else' is redundant here.
                val id = when (frame) { is Frame.SetStarted -> frame.id; is Frame.Samples -> frame.id; is Frame.SetEnd -> frame.id; else -> error("Unexpected frame") }
                                                                                                                                    ^^^^
backend/src/test/kotlin/calib/BodyCalibrationTest.kt:84:51: warning: unnecessary non-null assertion (!!) on a non-null receiver of type 'List<FloatArray>'.
        repeat(2) { assertArrayEquals(saved.frames!![it], restored.frames!![it], 0f) }
                                                  ^^
Compiling app
JUnit version 4.13.2
.....DERIVED plausible holds from recorded levels: [Per-device gains and absolute scale are unmeasured; using nominal 330 mV/g., Upper arm: fitted radius 1.1224323089643424 at nominal gain is outside the documented 1 ± 0.1 g check; true gain is unmeasured., Forearm resting on the table, palm up (upper arm): norm 0.6513258797205462 at nominal gain is outside the documented 1 ± 0.1 g check; absolute scale is unmeasured., Forearm: fitted radius 1.100104375518954 at nominal gain is outside the documented 1 ± 0.1 g check; true gain is unmeasured., Forearm resting on the table, palm up (forearm): norm 1.4309769650405741 at nominal gain is outside the documented 1 ± 0.1 g check; absolute scale is unmeasured.]
.DERIVED recorded proxy mount=0 radius=0.09769561690553455 offsets=[1304.9189603764978, 1055.234745424472, 1250.0935917072397]
DERIVED recorded proxy mount=1 radius=0.2483371796133405 offsets=[1340.7245887862382, 1118.206837975439, 1335.0782562180068]
DERIVED fixed proxy result: marginal; [Per-device gains and absolute scale are unmeasured; using nominal 330 mV/g., Upper arm: fitted radius 0.09769561690553455 at nominal gain is outside the documented 1 ± 0.1 g check; true gain is unmeasured., Forearm resting on the table, palm up (upper arm): norm 0.107676788975113 at nominal gain is outside the documented 1 ± 0.1 g check; absolute scale is unmeasured., Forearm: fitted radius 0.2483371796133405 at nominal gain is outside the documented 1 ± 0.1 g check; true gain is unmeasured., Forearm resting on the table, palm up (forearm): norm 0.24819254917511815 at nominal gain is outside the documented 1 ± 0.1 g check; absolute scale is unmeasured.]
.DERIVED controlled result: [Per-device gains and absolute scale are unmeasured; using nominal 330 mV/g., Upper arm: fitted radius 1.2121212121210259 at nominal gain is outside the documented 1 ± 0.1 g check; true gain is unmeasured., Forearm resting on the table, palm up (upper arm): norm 1.2121212121212122 at nominal gain is outside the documented 1 ± 0.1 g check; absolute scale is unmeasured., Forearm: fitted radius 1.2121212121210259 at nominal gain is outside the documented 1 ± 0.1 g check; true gain is unmeasured., Forearm resting on the table, palm up (forearm): norm 1.2121212121212122 at nominal gain is outside the documented 1 ± 0.1 g check; absolute scale is unmeasured.]
DERIVED controlled result: [Per-device gains and absolute scale are unmeasured; using nominal 330 mV/g., Upper arm: fitted offset outside the legacy 500–2500 mV check; per-device offset range is unmeasured., Forearm: fitted offset outside the legacy 500–2500 mV check; per-device offset range is unmeasured.]
...............................
Time: 1.409

OK (38 tests)

```

The direct fallback's earlier full backend/app JUnit invocation also attempted `DeviceLinkTest`. Its measured summary was `Tests run: 37, Failures: 7`; each failure was `java.net.SocketException: Operation not permitted` at `ServerSocket`. The final fallback excludes that socket-dependent class and includes contract tests. It does not claim those transport tests passed. `SeamTest` is included in the passing final run.

An additional temporary source copy reinstated the original radius/check-norm throws and original initializer offset bounds, keeping the same fit arithmetic. This isolated replay proves both original failure types without reverting fixed production files. Commands used the cached compiler with `/tmp/calibration-original/compiler.args` and JUnitCore class `com.tally.app.backend.calib.OriginalGatesTest`; its source is in `/tmp/calibration-original/`.

**Measured original-gate replay output:**

```text
JUnit version 4.13.2
.DERIVED original recorded-proxy refusal: Sensor response is uncertain. Calibration is unavailable; this set cannot be scored.
DERIVED original 400 mV/g refusal: Sensor response is uncertain. Calibration is unavailable; this set cannot be scored.
DERIVED original 2600 mV offset refusal: Failed requirement.

Time: 0.03

OK (1 test)

```

`git diff --check` passed (measured: exit status zero, no output).

## APK and provenance

Measured with:

```sh
stat -c '%n %s bytes %y' app/build/outputs/apk/debug/app-debug.apk
git rev-parse HEAD
sha256sum reference/model/paired-synchronized-offline/{L,R}/realtime_model.npz
```

Measured existing artifact:

```text
app/build/outputs/apk/debug/app-debug.apk 53684693 bytes 2026-11-17 16:26:12.092494995 -0500
```

Absolute path: `/home/peter/work/tally-research/01-app/app/build/outputs/apk/debug/app-debug.apk`. **This artifact predates the changes and does not contain this fix. Do not use it for the confirmation steps.** A fresh Gradle assembly remains blocked by the sandbox socket restriction.

Current source/build provenance (documented generated `backend/build/generated/source/buildConfig/debug/com/tally/app/backend/BuildConfig.java`, cross-checked with git and model hash commands):

```text
git HEAD: 91c30c892fc99d2937c557481c5b6dac715a8a20 (plus uncommitted working-tree changes)
app version: 1.0
model L sha256: 334111ce74e5c3f4ba0c24d0a5f9d27263ddae802ea275eab3903d45b247089c
model R sha256: a3a5d43c7be7dcdd94bd33a2b2969577d16fbf62605987d1ec9f84646d1d1fed
scorer sha256: 3c7af82589ee5832fe180e2abfbf2fc4cb55806a47d86e8292903d97c459244c
```

Recorded-source provenance is embedded verbatim in the fixture: firmware version `1`, MAC `88:57:21:AC:EE:49`, calibration id `nominal`, app version `1.0`, source git revision `fee3565b5d663c32c927ec52d92a6bc78f5bd1a8`, and the same model/scorer hashes. Those are documented recording metadata, not a new HELLO observed in this task. Synthetic tests use derived ids `body-123` / `body-456`, no firmware, no MAC, and no human-arm measurement. The production result provenance path is unchanged and continues using the active calibration id and HELLO metadata.

## Owner confirmation on the phone

Prerequisite: build a **fresh** APK from this working tree where Gradle can open its local sockets, then install it through the owner's normal phone workflow as an update to `com.tally.app`. Keep app data. The stale APK listed above cannot confirm this fix.

- Turn off **Demo data (debug)**. On Home, read **Calibration in use**; it must say `nominal` or the previously saved id.
- Connect to the ESP32, keep both straps in place, and open **Calibrate sensors**.
- Follow **References**: let the arm hang by the side, then hold it straight forward with palm up. For each capture, wait for **Captured:** followed by that body action before moving on.
- Follow **Remaining directions**: arm out to the side with palm forward, then arm above the head with the elbow straight. Stay within comfortable reach.
- Follow **Check, then repeat the references**: forearm resting on the table with palm up; repeat the hanging reference; repeat the forward/palm-up reference. These are the documented remaining captures in the existing plan.
- Press **Save calibration** once. During saving the action is disabled. Expect **Saved body holds. New sets use calibration body-…** and an explicit marginal/unmeasured-scale message. If refused, the message must name the body action(s) to repeat. Use **Repeat holds** to recapture; do not repeatedly press Save on the same bad geometry.
- Return Home immediately. **Calibration in use** must show exactly the saved `body-…` id and marginal status, without recording a set or reconnecting.
- Close and reopen the app through the normal phone UI. Home must show that same id. This is the physical AtomicFile/load confirmation; JVM JSON persistence checks already cover the stored fields.
- To check capture feedback, deliberately move during a hold: expect the named action plus a stillness refusal, with that hold still current. Also leave calibration after a successful hold and return during the same app instance: accepted progress and its message should remain. A recreated app/activity restarts the capture sequence safely.

Physical confirmation needs a physical sensor and a human arm. Builds and JVM tests cannot certify actual sensor gain, posture coverage, strap stability, or exercise accuracy.
