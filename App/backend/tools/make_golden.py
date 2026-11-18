"""Generate real-data R/V fixtures using the owner's complete reference checkout.

Run test_stdlib_parity.py in that checkout first, then:
python3 backend/tools/make_golden.py /path/to/full/reference/checkout
NumPy, paired_pipeline.py and data/phytmo are intentionally not shipped in the app.
"""
import argparse
import io
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_root", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    full = args.reference_root.resolve()
    data = full / "data/phytmo/inertial/upper"
    if not (full / "scripts/paired_pipeline.py").is_file() or not data.is_dir():
        parser.error("needs the full reference checkout with scripts/paired_pipeline.py and data/phytmo")
    sys.path[:0] = [str(root / "reference/scripts"), str(full / "scripts")]
    import tally_paired_stream as reference
    import tally_stdlib as runtime
    from paired_pipeline import records

    reference.MODEL_DIR = runtime.MODEL_DIR = root / "reference/model"
    models = {side: runtime.load_model(side) for side in "LR"}
    fixtures = []
    for side in "LR":
        count = 0
        for path, _, samples, error in records(data, side):
            if error or samples is None:
                continue
            wire = reference.wire_from_pair(samples, side)
            expected, actual, out = [], [], io.StringIO()
            reference.run(io.StringIO(wire), emit=False, reply=expected.append)
            runtime.run(io.StringIO(wire), emit=False, out=out, reply=actual.append,
                        models=models, live=False)
            record = json.loads(out.getvalue())
            if record["status"] != "scored":
                continue
            if expected != actual:
                raise AssertionError(f"R/V mismatch: {side} {path}")
            count += 1
            fixtures.append((side, f"{count:02d}", wire, "".join(expected)))
            if count == 6:
                break
        if count < 6:
            raise RuntimeError(f"need 6 scored real series for {side}; found {count}")
    destination = root / "backend/src/test/resources/golden"
    for side, name, wire, reply in fixtures:
        directory = destination / side
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}.wire").write_text(wire, encoding="ascii")
        (directory / f"{name}.reply").write_text(reply, encoding="ascii")
    print(f"measured: generated {len(fixtures)} real-series fixtures with byte-identical NumPy/stdlib R/V")


if __name__ == "__main__":
    main()
