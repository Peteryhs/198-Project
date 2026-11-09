"""Self-contained parser and C parity checks for the host replay harness."""
import math
import tempfile
import unittest
from pathlib import Path

from tally_replay import DATA, HEADER, HostReplay, parse_csv


class ReplayCsvTests(unittest.TestCase):
    def parse_text(self, content):
        with tempfile.TemporaryDirectory(prefix="tally-csv-test-") as directory:
            path = Path(directory) / "fixture.csv"
            path.write_text(content, encoding="utf-8")
            return parse_csv(path)

    def test_rejects_wrong_header(self):
        with self.assertRaisesRegex(ValueError, "header must exactly match"):
            self.parse_text("bad,header\n")

    def test_rejects_wrong_field_count(self):
        with self.assertRaisesRegex(ValueError, "expected 7 columns"):
            self.parse_text(",".join(HEADER) + "\n0,1,2\n")

    def test_rejects_nonfinite_or_float32_overflow(self):
        for value in ("nan", "inf", "1e100"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite float32"):
                self.parse_text(",".join(HEADER) + f"\n0,{value},0,0,0,0,0\n")

    def test_rejects_timestamp_outside_uint32(self):
        with self.assertRaisesRegex(ValueError, "timestamp exceeds uint32"):
            self.parse_text(",".join(HEADER) + "\n4294967296,0,0,0,0,0,0\n")

    def test_rejects_signed_timestamp(self):
        with self.assertRaisesRegex(ValueError, "unsigned integer"):
            self.parse_text(",".join(HEADER) + "\n-1,0,0,0,0,0,0\n")

    def test_temp_csv_replay_matches_direct_runtime(self):
        source = DATA / "A01EAH0_1-left-pair.csv"
        with tempfile.TemporaryDirectory(prefix="tally-replay-test-") as directory:
            path = Path(directory) / "fixture.csv"
            path.write_bytes(source.read_bytes())
            with HostReplay("EAH", 10, .5, 1.5, 3, "TEST-FIXTURE", True) as harness:
                report = harness.replay(path)
        self.assertEqual(report["result"]["parity"], "passed")
        self.assertEqual(report["data_provenance"]["dataset"], "unverified user-supplied replay CSV")
        self.assertTrue(report["test_configuration"]["target_is_prescribed"])
        self.assertIn("diagnostic_retained_cycle_mean_exercise_probabilities", report["result"])
        self.assertNotIn("exercise_probabilities", report["result"])

    def test_gap_resets_pool_but_preserves_visible_set_count(self):
        with tempfile.TemporaryDirectory(prefix="tally-replay-gap-") as directory:
            path = Path(directory) / "fixture.csv"
            rows = [",".join(HEADER)]
            for i in range(2400):
                ms = i*10 + (100 if i >= 1200 else 0)
                value = 1 + .4*math.sin(2*math.pi*i/200)
                rows.append(str(ms) + "," + ",".join([str(value)]*6))
            path.write_text("\n".join(rows)+"\n")
            with HostReplay("EAH", 1, 1.8, 2, 2.2, "SYNTHETIC-ONLY", True) as harness:
                report = harness.replay(path)
        result = report["result"]
        self.assertEqual(result["parity"], "passed")
        self.assertEqual(result["faults"], 2)
        self.assertFalse(result["assessment_available"])
        self.assertGreater(result["cycles"], result["retained_cycles_since_last_reset"])


if __name__ == "__main__":
    unittest.main()
