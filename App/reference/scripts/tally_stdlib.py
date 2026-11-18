"""Shield entry point: bounded ASCII serial framing and stdlib-only scoring.

The wire replies for valid sets match tally_paired_stream.py. See
docs/SHIELD-HARDENING.md for recovery limits: respawn cannot recover a lost set.
"""
from __future__ import annotations

import argparse
from array import array
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import select
import signal
import stat
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stdlib_runtime as rt

FS = 100
MAX_LINE = 128
MAX_SAMPLES = 60_000
RATE_LOW, RATE_HIGH = 95.0, 105.0
SIDES = ('L', 'R')
MODEL_DIR = Path(__file__).resolve().parents[1] / 'model'
IDLE_SECONDS = 2.0
SET_SECONDS = 610.0
SCORE_SECONDS = 20.0
REPLY_SECONDS = 25.0  # includes scoring; leave margin inside the MCU's 30 s wait
LOG_BYTES = 128 * 1024


class StreamError(Exception):
    """Framing or content problem that invalidates the whole set."""


def load_model(side: str, kind: str = 'paired-synchronized-offline') -> dict:
    if side not in SIDES:
        raise StreamError(f'side must be one of {SIDES}, got {side!r}')
    weights = rt.load_model(MODEL_DIR / kind / side / 'realtime_model.npz')
    sizes = {'quality_coef': 61, 'quality_intercept': 1,
             'exercise_coef': 183, 'exercise_intercept': 3}
    for key, size in sizes.items():
        vals = weights.get(key, [])
        if len(vals) != size or not all(math.isfinite(v) for v in vals):
            raise StreamError(f'invalid model field {key} for {side}')
    if sorted(weights.get('exercise_classes', [])) != ['EAH', 'EFE', 'SQZ']:
        raise StreamError(f'invalid model classes for {side}')
    return weights


def parse_header(tokens):
    if not tokens or tokens[0] != '#TALLY2':
        raise StreamError('expected #TALLY2 header')
    fields = {}
    for token in tokens[1:]:
        if '=' not in token:
            raise StreamError(f'bad header token {token!r}')
        k, v = token.split('=', 1)
        if k in fields:
            raise StreamError(f'duplicate header field {k}')
        fields[k] = v
    if fields != {'fs': str(FS), 'unit': 'g', 'range': '3',
                  'side': fields.get('side')} or fields.get('side') not in SIDES:
        raise StreamError('expected fs=100 unit=g range=3 side=L or R')
    return fields


def parse_sample(tokens):
    if len(tokens) != 9:
        raise StreamError(f'expected 9 fields in S line, got {len(tokens)}')
    try:
        seq, t_ms = int(tokens[1]), int(tokens[2])
        values = array('f', (rt.f32(float(v)) for v in tokens[3:]))
    except (ValueError, OverflowError) as exc:
        raise StreamError(f'unparseable S line: {exc}') from exc
    if not (0 <= seq < MAX_SAMPLES and 0 <= t_ms <= 0xffffffff):
        raise StreamError('sample counter outside protocol bounds')
    if not all(math.isfinite(v) for v in values):
        raise StreamError('non-finite acceleration sample')
    return seq, t_ms, values


def sensor_health_reason(values):
    """Flag exact zero or sample/channel plateaus; this is not open-circuit proof."""
    if len(values) < 2:
        return None
    if all(value == 0.0 for row in values for value in row):
        return 'all_zero_readings'
    if all(row == values[0] for row in values):
        return 'identical_repeated_samples'
    names = ('upper_arm_x', 'upper_arm_y', 'upper_arm_z',
             'forearm_x', 'forearm_y', 'forearm_z')
    for axis, name in enumerate(names):
        first = values[0][axis]
        if all(row[axis] == first for row in values):
            # shortcut: exact full-set plateaus can reject a valid static/short set;
            # require a moving exercise, and upgrade only with board evidence.
            return f'stuck_channel_{name}'
    return None


def reply_line(record: dict) -> str:
    verdict = record.get('verdict') or 'unknown'
    p_wrong = record.get('mean_p_wrong')
    p_text = 'nan' if p_wrong is None else f'{p_wrong:.3f}'
    exercise = record.get('exercise') or '-'
    return f'V {verdict} {p_text} {exercise}\n'


def reply_lines(record: dict):
    if record.get('status') == 'scored':
        for rep in record['repetitions']:
            yield (f"R {rep['rep_index']} {rep['verdict']} {rep['p_wrong']:.3f} "
                   f"{rep['exercise']} {rep['duration_s']:.3f}\n")
    yield reply_line(record)


@contextmanager
def scoring_budget(seconds):
    """Interrupt CPU scoring on Linux; never fabricate a verdict after the budget."""
    if seconds is None:
        yield
        return

    def expired(signum, frame):
        raise TimeoutError('scoring_timeout')

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def run(stream, side_override=None, out=None, emit=True, reply=None,
        models=None, live=False, reply_log=None):
    header = None
    values = []
    fault = None
    count = 0
    first_time = last_time = last_seq = None
    started = activity = time.monotonic()

    def emit_record(record, respond=False):
        nonlocal emit, out, reply_log
        # The MCU's deadline takes priority over optional diagnostics. A failed port
        # write is fatal: continuing could deliver a stale tail into a later set.
        responses = list(reply_lines(record)) if respond else []
        if reply is not None:
            for response in responses:
                reply(response)
        line = json.dumps(record) + '\n'
        if emit:
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except OSError:
                emit = False
        if out is not None:
            try:
                out.write(line)
                out.flush()
            except OSError:
                out = None
        if reply_log is not None and responses:
            try:
                reply_log.write(''.join(responses))
                reply_log.flush()
            except OSError:
                reply_log = None

    def reset():
        nonlocal header, values, fault, count, first_time, last_time, last_seq
        header, values, fault, count = None, [], None, 0
        first_time = last_time = last_seq = None

    def rejected(reason, end):
        return {'end': end, 'sample_count': count, 'side': header['side'] if header else None,
                'status': 'rejected', 'verdict': None, 'diagnostics': [reason]}

    for raw in stream:
        now = time.monotonic()
        if live and header is not None and (now - activity >= IDLE_SECONDS or
                                            now - started >= SET_SECONDS):
            emit_record(rejected('incomplete_set_timeout', 'timeout'))
            reset()  # no end observed: no unsolicited V, even if E arrives later
        if raw is None:  # serial timer tick, including a partial line with no newline
            continue
        if header is not None:
            activity = now
        try:
            if isinstance(raw, bytes):
                raw = raw.decode('ascii')
            line = raw.strip(' \t\r\n')
            if not line:
                continue
            if len(raw) > MAX_LINE + 2 or len(line) > MAX_LINE:
                raise StreamError(f'line longer than {MAX_LINE} bytes')
            if not line.isascii() or any(ord(c) < 32 and c != '\t' for c in line):
                raise StreamError('non-ASCII/control byte')
            tokens = line.split()
            if tokens[0] == '#TALLY2':
                if header is not None:
                    emit_record(rejected('superseded_by_header', 'reset'))
                reset()
                header = {'side': None}  # a malformed header still owns its following E
                started = activity = now
                header = parse_header(tokens)
                if side_override and header['side'] != side_override:
                    raise StreamError(f"--side {side_override} but header says {header['side']}")
            elif tokens[0] == 'E':
                # Orphan/duplicate ends cannot be associated safely after startup/reset.
                if header is None:
                    continue
                activity = now
                if live:
                    stream.reply_deadline = now + REPLY_SECONDS
                reason = tokens[1] if len(tokens) == 2 else 'invalid'
                record = rejected(fault or f'set_ended_{reason}', reason)
                if reason not in ('done', 'aborted', 'overflow'):
                    record['diagnostics'] = ['invalid_end_marker']
                elif fault is None and reason == 'done':
                    health_reason = sensor_health_reason(values)
                    if health_reason:
                        record['diagnostics'] = [health_reason]
                    elif count < 2:
                        record['diagnostics'] = ['no_samples']
                    else:
                        rate = (count - 1) * 1000.0 / (last_time - first_time)
                        record['measured_rate_hz'] = round(rate, 2)
                        if not RATE_LOW <= rate <= RATE_HIGH:
                            record['diagnostics'] = ['rate_out_of_tolerance']
                        else:
                            try:
                                with scoring_budget(SCORE_SECONDS if live else None):
                                    weights = models[header['side']] if models else load_model(header['side'])
                                    record.update(rt.score_set(values, weights))
                            except (ArithmeticError, ValueError, TimeoutError) as exc:
                                record['diagnostics'] = [f'scoring_failed: {exc}']
                emit_record(record, respond=True)
                reset()
            elif header is None:
                continue  # boot chatter, a partial old set, or noise before a header
            elif fault is not None:
                continue  # keep the first fault, but always recognise a fresh header/end
            elif tokens[0] == 'S':
                activity = now
                if count >= MAX_SAMPLES:
                    raise StreamError('more samples than one set allows')
                seq, t_ms, sample = parse_sample(tokens)
                if (last_seq is None and seq != 0) or (last_seq is not None and seq != last_seq + 1):
                    raise StreamError(f'sequence break at {seq}')
                if last_time is not None and t_ms <= last_time:
                    raise StreamError(f'timestamp not increasing at {t_ms} ms')
                if t_ms > SET_SECONDS * 1000:
                    raise StreamError('set timestamp exceeds duration limit')
                if first_time is None:
                    first_time = t_ms
                last_seq, last_time = seq, t_ms
                count += 1
                values.append(sample)
            else:
                raise StreamError(f'unknown line {line[:24]!r}')
        except (StreamError, UnicodeError) as exc:
            if header is not None and fault is None:
                fault = str(exc)
                values = []  # reject the whole set and release storage immediately
    if header is not None:
        emit_record(rejected(fault or 'incomplete_set_at_eof', 'incomplete_set_at_eof'))
        return 1
    return 0


class BoundedLog:
    """Best effort append log, at most two files; no open/truncate during startup."""
    def __init__(self, path, limit=LOG_BYTES):
        self.path, self.limit = Path(path), limit
        self.disabled = False

    def write(self, text):
        if self.disabled:
            return
        try:
            data = text.encode('ascii')  # JSON uses ensure_ascii; wire labels are ASCII
            if len(data) > self.limit:
                return
            backup = Path(str(self.path) + '.1')
            for path in (self.path, backup):
                if path.exists() or path.is_symlink():
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        raise OSError('diagnostic path must be a regular file')
                    if info.st_size > self.limit:
                        path.unlink()  # legacy oversized diagnostics are not retained
            size = self.path.stat().st_size if self.path.exists() else 0
            if size + len(data) > self.limit:
                self.path.replace(backup)
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT |
                         os.O_NONBLOCK | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'ab') as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise OSError('diagnostic path must be a regular file')
                handle.write(data)
        except OSError:
            self.disabled = True
            print('tally: diagnostic log disabled (write/rotation failed)', file=sys.stderr, flush=True)

    def flush(self):
        pass


def bounded_lines(handle):
    """Bound memory even for captures/stdin without newlines. Discard through LF."""
    while True:
        raw = handle.readline(MAX_LINE + 3)
        if not raw:
            return
        if not raw.endswith(b'\n') and len(raw) == MAX_LINE + 3:
            while True:
                tail = handle.readline(MAX_LINE + 3)
                if not tail or tail.endswith(b'\n'):
                    break
            yield b'!' * (MAX_LINE + 3)
        else:
            yield raw


class SerialPort:
    def __init__(self, path):
        import fcntl
        import termios

        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.reply_deadline = 0.0
        try:
            # Advisory locking protects cooperating tally processes, including root.
            # It cannot evict a getty/Bridge process that already owns this UART.
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            attrs = termios.tcgetattr(self.fd)
            attrs[0] = attrs[1] = attrs[3] = 0
            attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            attrs[4] = attrs[5] = termios.B115200
            attrs[6][termios.VMIN] = 1
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
            # Discard pre-start data: an old E has no trustworthy age/transaction.
            termios.tcflush(self.fd, termios.TCIOFLUSH)
        except BaseException:
            self.close()
            raise

    def __iter__(self):
        pending = bytearray()
        dropping = False
        while True:
            if not select.select([self.fd], [], [], 0.25)[0]:
                yield None
                continue
            try:
                chunk = os.read(self.fd, 512)
            except BlockingIOError:
                continue
            if not chunk:
                raise OSError('serial EOF; joint restart may be required')
            for byte in chunk:
                if byte == 10:
                    yield bytes(pending) + b'\n' if not dropping else b'!' * (MAX_LINE + 3)
                    pending.clear()
                    dropping = False
                elif not dropping:
                    pending.append(byte)
                    if len(pending) > MAX_LINE + 1:  # allow CR before LF
                        pending.clear()
                        dropping = True
            # A continuously readable, newline-free UART must still run set timers.
            yield None

    def write(self, line):
        data = line.encode('ascii')
        while data:
            remaining = self.reply_deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [self.fd], [], remaining)[1]:
                raise TimeoutError('serial reply deadline; joint restart required')
            try:
                written = os.write(self.fd, data)
            except BlockingIOError:
                continue
            if not written:
                raise OSError('serial write made no progress')
            data = data[written:]

    def close(self):
        os.close(self.fd)


def open_port(path):
    return SerialPort(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Score paired sets without NumPy or SciPy.')
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--port', help='serial device')
    source.add_argument('--file', type=Path, help='a captured stream to replay')
    source.add_argument('--stdin', action='store_true', help='read a capture from stdin')
    ap.add_argument('--side', choices=SIDES, help='reject the other side; install only this model')
    ap.add_argument('--out', type=Path, help='bounded JSONL log (prefer /tmp)')
    ap.add_argument('--reply', choices=('port', 'file', 'both', 'none'), default=None)
    ap.add_argument('--reply-file', type=Path, default=Path('verdicts.log'))
    ap.add_argument('--quiet', action='store_true', help='suppress JSON records on stdout')
    args = ap.parse_args(argv)
    mode = args.reply or ('port' if args.port else 'none')
    if mode in ('port', 'both') and not args.port:
        ap.error('--reply port/both requires --port')
    port = capture = None
    try:
        # Discover missing/corrupt/wrong models before accepting a set, not at E.
        models = {side: load_model(side) for side in ([args.side] if args.side else SIDES)}
        out = BoundedLog(args.out) if args.out else None
        reply_log = BoundedLog(args.reply_file) if mode in ('file', 'both') else None
        if args.port:
            port = open_port(args.port)
            stream = port
            print('tally: ready; waiting for a fresh #TALLY2 header', file=sys.stderr, flush=True)
        else:
            capture = args.file.open('rb') if args.file else sys.stdin.buffer
            stream = bounded_lines(capture)
        return run(stream, side_override=args.side, out=out, emit=not args.quiet,
                   reply=port.write if mode in ('port', 'both') else None,
                   models=models, live=bool(port), reply_log=reply_log)
    except (StreamError, OSError, ValueError, KeyError, ImportError) as exc:
        print(f'tally: fatal: {exc}; if a set was active, restart parser and MCU together',
              file=sys.stderr, flush=True)
        return 2
    finally:
        if port is not None:
            port.close()
        if capture is not None and args.file:
            capture.close()


if __name__ == '__main__':
    raise SystemExit(main())
