"""Small independent NumPy parity and reset-state check for the C GRU probe."""
from __future__ import annotations

import ctypes
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rnn_c_probe as export


ROOT = Path(__file__).resolve().parents[1]


class Output(ctypes.Structure):
    _fields_ = [("quality_probability", ctypes.c_float),
                ("exercise_probability", ctypes.c_float * 3)]


def reference(p, x, duration):
    h = np.zeros(8, np.float32)
    for row in x:
        xn = ((row - p["input_mean"]) / p["input_scale"]).astype(np.float32)
        gi = (p["weight_ih_l0"] @ xn + p["bias_ih_l0"]).astype(np.float32)
        gh = (p["weight_hh_l0"] @ h + p["bias_hh_l0"]).astype(np.float32)
        r = 1 / (1 + np.exp(-(gi[:8] + gh[:8])))
        z = 1 / (1 + np.exp(-(gi[8:16] + gh[8:16])))
        n = np.tanh(gi[16:] + r * gh[16:]).astype(np.float32)
        h = ((1 - z) * n + z * h).astype(np.float32)
    features = np.r_[h, np.float32((duration - p["duration_mean"]) / p["duration_scale"])]
    logits = (p["head_weight"] @ features + p["head_bias"]).astype(np.float32)
    q = 1 / (1 + np.exp(-logits[0]))
    ex = np.exp(logits[1:] - np.max(logits[1:])); ex /= ex.sum()
    return np.r_[q, ex]


def torch_reference(p, x, duration):
    import torch
    gru = torch.nn.GRU(6, 8, batch_first=True)
    with torch.no_grad():
        for name in ("weight_ih_l0", "weight_hh_l0", "bias_ih_l0", "bias_hh_l0"):
            getattr(gru, name).copy_(torch.from_numpy(p[name]))
        xn = (torch.from_numpy(x)[None] - torch.from_numpy(p["input_mean"])) / torch.from_numpy(p["input_scale"])
        _, hn = gru(xn)
        features = torch.cat((hn[0, 0], torch.tensor([(duration-p["duration_mean"])/p["duration_scale"]])))
        logits = torch.from_numpy(p["head_weight"]) @ features + torch.from_numpy(p["head_bias"])
        probs = torch.softmax(logits[1:], dim=0)
        return np.r_[torch.sigmoid(logits[0]).item(), probs.numpy()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, help="also run parity with the saved trained NPZ")
    ap.add_argument("--fold-json", type=Path, help="compare integrated C outputs with a saved held-out fold")
    ap.add_argument("--data-root", type=Path, default=ROOT / "data/phytmo/inertial/upper")
    ap.add_argument("--report", type=Path, help="merge held-out parity measurements into the C probe JSON")
    args = ap.parse_args()
    rng = np.random.default_rng(137)
    p = {k: rng.normal(0, .13, s).astype(np.float32) for k, s in export.SHAPES.items()}
    p["input_scale"] = rng.uniform(.7, 1.4, 6).astype(np.float32)
    p["duration_mean"], p["duration_scale"] = np.float32(2.2), np.float32(.8)
    with __import__("tempfile").TemporaryDirectory(prefix="rnn-c-test-") as td:
        d = Path(td)
        npz = d / "fixture.npz"
        np.savez(npz, **p)
        params = export._load(args.weights if args.weights else npz)
        header = d / "tiny_gru_weights.h"
        export.export_header(params, header)
        wrapper = d / "wrapper.c"
        wrapper.write_text('#include "tiny_gru_weights.h"\n' + export.integrated_wrapper() +
                           'const TinyGruModel *fixture_model(void){return &tiny_gru_default_model;}\n'
                           'int predict(const float*x,unsigned n,float d,TinyGruOutput*y){'
                           'return tiny_gru_predict(&tiny_gru_default_model,x,n,d,y);}\n')
        so = d / "probe.so"
        subprocess.run(["cc", "-shared", "-fPIC", "-O2", "-I", str(d), "-I",
                        str(ROOT / "model/rnn-experiment"), "-I", str(ROOT / "model/streaming"),
                        str(wrapper), str(ROOT / "model/rnn-experiment/tiny_gru.c"),
                        str(ROOT / "model/streaming/paired_stream.c"), "-lm", "-o", str(so)], check=True)
        lib = ctypes.CDLL(str(so)); f = lib.predict
        f.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_uint, ctypes.c_float,
                      ctypes.POINTER(Output)]; f.restype = ctypes.c_int
        torch_checked = True
        try:
            import torch  # noqa: F401
        except ModuleNotFoundError:
            torch_checked = False
        for n in (1, 2, 7, 31):
            x = rng.normal(size=(n, 6)).astype(np.float32)
            expected = reference(params, x, 2.6)
            out = Output()
            ok = f(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), n, 2.6, ctypes.byref(out))
            actual = np.r_[out.quality_probability, list(out.exercise_probability)]
            np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=2e-6)
            if torch_checked:
                np.testing.assert_allclose(actual, torch_reference(params, x, 2.6), rtol=2e-5, atol=2e-6)
            assert ok == 1 and abs(float(out.exercise_probability[0] + out.exercise_probability[1] +
                                          out.exercise_probability[2]) - 1) < 2e-6
        # Calling a fresh sequence after a long one must start from zero hidden state.
        x = rng.normal(size=(3, 6)).astype(np.float32); out = Output()
        assert f(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(x), 2.6, ctypes.byref(out))
        np.testing.assert_allclose(np.r_[out.quality_probability, list(out.exercise_probability)],
                                   reference(params, x, 2.6), rtol=2e-5, atol=2e-6)
        assert f(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), 0, 2.6, ctypes.byref(out)) == 0
        x[0, 0] = np.nan
        assert f(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(x), 2.6, ctypes.byref(out)) == 0
        # Feed raw 100 Hz samples through the accepted detector and compare each
        # detected cycle against rnn_data's independent capture/downsample path.
        from rnn_data import _Capture, _downsample
        t = np.arange(1400, dtype=np.float32) * .01
        raw = np.zeros((len(t), 6), np.float32)
        raw[:, 3] = 1 + .35 * np.sin(2 * np.pi * t / 1.5)
        raw[:, 0] = .1 * np.sin(2 * np.pi * t / .73)
        capture = _Capture()
        try:
            cycles, features = capture(raw)
        finally:
            capture.close()
        assert len(cycles) >= 3, f"synthetic fixture only triggered {len(cycles)} cycles"
        reference_fn = torch_reference if torch_checked else reference
        expected = np.mean([reference_fn(params, _downsample(c), float(feat[0]))
                            for c, feat in zip(cycles, features)], axis=0)
        series = Output(); reps = ctypes.c_uint()
        sf = lib.tiny_gru_series_predict
        sf.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_uint,
                       ctypes.POINTER(Output), ctypes.POINTER(ctypes.c_uint)]
        sf.restype = ctypes.c_int
        model = lib.fixture_model; model.restype = ctypes.c_void_p
        assert sf(model(), raw[:300].ctypes.data_as(ctypes.POINTER(ctypes.c_float)), 300,
                  ctypes.byref(series), ctypes.byref(reps)) == 0
        ok = sf(model(), raw.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(raw),
                ctypes.byref(series), ctypes.byref(reps))
        actual = np.r_[series.quality_probability, list(series.exercise_probability)]
        assert ok == 1 and reps.value == len(cycles)
        np.testing.assert_allclose(actual, expected, rtol=3e-5, atol=3e-6)
        default = lib.tiny_gru_series_predict_default
        default.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_uint,
                            ctypes.POINTER(Output), ctypes.POINTER(ctypes.c_uint)]
        default.restype = ctypes.c_int
        assert default(raw.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(raw),
                       ctypes.byref(series), ctypes.byref(reps)) == 1
        np.testing.assert_allclose(np.r_[series.quality_probability, list(series.exercise_probability)],
                                   expected, rtol=3e-5, atol=3e-6)
        heldout = None
        if args.fold_json:
            import paired_pipeline as pp
            fold = json.loads(args.fold_json.read_text())
            expected_rows = {r["source"]: r for r in fold["rows"]}
            measured = []
            for path, meta, samples, error in pp.records(args.data_root, "L"):
                if meta[0] != fold["heldout_person"]:
                    continue
                source = path.relative_to(args.data_root).as_posix()
                if source not in expected_rows:
                    continue
                assert not error and samples is not None, f"fold source {source} failed to load: {error}"
                samples = np.ascontiguousarray(np.clip(samples, -3, 3), dtype=np.float32)
                count = ctypes.c_uint()
                ok = default(samples.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(samples),
                             ctypes.byref(series), ctypes.byref(count))
                assert ok == 1, f"integrated C probe abstained on retained source {source} (raw={samples.shape}, cycles={count.value}, error={error})"
                want = expected_rows[source]
                q_error = abs(float(series.quality_probability) - want["quality_wrong_probability"])
                ex_error = float(np.max(np.abs(np.asarray(series.exercise_probability) -
                                                np.asarray(want["exercise_probabilities"]))))
                assert count.value == want["cycles"], f"{source}: cycles {count.value} != {want['cycles']}"
                measured.append({"source": source, "cycles": int(count.value),
                                 "quality_probability_abs_error": q_error,
                                 "max_exercise_probability_abs_error": ex_error})
            expected_sources = set(expected_rows)
            got_sources = {r["source"] for r in measured}
            assert got_sources == expected_sources, f"held-out source coverage differs: missing={sorted(expected_sources-got_sources)}, extra={sorted(got_sources-expected_sources)}"
            heldout = {"heldout_person": fold["heldout_person"], "fold_json": str(args.fold_json),
                       "count": len(measured), "sources": measured,
                       "max_quality_probability_abs_error": max(r["quality_probability_abs_error"] for r in measured),
                       "max_exercise_probability_abs_error": max(r["max_exercise_probability_abs_error"] for r in measured),
                       "cycle_counts_match": True,
                       "interpretation": "integrated C implementation parity with saved Torch fold outputs on retained real held-out series; not hardware timing"}
            assert heldout["max_quality_probability_abs_error"] < 5e-5
            assert heldout["max_exercise_probability_abs_error"] < 5e-5
            if args.report:
                report = json.loads(args.report.read_text()) if args.report.exists() else {}
                report["heldout_series_parity"] = heldout
                args.report.write_text(json.dumps(report, indent=2) + "\n")
    ref = "NumPy/PyTorch" if torch_checked else "NumPy"
    msg = f"C/{ref} GRU parity passed for lengths 1, 2, 7, 31 and {len(cycles)} detector cycles; reset/abstain passed"
    if args.fold_json:
        msg += f"; {heldout['count']} real held-out series max errors q={heldout['max_quality_probability_abs_error']:.2g}, ex={heldout['max_exercise_probability_abs_error']:.2g}"
    print(msg)


if __name__ == "__main__":
    main()
