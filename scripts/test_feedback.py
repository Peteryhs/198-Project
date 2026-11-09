import ctypes
import subprocess
import tempfile
import unittest
from pathlib import Path

from feedback_replay import Config, Measurement, Result, ROOT, replay


class FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="feedback-test-")
        library = Path(cls.temp.name) / "feedback.so"
        subprocess.run(["cc", "-std=c99", "-shared", "-fPIC", "-O2", "-I",
                        str(ROOT / "model/feedback"), str(ROOT / "model/feedback/feedback.c"),
                        "-lm", "-o", str(library)], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.feedback_evaluate.argtypes = [ctypes.POINTER(Config), ctypes.POINTER(Measurement)]
        cls.lib.feedback_evaluate.restype = Result

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def evaluate(self, config, measurement):
        return self.lib.feedback_evaluate(ctypes.byref(config), ctypes.byref(measurement))

    def test_fixture_replay(self):
        results = replay(ROOT / "configs/feedback-example.json", ROOT / "docs/runs/phase3/feedback-cases.json")
        self.assertEqual(len(results), 5)

    def test_inclusive_range_and_simultaneous_deviation_abstention(self):
        config = Config(1, 1.5, 1.2, 1.8, 1, 1, b"clinician-approved-v1")
        measurement = Measurement(1, 1, 1.2, 1, 1, b"video-clip-44", b"independent-rater-boundaries")
        self.assertEqual(self.evaluate(config, measurement).cue, 1)
        config.target_seconds = config.max_seconds
        measurement.measured_seconds = config.max_seconds
        self.assertEqual(self.evaluate(config, measurement).cue, 1)
        # An unsupported category cannot trigger a tempo cue.
        measurement.category = 2
        result = self.evaluate(config, measurement)
        self.assertEqual((result.cue, result.reason), (0, 1))
        measurement.category = 1
        measurement.exercise_id = 2
        result = self.evaluate(config, measurement)
        self.assertEqual((result.cue, result.reason, result.target_applies), (0, 3, 0))

    def test_rejects_nonfinite_and_inconsistent_config_and_measurements(self):
        valid = Measurement(1, 1, 1.0, 1, 1, b"video-1", b"double-rated-video")
        for target, lower, upper in [(float("nan"), 1.2, 1.8), (1.5, float("inf"), 1.8),
                                     (1.5, 1.2, float("inf"))]:
            config = Config(1, target, lower, upper, 1, 1, b"prescription-v1")
            self.assertEqual(self.evaluate(config, valid).reason, 2)
        config = Config(1, 1.5, 1.8, 1.2, 1, 1, b"prescription-v1")
        self.assertEqual(self.evaluate(config, valid).reason, 2)
        config = Config(1, 1.5, 1.2, 1.8, 1, 1, b"prescription-v1")
        valid.measured_seconds = float("inf")
        self.assertEqual(self.evaluate(config, valid).reason, 4)

    def test_requires_prescription_and_boundary_provenance(self):
        config = Config(1, 1.5, 1.2, 1.8, 0, 1, b"example")
        measurement = Measurement(1, 1, 1.0, 1, 1, b"evidence", b"video-rater")
        self.assertEqual(self.evaluate(config, measurement).reason, 2)
        config.target_is_prescribed = 1
        measurement.repetition_boundary_independently_validated = 0
        self.assertEqual(self.evaluate(config, measurement).reason, 5)
        measurement.repetition_boundary_independently_validated = 1
        measurement.boundary_evidence_scope = b""
        self.assertEqual(self.evaluate(config, measurement).reason, 6)

    def test_null_pointers_unsupported_categories_and_invalid_flag(self):
        measurement = Measurement(1, 1, 1.0, 1, 1, b"evidence", b"double-rated-video")
        self.assertEqual(self.lib.feedback_evaluate(None, ctypes.byref(measurement)).reason, 2)
        config = Config(1, 1.5, 1.2, 1.8, 1, 1, b"prescription-v1")
        self.assertEqual(self.lib.feedback_evaluate(ctypes.byref(config), None).reason, 2)
        for category in (2, 3, 4, 5):
            measurement.category = category
            result = self.evaluate(config, measurement)
            self.assertEqual((result.cue, result.reason), (0, 1))
        measurement.category = 1
        measurement.exercise_id = 1
        measurement.measurement_is_valid = 0
        self.assertEqual(self.evaluate(config, measurement).reason, 4)


if __name__ == "__main__":
    unittest.main()
