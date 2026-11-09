"""Measure small C models on Cortex-M4F and optionally link a real UNO R4 probe.

The Arduino probe deliberately retains the existing tally application and paired
model, then adds both single-sensor models and a separate 3 s ring. It measures
co-residency, not a validated substitution into the paired application.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs/runs/small-model"
FLAGS = ["--target=arm-none-eabi", "-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16",
         "-mfloat-abi=hard", "-Oz", "-std=c99", "-ffreestanding", "-fno-builtin",
         "-fdata-sections", "-ffunction-sections", "-fstack-usage"]


def run(command, *, check=True):
    command = list(map(str, command))
    result = subprocess.run(command, text=True, capture_output=True)
    record = {"command": command, "returncode": result.returncode,
              "stdout": result.stdout, "stderr": result.stderr}
    if check and result.returncode:
        raise RuntimeError(json.dumps(record, indent=2))
    return record


def section_totals(output):
    totals = {"text": 0, "rodata": 0, "exidx": 0, "data": 0, "bss": 0}
    for line in output.splitlines():
        match = re.match(r"^(\.[^\s]+)\s+(\d+)\s", line)
        if match:
            name, size = match.group(1), int(match.group(2))
            for key in totals:
                if name == "." + key or name.startswith("." + key + ".") or (key == "exidx" and name.startswith(".ARM.exidx")):
                    totals[key] += size
    totals["flash_object_bytes"] = totals["text"] + totals["rodata"] + totals["exidx"] + totals["data"]
    return totals


def measure_model(model_dir, name, temporary):
    """Compile one model with no report writes, suitable for pre-export gating."""
    model_dir, temporary = Path(model_dir), Path(temporary)
    obj = temporary / f"{name}.o"
    (temporary / "math.h").write_text("float expf(float);float sqrtf(float);\n#define isfinite(x) __builtin_isfinite(x)\n")
    compile_result = run(["clang", *FLAGS, "-I", temporary, "-I", model_dir, "-c", model_dir / f"{name}.c", "-o", obj])
    sections = run(["llvm-size", "-A", obj])
    unresolved = run(["llvm-nm", "-u", obj])
    stack = obj.with_suffix(".su")
    source = (model_dir / f"{name}.c").read_text()
    node_count = re.search(r"static const float value\[(\d+)\]", source)
    tree_count = re.search(r"static const uint16_t root\[(\d+)\]", source)
    return {"nodes": int(node_count[1]) if node_count else None,
            "trees": int(tree_count[1]) if tree_count else None, "compile": compile_result, "sections": sections, "totals": section_totals(sections["stdout"]),
            "unresolved": unresolved["stdout"], "stack_usage": stack.read_text() if stack.exists() else ""}


# This computes the same statistic-major x/y/z order as harness.window_features.
FEATURE_PROBE = r'''
#include <math.h>
static float small_ring[300][3], small_features[31];
static void small_window_features(void) {
  for (unsigned a=0; a<3; ++a) {
    float mean=0, energy=0, lo=small_ring[0][a], hi=lo;
    for (unsigned i=0; i<300; ++i) {
      float x=small_ring[i][a]; mean+=x; energy+=x*x;
      if(x<lo)lo=x; if(x>hi)hi=x;
    }
    mean/=300; energy/=300;
    float variance=0, third=0, fourth=0; unsigned crossings=0;
    int previous=0;
    for (unsigned i=0; i<300; ++i) {
      float d=small_ring[i][a]-mean, sq=d*d;
      variance+=sq; third+=sq*d; fourth+=sq*sq;
      int sign=(d>0)-(d<0); if(i && sign!=previous)++crossings; previous=sign;
    }
    variance/=300; float sd=sqrtf(variance), scale=sd>0 ? sd : 1;
    small_features[1+a]=mean; small_features[4+a]=sd;
    small_features[7+a]=lo; small_features[10+a]=hi;
    small_features[13+a]=hi-lo; small_features[16+a]=sqrtf(energy);
    small_features[19+a]=third/(300*scale*scale*scale);
    small_features[22+a]=fourth/(300*scale*scale*scale*scale)-3;
    small_features[25+a]=energy; small_features[28+a]=crossings/300.0f;
  }
}
'''


def state_sizes(temporary):
    source = temporary / "state_sizes.c"
    source.write_text('#include "tally_app.h"\n'
                      'const unsigned char pair_runtime_size[sizeof(PairRuntime)];\n'
                      'const unsigned char tally_app_size[sizeof(TallyApp)];\n'
                      'const unsigned char single_ring_size[300*3*sizeof(float)];\n'
                      'const unsigned char feature_vector_size[31*sizeof(float)];\n')
    obj = temporary / "state_sizes.o"
    compiled = run(["clang", *FLAGS, "-I", ROOT / "model/application", "-c", source, "-o", obj])
    symbols = run(["llvm-nm", "-S", obj])
    sizes = {}
    for line in symbols["stdout"].splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[3].endswith("_size"):
            sizes[fields[3].removesuffix("_size")] = int(fields[1], 16)
    assert sizes["single_ring"] == 3600 and sizes["feature_vector"] == 124
    return {"compile": compiled, "symbols": symbols, "bytes": sizes}


def arduino_probe(cli, model_dir, temporary):
    directory = temporary / "small_model_probe"
    directory.mkdir()
    for name in ("form_rep", "form_window"):
        for suffix in (".c", ".h"):
            shutil.copyfile(model_dir / (name + suffix), directory / (name + suffix))
    original = ROOT / "hardware/198project/198project.ino"
    sketch = ('#include <Arduino.h>\n#include "form_rep.h"\n#include "form_window.h"\n'
              '#define setup tally_probe_setup\n#define loop tally_probe_loop\n'
              f'#include "{original}"\n#undef setup\n#undef loop\n' + FEATURE_PROBE +
              '\nvoid setup(){tally_probe_setup();}\n'
              'void loop(){\n  tally_probe_loop();\n'
              '  unsigned row=micros()%300;\n'
              '  for(unsigned a=0;a<3;++a)small_ring[row][a]=(float)analogRead(A0+a)/1024.0f;\n'
              '  small_features[0]=3.0f; small_window_features();\n'
              '  Serial.println(form_rep_predict(small_features),6);\n'
              '  Serial.println(form_window_predict(small_features+1),6);\n}\n')
    (directory / "small_model_probe.ino").write_text(sketch)
    (directory / "tally_processing.c").write_text(
        f'#include "{ROOT / "hardware/198project/tally_processing.c"}"\n')
    command = [cli, "compile", "--fqbn", "arduino:renesas_uno:minima", "--build-path",
               temporary / "arduino-build", directory]
    compilation = run(command, check=False)
    text = compilation["stdout"] + compilation["stderr"]
    flash = re.search(r"Sketch uses (\d+) bytes.*Maximum is (\d+) bytes", text)
    ram = re.search(r"Global variables use (\d+) bytes.*Maximum is (\d+) bytes", text)
    result = {"compile": compilation, "cli_version": run([cli, "version"]),
              "installed_cores": run([cli, "core", "list"]), "sketch": sketch,
              "scope": "Real board-core link of existing tally sketch/paired model plus both small models, actual statistic extraction and an additional single-sensor ring. Resource probe only; no physical validation or production model substitution."}
    if compilation["returncode"] == 0 and flash and ram:
        result.update({"linked_flash_bytes": int(flash[1]), "flash_limit_bytes": int(flash[2]),
                       "linked_static_ram_bytes": int(ram[1]), "ram_limit_bytes": int(ram[2])})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "model/small")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--budget-bytes", type=int, default=120000)
    parser.add_argument("--arduino-cli", type=Path)
    parser.add_argument("--skip-arduino", action="store_true")
    args = parser.parse_args()
    if args.budget_bytes <= 0:
        parser.error("--budget-bytes must be positive")
    with tempfile.TemporaryDirectory(prefix="small-target-") as directory:
        temporary = Path(directory)
        models = {name: measure_model(args.model_dir, name, temporary)
                  for name in ("form_rep", "form_window")}
        total = sum(model["totals"]["flash_object_bytes"] for model in models.values())
        if total > args.budget_bytes:
            raise SystemExit(f"combined model object budget exceeded: {total} > {args.budget_bytes} bytes")
        report = {"measurement": "Cortex-M4F object sizes, not linked flash", "models": models,
                  "state_sizes": state_sizes(temporary),
                  "combined_model_object_bytes": total, "model_budget_bytes": args.budget_bytes,
                  "model_budget_pass": True, "ram_arithmetic": {
                      "single_sensor_window_ring": "300 samples * 3 axes * sizeof(float)=3600 B",
                      "feature_vector": "31 * sizeof(float)=124 B",
                      "inference_static_ram_bytes": sum(m["totals"]["bss"] + m["totals"]["data"] for m in models.values()),
                      "stack_reserve_bytes": 4096,
                      "scope": "The real link below includes the existing paired app state and an extra single-sensor ring; stack/interrupt high-water is unmeasured."}}
        cli = args.arduino_cli or shutil.which("arduino-cli")
        local_cli = ROOT / "tmp/small-arduino/arduino-cli"
        if not cli and local_cli.is_file():
            cli = local_cli
        if cli and not args.skip_arduino:
            report["arduino"] = arduino_probe(cli, args.model_dir, temporary)
            linked = report["arduino"]
            if "linked_static_ram_bytes" in linked:
                report["ram_arithmetic"]["linked_static_plus_stack_reserve_bytes"] = linked["linked_static_ram_bytes"] + 4096
                report["ram_arithmetic"]["headroom_after_stack_reserve_bytes"] = linked["ram_limit_bytes"] - linked["linked_static_ram_bytes"] - 4096
                linked["flash_headroom_bytes"] = linked["flash_limit_bytes"] - linked["linked_flash_bytes"]
                linked["conservative_entire_probe_within_model_ceiling"] = linked["linked_flash_bytes"] <= args.budget_bytes
                if linked["linked_flash_bytes"] > linked["flash_limit_bytes"]:
                    raise SystemExit("linked board flash budget exceeded")
                if report["ram_arithmetic"]["headroom_after_stack_reserve_bytes"] < 0:
                    raise SystemExit("linked static RAM plus 4096-byte stack reserve exceeds board RAM")
        else:
            report["arduino"] = {"scope": "object sizes, not linked flash", "reason": "Arduino CLI not found or --skip-arduino selected"}
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "target.json").write_text(json.dumps(report, indent=2) + "\n")
        lines = ["Small model target measurement", report["measurement"], ""]
        for name, model in models.items():
            lines.extend([name, "$ " + " ".join(model["compile"]["command"]),
                          "$ " + " ".join(model["sections"]["command"]), model["sections"]["stdout"],
                          "UNRESOLVED", model["unresolved"] or "(none)", "STACK", model["stack_usage"]])
        lines += [f"Combined model object bytes: {total} / {args.budget_bytes}",
                  "ARDUINO", json.dumps(report["arduino"], indent=2),
                  "RAM", json.dumps(report["ram_arithmetic"], indent=2)]
        (args.out / "target.log").write_text("\n".join(lines) + "\n")
        print(json.dumps({"models": {name: model["totals"] for name, model in models.items()},
                          "combined_model_object_bytes": total, "arduino": report["arduino"].get("linked_flash_bytes", report["arduino"].get("reason", "compile failed")),
                          "ram_arithmetic": report["ram_arithmetic"]}, indent=2))


if __name__ == "__main__":
    main()
