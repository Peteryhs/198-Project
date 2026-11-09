"""Measure the Cortex-M4F object budget for the complete tally feedback path."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/runs/basic-feedback"
STREAM = ROOT / "model/streaming"
FEEDBACK = ROOT / "model/feedback"
APP = ROOT / "model/application"
MODEL = ROOT / "model/paired-synchronized-causal/L"
ARDUINO = ROOT / "hardware/198project"
RESERVES = {"stack": 4096, "core": 4096, "display": 1024, "interrupt": 1024}


def run(command):
    command = list(map(str, command))
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr}")
    return {"command": command, "stdout": result.stdout, "stderr": result.stderr}


def parse_sections(text):
    sections = []
    for line in text.splitlines():
        match = re.match(r"^([^\s]+)\s+(\d+)\s+", line)
        if match and match.group(1) != "Total":
            sections.append({"name": match.group(1), "bytes": int(match.group(2))})
    return sections


def parse_symbols(text):
    symbols = []
    for line in text.splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) == 4 and re.fullmatch(r"[0-9a-fA-F]+", fields[0]) and re.fullmatch(r"[0-9a-fA-F]+", fields[1]):
            symbols.append({"address": int(fields[0], 16), "bytes": int(fields[1], 16), "type": fields[2], "name": fields[3]})
    return symbols


def parse_size_totals(text):
    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("malformed llvm-size output")
    values = lines[1].split()
    if len(values) < 5:
        raise ValueError("malformed llvm-size output")
    return {"text_bytes": int(values[0]), "data_bytes": int(values[1]),
            "bss_bytes": int(values[2]), "dec_bytes": int(values[3])}


def main():
    sources = [STREAM / "paired_stream.c", STREAM / "paired_runtime.c",
               FEEDBACK / "feedback.c", FEEDBACK / "feedback_policy.c",
               APP / "tally_app.c"]
    missing = [str(path.relative_to(ROOT)) for path in sources if not path.is_file()]
    if missing:
        raise SystemExit("required target sources not found: " + ", ".join(missing))

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tally-arm-") as directory:
        temp = Path(directory)
        (temp / "math.h").write_text(
            "float sqrtf(float);float fminf(float,float);float fmaxf(float,float);float expf(float);\n"
            "#define isfinite(x) __builtin_isfinite(x)\n#define INFINITY __builtin_inff()\n"
        )
        (temp / "Arduino.h").write_text(
            "#include <stdint.h>\nclass HardwareSerial { public: void begin(unsigned long); "
            "int available(); int read(); void print(const char*); void print(char); "
            "void print(int); void print(unsigned); void print(unsigned long); "
            "void print(float,int=2); void println(); void println(const char*); "
            "void println(int); void println(unsigned); void println(unsigned long); "
            "void println(float,int=2); }; extern HardwareSerial Serial;\n"
        )
        linkage = "#ifdef __cplusplus\nextern \"C\" {\n#endif\n"
        end_linkage = "#ifdef __cplusplus\n}\n#endif\n"
        (temp / "stdio.h").write_text("#define NULL 0\n" + linkage +
                                      "int sscanf(const char *,const char *,...);\n" + end_linkage)
        (temp / "stdlib.h").write_text("#define NULL 0\n" + linkage + "float strtof(const char *,char **);\n" + end_linkage)
        (temp / "string.h").write_text(linkage +
                                       "typedef __SIZE_TYPE__ size_t;\n"
                                       "char *strcpy(char *,const char *);size_t strlen(const char *);"
                                       "int strcmp(const char *,const char *);\n" + end_linkage)
        core_obj = temp / "tally_processing.o"
        sketch_obj = temp / "198project.o"
        flags = ["clang", "--target=arm-none-eabi", "-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16",
                 "-mfloat-abi=hard", "-Oz", "-ffreestanding", "-fno-builtin", "-fdata-sections",
                 "-ffunction-sections", "-fstack-usage", "-I", str(temp), "-I", str(STREAM),
                 "-I", str(FEEDBACK), "-I", str(APP), "-I", str(MODEL)]
        processing_compile = run(flags + ["-I", ARDUINO, "-c", ARDUINO / "tally_processing.c", "-o", core_obj])
        sketch_compile = run(["clang++", "--target=arm-none-eabi", "-mcpu=cortex-m4", "-mthumb",
                              "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard", "-Oz", "-ffreestanding",
                              "-fno-builtin", "-fno-exceptions", "-fno-rtti", "-fdata-sections",
                              "-ffunction-sections", "-fstack-usage", "-I", temp, "-I", ARDUINO,
                              "-x", "c++", "-c", ARDUINO / "198project.ino", "-o", sketch_obj])
        obj = temp / "arduino_path.o"
        linker = shutil.which("ld.lld") or "/usr/lib64/rocm/llvm/bin/ld.lld"
        link_result = run([linker, "-r", "-o", obj, core_obj, sketch_obj])
        sections_result = run(["llvm-size", "-A", obj])
        totals_result = run(["llvm-size", obj])
        symbols_result = run(["llvm-nm", "-S", "--size-sort", obj])
        undefined_result = run(["llvm-nm", "-u", obj])
        baseline_probe = temp / "baseline_probe.c"
        baseline_probe.write_text('#include "paired_runtime.h"\nPairRuntime live;static float result[4];\n'
                                  'int ingest(unsigned ms,const float x[6]){return pair_push(&live,ms,x,result,result+3);}\n'
                                  'int finish(void){return pair_series(&live,result,result+3);}\n')
        baseline_unity = temp / "baseline.c"
        baseline_unity.write_text("".join(f'#include "{source}"\n' for source in sources[:2]) +
                                  f'#include "{baseline_probe}"\n')
        baseline_obj = temp / "baseline.o"
        baseline_compile = run(flags + ["-c", baseline_unity, "-o", baseline_obj])
        baseline_sections = run(["llvm-size", "-A", baseline_obj])
        baseline_totals = run(["llvm-size", baseline_obj])
        size_source = temp / "sizes.c"
        size_source.write_text('#include "tally_app.h"\n'
                               'const unsigned char pair_runtime_size[sizeof(PairRuntime)];\n'
                               'const unsigned char tally_app_size[sizeof(TallyApp)];\n')
        size_obj = temp / "sizes.o"
        size_compile = run(flags + ["-c", size_source, "-o", size_obj])
        state_sizes = run(["llvm-nm", "-S", size_obj])
        stack_files = sorted(temp.glob("*.su"))
        stack_text = "".join(f"[{path.name}]\n{path.read_text()}" for path in stack_files)
        sections = parse_sections(sections_result["stdout"])
        symbols = parse_symbols(symbols_result["stdout"])
        state_symbols = parse_symbols(state_sizes["stdout"])
        bss = sum(s["bytes"] for s in sections if s["name"].startswith(".bss"))
        data = sum(s["bytes"] for s in sections if s["name"].startswith(".data"))
        type_sizes = {symbol["name"].removesuffix("_size"): symbol["bytes"]
                      for symbol in state_symbols}
        baseline_totals_parsed = parse_size_totals(baseline_totals["stdout"])
        full_totals_parsed = parse_size_totals(totals_result["stdout"])
        if bss != full_totals_parsed["bss_bytes"] or data != full_totals_parsed["data_bytes"]:
            raise ValueError("section accounting does not match llvm-size totals")
        app_state_overhead = bss + data - type_sizes["pair_runtime"]
        text_growth = full_totals_parsed.get("text_bytes", 0) - baseline_totals_parsed.get("text_bytes", 0)
        if app_state_overhead > 512:
            raise SystemExit(f"static state budget exceeded: PairRuntime plus {app_state_overhead} B (max 512 B extra)")
        if text_growth > 8192:
            raise SystemExit(f"provisional text growth exceeded: {text_growth} B (max 8192 B)")
        report = {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "measurement": "Cortex-M4F relocatable object with declaration-only Arduino shim; no board core or firmware link",
            "sources": [str((ARDUINO / "tally_processing.c").relative_to(ROOT)),
                        str((ARDUINO / "198project.ino").relative_to(ROOT))],
            "processing_compile": processing_compile,
            "sketch_compile": sketch_compile,
            "relocatable_combine": link_result,
            "baseline_compile": baseline_compile,
            "baseline_section_report": baseline_sections["stdout"],
            "baseline_size_totals": baseline_totals["stdout"],
            "baseline_totals": baseline_totals_parsed,
            "state_size_compile": size_compile,
            "state_size_symbols": state_sizes["stdout"],
            "state_sizes_bytes": type_sizes,
            "section_report": sections_result,
            "size_totals": totals_result,
            "totals": full_totals_parsed,
            "sections": sections,
            "symbols": symbols,
            "unresolved_helpers": undefined_result["stdout"].splitlines(),
            "stack_usage": stack_text,
            "persistent_storage": {"bss_bytes": bss, "data_bytes": data, "bss_plus_data_bytes": bss + data},
            "added_application_state_bytes": type_sizes.get("tally_app", 0) - type_sizes.get("pair_runtime", 0),
            "scaffold_static_overhead_bytes": bss + data - baseline_totals_parsed.get("bss_bytes", 0),
            "application_and_parser_over_pairruntime_bytes": app_state_overhead,
            "text_growth_over_baseline_bytes": text_growth,
            "budget_checks": {"static_extra_max_bytes": 512, "static_extra_pass": app_state_overhead <= 512,
                              "provisional_text_growth_max_bytes": 8192, "text_growth_pass": text_growth <= 8192},
            "reserves_bytes": RESERVES,
            "reserved_memory_bytes": sum(RESERVES.values()),
            "bss_data_plus_reserves_bytes": bss + data + sum(RESERVES.values()),
            "limitations": ["Relocatable object section sizes are not linked firmware totals.",
                            "Arduino.h is a declaration-only compile shim; the Arduino core is not included.",
                            "Unresolved Arduino, stdio, and math helpers require platform toolchain/runtime resolution at link time."],
        }
        (OUT / "target.json").write_text(json.dumps(report, indent=2) + "\n")
        lines = ["Basic feedback Cortex-M4F target measurement", "",
                 "This is a relocatable object measurement with an Arduino declaration shim, not a board-core build or linked firmware.",
                 "Sources: " + ", ".join(report["sources"]), "",
                 "BASELINE PAIR RUNTIME SECTIONS", baseline_sections["stdout"],
                 "BASELINE PAIR RUNTIME TOTALS", baseline_totals["stdout"],
                 "PAIRRUNTIME / TALLYAPP TYPE SIZES", state_sizes["stdout"],
                 f"Persistent size delta over PairRuntime: {type_sizes.get('tally_app', 0) - type_sizes.get('pair_runtime', 0)} bytes",
                 f"Sketch static overhead over baseline PairRuntime, including parser buffers: {bss + data - baseline_totals_parsed.get('bss_bytes', 0)} bytes",
                 f"Sketch BSS plus data beyond PairRuntime: {app_state_overhead} bytes (512-byte cap)",
                 f"Text growth over baseline object: {text_growth} bytes (8192-byte provisional cap)",
                 "SECTION TOTALS (llvm-size -A)", sections_result["stdout"],
                 "SYMBOL SIZES (llvm-nm -S --size-sort)", symbols_result["stdout"],
                 "UNRESOLVED HELPERS", undefined_result["stdout"] or "(none)",
                 "STACK USAGE", stack_text or "(no .su files produced)",
                 "EXPLICIT RESERVES", *(f"{name}: {size} bytes" for name, size in RESERVES.items()),
                 f".bss + .data + reserves: {bss + data + sum(RESERVES.values())} bytes",
                 "", "PROCESSING COMPILE", " ".join(processing_compile["command"]),
                 "SKETCH COMPILE", " ".join(sketch_compile["command"]),
                 "RELOCATABLE COMBINE", " ".join(link_result["command"]), ""]
        (OUT / "target.log").write_text("\n".join(lines))
        print(OUT / "target.log")
        print(f".bss={bss} .data={data} reserves={sum(RESERVES.values())}")


if __name__ == "__main__":
    main()
