"""No third-party test dependencies; includes real Linux PTYs and subprocesses.

Run: python3.10 -B -m unittest discover -s scripts -p test_shield_hardening.py -v
"""
import errno
import io
import json
import math
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stdlib_runtime as rt
import tally_stdlib as ts

HEADER = '#TALLY2 fs=100 unit=g range=3 side=L'
UNKNOWN = 'V unknown nan -\n'


def sample(i, t=None, value=1.0):
    ux, uy = .001 * math.sin(i * .2), .001 * math.cos(i * .17)
    fx, fy = .001 * math.sin(i * .13), .001 * math.cos(i * .11)
    return (f'S {i} {i * 10 if t is None else t} {ux:.8f} {uy:.8f} '
            f'{value:.8f} {fx:.8f} {fy:.8f} {value:.8f}')


def moving(side='L', n=800):
    return ([HEADER.replace('side=L', 'side=' + side)] +
            [sample(i, value=1 + .6 * math.sin(2 * math.pi * 1.2 * i / 100)) for i in range(n)] +
            ['E done'])


def run_lines(lines, **kwargs):
    output, sent = io.StringIO(), []
    ts.run(io.StringIO('\n'.join(lines) + '\n'), out=output, emit=False,
           reply=sent.append, **kwargs)
    return [json.loads(line) for line in output.getvalue().splitlines()], sent


class ParserTests(unittest.TestCase):
    def test_header_schema(self):
        self.assertEqual(ts.parse_header(HEADER.split())['side'], 'L')
        for bad in [HEADER.replace('#TALLY2', '#WRONG'), HEADER + ' side=R',
                    HEADER.replace('range=3', 'range=9'), HEADER.replace('fs=100 ', ''),
                    HEADER.replace('unit=g', 'unit=m/s2'), HEADER.replace('side=L', 'side=X')]:
            with self.subTest(bad=bad), self.assertRaises(ts.StreamError):
                ts.parse_header(bad.split())

    def test_malformed_header_owns_end_and_next_header_recovers(self):
        recs, sent = run_lines([HEADER.replace('fs=100', 'fs=99'), sample(0), 'E done'] + moving())
        self.assertEqual([r['status'] for r in recs], ['rejected', 'scored'])
        self.assertEqual(sent[0], UNKNOWN)

    def test_other_side_guard_and_auto_side(self):
        recs, sent = run_lines(moving('R'), side_override='L')
        self.assertEqual(recs[0]['status'], 'rejected')
        self.assertEqual(sent, [UNKNOWN])
        recs, _ = run_lines(moving('L') + moving('R'))
        self.assertEqual([r['side'] for r in recs], ['L', 'R'])
        self.assertTrue(all(r['status'] == 'scored' for r in recs))

    def test_sequence_and_timestamps_and_numeric_faults(self):
        for samples in [[sample(1)], [sample(0), sample(2)], [sample(0), sample(0, 10)],
                        [sample(0), sample(1, 20), sample(2, 10)],
                        [sample(0).replace('1.00000000', 'nan')],
                        [sample(0).replace('1.00000000', '1e300')],
                        [sample(0).replace('1.00000000', 'inf')],
                        [sample(0, -1)], [sample(0, 610001)], ['S 0 0 1 2']]:
            with self.subTest(samples=samples):
                recs, sent = run_lines([HEADER] + samples + ['E done'])
                self.assertEqual(recs[0]['status'], 'rejected')
                self.assertEqual(sent, [UNKNOWN])

    def test_reset_after_fault_and_two_headers_supersede_without_extra_verdict(self):
        for first in [[HEADER], [HEADER, sample(0)], [HEADER, 'broken', sample(0)]]:
            recs, sent = run_lines(first + moving('R'))
            self.assertEqual(recs[0]['end'], 'reset')
            self.assertEqual(recs[-1]['status'], 'scored')
            self.assertEqual(recs[-1]['side'], 'R')
            self.assertEqual(len([s for s in sent if s.startswith('V ')]), 1)

    def test_garbage_before_header_and_duplicate_or_orphan_end(self):
        recs, sent = run_lines(['noise', sample(30), 'E done', '#WRONG side=R'] +
                               moving() + ['E done', 'E aborted', sample(0), 'E done'])
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]['status'], 'scored')
        self.assertEqual(len([s for s in sent if s.startswith('V ')]), 1)

    def test_aborted_overflow_malformed_and_eof(self):
        for end in ['E aborted', 'E overflow', 'E wat', 'E done extra', 'E']:
            recs, sent = run_lines([HEADER, sample(0), sample(1), end])
            self.assertEqual(recs[0]['status'], 'rejected')
            self.assertEqual(sent, [UNKNOWN])
        recs, sent = run_lines([HEADER, sample(0)])
        self.assertEqual(recs[0]['diagnostics'], ['incomplete_set_at_eof'])
        self.assertEqual(sent, [])

    def test_limits_rate_and_scoring_failure(self):
        with patch.object(ts, 'MAX_SAMPLES', 2):
            recs, sent = run_lines([HEADER, sample(0), sample(1), sample(2), 'E done'])
        self.assertEqual(recs[0]['status'], 'rejected')
        self.assertEqual(sent, [UNKNOWN])
        recs, _ = run_lines([HEADER, sample(0, value=1.0),
                             sample(1, 30, value=1.1), 'E done'])
        self.assertEqual(recs[0]['diagnostics'], ['rate_out_of_tolerance'])
        for error in [OverflowError('large feature'), TimeoutError('scoring_timeout')]:
            with patch.object(rt, 'score_set', side_effect=error):
                recs, sent = run_lines([HEADER, sample(0), sample(1), 'E done'])
            self.assertEqual(recs[0]['status'], 'rejected')
            self.assertEqual(sent, [UNKNOWN])

    def test_reply_precedes_optional_io_failure_and_transport_failure_is_fatal(self):
        class Broken:
            def write(self, text):
                raise OSError(errno.ENOSPC, 'full')
        sent = []
        ts.run(io.StringIO('\n'.join(moving())), emit=False, out=Broken(), reply=sent.append)
        self.assertTrue(sent[-1].startswith('V '))
        with self.assertRaises(OSError):
            ts.run(io.StringIO('\n'.join(moving())), emit=False, reply=Broken().write)

    def test_live_idle_and_total_time_expire_without_unsolicited_verdict(self):
        class Stream:
            def __iter__(self):
                yield HEADER
                yield sample(0)
                clock[0] += 3
                yield None
                yield 'E done'
                yield from moving()
        clock = [0.0]
        out, sent = io.StringIO(), []
        with patch.object(ts.time, 'monotonic', side_effect=lambda: clock[0]):
            ts.run(Stream(), out=out, emit=False, reply=sent.append, live=True)
        recs = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(recs[0]['diagnostics'], ['incomplete_set_timeout'])
        self.assertEqual(recs[1]['status'], 'scored')
        self.assertEqual(len([s for s in sent if s.startswith('V ')]), 1)
        clock = [0.0]
        class Endless:
            def __iter__(self):
                yield HEADER
                for i in range(4):
                    clock[0] += 1
                    yield sample(i)
                yield 'E done'
        with patch.object(ts, 'SET_SECONDS', 3), patch.object(ts.time, 'monotonic', side_effect=lambda: clock[0]):
            out, sent = io.StringIO(), []
            ts.run(Endless(), out=out, emit=False, reply=sent.append, live=True)
        self.assertIn('incomplete_set_timeout', out.getvalue())
        self.assertEqual(sent, [])

    def test_continuous_faulted_set_keeps_end_association(self):
        clock = [0.0]
        class Stream:
            def __iter__(self):
                yield HEADER
                yield 'bad'
                for i in range(4):
                    clock[0] += 1
                    yield sample(i)
                yield 'E done'
        sent = []
        with patch.object(ts.time, 'monotonic', side_effect=lambda: clock[0]):
            ts.run(Stream(), emit=False, reply=sent.append, live=True)
        self.assertEqual(sent, [UNKNOWN])

    def test_malformed_header_refreshes_timer_after_long_uptime(self):
        clock = [0.0]
        class Stream:
            def __iter__(self):
                clock[0] = 1000
                yield '#TALLY2 fs=99 side=L'
                yield 'E done'
        sent = []
        with patch.object(ts.time, 'monotonic', side_effect=lambda: clock[0]):
            ts.run(Stream(), emit=False, reply=sent.append, live=True)
        self.assertEqual(sent, [UNKNOWN])

    def test_capture_bounded_ascii_reader(self):
        lines = list(ts.bounded_lines(io.BytesIO(b'x' * 100000 + b'\n' + HEADER.encode() + b'\r\n')))
        self.assertLessEqual(max(map(len, lines)), ts.MAX_LINE + 3)
        recs, sent = io.StringIO(), []
        ts.run(iter([HEADER.encode(), b'S 0 0 0 0 1 0 0 \xff\n', b'E done\n']),
               out=recs, emit=False, reply=sent.append)
        self.assertIn('rejected', recs.getvalue())
        self.assertEqual(sent, [UNKNOWN])

    def test_real_scoring_timer(self):
        before = signal.getsignal(signal.SIGALRM)
        with self.assertRaises(TimeoutError):
            with ts.scoring_budget(.02):
                time.sleep(.2)
        self.assertEqual(signal.getsignal(signal.SIGALRM), before)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0], 0)

    def test_log_rotation_and_failure_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'results.jsonl'
            log = ts.BoundedLog(path, limit=64)
            log.write('a\n' * 16)
            log.write('b\n' * 16)
            log.write('c\n' * 16)
            self.assertEqual(path.read_text(), 'c\n' * 16)
            self.assertEqual(Path(str(path) + '.1').stat().st_size, 64)
            ts.BoundedLog(path, limit=64).write('d\n')
            self.assertTrue(path.read_text().endswith('d\n'))
            log.write('z' * 65)
            self.assertLessEqual(path.stat().st_size, 64)
            bad = ts.BoundedLog(Path(temp) / 'missing' / 'x')
            bad.write('x')
            self.assertTrue(bad.disabled)
            # Legacy oversized logs cannot defeat the cap; FIFOs cannot block it.
            path.write_bytes(b'x' * 100)
            Path(str(path) + '.1').write_bytes(b'x' * 100)
            ts.BoundedLog(path, limit=64).write('new\n')
            self.assertEqual(path.read_text(), 'new\n')
            self.assertFalse(Path(str(path) + '.1').exists())
            fifo = Path(temp) / 'fifo'
            os.mkfifo(fifo)
            blocked = ts.BoundedLog(fifo)
            blocked.write('x')
            self.assertTrue(blocked.disabled)
            link = Path(temp) / 'link'
            link.symlink_to(path)
            ts.BoundedLog(link).write('bad\n')
            self.assertEqual(path.read_text(), 'new\n')

    def test_models_fail_before_port_open(self):
        with patch.object(ts, 'load_model', side_effect=ValueError('corrupt')), patch.object(ts, 'open_port') as opened:
            self.assertEqual(ts.main(['--port', '/not/a/port']), 2)
            opened.assert_not_called()
        for side in ts.SIDES:
            self.assertEqual(len(ts.load_model(side)['quality_coef']), 61)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.npz'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('bomb.npy', b'0' * 65537)
            with self.assertRaises(ValueError):
                rt.load_model(path)
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('truncated.npy', b'\x93NUMPY\x01\x00\x01\x00x ')
            with self.assertRaises(ValueError):
                rt.load_model(path)
        with self.assertRaises(ValueError):
            rt._read_npy(b'corrupt')


class PtyTests(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = pty.openpty()
        self.path = os.ttyname(self.slave)
        self.proc = None

    def tearDown(self):
        if self.proc:
            self.proc.kill()
            self.proc.communicate(timeout=3)
        os.close(self.master)
        os.close(self.slave)

    def start(self):
        self.proc = subprocess.Popen([sys.executable, '-B', str(Path(ts.__file__)),
                                      '--port', self.path, '--quiet'],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertTrue(select.select([self.proc.stderr], [], [], 3)[0])
        self.assertIn(b'ready', self.proc.stderr.readline())

    def send(self, data):
        # Small chunks avoid filling a PTY's kernel queues in the test writer.
        for start in range(0, len(data), 512):
            os.write(self.master, data[start:start + 512])

    def receive(self, timeout=3):
        result = b''
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not select.select([self.master], [], [], max(0, deadline - time.monotonic()))[0]:
                break
            result += os.read(self.master, 8192)
            if b'\nV ' in result or result.startswith(b'V '):
                if result.endswith(b'\n'):
                    break
        return result

    def test_raw_settings_bidirectional_and_flock_lock(self):
        port = ts.open_port(self.path)
        try:
            attrs = termios.tcgetattr(port.fd)
            self.assertEqual(attrs[0:2], [0, 0])
            self.assertEqual(attrs[3], 0)
            self.assertEqual(attrs[4:6], [termios.B115200] * 2)
            self.assertEqual(attrs[2] & termios.CSIZE, termios.CS8)
            self.assertFalse(attrs[2] & (termios.PARENB | termios.CSTOPB))
            with self.assertRaises(OSError):
                ts.open_port(self.path)
            port.reply_deadline = time.monotonic() + 1
            port.write(UNKNOWN)
            self.assertEqual(self.receive(), UNKNOWN.encode())
            port.reply_deadline = time.monotonic() - 1
            with self.assertRaises(TimeoutError):
                port.write(UNKNOWN)
        finally:
            port.close()
        # Normal closure must allow a supervised restart on the same device.
        ts.open_port(self.path).close()

    def test_partial_crlf_garbage_non_utf8_reset_and_duplicate_end(self):
        self.start()
        self.send(b'boot\xff\r\nE done\r\n#TAL')
        self.assertEqual(self.receive(.05), b'')
        self.send(b'LY2 fs=100 unit=g range=3 side=L\r\n')
        self.send((sample(0) + '\r\n').encode())
        self.send(b'S 1 10 0 0 \xff 0 0 1\r\nE done\r\n')
        self.assertEqual(self.receive(), UNKNOWN.encode())
        self.send(b'E done\n')
        self.assertEqual(self.receive(.05), b'')
        self.send((HEADER + '\n' + 'x' * 10000 + '\n').encode())
        self.send(('\r\n'.join(moving('R')) + '\r\n').encode())
        expected = ''.join(run_lines(moving('R'))[1]).encode()
        self.assertEqual(self.receive(), expected)

    def test_missing_end_timeout_and_next_set_recovery(self):
        self.start()
        self.send((HEADER + '\n' + sample(0) + '\npartial').encode())
        self.assertEqual(self.receive(2.3), b'')
        self.send(b'\nE done\n')
        self.assertEqual(self.receive(.05), b'')
        self.send(('\n'.join(moving()) + '\n').encode())
        self.assertEqual(self.receive(), ''.join(run_lines(moving())[1]).encode())

    def test_startup_flush_and_death_respawn_mid_set(self):
        # Configure the slave raw before queueing stale input, avoiding echo.
        port = ts.open_port(self.path)
        port.close()
        self.send((HEADER + '\n' + sample(0) + '\nE done\n').encode())
        self.start()
        self.assertEqual(self.receive(.05), b'')
        self.send((HEADER + '\n' + sample(0) + '\n').encode())
        self.proc.kill()
        self.proc.communicate(timeout=3)
        self.start()
        self.send((sample(1) + '\nE done\n').encode())
        self.assertEqual(self.receive(.05), b'')
        self.send(('\n'.join(moving()) + '\n').encode())
        self.assertEqual(self.receive(), ''.join(run_lines(moving())[1]).encode())

    def test_write_backpressure_is_bounded(self):
        port = ts.open_port(self.path)
        try:
            start = time.monotonic()
            port.reply_deadline = start + .05
            with self.assertRaises(TimeoutError):
                port.write('R ' + 'x' * 100000)
            self.assertLess(time.monotonic() - start, 1)
        finally:
            port.close()

    def test_continuous_newline_free_input_does_not_starve_timers(self):
        port = ts.open_port(self.path)
        try:
            with patch.object(ts.select, 'select', return_value=([port.fd], [], [])), \
                 patch.object(ts.os, 'read', return_value=b'x' * 512):
                with ts.scoring_budget(.05):
                    self.assertIsNone(next(iter(port)))
        finally:
            port.close()


if __name__ == '__main__':
    unittest.main()
