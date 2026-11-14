"""Tests for the paired board-to-parser stream.

Run from the repository root:

    .venv/bin/python -m unittest discover -s scripts -p 'test_tally_paired_stream.py' -v
"""
from __future__ import annotations

import io
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import tally_paired_stream as tp  # noqa: E402

HEADER = '#TALLY2 fs=100 unit=g range=3 side=L'


def sample(seq: int, t_ms: int, value: float = 1.0) -> str:
    return (f'S {seq} {t_ms} +0.00000000 +0.00000000 {value:+.8f} '
            f'+0.00000000 +0.00000000 {value:+.8f}')


def moving_set(seconds: float = 8.0, hz: float = 1.2, seq_start: int = 0,
               t_start: int = 0, rate: int = 100) -> list[str]:
    """A synthetic set with a periodic forearm magnitude, enough peaks for a verdict."""
    lines = []
    n = int(seconds * rate)
    for i in range(n):
        a = 0.6 * math.sin(2 * math.pi * hz * (i / rate))
        lines.append(sample(seq_start + i, t_start + i * 10, 1.0 + a))
    return lines


def capture(lines: list[str]) -> str:
    return '\n'.join(lines) + '\n'


def run_lines(text: str, side: str | None = None) -> dict:
    buffer = io.StringIO()
    tp.run(io.StringIO(text), side_override=side, out=buffer, emit=False)
    return json.loads(buffer.getvalue().splitlines()[-1]) if buffer.getvalue() else {}


class HeaderAndSampleParsing(unittest.TestCase):
    def test_header_accepted(self):
        fields = tp.parse_header(HEADER.split())
        self.assertEqual(fields['side'], 'L')
        self.assertEqual(fields['fs'], '100')
        self.assertEqual(fields['range'], '3')

    def test_header_rejects_unknown_side(self):
        with self.assertRaises(tp.StreamError):
            tp.parse_header('#TALLY2 fs=100 unit=g range=3 side=X'.split())

    def test_header_rejects_other_rate(self):
        with self.assertRaises(tp.StreamError):
            tp.parse_header('#TALLY2 fs=200 unit=g range=3 side=L'.split())

    def test_header_rejects_other_unit(self):
        with self.assertRaises(tp.StreamError):
            tp.parse_header('#TALLY2 fs=100 unit=m/s2 range=3 side=L'.split())

    def test_sample_accepted(self):
        seq, t_ms, values = tp.parse_sample(sample(0, 0).split())
        self.assertEqual((seq, t_ms), (0, 0))
        self.assertEqual(values.shape, (6,))

    def test_sample_rejects_missing_fields(self):
        with self.assertRaises(tp.StreamError):
            tp.parse_sample('S 0 0 +0.0 +0.0 +1.0 +0.0 +0.0'.split())

    def test_sample_rejects_non_finite(self):
        with self.assertRaises(tp.StreamError):
            tp.parse_sample(('S 0 0 nan +0.0 +1.0 +0.0 +0.0 +1.0').split())

    def test_sample_rejects_text(self):
        with self.assertRaises(tp.StreamError):
            tp.parse_sample(('S 0 0 +0.0 hello +1.0 +0.0 +0.0 +1.0').split())


class SetValidation(unittest.TestCase):
    def test_missing_header_is_rejected(self):
        record = run_lines(capture(moving_set(0.2)))
        self.assertEqual(record['status'], 'rejected')
        self.assertIn('sample before header', record['diagnostics'][0])

    def test_sequence_gap_is_rejected(self):
        lines = [HEADER] + moving_set(0.2)
        lines[-5] = sample(int(lines[-5].split()[1]) + 3, int(lines[-5].split()[2]))
        record = run_lines(capture(lines))
        self.assertEqual(record['status'], 'rejected')
        self.assertIn('sequence break', record['diagnostics'][0])

    def test_backwards_time_is_rejected(self):
        lines = [HEADER] + moving_set(0.2)
        parts = lines[-5].split()
        parts[2] = str(int(parts[2]) - 500)
        lines[-5] = ' '.join(parts)
        record = run_lines(capture(lines))
        self.assertEqual(record['status'], 'rejected')
        self.assertIn('timestamp not increasing', record['diagnostics'][0])

    def test_rate_outside_tolerance_is_rejected(self):
        slow = [HEADER] + [sample(i, i * 30) for i in range(40)] + ['E done']
        record = run_lines(capture(slow))
        self.assertEqual(record['status'], 'rejected')
        self.assertIn('rate_out_of_tolerance', record['diagnostics'])

    def test_side_guard(self):
        text = capture([HEADER] + moving_set(0.2) + ['E done'])
        record = run_lines(text, side='R')
        self.assertEqual(record['status'], 'rejected')
        self.assertIn('--side R but header says L', record['diagnostics'][0])

    def test_aborted_set_is_not_scored(self):
        text = capture([HEADER] + moving_set(2.0) + ['E aborted'])
        record = run_lines(text)
        self.assertEqual(record['status'], 'rejected')
        self.assertIsNone(record['verdict'])

    def test_eof_without_end_marker_is_rejected(self):
        text = capture([HEADER] + moving_set(0.5))
        record = run_lines(text)
        self.assertEqual(record['status'], 'rejected')
        self.assertIn('incomplete_set_at_eof', record['diagnostics'][0])


class ReplyChannel(unittest.TestCase):
    def test_reply_line_format(self):
        self.assertEqual(tp.reply_line({'verdict': 'correct', 'mean_p_wrong': 0.1843, 'exercise': 'EFE'}),
                         'V correct 0.184 EFE\n')

    def test_reply_line_for_unscored_set(self):
        self.assertEqual(tp.reply_line({'verdict': None, 'mean_p_wrong': None, 'exercise': None}),
                         'V unknown nan -\n')

    def test_run_sends_one_reply_per_set(self):
        sent = []
        text = capture([HEADER] + moving_set(8.0) + ['E done', HEADER] + moving_set(8.0) + ['E aborted'])
        tp.run(io.StringIO(text), out=None, emit=False, reply=sent.append)
        self.assertEqual(len(sent), 2)
        self.assertTrue(sent[0].startswith('V correct ') or sent[0].startswith('V wrong '))
        self.assertEqual(sent[1], 'V unknown nan -\n')


class Scoring(unittest.TestCase):
    def test_moving_set_is_scored(self):
        text = capture([HEADER] + moving_set(8.0) + ['E done'])
        record = run_lines(text)
        self.assertEqual(record['status'], 'scored')
        self.assertGreaterEqual(record['vector_count'], 3)
        self.assertIn(record['verdict'], ('correct', 'wrong'))
        self.assertIn(record['exercise'], ('EAH', 'EFE', 'SQZ'))
        self.assertAlmostEqual(record['measured_rate_hz'], 100.0, places=1)
        self.assertTrue(0.0 <= record['mean_p_wrong'] <= 1.0)

    def test_flat_set_has_no_verdict(self):
        text = capture([HEADER] + [sample(i, i * 10) for i in range(300)] + ['E done'])
        record = run_lines(text)
        self.assertEqual(record['status'], 'insufficient_reps')
        self.assertIsNone(record['verdict'])

    def test_wire_round_trip_keeps_every_sample(self):
        rng = np.random.default_rng(0)
        x = np.column_stack([np.sin(np.arange(600) / 12.0)] * 6) + rng.normal(0, 0.01, (600, 6))
        wire = tp.wire_from_pair(x, 'L')
        record = run_lines(wire)
        self.assertEqual(record['sample_count'], 600)
        self.assertEqual(record['side'], 'L')

    def test_both_sides_have_a_model(self):
        for side in ('L', 'R'):
            weights = tp.load_model(side)
            p, label = tp.predict(weights, np.zeros(61, dtype=np.float32))
            self.assertTrue(0.0 <= p <= 1.0)
            self.assertIn(label, ('EAH', 'EFE', 'SQZ'))


if __name__ == '__main__':
    unittest.main()
