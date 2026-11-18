"""Host-only checks: python3.14 -B backend/src/test/python/test_tally_app.py."""
import concurrent.futures
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "backend/src/main/python"), str(ROOT / "reference/scripts")]
import tally_app


def synthetic_wire(side="L", count=60_000):
    lines = [f"#TALLY2 fs=100 unit=g range=3 side={side}"]
    for i in range(count):
        phase = 2 * math.pi * 0.4 * i / 100
        row = (0.2 * math.sin(phase), 0.1 * math.cos(phase), 1 + 0.3 * math.sin(phase),
               0.3 * math.sin(phase + 0.2), 0.2 * math.cos(phase + 0.1),
               1 + 0.6 * math.sin(phase))
        lines.append(f"S {i} {i * 10} " + " ".join(f"{v:+.8f}" for v in row))
    return "\n".join(lines) + "\nE done\n"


def real_set_wire(set_id):
    """data/real-sets CSV (mV) to the app's #TALLY2 wire through its stored calibration."""
    lines = (ROOT / "data/real-sets" / f"{set_id}.csv").read_text(encoding="ascii").splitlines()
    meta = json.loads(lines[0].removeprefix("# meta="))
    cal = meta["calibration"]
    out = [f"#TALLY2 fs=100 unit=g range=3 side={meta['side']}"]
    for row in lines[3:]:
        f = row.split(",")
        g = [(int(v) - o) / k for v, o, k in zip(f[4:], cal["offset_mv"], cal["mv_per_g"])]
        out.append(f"S {f[2]} {int(f[3]) // 1000} " + " ".join(f"{v:+.8f}" for v in g))
    app_reps = len(json.loads(lines[1].removeprefix("# result="))["reps"])
    return "\n".join(out) + "\nE done\n", app_reps


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashes = json.loads(tally_app.init(str(ROOT / "reference/model")))

    def test_model_and_scorer_hashes(self):
        for side in "LR":
            model = ROOT / f"reference/model/paired-synchronized-offline/{side}/realtime_model.npz"
            self.assertEqual(self.hashes[side], hashlib.sha256(model.read_bytes()).hexdigest())
        source = b"".join((ROOT / "reference/scripts" / name).read_bytes()
                          for name in ("stdlib_runtime.py", "tally_stdlib.py"))
        self.assertEqual(tally_app.scorer_version(), hashlib.sha256(source).hexdigest())

    def test_synthetic_600_seconds_on_worker_without_signals(self):
        wire = synthetic_wire()
        start = time.perf_counter()
        with patch("signal.signal", side_effect=AssertionError("worker must not use signals")):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as worker:
                result = json.loads(worker.submit(tally_app.score_wire, wire).result())
        record = result["record"]
        self.assertEqual(record["status"], "scored")
        self.assertEqual(record["sample_count"], 60_000)
        self.assertEqual(record["measured_rate_hz"], 100.0)
        self.assertGreaterEqual(len(record["repetitions"]), 3)
        self.assertEqual(len(result["reply"]), len(record["repetitions"]) + 1)
        self.assertTrue(result["reply"][-1].startswith("V "))
        chart = record["chart"]
        self.assertLessEqual(len(chart["samples"]), 1200)
        self.assertEqual(0.0, chart["samples"][0]["time_s"])
        self.assertEqual(599.99, chart["samples"][-1]["time_s"])
        self.assertEqual(len(record["repetitions"]), len(chart["reps"]))
        for rep, span in zip(record["repetitions"], chart["reps"]):
            self.assertEqual(rep["rep_index"], span["index"])
            self.assertAlmostEqual(rep["duration_s"], span["end_s"] - span["start_s"] + 0.01, places=3)
        print(f"measured synthetic: samples={record['sample_count']} bytes={len(wire.encode('ascii'))} "
              f"reps={len(record['repetitions'])} seconds={time.perf_counter() - start:.3f} "
              f"reply={result['reply'][-1].strip()}")

    def test_wrong_end_and_sequence_gap_rejected(self):
        wire = synthetic_wire(side="R", count=800)
        for broken in (wire.replace("E done", "E timing"),
                       wire.replace("S 1 10 ", "S 2 10 ")):
            result = json.loads(tally_app.score_wire(broken))
            self.assertEqual(result["record"]["status"], "rejected")
            self.assertNotIn("chart", result["record"])
            self.assertEqual(result["reply"], ["V unknown nan -\n"])

    def test_exactly_one_record_required(self):
        with self.assertRaises(ValueError):
            tally_app.score_wire("")
        with self.assertRaises(ValueError):
            tally_app.score_wire(synthetic_wire(count=10) * 2)

    def test_rep_windows_are_scored_by_the_validated_features_and_model(self):
        wire = synthetic_wire(side="R", count=1200)
        out = io.StringIO()
        tally_app._ts.run(io.StringIO(wire), emit=False, out=out, models=tally_app._M, live=False)
        reference = json.loads(out.getvalue())
        result = json.loads(tally_app.score_wire(wire))
        record = result["record"]
        for key in ("end", "sample_count", "side", "measured_rate_hz"):
            self.assertEqual(reference[key], record[key])
        values = [tally_app._ts.parse_sample(line.split())[2] for line in wire.splitlines() if line.startswith("S ")]
        windows = tally_app.rep_windows(values)
        self.assertEqual(len(windows), len(record["repetitions"]))
        rt = tally_app._ts.rt
        for (a, b, p), rep in zip(windows, record["repetitions"]):
            row = rt.build_rows(values[a:b], [p - a])[0]
            p_wrong, label = rt.predict(tally_app._M["R"], row)
            self.assertEqual((rep["p_wrong"], rep["exercise"], rep["duration_s"]),
                             (round(p_wrong, 6), label, round(row[0], 3)))
        self.assertEqual(len(result["reply"]), len(windows) + 1)
        self.assertEqual(len(record["chart"]["reps"]), len(windows))

    def test_one_wrong_rep_makes_the_set_wrong_even_when_the_mean_is_low(self):
        reps = [{"rep_index": i + 1, "verdict": "wrong" if p >= 0.5 else "correct", "exercise": "X",
                 "duration_s": 2.0, "p_wrong": p} for i, p in enumerate((0.6, 0.6, 0.6, 0.01, 0.01))]
        mean = sum(rep["p_wrong"] for rep in reps) / 5
        record = {"status": "scored", "verdict": "wrong" if mean >= 0.5 else "correct",  # score_set's rule
                  "mean_p_wrong": round(mean, 6), "exercise": "X", "repetitions": reps}
        tally_app._decide(record, None)
        self.assertEqual((record["mean_verdict"], record["mean_p_wrong"]), ("correct", 0.364))
        self.assertEqual((record["verdict"], record["wrong_reps"]), ("wrong", 3))

    def test_intended_exercise_that_differs_from_the_class_is_wrong_exercise(self):
        wire = synthetic_wire(side="R", count=1200)
        plain = json.loads(tally_app.score_wire(wire))["record"]
        other = next(c for c in json.loads(tally_app.exercise_classes()) if c != plain["exercise"])
        result = json.loads(tally_app.score_wire(wire, other))
        record = result["record"]
        self.assertEqual((record["verdict"], record["exercise_check"], record["intended_exercise"]),
                         ("wrong_exercise", "mismatch", other))
        self.assertEqual(record["exercise"], plain["exercise"])
        self.assertTrue(result["reply"][-1].startswith("V wrong_exercise "))
        same = json.loads(tally_app.score_wire(wire, plain["exercise"]))["record"]
        self.assertEqual((same["exercise_check"], same["verdict"]), ("match", plain["verdict"]))
        with self.assertRaises(ValueError):
            tally_app.score_wire(wire, "not-a-class")

    def test_unspecified_exercise_reports_the_class_as_unverified(self):
        record = json.loads(tally_app.score_wire(synthetic_wire(side="R", count=1200)))["record"]
        self.assertIsNone(record["intended_exercise"])
        self.assertEqual(record["exercise_check"], "unverified")
        self.assertIn(record["verdict"], ("correct", "wrong"))

    def test_chart_decimation_preserves_actual_extremes(self):
        wire = synthetic_wire(count=5000)
        parsed = [tally_app._ts.parse_sample(line.split()) for line in wire.splitlines() if line.startswith("S ")]
        chart = tally_app._chart_data(parsed, {"status": "insufficient_reps"})
        samples = [row[2] for row in parsed]
        expected = max(math.sqrt(sum(v * v for v in row[3:])) for row in samples)
        self.assertEqual(expected, max(point["forearm_g"] for point in chart["samples"]))
        self.assertLessEqual(len(chart["samples"]), 1200)
        self.assertTrue(all(a["time_s"] < b["time_s"] for a, b in zip(chart["samples"], chart["samples"][1:])))

    def test_still_set_is_no_movement_not_reps(self):
        # Derived: board lying still, 3 mV white ADC noise through the nominal 1650 mV / 330 mV/g line.
        rng, lines = random.Random(5), ["#TALLY2 fs=100 unit=g range=3 side=L"]
        for i in range(6000):
            g = [(round(1650 + 330 * up + rng.gauss(0, 3)) - 1650) / 330 for up in (0, 0, 1, 0, 0, 1)]
            lines.append(f"S {i} {i * 10} " + " ".join(f"{v:+.8f}" for v in g))
        wire = "\n".join(lines) + "\nE done\n"
        raw = io.StringIO()
        tally_app._ts.run(io.StringIO(wire), emit=False, out=raw, models=tally_app._M, live=False)
        self.assertGreater(json.loads(raw.getvalue())["vector_count"], 30)  # the unchanged scorer invents reps
        result = json.loads(tally_app.score_wire(wire))
        record = result["record"]
        self.assertEqual((record["status"], record["diagnostics"], record["repetitions"]),
                         ("insufficient_reps", ["no_movement"], []))
        self.assertIsNone(record["exercise"])
        self.assertEqual(result["reply"], ["V unknown nan -\n"])
        self.assertEqual(record["chart"]["reps"], [])

    def test_real_sets_count_at_most_nine_reps_and_skip_still_periods(self):
        # Owner: each set is 3 correct + 3 incorrect EAH reps and a few seconds of spasm, so 6..9 reps.
        # Still periods read off the raw upper-arm y channel (flat, <= 18 mV sd); see ANALYSIS.md.
        still = {"1183368908": [(7.6, 9.4), (11.6, 13.2), (15.2, 17.6)],
                 "1852035896": [(14.6, 15.9)], "2407633944": [(0.25, 0.75), (7.5, 8.3)]}
        for set_id, periods in still.items():
            with self.subTest(set_id=set_id):
                wire, app_reps = real_set_wire(set_id)
                out = io.StringIO()
                tally_app._ts.run(io.StringIO(wire), emit=False, out=out, models=tally_app._M, live=False)
                self.assertEqual(json.loads(out.getvalue())["vector_count"], app_reps)  # the defect reproduces
                record = json.loads(tally_app.score_wire(wire, "EAH"))["record"]
                self.assertEqual(record["status"], "scored")
                self.assertTrue(6 <= len(record["repetitions"]) <= 9, len(record["repetitions"]))
                for span in record["chart"]["reps"]:
                    for lo, hi in periods:
                        overlap = min(span["end_s"], hi) - max(span["start_s"], lo)
                        self.assertLess(overlap, 0.2, (span, lo, hi))

    @unittest.skipUnless(os.environ.get("TALLY_KOTLIN_WIRE"), "run backend/tools/host_checks.py for Kotlin wire")
    def test_kotlin_calibrated_wire(self):
        wire = Path(os.environ["TALLY_KOTLIN_WIRE"]).read_text(encoding="ascii")
        record = json.loads(tally_app.score_wire(wire))["record"]
        self.assertEqual(record["status"], "scored")
        self.assertEqual(record["sample_count"], 60_000)
        self.assertEqual(record["side"], "L")
        self.assertEqual(record["measured_rate_hz"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
