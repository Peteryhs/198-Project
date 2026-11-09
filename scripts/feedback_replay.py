"""Replay declared duration fixtures through the portable C feedback function."""
import argparse
import ctypes
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXERCISES = {"EAH": 1, "EFE": 2, "SQZ": 3}


class Config(ctypes.Structure):
    _fields_ = [("category", ctypes.c_int), ("target_seconds", ctypes.c_float),
                ("min_seconds", ctypes.c_float), ("max_seconds", ctypes.c_float),
                ("target_is_prescribed", ctypes.c_int), ("exercise_id", ctypes.c_int),
                ("prescription_id", ctypes.c_char_p)]


class Measurement(ctypes.Structure):
    _fields_ = [("category", ctypes.c_int), ("exercise_id", ctypes.c_int),
                ("measured_seconds", ctypes.c_float),
                ("measurement_is_valid", ctypes.c_int),
                ("repetition_boundary_independently_validated", ctypes.c_int),
                ("boundary_evidence_id", ctypes.c_char_p),
                ("boundary_evidence_scope", ctypes.c_char_p)]


class Result(ctypes.Structure):
    _fields_ = [("cue", ctypes.c_int), ("reason", ctypes.c_int),
                ("target_applies", ctypes.c_int), ("target_seconds", ctypes.c_float),
                ("target_min_seconds", ctypes.c_float), ("target_max_seconds", ctypes.c_float),
                ("measured_seconds", ctypes.c_float), ("exercise_id", ctypes.c_int),
                ("prescription_id", ctypes.c_char_p),
                ("boundary_evidence_id", ctypes.c_char_p),
                ("boundary_evidence_scope", ctypes.c_char_p), ("message", ctypes.c_char_p)]


CUES = {0: "ABSTAIN", 1: "ON_TARGET", 2: "TOO_FAST", 3: "TOO_SLOW"}


def replay(config_path, cases_path):
    config_json = json.loads(config_path.read_text())
    cases_json = json.loads(cases_path.read_text())
    if "synthetic fixture" not in cases_json.get("provenance", ""):
        raise ValueError("replay cases must disclose synthetic fixture provenance")
    with tempfile.TemporaryDirectory(prefix="feedback-replay-") as temp:
        library = Path(temp) / "feedback.so"
        subprocess.run(["cc", "-std=c99", "-shared", "-fPIC", "-O2", "-I",
                        str(ROOT / "model/feedback"), str(ROOT / "model/feedback/feedback.c"),
                        "-lm", "-o", str(library)], check=True)
        lib = ctypes.CDLL(str(library))
        lib.feedback_evaluate.argtypes = [ctypes.POINTER(Config), ctypes.POINTER(Measurement)]
        lib.feedback_evaluate.restype = Result
        prescription = config_json["prescription_id"].encode()
        exercise = EXERCISES[config_json["exercise_id"]]
        config = Config(1, config_json["target_seconds"], config_json["min_seconds"],
                        config_json["max_seconds"], config_json["target_is_prescribed"], exercise, prescription)
        outcomes = []
        for case in cases_json["cases"]:
            evidence_id, scope = case["evidence_id"].encode(), case["scope"].encode()
            measurement = Measurement(1, exercise, case["measured_seconds"], case["valid"],
                                      case["boundary_validated"], evidence_id, scope)
            result = lib.feedback_evaluate(ctypes.byref(config), ctypes.byref(measurement))
            cue = CUES[result.cue]
            if cue != case["expected"]:
                raise AssertionError(f"{case['name']}: expected {case['expected']}, got {cue}")
            outcomes.append((case["name"], cue, result.reason, result.target_applies,
                             result.measured_seconds, result.target_seconds, result.target_min_seconds,
                             result.target_max_seconds, result.prescription_id.decode() if result.prescription_id else "",
                             result.boundary_evidence_id.decode() if result.boundary_evidence_id else "",
                             result.boundary_evidence_scope.decode() if result.boundary_evidence_scope else "",
                             result.message.decode()))
        return outcomes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/feedback-example.json")
    parser.add_argument("--cases", type=Path, default=ROOT / "docs/runs/phase3/feedback-cases.json")
    args = parser.parse_args()
    for name, cue, reason, applies, measured, target, lower, upper, prescription, evidence, scope, message in replay(args.config, args.cases):
        print(f"{name}: {cue}; reason={reason}; target_applies={applies}; measured={measured:g}s; "
              f"target={target:g}s; target_min={lower:g}s; target_max={upper:g}s; prescription={prescription}; "
              f"boundary_evidence={evidence}; scope={scope}; message={message}")
    print("No real or patient repetition data used; fixture evidence is not deployment validation.")


if __name__ == "__main__":
    main()
