"""Reproduce the Cortex-M4F object and caller-storage budget for feedback."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "model/paired-synchronized-causal/L"


def run(command):
    print("$", " ".join(map(str, command)))
    return subprocess.check_output(command, text=True)


def main():
    with tempfile.TemporaryDirectory(prefix="feedback-arm-") as directory:
        temp = Path(directory)
        (temp / "math.h").write_text(
            "float sqrtf(float);float fminf(float,float);float fmaxf(float,float);float expf(float);\n"
            "#define isfinite(x) __builtin_isfinite(x)\n#define INFINITY __builtin_inff()\n"
        )
        probe = temp / "probe.c"
        probe.write_text(
            '#include "paired_runtime.h"\nPairRuntime live;\nfloat result[4];\n'
            'int ingest(unsigned ms,const float x[6]){return pair_push(&live,ms,x,result,&result[3]);}\n'
            'int finish(void){return pair_series(&live,result,&result[3]);}\n'
        )
        sizes = temp / "sizes.c"
        sizes.write_text(
            '#include "feedback.h"\n'
            'const unsigned char config_bytes[sizeof(FeedbackConfig)];\n'
            'const unsigned char measurement_bytes[sizeof(FeedbackMeasurement)];\n'
            'const unsigned char result_bytes[sizeof(FeedbackResult)];\n'
        )
        flags = ["clang", "--target=arm-none-eabi", "-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16",
                 "-mfloat-abi=hard", "-Oz", "-ffreestanding", "-fno-builtin", "-fdata-sections",
                 "-ffunction-sections", "-fstack-usage", "-I", str(temp), "-I", str(ROOT / "model/streaming"),
                 "-I", str(MODEL)]
        for label, include_feedback in (("baseline", False), ("with_feedback", True)):
            unity = temp / f"{label}.c"
            sources = [ROOT / "model/streaming/paired_stream.c", ROOT / "model/streaming/paired_runtime.c", probe]
            if include_feedback:
                sources.append(ROOT / "model/feedback/feedback.c")
            unity.write_text("".join(f'#include "{source}"\n' for source in sources))
            obj = temp / f"{label}.o"
            run(flags + ["-c", str(unity), "-o", str(obj)])
            print(run(["llvm-size", "-A", str(obj)]), end="")
            print(run(["llvm-size", str(obj)]), end="")
            print("UNRESOLVED SYMBOLS\n" + run(["llvm-nm", "-u", str(obj)]), end="")

        size_object = temp / "sizes.o"
        run(flags + ["-I", str(ROOT / "model/feedback"), "-c", str(sizes), "-o", str(size_object)])
        print("ARM API STORAGE SIZES (llvm-nm symbol bytes)\n" + run(["llvm-nm", "-S", str(size_object)]), end="")
        for usage in sorted(temp.glob("*.su")):
            print(f"STACK USAGE {usage.name}\n{usage.read_text()}", end="")


if __name__ == "__main__":
    main()
