"""Offline Kotlin checks using this machine's cached compiler; this does not build an APK."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
    coordinates = (
        ("org.jetbrains.kotlin", "kotlin-compiler-embeddable", "2.0.21"),
        ("org.jetbrains.kotlin", "kotlin-stdlib", "2.0.21"),
        ("org.jetbrains.kotlin", "kotlin-reflect", "1.9.23"),
        ("org.jetbrains.intellij.deps", "trove4j", "1.0.20200330"),
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm", "1.6.4"),
        ("org.jetbrains", "annotations", "23.0.0"),
        ("com.chaquo.python.runtime", "chaquopy_java", "17.2.0"),
        ("org.json", "json", "20160810"),
    )
    jars = []
    for group, artifact, version in coordinates:
        matches = list((cache / group / artifact / version).glob(f"*/{artifact}-{version}.jar"))
        if len(matches) != 1:
            raise SystemExit(f"needs cached {group}:{artifact}:{version}")
        jars.append(str(matches[0]))
    android_home = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
    android_jar = android_home / "platforms/android-36/android.jar"
    if not android_jar.is_file():
        raise SystemExit(f"needs {android_jar}")
    java_home = Path(os.environ.get("JAVA_HOME", str(Path.home() / ".jdks/jdk-21.0.12+8")))
    java = str(java_home / "bin/java")
    classpath = os.pathsep.join(jars + [str(android_jar)])
    source = b"".join((root / "reference/scripts" / name).read_bytes()
                      for name in ("stdlib_runtime.py", "tally_stdlib.py"))
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = sorted((root / "contract/src/main/kotlin").rglob("*.kt"))
    sources += sorted((root / "backend/src/main/kotlin").rglob("*.kt"))
    checks = sorted((root / "backend/src/test/kotlin").rglob("*Checks.kt"))
    with tempfile.TemporaryDirectory(prefix="tally-host-") as temporary:
        temporary = Path(temporary)
        config = temporary / "BuildConfig.kt"
        config.write_text("package com.tally.app.backend\ninternal object BuildConfig {\n" +
                          f"const val SCORER_SHA256 = {json.dumps(hashlib.sha256(source).hexdigest())}\n" +
                          f"const val GIT_REV = {json.dumps(rev)}\n" +
                          'const val APP_VERSION = "1.0"\nconst val DEBUG = true\n}\n')
        output = temporary / "classes"
        wire = temporary / "kotlin-synthetic.wire"
        subprocess.run([java, "-cp", classpath, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
                        "-no-stdlib", "-no-reflect", "-classpath", classpath, "-jvm-target", "21",
                        "-d", str(output), str(config), *map(str, sources + checks)], check=True)
        print(f"measured: compiled {len(sources)} main Kotlin files against cached dependencies; "
              "temporary BuildConfig, no APK/Gradle validation", flush=True)
        for check in checks:
            package = next(line.split()[1] for line in check.read_text().splitlines()
                           if line.startswith("package "))
            subprocess.run([java, "-cp", str(output) + os.pathsep + classpath,
                            f"{package}.{check.stem}", str(wire)], check=True)
        if wire.is_file():
            environment = os.environ.copy()
            environment["TALLY_KOTLIN_WIRE"] = str(wire)
            subprocess.run(["python3.14", "-B", str(root / "backend/src/test/python/test_tally_app.py")],
                           env=environment, check=True)


if __name__ == "__main__":
    main()
