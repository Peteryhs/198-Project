"""Board-to-parser stream for the paired (two-sensor) repetition model.

The firmware sends ASCII lines over the serial link the Yun's Linux CPU reads:

    #TALLY2 fs=100 unit=g range=3 side=L          once per session
    S <seq> <t_ms> <ux> <uy> <uz> <fx> <fy> <fz>  one per sample, 8 decimals, g
    E done                                        one per set (aborted | overflow also accepted)

One set is the unit of scoring. The parser validates the framing, cuts repetition
cycles with the training rule (forearm magnitude peaks, midpoints, edges), builds the
61 features the paired model takes (duration, upper statistics, forearm statistics) and
answers with the model for the declared side.

Run:
    python3 scripts/tally_paired_stream.py --port /dev/ttyATH0 --side L --out result.jsonl
    python3 scripts/tally_paired_stream.py --file capture.log --side L
    python3 scripts/tally_paired_stream.py --stdin --side L
    python3 scripts/tally_paired_stream.py --self-test --series 25 --side L

The model files live in model/paired-synchronized-offline/<side>/realtime_model.npz and
hold an affine quality head plus a three-way exercise head. Feature extraction and the
cycle rule are imported from scripts/harness.py, scripts/reps.py and
scripts/paired_pipeline.py, so the parser cannot drift from training.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))

from paired_pipeline import offline_features  # noqa: E402

FS = 100
MAX_LINE = 128
MAX_SAMPLES = 60_000
RATE_LOW, RATE_HIGH = 95.0, 105.0
MODEL_DIR = REPO / 'model'
DATA_ROOT = REPO / 'data/phytmo/inertial/upper'
SIDES = ('L', 'R')


class StreamError(Exception):
    """Framing or content problem that invalidates the whole set."""


def load_model(side: str, kind: str = 'paired-synchronized-offline') -> dict:
    """Load the affine paired model for one side. Weights are pre-scaled for raw features."""
    if side not in SIDES:
        raise StreamError(f'side must be one of {SIDES}, got {side!r}')
    path = MODEL_DIR / kind / side / 'realtime_model.npz'
    if not path.exists():
        raise StreamError(f'missing model {path}')
    with np.load(path) as z:  # our own exported weights, not third-party pickle
        weights = {k: np.asarray(z[k]) for k in z.files}
    if weights['quality_coef'].shape[1] != 61:
        raise StreamError(f'expected 61 inputs, model has {weights["quality_coef"].shape[1]}')
    return weights


def predict(weights: dict, x: np.ndarray) -> tuple[float, str]:
    """Return (P(wrong form), exercise label) for one 61-value repetition."""
    f = np.asarray(x, dtype=np.float32).reshape(1, -1)
    q = float(weights['quality_intercept'][0]) + float((weights['quality_coef'] @ f.ravel())[0])
    p_wrong = 1.0 / (1.0 + np.exp(-q))
    z = (weights['exercise_coef'] @ f.ravel() + weights['exercise_intercept']).astype(np.float64)
    z -= z.max()
    e = np.exp(z)
    e /= e.sum()
    label = str(weights['exercise_classes'][int(np.argmax(e))])
    return p_wrong, label


def parse_header(tokens: list[str]) -> dict:
    """#TALLY2 fs=100 unit=g range=3 side=L -> {'side': 'L', ...}"""
    fields = {}
    for token in tokens[1:]:
        if '=' not in token:
            raise StreamError(f'bad header token {token!r}')
        k, v = token.split('=', 1)
        fields[k] = v
    if fields.get('fs') not in (None, str(FS)):
        raise StreamError(f"header fs must be {FS}, got {fields['fs']!r}")
    if fields.get('unit', 'g') != 'g':
        raise StreamError(f"header unit must be g, got {fields['unit']!r}")
    side = fields.get('side')
    if side not in SIDES:
        raise StreamError(f'header side must be L or R, got {side!r}')
    return fields


def parse_sample(tokens: list[str]) -> tuple[int, int, np.ndarray]:
    """S <seq> <t_ms> <ux> <uy> <uz> <fx> <fy> <fz>"""
    if len(tokens) != 9:
        raise StreamError(f'expected 9 fields in S line, got {len(tokens)}')
    try:
        seq = int(tokens[1])
        t_ms = int(tokens[2])
        values = np.array([float(v) for v in tokens[3:]], dtype=np.float32)
    except ValueError as exc:
        raise StreamError(f'unparseable S line: {exc}') from exc
    if not np.isfinite(values).all():
        raise StreamError('non-finite acceleration sample')
    return seq, t_ms, values


def score_set(samples: np.ndarray, t_ms: np.ndarray, weights: dict,
              return_rows: bool = False) -> dict:
    """Cut cycles, build the 61 features, predict per repetition, pool to a set verdict."""
    x = np.asarray(samples, dtype=np.float64)
    rows = offline_features(x)
    if rows.shape[0] < 3:
        return {
            'status': 'insufficient_reps',
            'vector_count': int(rows.shape[0]),
            'mean_p_wrong': None,
            'verdict': None,
            'exercise': None,
            'repetitions': [],
            'diagnostics': ['fewer_than_3_cycles'],
        }
    probs, exercises, reps = [], [], []
    for row in rows:
        p, label = predict(weights, row)
        probs.append(p)
        exercises.append(label)
        reps.append({'duration_s': round(float(row[0]), 3), 'p_wrong': round(p, 6)})
    mean_p = float(np.mean(probs))
    counts = {label: exercises.count(label) for label in set(exercises)}
    out = {
        'status': 'scored',
        'vector_count': int(rows.shape[0]),
        'mean_p_wrong': round(mean_p, 6),
        'verdict': 'wrong' if mean_p >= 0.5 else 'correct',
        'exercise': max(counts, key=counts.get),
        'repetitions': reps,
        'diagnostics': [],
    }
    return (out, rows) if return_rows else out


def reply_line(record: dict) -> str:
    """The one line the board reads back: V <verdict> <mean_p_wrong> <exercise>."""
    verdict = record.get('verdict') or 'unknown'
    p_wrong = record.get('mean_p_wrong')
    p_text = 'nan' if p_wrong is None else f'{p_wrong:.3f}'
    exercise = record.get('exercise') or '-'
    return f'V {verdict} {p_text} {exercise}\n'


def run(stream, side_override: str | None = None, out=None, emit: bool = True,
        reply=None) -> int:
    """Read the line stream and score every complete set.

    A framing fault drops the set it belongs to and the parser resynchronises at the next end
    marker, so one bad line cannot stop a session. Prints one JSON object per set.
    """
    header = None
    seqs: list[int] = []
    times: list[int] = []
    values: list[np.ndarray] = []
    sets = 0
    fault: str | None = None

    def emit_record(record: dict) -> None:
        nonlocal sets
        line = json.dumps(record)
        if emit:
            print(line, flush=True)
        if out is not None:
            out.write(line + '\n')
            out.flush()
        if reply is not None:
            try:
                reply(reply_line(record))
            except OSError:
                pass
        sets += 1

    def side_now():
        return header['side'] if header else side_override

    def rejected(reason: str, end: str) -> None:
        emit_record({'end': end, 'sample_count': len(seqs), 'status': 'rejected',
                     'verdict': None, 'side': side_now(), 'diagnostics': [reason]})

    def flush(end_reason: str) -> None:
        nonlocal seqs, times, values
        record = {'end': end_reason, 'sample_count': len(seqs), 'side': side_now()}
        if header is None:
            record.update({'status': 'rejected', 'verdict': None, 'diagnostics': ['missing_header']})
        elif end_reason != 'done':
            record.update({'status': 'rejected', 'verdict': None,
                           'diagnostics': [f'set_ended_{end_reason}']})
        elif len(seqs) < 2:
            record.update({'status': 'rejected', 'verdict': None, 'diagnostics': ['no_samples']})
        else:
            rate = (len(times) - 1) * 1000.0 / max(1, times[-1] - times[0])
            record['measured_rate_hz'] = round(rate, 2)
            if not (RATE_LOW <= rate <= RATE_HIGH):
                record.update({'status': 'rejected', 'verdict': None,
                               'diagnostics': ['rate_out_of_tolerance']})
            else:
                record.update(score_set(np.vstack(values), np.asarray(times), load_model(side_now())))
        emit_record(record)
        seqs, times, values = [], [], []

    for raw in stream:
        line = raw.strip()
        if not line:
            continue
        if fault is not None:
            if line.startswith('E '):
                rejected(fault, line[2:].strip() or 'done')
                seqs, times, values = [], [], []
                fault = None
            continue
        try:
            if len(line) > MAX_LINE:
                raise StreamError(f'line longer than {MAX_LINE} bytes')
            if line.startswith('#TALLY2'):
                header = parse_header(line.split())
                if side_override and header['side'] != side_override:
                    raise StreamError(f"--side {side_override} but header says {header['side']}")
                continue
            if line.startswith('#'):
                continue
            if line.startswith('S '):
                if header is None:
                    raise StreamError('sample before header')
                seq, t_ms, sample_values = parse_sample(line.split())
                if seqs and seq != seqs[-1] + 1:
                    raise StreamError(f'sequence break at {seq} (previous {seqs[-1]})')
                if times and t_ms <= times[-1]:
                    raise StreamError(f'timestamp not increasing at {t_ms} ms')
                seqs.append(seq)
                times.append(t_ms)
                values.append(sample_values)
                if len(seqs) > MAX_SAMPLES:
                    raise StreamError(f'set exceeds {MAX_SAMPLES} samples')
                continue
            if line.startswith('E '):
                flush(line[2:].strip() or 'done')
                continue
            raise StreamError(f'unexpected record {line[:24]!r}')
        except StreamError as exc:
            fault = str(exc)
            seqs, times, values = [], [], []

    if fault is not None:
        rejected(fault, 'incomplete_set_at_eof')
    elif seqs:
        flush('incomplete_set_at_eof')
    return 0 if sets else 1


def wire_from_pair(x: np.ndarray, side: str, decimals: int = 8) -> str:
    """Turn an aligned (n, 6) pair into the exact bytes the firmware would send."""
    lines = [f'#TALLY2 fs=100 unit=g range=3 side={side}']
    fmt = '{:+.%df}' % decimals
    for i, row in enumerate(x):
        lines.append('S {} {} {} {} {} {} {} {}'.format(
            i, int(round(i * 1000 / FS)), *(fmt.format(v) for v in row)))
    lines.append('E done')
    return '\n'.join(lines) + '\n'


def self_test(count: int, side: str) -> int:
    """Replay real paired recordings through the wire format and diff features.

    Two comparisons are reported separately:
      parser_vs_same_input  - the scored vectors against the training extractor run on the
                              same decoded values. Any difference here is a parser bug.
      wire_quantization     - those vectors against the extractor run on the original float64
                              recordings. This is the 8-decimal text rounding, not a parser bug.
    """
    from paired_pipeline import records

    weights = load_model(side)
    seen = 0
    slots = 0
    over_impl = 0
    max_impl = 0.0
    max_quant = 0.0
    agree = 0
    reps_total = 0
    shape_mismatch = []

    for path, meta, x, error in records(DATA_ROOT, side):
        if error or x is None:
            continue
        wire = wire_from_pair(x, side)
        times, values = [], []
        for line in wire.splitlines():
            if line.startswith('S '):
                parts = line.split()
                times.append(int(parts[2]))
                values.append(np.array([float(v) for v in parts[3:]], dtype=np.float32))
        if not values:
            continue
        parsed = np.vstack(values).astype(np.float64)
        record, rows = score_set(parsed, np.asarray(times), weights, return_rows=True)

        same_input = offline_features(parsed)
        original = offline_features(np.asarray(x, dtype=np.float64))
        reps_total += int(original.shape[0])
        if rows.shape != same_input.shape:
            shape_mismatch.append(str(path.relative_to(DATA_ROOT)))
        else:
            d_impl = np.abs(rows.astype(np.float64) - same_input.astype(np.float64))
            slots += d_impl.size
            over_impl += int((d_impl > 1e-6).sum())
            max_impl = max(max_impl, float(d_impl.max()))
        if same_input.shape == original.shape and same_input.size:
            max_quant = max(max_quant, float(np.abs(same_input - original).max()))

        ref_p = float(np.mean([predict(weights, row)[0] for row in original]))
        ref_verdict = 'wrong' if ref_p >= 0.5 else 'correct'
        agree += int(record.get('verdict') == ref_verdict)
        seen += 1
        if seen >= count:
            break

    report = {
        'side': side,
        'series_compared': seen,
        'repetitions_compared': reps_total,
        'parser_vs_same_input_max_delta': max_impl,
        'slots_compared': slots,
        'slots_over_1e-6': over_impl,
        'wire_quantization_max_delta': max_quant,
        'verdict_agreement_percent': round(100.0 * agree / seen, 4) if seen else None,
        'shape_mismatches': shape_mismatch,
        'target_met': bool(seen and over_impl == 0 and not shape_mismatch),
    }
    print(json.dumps(report, indent=2))
    return 0 if report['target_met'] else 1


def find_port() -> str:
    """Pick the serial device the shield exposes, without the user naming it."""
    from glob import glob
    candidates = ['/dev/ttyATH0']
    candidates += sorted(glob('/dev/ttyACM*')) + sorted(glob('/dev/ttyUSB*'))
    for path in candidates:
        if Path(path).exists():
            return path
    raise StreamError(
        'no serial device found. Looked for /dev/ttyATH0, /dev/ttyACM*, /dev/ttyUSB*. '
        'Connect the shield, or pass --port PATH, or use --file CAPTURE')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = ap.add_mutually_exclusive_group()
    source.add_argument('--port', help='serial device; found automatically when omitted')
    source.add_argument('--file', type=Path, help='a captured stream to replay')
    source.add_argument('--stdin', action='store_true', help='read a capture from stdin')
    source.add_argument('--self-test', action='store_true', help='replay real pairs and diff features')
    ap.add_argument('--side', choices=SIDES, help='only to reject a set whose header names the other side')
    ap.add_argument('--series', type=int, default=25, help='series to replay in --self-test')
    ap.add_argument('--out', type=Path, help='also write the JSONL records here')
    ap.add_argument('--reply', choices=('port', 'file', 'both', 'none'),
                    help='send the verdict line back; defaults to the port when reading one, else file')
    ap.add_argument('--reply-file', type=Path, default=Path('verdicts.log'),
                    help='file that receives the verdict lines (default verdicts.log)')
    args = ap.parse_args(argv)

    try:
        if args.self_test:
            return self_test(args.series, args.side or 'L')
        out = args.out.open('w') if args.out else None
        sink = make_reply(args)
        if args.stdin:
            return run(sys.stdin, args.side, out, reply=sink)
        if args.file:
            if not args.file.exists():
                raise StreamError(f'capture not found: {args.file}')
            with args.file.open() as fh:
                return run(fh, args.side, out, reply=sink)
        port = args.port or find_port()
        print(json.dumps({'note': f'reading {port}'}), file=sys.stderr, flush=True)
        with open_port(port) as fd:
            if args.reply in (None, 'port', 'both'):
                sink = combine(sink, port_writer(port))
            return run(fd, args.side, out, reply=sink)
    except (StreamError, OSError) as exc:
        print(json.dumps({'status': 'rejected', 'verdict': None, 'diagnostics': [str(exc)]}))
        return 2


def make_reply(args):
    """Build the reply sink: a file, or None when replies are off."""
    if args.reply in (None, 'file', 'both'):
        path = args.reply_file
        handle = path.open('a', buffering=1)
        print(json.dumps({'note': f'verdict lines to {path}'}), file=sys.stderr, flush=True)
        return lambda line: handle.write(line)
    return None


def combine(first, second):
    """Call both sinks; one failing does not stop the other."""
    def sink(line: str) -> None:
        for fn in (first, second):
            if fn is None:
                continue
            try:
                fn(line)
            except OSError:
                pass
    return sink


def port_writer(path: str):
    """A separate write handle for the serial device; reading stays on the reader."""
    try:
        handle = open(path, 'w', buffering=1)
    except OSError as exc:
        print(json.dumps({'note': f'cannot write replies to {path}: {exc}'}), file=sys.stderr, flush=True)
        return None
    return lambda line: handle.write(line)


def open_port(path: str):
    """Open a POSIX serial device as raw 115200 baud, 8 data bits, no parity, 1 stop bit."""
    import io
    import os
    import termios

    fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
    try:
        try:
            attrs = termios.tcgetattr(fd)
        except termios.error as exc:
            raise OSError(*exc.args) from exc
        attrs[0] = 0  # raw input: no translations, flow control, or signal chars
        attrs[1] = 0  # raw output
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0  # raw mode: no canonical input or echo
        attrs[4] = termios.B115200
        attrs[5] = termios.B115200
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0
        try:
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except termios.error as exc:
            raise OSError(*exc.args) from exc
        return io.open(fd, 'r', buffering=1, errors='replace', closefd=True)
    except BaseException:
        os.close(fd)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
