# Rescore and scoring feedback fix

The source fix is complete after the calibration-save pass. **APK assembly is not verified:** both requested Gradle tasks failed before compilation because this sandbox cannot provide Gradle's local socket service. Cached Kotlin/Compose compilation and the socket-free JVM suite pass. The existing APK is stale and does not contain this fix.

## Cause, with evidence

The deterministic defect is **Gemini HTTP on the UI thread, followed by dropping a null exception message**. At task start:

- `app/src/main/kotlin/TallyApplication.kt:29` supplies `MainScope()` to UI actions.
- `app/src/main/kotlin/ui/TallyApp.kt:356` called `backend.rescore(id)` and handled failure with only `message = it.message`.
- `backend/src/main/kotlin/AndroidTallyBackend.kt:453` (`rescore`), `:440` (`scorePartial`) and `:477` (`scoreRecording`) inherited the caller dispatcher. A suspend declaration and a mutex do not switch threads. The Gemini branch called blocking `GeminiScorer.score` directly, unlike the automatic end-of-set path launched on the backend's IO scope.
- `backend/src/main/kotlin/score/GeminiScorer.kt`, `post` (current line 237), opens the HTTP output stream synchronously. Its original catch handled only `GeminiError`, so Android's thread exception bypassed last-call-status reporting.

Android documents [NetworkOnMainThreadException](https://developer.android.com/reference/android/os/NetworkOnMainThreadException) for networking on the main thread and documents that its constructor has no detail message. **Derived from this call chain:** with an eligible archive and a nonempty fallback key, the retry reaches `Scoring`, throws before the HTTP request can complete, enters `Failed`, and returns `Result.failure`. Assigning its null message produces no text. It cannot reach `Done` or replace the stored result.

This is a source-path diagnosis, not a phone observation. The owner's archive, exact SetId and crash trace were not supplied, and no phone was used. The following table separates the actual code defects from possible data-specific refusals rather than inventing a measured phone trace.

| Candidate | Evidence and conclusion |
|---|---|
| Button not wired | The no-result button was wired to `rescore` using the route id (or explicit `scorePartial`). However, an existing-result `ResultScreen` exposed only Close and Export. It now has **Score this set again** too. |
| Failure dropped by UI | Confirmed: the original no-result/retry handlers assigned nullable `Throwable.message`. The backend's generic `attempt` returns `Result.failure`; a null message made it invisible. |
| `restore(id)` refuses archive | Still possible for an unknown id, invalid calibration, corrupt frames, or invalid sequence. Complete valid archives replay in the JVM regression. Interrupted archives still require explicit partial eligibility. No supplied archive establishes a restore refusal as the owner's cause. These failures now display text even before session state changes. |
| Gemini throws before posting | Confirmed dispatcher defect in the source path above. Also, enabled fallback with a blank key silently chose the local model; this now returns an actionable failure. Network, HTTP and parsing exceptions now all update last-call status and fail the set. |
| Success but stale result screen | The original effect already re-read on `id` and `session`; it was not simply missing a refresh. It depended on observing a session change. Retry now assigns the returned result directly as well, including when a repeated score equals the previous value. |

## Id and state trace

Documented current code path:

- `TallyApp.kt:147` decodes the navigation Long into the original unsigned `SetId`; `ResultRoute` captures that id in the retry at line 353. State is keyed by backend and id. It never creates a replacement id.
- `AndroidTallyBackend.kt:455` runs retry on IO. `restore` at line 530 reads `meta(id)` and `frames(id)` and constructs `SetRecorder(id, ...)`. Frame replay checks the archived ids, side, sequence, timing and end count. It retains the calibration saved with the set.
- At line 465 an eligible normal retry sets `mutableSession = Scoring(id)`. Explicit partial scoring sets the same state at line 449. A refusal before this point returns failure without manufacturing `Scoring` or `Done`.
- `scoreRecording` at line 483 also enforces IO for all callers. Successful conversion uses `recording.id` at line 513, `saveResult(result)` replaces that id's result at line 519, and line 520 sets `Done(result)`. Exceptions set `Failed` at line 524 and return failure; existing stored results are kept.
- `ResultRoute` line 354 displays the returned success; line 355 displays failure. Its load effect still reads matching `Done` or `backend.result(id)` and now catches read failures too.

Measured JVM regression (`GeminiScorerTest.streamedDeltasBuildAndPersistReplacementUnderTheSameUnsignedId`): the derived fixture id is `UInt.MAX_VALUE` (4294967295). The test replaces a prior result under this id; `repository.result(id)` and a newly opened repository both equal the replacement with parsed reps. This validates persistence and unsigned-id handling, not Android session execution.

New production diagnostics name `rescore requested id=…`, `state=Scoring`, `state=Done stored=… path=…`, `state=Failed`, and `result id=… stored=… path=…`. Restore failures also log the requested id and exception. These are available through the existing Home → Diagnostics → Copy flow; no API key is logged. No runtime phone state transitions are claimed here.

## Changes and checks

- `AndroidTallyBackend`: IO at retry, partial retry, and the common scoring boundary. Enabled fallback requires its key. Scoring failures retain an exception-class fallback message. Added the id/state diagnostics above.
- `GeminiScorer`: one optional internal transport function allows canned replies without a socket. Production and tests share HTTP response decoding, payload construction, parsing, record building and result conversion. Handles streamed deltas, whole interaction events and whole JSON replies, including text outputs and the existing model-output steps. Missing `reps` is malformed, rather than silently becoming an empty score; an explicitly empty reps array remains a valid no-reps answer. HTTP refusals, stream errors, malformed replies and exceptions all fail and update `GeminiCallStatus`. Successful call status is saved in result diagnostics for later viewing.
- `ResultScreen`: scorer path comes from saved provenance, separately from the current toggle. Gemini results show their saved call status; the latest process-wide Gemini call status is labelled separately. Removed local-model origin copy from Gemini results. Retry shows progress, guards duplicate presses, reports success/failure near the action and refreshes directly.
- UI failure handling: connect, start, stop, abort, partial/retry scoring, export, result loading and mode changes all display nonempty failure text. Existing calibration capture/save failure feedback remains. `ScoringScreen` can display result-read failure text too. Export also catches Android share-sheet launch failures.
- `ScoringFeedbackTest`: null and blank exception messages, explicit error text, provenance-based path labels.
- `GeminiScorerTest`: payload intended-exercise descriptions, trace construction, streamed-delta reply, whole JSON and whole-event replies, all exercise-description/code mappings, rep count/verdict/duration, persistence replacement under the same id, refused/malformed calls and null-message errors. Runs the existing archive replay assertions too.

No dependency added for this fix, no contract API change, no package-id change, no Python/model arithmetic changes. Existing calibration-save edits and other working-tree changes were preserved. `SeamTest` remains green in the measured direct suite; app backend imports remain limited to `TallyBackendFactory`.

Visual contract: mobile Result workflow, existing repo UI as the design source and reference family, existing density/layout and dedicated result page. Creation mode is unchanged: recording remains a separate page. Add visible pending/success/error feedback and scorer identity using existing Body and button components. No screen redesign. Kotlin/Compose compilation and copy tests ran; rendered inspection was not performed, per the no-emulator/no-device instruction.

## Commands and actual output

Requested toolchain, with the writable cached Gradle home already prepared during the calibration-save pass:

```sh
export JAVA_HOME="$HOME/.jdks/jdk-21.0.12+8"
export ANDROID_HOME="$HOME/Android/Sdk"
export GRADLE_USER_HOME=/tmp/tally-gradle
./gradlew test
./gradlew :app:assembleDebug
```

Both measured exit statuses are **1**. Their complete output follows.

Measured `./gradlew test` output:

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

Measured `./gradlew :app:assembleDebug` output:

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

Gradle fails before tasks execute because it cannot open the local sockets its lock service requires. This is an environment blocker, not a test or build pass. Permission policy in this session disallows escalation. Project build configuration and security settings were not weakened.

Additional measured check, using the calibration pass's temporary cached compiler runner:

```sh
python3 /tmp/check-calibration.py > /tmp/rescore-jvm.log 2>&1
```

Measured exit status: **0**. It compiles all contract/backend/app Kotlin sources and tests, including Compose, with cached dependencies and existing generated BuildConfig/R artifacts, then runs JUnitCore. Compiler arguments are retained in `/tmp/calibration-jvm/{contract,backend,app}.args`; runtime classpath is `/tmp/calibration-jvm/runtime-classpath`. The runner excludes `DeviceLinkTest`, which opens sockets prohibited here. It includes `SeamTest`. This does not package an APK or execute an Android app. Normal reproducible test entry points remain the Gradle tasks above.

Complete measured direct-check output:

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
.............RecorderChecks derived fixture: 60000 contiguous calibrated samples; malformed frames rejected
........................
Time: 1.717

OK (44 tests)
```

Measured `git diff --check`: exit status **0**, no output.

## APK and provenance

Measured using `stat -c '%n %s bytes %y' app/build/outputs/apk/debug/app-debug.apk`:

```text
app/build/outputs/apk/debug/app-debug.apk 53684693 bytes 2026-11-17 16:26:12.092494995 -0500
```

Absolute path: `/home/peter/work/tally-research/01-app/app/build/outputs/apk/debug/app-debug.apk`.
**This is the existing stale APK, not an APK containing this fix. No fresh APK was produced.**

Measured `git rev-parse HEAD`: `91c30c892fc99d2937c557481c5b6dac715a8a20`, plus uncommitted working-tree changes.

Measured by `sha256sum reference/model/paired-synchronized-offline/{L,R}/realtime_model.npz`:

```text
L: 334111ce74e5c3f4ba0c24d0a5f9d27263ddae802ea275eab3903d45b247089c
R: a3a5d43c7be7dcdd94bd33a2b2969577d16fbf62605987d1ec9f84646d1d1fed
```

Measured scorer SHA-256 by hashing concatenated `reference/scripts/stdlib_runtime.py`, then `reference/scripts/tally_stdlib.py` in build order with Python hashlib:
`3c7af82589ee5832fe180e2abfbf2fc4cb55806a47d86e8292903d97c459244c`.

Documented `app/build.gradle.kts`: application id `com.tally.app`, app version `1.0`. Model/scorer bytes are unchanged. Local results retain their side's model hash and scorer hash. Gemini results retain their distinct model kind and the existing `-` hash markers because those binaries did not score that result. Both paths retain git revision, firmware version and MAC from the recording's HELLO, archived calibration id and app version. No new HELLO was observed here. Canned tests use explicitly derived fixture provenance, not physical measurements.

## Exact owner confirmation steps

Prerequisite: a freshly assembled APK from this source tree. The stale APK above cannot confirm the fix. Run the requested Gradle tasks in a build environment that permits Gradle's local socket service, then install the fresh debug APK through the owner's normal phone update workflow, retaining data for `com.tally.app`.

1. Open Tally. Turn **Demo data (debug)** off. Use an existing archived set; rescoring it does not need a connected sensor or another arm movement.
2. Turn Gemini fallback on and enter the owner's working API key. Make sure the phone has internet access. Open the existing set from History. In Details, note **Set identifier** and the existing model kind.
3. Tap **Score this set again** (or **Score this set** if no result exists). Expect immediate scoring text and a disabled retry while the call is pending. On success, expect visible success feedback, **Scored by: Gemini fallback**, saved call status, last Gemini call status, and the returned exercise/reps. A valid no-movement answer can contain no reps; it must still show an answered status.
4. Close and reopen the same set. Its identifier must be unchanged and its saved Gemini result/status must remain. Current-toggle changes alone must not relabel the saved result.
5. Return Home, clear the fallback key while keeping fallback on, reopen the set and retry. Expect **Scoring failed: Gemini fallback is enabled but its API key is empty…**. The prior result remains visible; no empty score replaces it.
6. Enter a deliberately invalid key and retry with internet available. Expect visible HTTP refusal text and **Last Gemini call: Gemini failed: …**. With no internet, expect a visible network error instead. Restore the working key afterwards.
7. Turn fallback off, reopen the same set and retry. Expect **Scored by: codex-side model (paired-synchronized-offline)** on success, unchanged set identifier, and local model/scorer hashes in Details. A local scorer refusal must show its error text.
8. If any step fails, go Home → Diagnostics → Copy. Match the requested id, `Scoring`, `Done stored=… path=…` or `Failed` entries. Copy the visible failure too. This distinguishes archive refusal before `Scoring` from a scoring failure afterwards without adb.

The live sensor/calibration and arm-form accuracy checks need a physical sensor and a human arm. This pass did not measure model accuracy or make a live Gemini call. No emulator, device, or adb was used.
