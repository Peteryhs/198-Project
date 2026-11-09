"""Check the generated linear C export against a fresh sklearn fit and cached features."""
from __future__ import annotations

import argparse
import ctypes
import json
import shlex
import subprocess
import tempfile
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir", type=Path, help="directory containing realtime_model.h/.npz")
    ap.add_argument("--features-root", type=Path, default=Path("training-data"))
    ap.add_argument("--sensor", choices=("all", "Larm"), default="all")
    ap.add_argument("--arm-object", action="store_true", help="also emit an unlinked Cortex-M4 object")
    ap.add_argument("--report", type=Path, help="optional JSON report path")
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import realtime_pipeline as rp

    bags, y, subjects, exercises, _ = rp.load_cache(args.features_root, args.sensor)
    X, yr, ye, weights = rp.flattened(bags, y, exercises, np.ones(len(y), dtype=bool))
    qm, em = rp.fit_model(X, yr, weights), rp.fit_model(X, ye, weights)
    q, e = qm.named_steps["logisticregression"], em.named_steps["logisticregression"]
    expected = {
        "exercise_coef": (e.coef_ / em.named_steps["standardscaler"].scale_).astype(np.float32),
        "exercise_intercept": (e.intercept_ - (e.coef_ / em.named_steps["standardscaler"].scale_) @ em.named_steps["standardscaler"].mean_).astype(np.float32),
        "quality_coef": (q.coef_[0] / qm.named_steps["standardscaler"].scale_).astype(np.float32),
        "quality_intercept": np.float32(q.intercept_[0] - (q.coef_[0] / qm.named_steps["standardscaler"].scale_) @ qm.named_steps["standardscaler"].mean_),
    }
    exported = np.load(args.model_dir / "realtime_model.npz", allow_pickle=False)
    if not np.array_equal(exported["exercise_classes"], em.classes_):
        raise AssertionError(f"exported exercise class order {exported['exercise_classes']} differs from sklearn {em.classes_}")
    coefficient_errors = {k: float(np.max(np.abs(exported[k] - v))) for k, v in expected.items()}
    if max(coefficient_errors.values()) > 1e-6:
        raise AssertionError(f"exported coefficient mismatch: {coefficient_errors}")

    with tempfile.TemporaryDirectory(prefix="verify-linear-") as td:
        temp = Path(td)
        (temp / "wrapper.c").write_text(
            '#include "realtime_model.h"\n'
            'int predict(const float *x,float *e,float *q){return rt_predict_rep(x,e,q);}\n'
            'const char *error_category(void){return rt_error_category();}\n')
        so = temp / "wrapper.so"
        host_cmd = ["cc", "-shared", "-fPIC", "-O2", "-I", str(args.model_dir), str(temp / "wrapper.c"), "-lm", "-o", str(so)]
        subprocess.run(host_cmd, check=True)
        lib = ctypes.CDLL(str(so)); f = lib.predict
        f.argtypes = [ctypes.POINTER(ctypes.c_float)] * 3; f.restype = ctypes.c_int
        lib.error_category.restype = ctypes.c_char_p
        err_ex = err_q = 0.0; rep_diffs = series_q_diffs = series_ex_diffs = 0; nrep = 0
        for i, bag in enumerate(bags):
            c_ex = []; c_q = []; py_ex = em.predict_proba(bag); py_q = qm.predict_proba(bag)[:, 1]
            for row, py_e, py_quality in zip(bag, py_ex, py_q):
                x = np.ascontiguousarray(row, dtype=np.float32); ex = np.zeros(len(em.classes_), np.float32); qual = np.zeros(1, np.float32)
                if not f(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), ex.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), qual.ctypes.data_as(ctypes.POINTER(ctypes.c_float))):
                    raise AssertionError(f"C rejected finite feature row in series {i}")
                err_ex = max(err_ex, float(np.max(np.abs(ex - py_e))))
                err_q = max(err_q, float(abs(qual[0] - py_quality)))
                c_ex.append(ex); c_q.append(qual[0]); nrep += 1
            rep_diffs += int(np.count_nonzero(np.argmax(c_ex, axis=1) != np.argmax(py_ex, axis=1)))
            c_q_decision = int(np.mean(c_q) >= .5); py_q_decision = int(np.mean(py_q) >= .5)
            series_q_diffs += int(c_q_decision != py_q_decision)
            c_ex_decision = int(np.argmax(np.mean(c_ex, axis=0))); py_ex_decision = int(np.argmax(np.mean(py_ex, axis=0)))
            series_ex_diffs += int(c_ex_decision != py_ex_decision)
        if max(err_ex, err_q) > 2e-5 or rep_diffs or series_q_diffs or series_ex_diffs:
            raise AssertionError(f"C/sklearn parity failed: ex={err_ex} q={err_q} repdiffs={rep_diffs} series_qdiffs={series_q_diffs} series_exdiffs={series_ex_diffs}")
        coefficient_bytes = sum(exported[k].nbytes for k in ("exercise_coef", "exercise_intercept", "quality_coef", "quality_intercept"))
        report = {"series": len(bags), "repetitions": nrep, "max_exercise_probability_error": err_ex,
                  "max_quality_probability_error": err_q, "implementation_rep_class_differences": rep_diffs,
                  "series_quality_decision_differences": series_q_diffs,
                  "series_exercise_decision_differences": series_ex_diffs,
                  "interpretation": "class differences compare C against sklearn implementation only; repetition correctness has no ground truth",
                  "error_category": lib.error_category().decode(), "coefficient_max_abs_errors": coefficient_errors,
                  "coefficient_float32_bytes_excluding_class_labels": int(coefficient_bytes),
                  "header_bytes": (args.model_dir / "realtime_model.h").stat().st_size,
                  "npz_bytes": (args.model_dir / "realtime_model.npz").stat().st_size,
                  "host_compile_command": shlex.join(host_cmd)}
        if args.arm_object:
            shim = temp / "math.h"
            shim.write_text("float expf(float);\n#define isfinite(x) __builtin_isfinite(x)\n#define INFINITY __builtin_inff()\n")
            arm = temp / "arm.o"
            arm_cmd = ["clang", "--target=arm-none-eabi", "-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard", "-Oz", "-ffreestanding", "-fno-builtin", "-fdata-sections", "-ffunction-sections", "-I", str(temp), "-I", str(args.model_dir), "-c", str(temp / "wrapper.c"), "-o", str(arm)]
            subprocess.run(arm_cmd, check=True)
            size_cmd = ["llvm-size", "-A", str(arm)]
            report["arm_compile_command"] = shlex.join(arm_cmd)
            report["arm_object_sections"] = subprocess.check_output(size_cmd, text=True)
            report["arm_size_command"] = shlex.join(size_cmd)
            report["arm_measurement_scope"] = "unlinked Cortex-M4 object; expf unresolved; excludes board/core/libm/runtime"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
