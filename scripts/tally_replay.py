"""Host replay harness for the TallyApp C API and the declared PHYTMO demo."""
import argparse
import ctypes
import csv
import hashlib
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/arduino-replay-demo"
MODEL = ROOT / "model/paired-synchronized-causal/L"
EXERCISES = {"EAH": 1, "EFE": 2, "SQZ": 3}
HEADER = ("time_ms", "upper_ax_g", "upper_ay_g", "upper_az_g",
          "forearm_ax_g", "forearm_ay_g", "forearm_az_g")


class FeedbackConfig(ctypes.Structure):
    _fields_ = [("category", ctypes.c_int), ("target_seconds", ctypes.c_float),
                ("min_seconds", ctypes.c_float), ("max_seconds", ctypes.c_float),
                ("target_is_prescribed", ctypes.c_int), ("exercise_id", ctypes.c_int),
                ("prescription_id", ctypes.c_char_p)]


class Config(ctypes.Structure):
    _fields_ = [("timing", FeedbackConfig), ("target_count", ctypes.c_uint32)]


class Output(ctypes.Structure):
    _fields_ = [("state", ctypes.c_int), ("target_count", ctypes.c_uint32),
                ("cycles", ctypes.c_uint32), ("active_ms", ctypes.c_uint32),
                ("faults", ctypes.c_uint32), ("cycle_seconds", ctypes.c_float),
                ("duration_available", ctypes.c_int), ("cue", ctypes.c_int),
                ("timing_reason", ctypes.c_int), ("assessment_available", ctypes.c_int),
                ("exercise_probability", ctypes.c_float * 3),
                ("mean_quality_probability", ctypes.c_float)]


def _manifest():
    manifest = json.loads((DATA / "manifest.json").read_text())
    return {item["file"]: item for item in manifest}


def parse_csv(path):
    """Parse any replay strictly; return rows and file SHA-256."""
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = []
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.reader(source, strict=True)
        try:
            header = next(reader)
        except (StopIteration, csv.Error) as error:
            raise ValueError(f"{path.name}: missing or malformed CSV header") from error
        if tuple(header) != HEADER:
            raise ValueError(f"{path.name}: header must exactly match {','.join(HEADER)}")
        try:
            for line, fields in enumerate(reader, start=2):
                if len(fields) != 7:
                    raise ValueError(f"{path.name}:{line}: expected 7 columns, got {len(fields)}")
                timestamp = fields[0]
                if not re.fullmatch(r"[0-9]+", timestamp):
                    raise ValueError(f"{path.name}:{line}: timestamp must be an unsigned integer")
                ms = int(timestamp)
                if ms > 0xffffffff:
                    raise ValueError(f"{path.name}:{line}: timestamp exceeds uint32")
                try:
                    values = tuple(float(item) for item in fields[1:])
                except ValueError as error:
                    raise ValueError(f"{path.name}:{line}: invalid acceleration value") from error
                if not all(math.isfinite(item) and math.isfinite(ctypes.c_float(item).value) for item in values):
                    raise ValueError(f"{path.name}:{line}: accelerations must be finite float32 values")
                rows.append((ms, values))
        except csv.Error as error:
            raise ValueError(f"{path.name}: malformed CSV: {error}") from error
    return rows, digest


def load_replay_csv(path):
    """Parse a declared demo replay and verify its manifest sample count."""
    path = Path(path)
    if path.parent.resolve() != DATA.resolve() or path.name not in _manifest():
        raise ValueError(f"replay must be one of the declared files in {DATA}")
    rows, digest = parse_csv(path)
    entry = _manifest()[path.name]
    if len(rows) != entry["samples"]:
        raise ValueError(f"{path.name}: manifest declares {entry['samples']} rows, found {len(rows)}")
    return rows, {**entry, "sha256": digest}


def _compile_library(directory):
    bridge = Path(directory) / "bridge.c"
    library = Path(directory) / "libtally_host.so"
    bridge.write_text('''#include "tally_app.h"
static TallyApp app;
static PairRuntime direct;
int host_configure(const TallyConfig *c) { app = (TallyApp){0}; pair_reset(&direct); return tally_configure(&app, c); }
int host_start(uint32_t ms) { pair_reset(&direct); return tally_start(&app, ms); }
int host_push(uint32_t ms, const float x[6], int *direct_status) {
    float ex[3], q;
    int status = tally_push(&app, ms, x);
    *direct_status = pair_push(&direct, ms, x, ex, &q);
    return status;
}
int host_finish(uint32_t ms) { return tally_finish(&app, ms); }
void host_output(TallyOutput *out) { *out = app.output; }
int host_cue(void) { return app.output.cue; }
uint32_t host_app_count(void) { return app.runtime.count; }
uint32_t host_direct_count(void) { return direct.count; }
int host_direct_series(float ex[3], float *q) { return pair_series(&direct, ex, q); }
''', encoding="utf-8")
    sources = [ROOT / "model/streaming/paired_stream.c",
               ROOT / "model/streaming/paired_runtime.c",
               ROOT / "model/feedback/feedback.c",
               ROOT / "model/feedback/feedback_policy.c",
               ROOT / "model/application/tally_app.c", bridge]
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", "-O2",
                    "-I", str(ROOT / "model/streaming"),
                    "-I", str(ROOT / "model/feedback"),
                    "-I", str(ROOT / "model/application"),
                    "-I", str(MODEL), *map(str, sources), "-lm", "-o", str(library)], check=True)
    lib = ctypes.CDLL(str(library))
    lib.host_configure.argtypes, lib.host_configure.restype = [ctypes.POINTER(Config)], ctypes.c_int
    lib.host_start.argtypes, lib.host_start.restype = [ctypes.c_uint32], ctypes.c_int
    lib.host_push.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_int)]
    lib.host_push.restype = ctypes.c_int
    lib.host_finish.argtypes, lib.host_finish.restype = [ctypes.c_uint32], ctypes.c_int
    lib.host_output.argtypes = [ctypes.POINTER(Output)]
    lib.host_cue.restype = ctypes.c_int
    lib.host_app_count.restype = lib.host_direct_count.restype = ctypes.c_uint32
    lib.host_direct_series.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
    lib.host_direct_series.restype = ctypes.c_int
    return lib


class HostReplay:
    """Reusable C-backed harness; supplied settings are explicitly test-only."""
    def __init__(self, exercise, count, min_seconds, target_seconds, max_seconds, prescription_id,
                 target_is_prescribed):
        if exercise not in EXERCISES:
            raise ValueError("exercise must be EAH, EFE, or SQZ")
        if not isinstance(count, int) or not 1 <= count <= 0xffffffff:
            raise ValueError("count must be an integer in uint32 range")
        if not prescription_id or "\0" in prescription_id:
            raise ValueError("prescription-id must be a non-empty string")
        values = (min_seconds, target_seconds, max_seconds)
        if not all(math.isfinite(value) for value in values) or not (0 < min_seconds <= target_seconds <= max_seconds):
            raise ValueError("timing bounds must be finite and satisfy 0 < min <= target <= max")
        self._temp = tempfile.TemporaryDirectory(prefix="tally-host-replay-")
        self.lib = _compile_library(self._temp.name)
        self._prescription = prescription_id.encode()
        timing = FeedbackConfig(1, target_seconds, min_seconds, max_seconds, int(target_is_prescribed),
                                 EXERCISES[exercise], self._prescription)
        self._config = Config(timing, count)
        if not self.lib.host_configure(ctypes.byref(self._config)):
            raise ValueError("TallyApp rejected the supplied test-only configuration")
        self.settings = {"exercise": exercise, "count": count, "min_seconds": min_seconds,
                         "target_seconds": target_seconds, "max_seconds": max_seconds,
                         "prescription_id": prescription_id,
                         "target_is_prescribed": bool(target_is_prescribed),
                         "status": "test-only supplied values; prescription status is caller-asserted"}

    def close(self):
        self._temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def replay(self, csv_path):
        path = Path(csv_path)
        if path.parent.resolve() == DATA.resolve() and path.name in _manifest():
            rows, manifest = load_replay_csv(path)
            data_provenance = {"dataset": "PHYTMO / Garcia-de-Villa et al., Scientific Data 9:266 (2022)",
                               "license": "CC BY 4.0", "source_description": "declared synchronized six-channel replay demo; source range differs and software clipping is approximate",
                               "file": manifest["file"], "file_sha256": manifest["sha256"],
                               "whole_recording_label": manifest["whole_recording_label"],
                               "recorded_exercise": manifest["exercise"], "samples": len(rows),
                               "rate_hz": manifest["rate_hz"], "units": manifest["units"],
                               "original_sources": manifest["sources"]}
        else:
            rows, digest = parse_csv(path)
            data_provenance = {"dataset": "unverified user-supplied replay CSV", "file": path.name,
                               "file_sha256": digest, "samples": len(rows),
                               "units": "g as declared by the CSV column names; not independently verified"}
        if not rows:
            raise ValueError("replay CSV must contain at least one data row")
        first_ms, last_ms = rows[0][0], rows[-1][0]
        if not self.lib.host_start(first_ms):
            raise RuntimeError("TallyApp failed to start")
        cycle_statuses = []
        cue_count = 0
        for index, (ms, values) in enumerate(rows):
            sample = (ctypes.c_float * 6)(*values)
            direct_status = ctypes.c_int()
            status = self.lib.host_push(ms, sample, ctypes.byref(direct_status))
            if status != direct_status.value:
                raise AssertionError(f"sample {index} ({ms} ms): TallyApp status {status} != PairRuntime {direct_status.value}")
            if status == 1:
                cycle_statuses.append({"sample_index": index, "timestamp_ms": ms, "status": status})
            cue_count += self.lib.host_cue() != 0
        if cue_count:
            raise AssertionError(f"timing boundary is unvalidated but TallyApp emitted {cue_count} cues")
        if not self.lib.host_finish(last_ms):
            raise RuntimeError("TallyApp failed to finish")
        output = Output()
        self.lib.host_output(ctypes.byref(output))
        direct_ex = (ctypes.c_float * 3)()
        direct_quality = ctypes.c_float()
        direct_available = self.lib.host_direct_series(direct_ex, ctypes.byref(direct_quality))
        direct_count = self.lib.host_direct_count()
        app_count = self.lib.host_app_count()
        if app_count != direct_count or output.cycles != len(cycle_statuses):
            raise AssertionError(f"cycle count mismatch: TallyApp {output.cycles}/{app_count}, PairRuntime {direct_count}")
        if bool(direct_available) != bool(direct_count):
            raise AssertionError("PairRuntime series availability does not match its cycle count")
        if direct_available:
            for i, (actual, expected) in enumerate(zip(output.exercise_probability, direct_ex)):
                if not math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-7):
                    raise AssertionError(f"exercise probability {i} differs: TallyApp {actual}, PairRuntime {expected}")
            if not math.isclose(output.mean_quality_probability, direct_quality.value, rel_tol=1e-6, abs_tol=1e-7):
                raise AssertionError("quality probability differs between TallyApp and PairRuntime")
        return {
            "data_provenance": data_provenance,
            "model_provenance": {"artifact": "model/paired-synchronized-causal/L/realtime_model.h",
                                 "metadata": json.loads((MODEL / "metadata.json").read_text()),
                                 "series_label_scope": "recording-level; cycle outputs are not anatomical-repetition labels"},
            "test_configuration": self.settings,
            "result": {"state": output.state, "cycles": output.cycles, "cycle_statuses": cycle_statuses,
                       "cycle_interpretation": "detected cycles; not validated anatomical repetitions",
                       "active_ms": output.active_ms, "faults": output.faults,
                       "assessment_available": bool(output.assessment_available),
                       "diagnostic_retained_cycle_mean_exercise_probabilities": list(output.exercise_probability),
                       "diagnostic_retained_cycle_mean_quality_probability": output.mean_quality_probability,
                       "probability_interpretation": "mean model P(study class 1: incorrect recording); not fraction of incorrect repetitions; assessment requires assessment_available",
                       "model_series_label": ("incorrect" if output.mean_quality_probability >= .5 else "correct") if output.assessment_available else None,
                       "direct_pair_runtime_count": direct_count,
                       "retained_cycles_since_last_reset": app_count,
                       "direct_pair_runtime_probabilities": list(direct_ex),
                       "direct_pair_runtime_mean_quality_probability": direct_quality.value,
                       "parity": "passed"},
            "timing_cues": {"count": cue_count, "unavailable_reason": "repetition boundary is not independently validated"},
            "limits": ["The manifest labels whole recordings, not individual cycles.",
                       "Replay is not a physical sensor or real-time latency test.",
                       "The supplied test-only timing values are not validated clinical prescriptions."]}


def replay(csv_path, *, exercise, count, min_seconds, target_seconds, max_seconds, prescription_id,
           target_is_prescribed):
    with HostReplay(exercise, count, min_seconds, target_seconds, max_seconds, prescription_id,
                    target_is_prescribed) as harness:
        return harness.replay(csv_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, default=DATA / "A01EAH0_1-left-pair.csv")
    parser.add_argument("--exercise", required=True, choices=EXERCISES)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--min-seconds", required=True, type=float)
    parser.add_argument("--target-seconds", required=True, type=float)
    parser.add_argument("--max-seconds", required=True, type=float)
    parser.add_argument("--prescription-id", required=True)
    parser.add_argument("--prescribed", action="store_true", required=True,
                        help="explicitly assert that the test-only target is prescribed")
    parser.add_argument("--out", type=Path, required=True, help="write the JSON report to this path")
    args = parser.parse_args()
    report = replay(args.csv, exercise=args.exercise, count=args.count, min_seconds=args.min_seconds,
                    target_seconds=args.target_seconds, max_seconds=args.max_seconds,
                    prescription_id=args.prescription_id,
                    target_is_prescribed=args.prescribed)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    args.out.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
