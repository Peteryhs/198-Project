"""Host integration checks: py -B backend/tools/pipeline_checks.py. No Android execution."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path.home() / ".gradle/caches/modules-2/files-2.1"
OUTPUT_ROOT = ROOT / "backend/build/pipeline-checks"
OUT = OUTPUT_ROOT / f"run-{time.time_ns()}"


def cached_jar(group, artifact, preferred=None):
    directory = CACHE / group / artifact
    if preferred and (directory / preferred).is_dir():
        versions = [directory / preferred]
    else:
        versions = sorted(directory.glob("*"),
                          key=lambda path: tuple(int(n) for n in re.findall(r"\d+", path.name)), reverse=True)
    for version in versions:
        matches = list(version.glob(f"*/{artifact}-{version.name}.jar"))
        if len(matches) == 1:
            return matches[0]
    raise SystemExit(f"Needs an existing cached {group}:{artifact}; no dependency is installed automatically")


def run(command, cwd=ROOT, env=None):
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="", flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    return result.stdout


def main():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    # Context/AtomicFile signatures are used only for compilation. Host checks never execute Android APIs.
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    android_candidates = list((Path(android_home) / "platforms").glob("*/android.jar")) if android_home else []
    android_candidates += list((Path.home() / ".gradle/caches").glob("*/transforms/*/transformed/android.jar"))
    if not android_candidates:
        raise SystemExit("Needs an existing Android API jar for signature compilation; no SDK is installed automatically")
    android_jar = sorted(android_candidates)[-1]
    compiler = cached_jar("org.jetbrains.kotlin", "kotlin-compiler-embeddable")
    compiler_version = compiler.parent.parent.name
    jars = [cached_jar("org.json", "json", "20160810") if (CACHE / "org.json/json").is_dir()
            else ROOT / "backend/build/host-check-deps/json-20160810.jar"]
    if not jars[0].is_file():
        raise SystemExit("Needs json-20160810.jar from the existing host_checks.py coordinates in "
                         "backend/build/host-check-deps/ or the Gradle cache")
    jars += [compiler, cached_jar("org.jetbrains.kotlin", "kotlin-stdlib", compiler_version),
             cached_jar("org.jetbrains.kotlin", "kotlin-script-runtime", compiler_version),
             cached_jar("org.jetbrains.kotlin", "kotlin-reflect", "1.6.10"),
             cached_jar("org.jetbrains.kotlin", "kotlin-daemon-embeddable", compiler_version),
             cached_jar("org.jetbrains.kotlin", "kotlin-build-tools-api", compiler_version),
             cached_jar("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm", "1.8.0"),
             cached_jar("org.jetbrains", "annotations", "23.0.0"),
             cached_jar("junit", "junit", "4.13.2"),
             cached_jar("org.hamcrest", "hamcrest-core", "1.3"), android_jar]
    classpath = os.pathsep.join(map(str, jars))
    java = shutil.which("java")
    if not java:
        raise SystemExit("Needs an existing Java runtime")
    classes = OUT / "classes"
    classes.mkdir(exist_ok=True)
    source_hash = hashlib.sha256(b"".join((ROOT / "reference/scripts" / name).read_bytes()
                                        for name in ("stdlib_runtime.py", "tally_stdlib.py"))).hexdigest()
    git_rev = run(["git", "rev-parse", "HEAD"]).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    manifest = {
        "scope": "host-only loopback TCP; synthetic sender; no Android Wi-Fi or Chaquopy execution",
        "git_rev": git_rev + ("-dirty" if dirty else ""),
        "scorer_sha256": source_hash,
        "model_sha256": {side: hashlib.sha256((ROOT / "reference/model/paired-synchronized-offline" / side /
                                              "realtime_model.npz").read_bytes()).hexdigest() for side in "LR"},
        "app_version": "1.0-host-check",
        "java": run([java, "-version"]).strip(),
        "classpath": [str(path) for path in jars],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    config = OUT / "BuildConfig.kt"
    config.write_text('package com.tally.app.backend\ninternal object BuildConfig {\n' +
                      f'const val SCORER_SHA256 = "{source_hash}"\n' +
                      f'const val GIT_REV = "{manifest["git_rev"]}"\n' +
                      'const val APP_VERSION = "1.0-host-check"\nconst val DEBUG = true\n}\n', encoding="utf-8")
    excluded = {"AndroidTallyBackend.kt", "TallyBackendFactory.kt", "PythonScorer.kt", "RecordingService.kt"}
    sources = sorted((ROOT / "contract/src/main/kotlin").rglob("*.kt"))
    sources += [path for path in sorted((ROOT / "backend/src/main/kotlin").rglob("*.kt")) if path.name not in excluded]
    tests = sorted((ROOT / "contract/src/test/kotlin").rglob("*.kt"))
    tests += [path for path in sorted((ROOT / "backend/src/test/kotlin").rglob("*.kt")) if path.name != "Wpa2PassphraseTest.kt"]
    tests += sorted((ROOT / "app/src/test/kotlin").rglob("*.kt"))
    sources += [ROOT / "app/src/main/kotlin/ui/Copy.kt", ROOT / "app/src/main/kotlin/ui/ChartMath.kt",
                ROOT / "app/src/main/kotlin/WifiPassphraseStore.kt", config]
    run([java, "-cp", classpath, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect",
         "-classpath", classpath, "-jvm-target", "17", "-d", classes, *sources, *tests])
    execution = [java, "-cp", os.pathsep.join([str(classes), str(ROOT / "backend/src/test/resources"), classpath])]
    unit_classes = []
    for file in tests:
        text = file.read_text(encoding="utf-8")
        if "@Test" in text:
            package = re.search(r"^package ([\w.]+)", text, re.M).group(1)
            unit_classes.append(package + "." + file.stem)
    junit = run([*execution, "org.junit.runner.JUnitCore", *unit_classes], cwd=ROOT / "app")
    for name in ("link.FrameCodecChecks", "store.StorageChecks", "session.RecorderChecks"):
        run([*execution, "com.tally.app.backend." + name, OUT / "kotlin-synthetic.wire"])
    probe = "com.tally.app.backend.session.PipelineChecks"
    run([*execution, probe, "capture", OUT])
    sys.path[:0] = [str(ROOT / "backend/src/main/python"), str(ROOT / "reference/scripts")]
    import tally_app
    assert json.loads(tally_app.init(str(ROOT / "reference/model"))) == manifest["model_sha256"]
    assert tally_app.scorer_version() == source_hash
    records = {}
    for side in "LR":
        wire = (OUT / f"{side}.wire").read_text(encoding="ascii")
        output = tally_app.score_wire(wire)
        (OUT / f"{side}.score.json").write_text(output, encoding="utf-8")
        record = json.loads(output)["record"]
        assert record["side"] == side and record["status"] == "scored"
        records[side] = {key: record[key] for key in ("status", "sample_count", "measured_rate_hz", "verdict", "mean_p_wrong", "exercise")}
        print(f"measured host fixture {side}: {json.dumps(records[side])}", flush=True)
    run([*execution, probe, "verify", OUT])
    environment = os.environ.copy()
    environment["TALLY_KOTLIN_WIRE"] = str(OUT / "kotlin-synthetic.wire")
    python = run([sys.executable, "-B", ROOT / "backend/src/test/python/test_tally_app.py"], env=environment)
    summary = {"passed": True, "scope": manifest["scope"], "junit": junit, "python": python,
               "scored_fixtures": records, "elapsed_seconds": round(time.perf_counter() - started, 3),
               "excluded_android_sources": sorted(excluded), "manifest": "manifest.json"}
    (OUT / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUTPUT_ROOT / "latest.json").write_text(json.dumps({"results": str(OUT / "results.json"),
                                                        "manifest": str(OUT / "manifest.json")}, indent=2), encoding="utf-8")
    print(f"measured: host pipeline checks passed; evidence in {OUT / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
