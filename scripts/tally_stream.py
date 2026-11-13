"""Parse and score bounded TALLY1 accelerometer streams."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from harness import window_features
from reps import ACC, FS, detrend, find_peaks  # find_peaks uses this exact preprocessing.

MAX_LINE = 64
MAX_SAMPLES = 60_000
SEQ_MOD = 1 << 31
_DECIMAL = re.compile(r"[+-]?\d+\.\d{8}\Z")


class StreamParser:
    """Incrementally parse TALLY1 lines and score each completed set.

    A parser holds at most ``max_samples`` rows. Invalid sets are consumed through
    their E record and are never passed to the model.
    """

    def __init__(self, model_path: str | Path | None = None, max_samples: int = MAX_SAMPLES,
                 model=None):
        if max_samples < 10:
            raise ValueError("max_samples must be at least 10")
        self.max_samples = int(max_samples)
        self._samples = np.empty((self.max_samples, 3), dtype=np.float64)
        self._model = model
        self.model_path = Path(model_path) if model_path else ROOT / "model/small/form_rep.joblib"
        self.last_vectors = np.empty((0, 31), dtype=np.float32)
        self.reset()

    def reset(self) -> None:
        """Start a new device session; a new header is required."""
        self._header_seen = False
        self._reset_set()

    def _reset_set(self, clear_vectors: bool = True) -> None:
        self._count = 0
        self._expected_seq = 0
        self._active = False
        self._invalid = False
        self._discard = False
        self._dropped_count = 0
        self._gap_count = 0
        self._timed_count = 0
        self._first_at = None
        self._last_at = None
        self._diagnostics: list[str] = []
        if clear_vectors:
            self.last_vectors = np.empty((0, 31), dtype=np.float32)
            self._vectors_sha256 = None
            self._repetitions = []

    def _diag(self, message: str) -> None:
        if message not in self._diagnostics and len(self._diagnostics) < 8:
            self._diagnostics.append(message)

    def _result(self, status: str, end: str | None, *, rate=None, probability=None,
                verdict=None) -> dict:
        result = {
            "status": status,
            "end": end,
            "sample_count": self._count,
            "vector_count": int(len(self.last_vectors)),
            "dropped_count": self._dropped_count,
            "gap_count": self._gap_count,
            "measured_rate_hz": rate,
            "mean_p_wrong": probability,
            "verdict": verdict,
            "vectors_sha256": getattr(self, "_vectors_sha256", None),
            "repetitions": getattr(self, "_repetitions", []),
            "diagnostics": list(self._diagnostics),
        }
        self._reset_set(clear_vectors=False)
        self._vectors_sha256 = None
        self._repetitions = []
        return result

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return text.split()

    def _parse_header(self, line: str) -> bool:
        parts = self._tokens(line)
        return parts == ["#TALLY1", "fs=100", "unit=g", "ax=+x", "ay=+y", "az=+z"]

    def _get_model(self):
        if self._model is None:
            import joblib
            self._model = joblib.load(self.model_path)
        return self._model

    def _score(self, end: str, rate: float | None, unverified: bool) -> dict:
        if end != "done":
            return self._result("aborted", end, rate=rate)
        if self._invalid:
            return self._result("rejected", end, rate=rate)
        if self._discard:
            return self._result("aborted", end, rate=rate)
        if rate is not None and not 95.0 <= rate <= 105.0:
            self._diag("rate_out_of_range")
            return self._result("rejected", end, rate=rate)
        if unverified:
            self._diag("rate_unverified")
        if self._count == 0:
            self._diag("no_samples")
            return self._result("rejected", end, rate=rate)

        sig = np.zeros((self._count, 10), dtype=np.float64)
        sig[:, ACC] = self._samples[:self._count]
        peaks = find_peaks(sig)
        if len(peaks) < 2:
            self._diag("fewer_than_2_peaks")
            return self._result("insufficient_reps", end, rate=rate)
        bounds = [0] + list((peaks[1:] + peaks[:-1]) // 2) + [self._count]
        rows = [np.r_[(b-a)/FS, window_features(sig[a:b, ACC][None, :, :])[0]]
                for a, b in zip(bounds[:-1], bounds[1:]) if b-a >= 10]
        if len(rows) < 3:
            self._diag("fewer_than_3_segments")
            return self._result("insufficient_reps", end, rate=rate)
        vectors = np.asarray(rows, dtype=np.float32)
        if not np.isfinite(vectors).all():
            self._diag("nonfinite_features")
            return self._result("rejected", end, rate=rate)
        self.last_vectors = vectors
        try:
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=1):
                probabilities = np.asarray(self._get_model().predict_proba(vectors))[:, 1]
            probability = float(np.mean(probabilities))
        except Exception as exc:
            self._diag(f"scoring_error:{type(exc).__name__}")
            return self._result("error", end, rate=rate)
        if not np.isfinite(probability):
            self._diag("nonfinite_probability")
            return self._result("error", end, rate=rate)
        self._vectors_sha256 = hashlib.sha256(vectors.astype("<f4", copy=False).tobytes(order="C")).hexdigest()
        self._repetitions = []
        for a, b in zip(bounds[:-1], bounds[1:]):
            if b-a < 10:
                continue
            idx = len(self._repetitions)
            self._repetitions.append({
                "start_sample": int(a), "end_sample": int(b),
                "duration_s": float((b-a) / FS),
                "p_wrong": float(probabilities[idx]),
            })
        return self._result("ok_unverified_rate" if unverified else "ok", end,
                            rate=rate, probability=probability,
                            verdict="wrong" if probability >= .5 else "correct")

    def feed_line(self, line: bytes, received_at: float | None = None) -> dict | None:
        """Consume one wire line, returning a result only for a terminal E record."""
        if not isinstance(line, bytes):
            raise TypeError("line must be bytes")
        if not self._active:
            self.last_vectors = np.empty((0, 31), dtype=np.float32)
            self._vectors_sha256 = None
            self._repetitions = []
        if len(line) > MAX_LINE:
            self._active = True
            self._invalid = True
            self._diag("line_too_long")
            return None
        if not line.endswith(b"\n"):
            self._active = True
            self._invalid = True
            self._diag("unterminated_line")
            return None
        line = line[:-1]
        if line.endswith(b"\r"):
            line = line[:-1]
        try:
            text = line.decode("ascii").strip()
        except UnicodeDecodeError:
            self._active = True
            self._invalid = True
            self._diag("non_ascii")
            return None
        if not text:
            return None

        if text.startswith("#TALLY1"):
            if self._header_seen:
                self._active = True
                self._invalid = True
                self._diag("duplicate_header")
            elif not self._parse_header(text):
                self._active = True
                self._invalid = True
                self._diag("invalid_header")
            else:
                self._header_seen = True
            return None
        if text.startswith("#"):
            return None
        parts = self._tokens(text)
        if not self._header_seen:
            self._invalid = True
            self._active = True
            self._diag("header_required")
            if parts and parts[0] == "E":
                return self._result("rejected", parts[1] if len(parts) > 1 else None)
            return None

        if parts and parts[0] == "E":
            self._active = True
            if len(parts) != 2 or parts[1] not in {"done", "aborted", "overflow"}:
                self._invalid = True
                self._diag("invalid_end_record")
                return None
            duration = (self._last_at - self._first_at) if self._first_at is not None else None
            rate = ((self._count - 1) / duration if duration and duration > 0 and self._count > 1 else None)
            unverified = self._timed_count != self._count or rate is None
            if self._timed_count and (self._timed_count != self._count or (self._count > 1 and rate is None)):
                self._invalid = True
                self._diag("invalid_arrival_timing")
            if unverified:
                self._diag("rate_unverified")
            return self._score(parts[1], rate, unverified)

        if self._discard:
            if parts and parts[0] == "S":
                self._dropped_count += 1
            return None
        if self._invalid:
            if parts and parts[0] == "S":
                self._dropped_count += 1
            return None
        self._active = True
        if len(parts) != 5 or parts[0] != "S" or not parts[1].isdigit():
            self._invalid = True
            self._diag("invalid_sample_record")
            return None
        try:
            seq = int(parts[1])
            if not 0 <= seq < SEQ_MOD:
                raise ValueError
            if seq != self._expected_seq:
                if (seq - self._expected_seq) % SEQ_MOD < (SEQ_MOD // 2):
                    self._gap_count += (seq - self._expected_seq) % SEQ_MOD
                raise ValueError
            values = parts[2:]
            xyz = [float(value) for value in values]
            if not all(np.isfinite(xyz)):
                self._invalid = True
                self._diag("nonfinite_sample")
                return None
            if not all(_DECIMAL.fullmatch(value) for value in values):
                self._invalid = True
                self._diag("invalid_sample_decimal")
                return None
        except ValueError:
            self._invalid = True
            self._diag("invalid_sequence_or_decimal")
            return None
        if self._count >= self.max_samples:
            self._discard = True
            self._dropped_count += 1
            self._diag("sample_limit_exceeded")
            return None
        self._samples[self._count] = xyz
        if self._count == 0:
            self.last_vectors = np.empty((0, 31), dtype=np.float32)
        self._count += 1
        self._expected_seq = (seq + 1) % SEQ_MOD
        if received_at is not None:
            received_at = float(received_at)
            if not np.isfinite(received_at) or (self._last_at is not None and received_at < self._last_at):
                self._invalid = True
                self._diag("invalid_arrival_timing")
                return None
            self._timed_count += 1
            if self._first_at is None:
                self._first_at = float(received_at)
            self._last_at = float(received_at)
        return None


def _bounded_lines(stream):
    """Yield lines with at most MAX_LINE+1 bytes, draining oversized lines."""
    while True:
        line = stream.readline(MAX_LINE + 1)
        if not line:
            return
        if len(line) > MAX_LINE and not line.endswith(b"\n"):
            while line and not line.endswith(b"\n"):
                line = stream.readline(MAX_LINE + 1)
            yield b"!" * (MAX_LINE + 1)
        else:
            yield line


def _serial_stream(port: str):
    import termios
    fd = os.open(port, os.O_RDONLY | os.O_NOCTTY)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[4] = attrs[5] = termios.B115200
    attrs[6][termios.VMIN] = 1
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return os.fdopen(fd, "rb", buffering=0)


class _VectorArchive:
    """Spool all sets to disk so --npz does not accumulate vectors in RAM."""

    def __init__(self):
        import tempfile
        self.rows = tempfile.TemporaryFile()
        self.starts = tempfile.TemporaryFile()
        self.row_count = 0
        self.set_count = 0
        self.starts.write(np.array([0], dtype='<i8').tobytes())

    def append(self, vectors):
        self.rows.write(vectors.astype('<f4', copy=False).tobytes(order='C'))
        self.row_count += len(vectors)
        self.set_count += 1
        self.starts.write(np.array([self.row_count], dtype='<i8').tobytes())

    def save(self, path):
        import shutil
        import zipfile
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for name, spool, shape, dtype in [
                ('rep_X', self.rows, (self.row_count, 31), '<f4'),
                ('rep_starts', self.starts, (self.set_count + 1,), '<i8'),
            ]:
                spool.seek(0)
                with archive.open(name + '.npy', 'w', force_zip64=True) as member:
                    np.lib.format.write_array_header_1_0(member, {
                        'descr': dtype, 'fortran_order': False, 'shape': shape})
                    shutil.copyfileobj(spool, member)

    def close(self):
        self.rows.close()
        self.starts.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group()
    source.add_argument('--port', help='POSIX serial device (115200 8N1; live arrival timing)')
    source.add_argument('--file', type=Path, help='read a captured stream (rate is unverified)')
    source.add_argument('--stdin', action='store_true', help='read a captured stream from stdin')
    ap.add_argument('--fs', type=int, default=100, choices=(100,))
    ap.add_argument('--out', type=Path, help='mirror result JSONL including diagnostics')
    ap.add_argument('--npz', type=Path, help='save all rep_X rows and per-set rep_starts offsets')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--series', type=int, default=25)
    args = ap.parse_args(argv)
    if args.self_test:
        print(json.dumps(self_test(args.series), allow_nan=False))
        return 0
    paths = [Path(path).resolve() for path in (args.file or args.port, args.out, args.npz) if path]
    if len(set(paths)) != len(paths):
        ap.error('input, --out and --npz paths must differ')
    parser = StreamParser()
    stream = (_serial_stream(args.port) if args.port else
              args.file.open('rb') if args.file else sys.stdin.buffer)
    out = args.out.open('w', encoding='utf-8') if args.out else None
    vectors = _VectorArchive() if args.npz else None

    def emit(result):
        encoded = json.dumps(result, allow_nan=False)
        print(encoded, flush=True)
        if out:
            out.write(encoded + '\n')
            out.flush()
        if vectors:
            vectors.append(parser.last_vectors)
        for diagnostic in result['diagnostics']:
            print(diagnostic, file=sys.stderr)

    try:
        try:
            for line in _bounded_lines(stream):
                result = parser.feed_line(line, time.monotonic() if args.port else None)
                if result is not None:
                    emit(result)
        except (OSError, KeyboardInterrupt) as exc:
            if parser._active:
                parser._diag(f'input_read_failed:{type(exc).__name__}')
                emit(parser._result('aborted', None))
            else:
                print(f'input_read_failed:{type(exc).__name__}', file=sys.stderr)
            return 2
        if parser._active:
            parser._diag('incomplete_set_at_eof')
            emit(parser._result('rejected', None))
        return 0
    finally:
        if args.file or args.port:
            stream.close()
        if out:
            out.close()
        if vectors:
            try:
                vectors.save(args.npz)
            finally:
                vectors.close()


def self_test(series: int = 25) -> dict:
    """Compare real wire round-trips to original and wire-quantized training inputs."""
    import shutil
    import tempfile
    from datetime import datetime, timezone
    import train_small
    from harness import read_inertial

    if series < 1:
        raise ValueError('--series must be positive')
    root = ROOT / 'data/phytmo/inertial/upper'
    # Use the actual load_data authority without writing the repository cache.
    with tempfile.TemporaryDirectory(prefix='tally-parity-') as tmp:
        cache = Path(tmp) / 'training.npz'
        existing = ROOT / 'tmp/small-data.npz'
        if existing.exists():
            shutil.copyfile(existing, cache)
        training = train_small.load_data(root=root, cache=cache)
    if series > len(training['series_source']):
        raise ValueError(f'only {len(training["series_source"])} training-eligible series available')

    def training_rows(sig):
        # The per-series path from train_small.load_data, with its imported helpers.
        peaks = train_small.find_peaks(sig)
        if len(peaks) < 2:
            return np.empty((0, 31), dtype=np.float32)
        bounds = [0] + list((peaks[1:] + peaks[:-1]) // 2) + [len(sig)]
        rows = [np.r_[[(b-a)/train_small.FS],
                      train_small.window_features(sig[a:b, train_small.ACC][None, :, :])[0]]
                for a, b in zip(bounds[:-1], bounds[1:]) if b-a >= 10]
        return (np.vstack(rows).astype(np.float32) if len(rows) >= 3
                else np.empty((0, 31), dtype=np.float32))

    parser = StreamParser()
    parser.feed_line(b'#TALLY1 fs=100 unit=g ax=+x ay=+y az=+z\n')
    original_deltas, wire_deltas = [], []
    verdict_matches = wire_verdict_matches = 0
    original_reps = parsed_reps = matched_reps = 0
    shape_mismatches = []
    sources, per_series = [], []
    for index, source in enumerate(training['series_source'][:series]):
        source = str(source)
        sig = read_inertial(str(root / source))
        start, end = training['rep_starts'][index:index+2]
        reference = training['rep_X'][start:end].astype(np.float32)
        replay_reference = training_rows(sig)
        if not np.array_equal(reference, replay_reference):
            raise AssertionError(f'cached load_data reference differs from current source: {source}')
        quantized = np.zeros_like(sig)
        for seq, values in enumerate(sig[:, train_small.ACC]):
            fields = [f'{value:.8f}' for value in values]
            quantized[seq, train_small.ACC] = [float(value) for value in fields]
            line = f'S {seq} {" ".join(fields)}\n'.encode('ascii')
            if len(line) > 64:
                raise AssertionError(f'wire line exceeds contract: {source}:{seq}')
            if parser.feed_line(line) is not None:
                raise AssertionError('set ended before E')
        result = parser.feed_line(b'E done\n')
        actual = parser.last_vectors.copy()
        quantized_reference = training_rows(quantized)
        if actual.shape != quantized_reference.shape:
            raise AssertionError(f'parser segmentation differs from quantized training path: {source}')
        wire_delta = np.abs(actual.astype(np.float64) - quantized_reference.astype(np.float64))
        wire_deltas.append(wire_delta.ravel())
        # Scoring the true float32 training rows establishes the original series verdict.
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            original_p = float(np.mean(parser._get_model().predict_proba(reference)[:, 1]))
            quantized_p = float(np.mean(parser._get_model().predict_proba(quantized_reference)[:, 1]))
        original_verdict = 'wrong' if original_p >= .5 else 'correct'
        wire_verdict = 'wrong' if quantized_p >= .5 else 'correct'
        verdict_matches += result['verdict'] == original_verdict
        wire_verdict_matches += result['verdict'] == wire_verdict
        original_reps += len(reference)
        parsed_reps += len(actual)
        if actual.shape == reference.shape:
            delta = np.abs(actual.astype(np.float64) - reference.astype(np.float64))
            original_deltas.append(delta.ravel())
            matched_reps += len(reference)
            max_delta = float(delta.max())
            over = int(np.count_nonzero(delta > 1e-6))
        else:
            shape_mismatches.append(source)
            max_delta, over = None, None
        sources.append(source)
        per_series.append({'source': source, 'sample_count': len(sig),
                           'reference_repetitions': len(reference), 'wire_repetitions': len(actual),
                           'max_abs_delta': max_delta, 'slots_exceeding_tolerance': over,
                           'reference_verdict': original_verdict, 'parser_verdict': result['verdict'],
                           'reference_mean_p_wrong': original_p,
                           'parser_mean_p_wrong': result['mean_p_wrong'],
                           'vectors_sha256': result['vectors_sha256']})

    def metrics(parts):
        values = np.concatenate(parts) if parts else np.empty(0)
        return {'slots_compared': len(values),
                'max_abs_delta': float(values.max()) if len(values) else None,
                'median_abs_delta': float(np.median(values)) if len(values) else None,
                'slots_exceeding_tolerance': int(np.count_nonzero(values > 1e-6))}

    report = {
        'command': f'.venv/bin/python scripts/tally_stream.py --self-test --series {series}',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'series_compared': series, 'repetitions_compared': matched_reps,
        'reference_repetitions': original_reps, 'wire_repetitions': parsed_reps,
        'unpaired_reference_repetitions': original_reps - matched_reps,
        'unpaired_wire_repetitions': parsed_reps - matched_reps,
        'feature_comparison_scope': 'All 31 slots of same-shape series, paired by repetition index; different-shape series are reported separately, not silently aligned or truncated',
        'tolerance': 1e-6, **metrics(original_deltas),
        'verdict_matches': verdict_matches,
        'verdict_agreement_percent': 100.0 * verdict_matches / series,
        'segmentation_shape_mismatches': shape_mismatches,
        'target_met': (not shape_mismatches and verdict_matches == series
                       and metrics(original_deltas)['max_abs_delta'] < 1e-6),
        'why': ('The fixed eight-decimal wire rounds PHYTMO accelerations before extraction. '
                'Original CSVs retain more precision. Quantization changes statistic values '
                'and can change zero crossings or peaks. No extra precision is transmitted.'),
        'same_quantized_input_control': {
            **metrics(wire_deltas), 'repetitions_compared': parsed_reps,
            'target_met': metrics(wire_deltas)['max_abs_delta'] < 1e-6 and wire_verdict_matches == series,
            'verdict_matches': wire_verdict_matches,
            'verdict_agreement_percent': 100.0 * wire_verdict_matches / series,
            'reference': 'Exact train_small.load_data per-series rule using imported training functions on decoded eight-decimal samples',
        },
        'reference': 'train_small.load_data full dataset (cache identity checked); per-series replay asserted bit-exact against its float32 rep_X',
        'series_selection': 'First N sorted training-eligible series_source entries; deterministic, not an accuracy evaluation',
        'rate_validation': 'Offline replay has no arrival/acquisition timing evidence; measured_rate_hz is null',
        'not_exercised': ['physical board', 'real serial port', 'Yun deployment/RAM', 'accuracy under sampling drift'],
        'series': per_series,
    }
    output = ROOT / 'docs/runs/stream/parser-parity.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
