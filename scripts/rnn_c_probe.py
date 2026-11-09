"""Export one PyTorch GRU state dict NPZ to C and report a Cortex-M4 object size."""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SHAPES = {"weight_ih_l0": (24, 6), "weight_hh_l0": (24, 8),
          "bias_ih_l0": (24,), "bias_hh_l0": (24,),
          "head_weight": (4, 9), "head_bias": (4,),
          "input_mean": (6,), "input_scale": (6,)}


def _load(path: Path) -> dict[str, np.ndarray | float]:
    with np.load(path, allow_pickle=False) as z:
        required = set(SHAPES) | {"duration_mean", "duration_scale"}
        if set(z.files) != required:
            raise ValueError(f"NPZ keys differ: missing={sorted(required-set(z.files))}, extra={sorted(set(z.files)-required)}")
        out: dict[str, np.ndarray | float] = {}
        for name, shape in SHAPES.items():
            a = np.asarray(z[name], dtype=np.float32)
            if a.shape != shape or not np.isfinite(a).all():
                raise ValueError(f"{name} must be finite float32 with shape {shape}")
            out[name] = a
        for name in ("duration_mean", "duration_scale"):
            a = np.asarray(z[name], dtype=np.float32)
            if a.size != 1 or not np.isfinite(a).all():
                raise ValueError(f"{name} must be a finite scalar")
            out[name] = float(a.reshape(()))
    if np.any(out["input_scale"] <= 0) or out["duration_scale"] <= 0:
        raise ValueError("normalization scales must be positive")
    return out


def _cfloat(x: float) -> str:
    s = f"{float(x):.9g}"
    return (s if "." in s or "e" in s else s + ".0") + "f"


def _array(name: str, value: np.ndarray) -> str:
    vals = ", ".join(_cfloat(x) for x in value.ravel())
    return f"static const float {name}[{value.size}] = {{{vals}}};\n"


def export_header(params: dict[str, np.ndarray | float], path: Path) -> None:
    names = [("weight_ih", "weight_ih_l0"), ("weight_hh", "weight_hh_l0"),
             ("bias_ih", "bias_ih_l0"), ("bias_hh", "bias_hh_l0"),
             ("head_weight", "head_weight"), ("head_bias", "head_bias"),
             ("input_mean", "input_mean"), ("input_scale", "input_scale")]
    body = "".join(_array(cname, params[pname]) for cname, pname in names)
    body += ("static const TinyGruModel tiny_gru_default_model = {"
             "weight_ih, weight_hh, bias_ih, bias_hh, head_weight, head_bias, "
             f"input_mean, input_scale, {_cfloat(params['duration_mean'])}, "
             f"{_cfloat(params['duration_scale'])}" "};\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("/* Generated from float32 PyTorch weights; gate order r,z,n. */\n"
                    "#ifndef TINY_GRU_WEIGHTS_H\n#define TINY_GRU_WEIGHTS_H\n"
                    "#include \"tiny_gru.h\"\n" + body + "#endif\n")


def integrated_wrapper() -> str:
    return '''#include "paired_stream.h"
#include "tiny_gru.h"
#include <math.h>
static PairStream stream;
static float downsampled[150][6];
static float cycle_features[61];
int tiny_gru_series_predict(const TinyGruModel *model, const float *raw, unsigned n,
                            TinyGruOutput *out, unsigned *repetitions) {
    if (!model || !raw || !n || !out || !repetitions) return 0;
    *repetitions = 0;
    stream_reset(&stream);
    float quality = 0.0f, exercise[3] = {0.0f, 0.0f, 0.0f};
    unsigned count = 0;
    for (unsigned t = 0; t < n; ++t) {
        unsigned before = stream.n;
        int ready = stream_push(&stream, t * 10u, raw + t * 6u, cycle_features);
        if (ready < 0) return 0;
        if (ready == 1) {
            unsigned samples = before == STREAM_CAP ? 1u : before + 1u;
            unsigned steps = 0;
            for (unsigned i = 0; i < samples; i += 4) {
                unsigned group = samples - i < 4 ? samples - i : 4;
                for (unsigned k = 0; k < 6; ++k) {
                    float sum = 0.0f;
                    for (unsigned j = 0; j < group; ++j) sum += stream.samples[i + j][k];
                    downsampled[steps][k] = sum / (float)group;
                }
                ++steps;
            }
            TinyGruOutput rep;
            if (!tiny_gru_predict(model, &downsampled[0][0], steps, cycle_features[0], &rep)) return 0;
            quality += rep.quality_probability;
            for (unsigned k = 0; k < 3; ++k) exercise[k] += rep.exercise_probability[k];
            ++count;
            *repetitions = count;
        }
    }
    if (count < 3) return 0;
    out->quality_probability = quality / (float)count;
    for (unsigned k = 0; k < 3; ++k) out->exercise_probability[k] = exercise[k] / (float)count;
    *repetitions = count;
    return 1;
}
int tiny_gru_series_predict_default(const float *raw, unsigned n,
                                    TinyGruOutput *out, unsigned *repetitions) {
    return tiny_gru_series_predict(&tiny_gru_default_model, raw, n, out, repetitions);
}
'''


def arm_object(header: Path, outdir: Path) -> dict:
    (outdir / "math.h").write_text("float expf(float);\nfloat tanhf(float);\nfloat fmaxf(float,float);\nfloat fminf(float,float);\nfloat sqrtf(float);\n#define isfinite(x) __builtin_isfinite(x)\n")
    wrapper = outdir / "probe.c"
    wrapper.write_text(integrated_wrapper().replace('#include "tiny_gru.h"',
                       f'#include "tiny_gru.h"\n#include "{header.name}"'))
    obj = outdir / "tiny_gru.o"
    common = ["clang", "--target=arm-none-eabi", "-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16",
           "-mfloat-abi=hard", "-Oz", "-ffreestanding", "-fno-builtin", "-fdata-sections",
           "-ffunction-sections", "-fstack-usage", "-I", str(outdir), "-I", str(header.parent), "-I", str(ROOT / "model/rnn-experiment"),
           "-I", str(ROOT / "model/streaming"),
           "-c"]
    impl_cmd = common + [str(ROOT / "model/rnn-experiment/tiny_gru.c"), "-o", str(outdir / "tiny_gru_impl.o")]
    stream_obj = outdir / "paired_stream.o"
    stream_cmd = common + [str(ROOT / "model/streaming/paired_stream.c"), "-o", str(stream_obj)]
    wrapper_cmd = common + [str(wrapper), "-o", str(obj)]
    subprocess.run(impl_cmd, check=True)
    subprocess.run(stream_cmd, check=True)
    subprocess.run(wrapper_cmd, check=True)
    impl = outdir / "tiny_gru_impl.o"
    sizes = "\n".join(subprocess.check_output(["llvm-size", "-A", str(o)], text=True)
                       for o in (impl, stream_obj, obj))
    stack_files = sorted(outdir.glob("*.su"))
    stack_usage = "\n".join(f.read_text() for f in stack_files)
    stack_bytes = []
    for line in stack_usage.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2 and cols[1].isdigit():
            stack_bytes.append(int(cols[1]))
    symbols = set()
    for o in (impl, stream_obj, obj):
        symbols.update(s.split()[-1] for s in subprocess.check_output(["llvm-nm", "-u", str(o)], text=True).splitlines() if s.split())
    text_bytes = 0
    rodata_bytes = 0
    state_components = {}
    for line in sizes.splitlines():
        m = re.match(r"\.text(?:\.[^\s]+)?\s+(\d+)", line.strip())
        if m: text_bytes += int(m.group(1))
        m = re.match(r"\.bss\.([^\s]+)\s+(\d+)", line.strip())
        if m: state_components[m.group(1)] = int(m.group(2))
        m = re.match(r"\.rodata(?:\.[^\s]+)?\s+(\d+)", line.strip())
        if m: rodata_bytes += int(m.group(1))
    return {"arm_compile_commands": [shlex.join(impl_cmd), shlex.join(stream_cmd), shlex.join(wrapper_cmd)],
            "arm_object_sections": sizes, "unresolved_symbols": sorted(symbols),
            "measurement_scope": "separate unlinked Cortex-M4 GRU, accepted detector, and integration/weight objects; libm and cross-object helpers unresolved; excludes board and firmware",
            "object_text_bytes_sum": text_bytes,
            "embedded_weight_parameter_bytes_float32": 1752,
            "weight_wrapper_rodata_bytes_from_llvm_size": rodata_bytes,
            "stack_usage_files": stack_usage,
            "max_reported_function_stack_bytes": max(stack_bytes) if stack_bytes else None,
            "known_inference_call_chain_stack_bytes": 112 + 384 + 8,
            "known_inference_call_chain_note": "wrapper + GRU + sigmoid frames, from Clang .su; unresolved library helper stacks are excluded",
            "integrated_static_state_bytes": sum(state_components.values()),
            "integrated_static_state_components_bytes_from_llvm_size": state_components}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("weights", type=Path, help="NPZ exported by the fold trainer")
    ap.add_argument("--header", type=Path, required=True, help="generated weight header path")
    ap.add_argument("--report", type=Path, help="optional JSON report path")
    ap.add_argument("--arm-object", action="store_true", help="compile a relocatable Cortex-M4 size probe")
    args = ap.parse_args()
    params = _load(args.weights)
    export_header(params, args.header)
    report = {"weights_npz": str(args.weights), "header": str(args.header),
              "weight_bytes_float32": int(sum(x.nbytes for x in params.values() if isinstance(x, np.ndarray)) + 8),
              "weight_header_bytes": args.header.stat().st_size,
              "kernel_local_float_storage_estimate_bytes": 8 * 4 + 6 * 4 + 24 * 4 + 24 * 4 + 4 * 8 * 4 + 4 * 4 + 4,
              "kernel_local_storage_note": "conservative sum of named float temporaries; Clang .su function frame is the measured 384 B and is reported separately"}
    if args.arm_object:
        with tempfile.TemporaryDirectory(prefix="rnn-c-probe-") as d:
            report.update(arm_object(args.header, Path(d)))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
