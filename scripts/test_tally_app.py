"""Host behavioral checks of the actual portable application and Arduino scaffold."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="tally-app-test-") as directory:
        binary = Path(directory) / "tests"
        command = ["cc", "-std=c99", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                   "-I", str(ROOT / "model/application"),
                   "-I", str(ROOT / "model/paired-synchronized-causal/L"),
                   str(ROOT / "tests/tally_app_test.c"),
                   str(ROOT / "hardware/198project/tally_processing.c"), "-lm", "-o", str(binary)]
        print("$", " ".join(command), flush=True)
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True)
        processing = Path(directory) / "processing.o"
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-c",
                        str(ROOT / "hardware/198project/tally_processing.c"), "-o", str(processing)], check=True)
        subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror", "-I",
                        str(ROOT / "tests/arduino"), str(ROOT / "tests/arduino_sketch_test.cpp"),
                        str(processing), "-lm", "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
