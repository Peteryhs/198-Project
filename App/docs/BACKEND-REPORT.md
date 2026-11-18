# Backend implementation report

Implemented the backend and a plain-text Compose shell. **The Android build has not passed.** The requested Gradle invocation fails before project configuration because this sandbox cannot open sockets. No phone or ESP32 execution is claimed.

## Delivered

- Frozen pure-JVM contract and canned `FakeTallyBackend`; `exportCsv` returns a content-URI `String`. No contract type changes after the source review gate.
- Frozen `ESP32-WIRE-V1.md`, copied verbatim from the plan's wire section. Wrapper files are byte-identical to the specified existing project.
- Binary framing/CRC and payload validation, network-bound TCP socket, one reader thread, complete-frame stall detection, reconnect/RESUME with the next contiguous sequence. No gap filling.
- Preallocated samples and live ring, immutable per-set calibration snapshot, six-pose calibration, raw frame archive, atomic metadata/results, history, rescore, explicit partial scoring, CSV and a read-only content provider.
- Foreground `connectedDevice` service and recording-only Wi-Fi/partial wake locks. The backend owns the reader; the foreground service protects its recording lifetime.
- Unchanged validated Python inputs copied by Gradle into the generated Python source set; unchanged model/metadata assets copied at build. `tally_app.py` exposes only `init`, `score_wire`, `scorer_version`. Interpreter warm-up begins when the application creates the backend; scoring occurs after a set ends.
- Results persist both model hashes, scorer hash, git revision, firmware/MAC, calibration identity and app version. The contract exposes the selected side's model hash as specified.
- The app imports only the contract and backend factory. Its shell displays link/session text; no screen design or theme work.

**Documented configuration:** AGP 9.1.1, copied Gradle 9.3.1 wrapper, Kotlin/Compose compiler 2.4.10, Chaquopy 17.2.0/Python 3.14, minimum API 29, compile/target API 36, arm64 only (`build.gradle.kts` files and wrapper properties). Minimum API/ABI are implementation assumptions awaiting the plan's phone check.

The service declares `FOREGROUND_SERVICE` and `FOREGROUND_SERVICE_CONNECTED_DEVICE`, with `CHANGE_NETWORK_STATE` and `CHANGE_WIFI_STATE` satisfying the documented connected-device prerequisite. [Android foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types#connected-device). AGP supplies Kotlin support in Android modules; no Kotlin Android plugin is applied. [Built-in Kotlin](https://developer.android.com/build/migrate-to-built-in-kotlin).

## Verification actually run

All exit codes, counts, times and outputs in this section are **measured** by the commands shown. Timings are host measurements, not phone performance or accuracy evidence.

Required build:

```sh
env JAVA_HOME=/home/peter/.jdks/jdk-21.0.12+8 \
    ANDROID_HOME=/home/peter/Android/Sdk \
    GRADLE_USER_HOME=/tmp/tally-gradle \
    GIT_DIR=/tmp/tally-backend-implementation.git \
    ./gradlew :contract:test :backend:assembleDebug :app:assembleDebug
```

Exit **1**, before any Gradle task executes:

```text
Downloading https://services.gradle.org/distributions/gradle-9.3.1-bin.zip
Exception in thread "main" java.net.SocketException: Operation not permitted
```

Diagnostic using an already installed distribution, without changing the required wrapper:

```sh
env JAVA_HOME=/home/peter/.jdks/jdk-21.0.12+8 \
    ANDROID_HOME=/home/peter/Android/Sdk GRADLE_USER_HOME=/tmp/tally-gradle \
    /home/peter/.gradle/wrapper/dists/gradle-9.4.1-bin/arn2x92ynaizyzdaamcbpbhtj/gradle-9.4.1/bin/gradle \
    --offline --no-daemon :contract:test
```

Exit **1**: `FileLockContentionHandler` could not initialize: `Could not determine a usable wildcard IP for this machine.` This diagnostic is not a replacement build.

Runnable host verification:

```sh
env JAVA_HOME=/home/peter/.jdks/jdk-21.0.12+8 \
    ANDROID_HOME=/home/peter/Android/Sdk \
    GIT_DIR=/tmp/tally-backend-implementation.git \
    python3.14 -B backend/tools/host_checks.py
```

Exit **0**, final output:

```text
measured: compiled 20 main Kotlin files against cached dependencies; temporary BuildConfig, no APK/Gradle validation
FrameCodec self-check passed
Recorder self-check passed: measured 60000 contiguous calibrated samples and malformed-frame rejection
Storage, CSV, wire writer and fake self-checks passed
Ran 5 tests in 2.189s
OK
measured synthetic: samples=60000 bytes=5197823 reps=240 seconds=1.015 reply=V correct 0.043 SQZ
```

This compiles the contract/backend sources against installed Android API stubs, cached Chaquopy/JSON/coroutines and a temporary BuildConfig. The fallback compiler is Kotlin **2.0.21** and cached coroutines **1.6.4**; it does **not** verify the configured Gradle dependency graph, Compose compilation, manifest merging, Python packaging, DEX or APK assembly.

The executable JVM assertions cover command round trips; every frame type; truncation, CRC, lengths and malformed payloads; full-capacity ingestion and ring wrap; sequence/timestamp/end-count rejection; calibration and JSON snapshots; full/partial archive replay; rejected-end partial exclusion; repository reopen/provenance; CSV marker validation; locale-independent wire formatting; fake replay and cancellation. Python tests score both synthetic text and Kotlin-generated calibrated wire, and check worker execution without signal handlers, hashes, invalid ends/sequences and single-record ownership. Conventional JUnit tests are also present; Gradle could not run them.

```sh
python3.14 -B -m unittest discover -s reference/scripts -p test_shield_hardening.py -q
```

Exit **0**: `Ran 22 tests in 2.985s`, `OK`. Expected diagnostic/fatal fixture messages precede the summary.

```sh
python3.14 -B backend/tools/make_golden.py reference
```

Exit **2** with the explicit prerequisite error: missing `scripts/paired_pipeline.py` and `data/phytmo`. No synthetic data is presented as real golden fixtures. The generator's full-data/parity path remains unverified.

```sh
adb devices -l
```

Exit **1**: USB/netlink unavailable and listener creation `Operation not permitted`. Phone API/ABI and every device measurement **need hardware**.

Additional source assertions passed: exact plan/wire equality; wrapper byte equality; restricted app imports; no changes under `reference/`. `git diff --check` passed. No build output or hardware result was substituted for these checks.

## Provenance inputs

**Measured** from the original files using Python `hashlib.sha256`; scorer digest concatenates `stdlib_runtime.py` then `tally_stdlib.py`, matching the Gradle task and bridge:

| Input | Bytes (measured) | SHA-256 (measured) |
|---|---:|---|
| `reference/model/paired-synchronized-offline/L/realtime_model.npz` | 2114 | `334111ce74e5c3f4ba0c24d0a5f9d27263ddae802ea275eab3903d45b247089c` |
| `reference/model/paired-synchronized-offline/R/realtime_model.npz` | 2111 | `a3a5d43c7be7dcdd94bd33a2b2969577d16fbf62605987d1ec9f84646d1d1fed` |
| Concatenated validated scorer sources | — | `3c7af82589ee5832fe180e2abfbf2fc4cb55806a47d86e8292903d97c459244c` |

The R file differs in size from the brief; neither model was rewritten. Firmware, MAC and real calibration provenance can only come from hardware; the host fixtures identify themselves as fixtures.

## Review and remaining work

Source phase gate reviewed contract names, JVM purity, wrapper origin and exact wire text. The compile gate was explicitly blocked, not passed. Agents handled contract/skeleton, link, Python and storage/service workstreams; the skeleton agent took storage after the source gate because the available concurrency includes the integration agent.

The final ponytail review fixed HELLO length, generated-source ordering, fake cancellation, stale/dead link callbacks, reconnect-job races, orphan device-set abort, interrupted rescore state, invalid partial eligibility, partial archive rescore/export, rescore provenance and stale service callbacks. No further abstractions or dependencies were added for speculative features.

- **Documented update:** the home screen's **Demo data (debug)** switch selects the canned backend at runtime. Demo screens are labelled, history stays separate in memory, and CSV export shares a labelled canned rep summary through the existing provider. See `docs/ANDROID-DEBUG.md`.
- **Provisioning required:** the spec supplies no WPA2 passphrase. Supply the provisioned credential on the first `TallyBackendFactory.create(context, passphrase)` call. Without it `connect()` returns an actionable failure. No password was invented or stored. The future UI must request the applicable Wi-Fi/location runtime permission before connecting.
- **Needs a normal build environment:** rerun the required Gradle command, plus `:backend:testDebugUnitTest :app:testDebugUnitTest`. APK/Compose/Chaquopy integration remains unverified.
- **Needs hardware:** Wi-Fi selection/binding, association recovery, firmware RESUME/end semantics, foreground service/locks, URI grant behavior, real calibration, process death and background recording. Android lifecycle orchestration has source review and API compilation, not an executed lifecycle test.
- **Needs full reference data and hardware:** real golden fixtures, NumPy parity and device reply-byte equality; all phone timings, ADC/power/radio measurements and labelled new-sensor validation. This is not a release acceptance claim.
- **Documented durability limit:** buffered frames flush every second (plan ingest policy). Process death may lose the unflushed tail; explicit partial scoring uses only the verified durable contiguous prefix and records truncation. Corrupt frames are never repaired. Unreadable folders are preserved; metadata that cannot produce a typed summary is omitted from history.
- **Derived partial duration gate:** 480 samples = 4 × minimum 1.2-second peak spacing × documented 100 Hz. This only enables requesting partial scoring; Python still determines whether enough cycles exist.

## Commits and sandbox limitation

The real `.git` directory is read-only here: creating the requested branch there failed with `Unable to create ... backend-implementation.lock: Read-only file system`. A copied Git directory at `/tmp/tally-backend-implementation.git`, using this workspace as its work tree, holds the `backend-implementation` branch and small commits. No push occurred. The original repository's branch/index were not changed.

Implementation commits, **measured** with `git log`:

- `2604285` Freeze backend contract, wire specification and module skeleton
- `bf21089` Add framed ESP32 link and unchanged Python scoring bridge
- `abf7035` Persist contiguous sets, calibration, partial archives and CSV exports
- `2746282` Integrate recording lifecycle, resume recovery and backend app shell

A final report commit follows. `/tmp/backend-implementation.bundle` preserves the branch for import outside this sandbox:

```sh
git fetch /tmp/backend-implementation.bundle backend-implementation:backend-implementation
```

Skipped screen design and hardware claims. Remaining risk: Android packaging/lifecycle and real-sensor accuracy are unverified until the blocked build and hardware gates pass.
