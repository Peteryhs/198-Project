from pathlib import Path

import numpy as np

from placement_model_sweep import PATTERN, grid, select_sources, training_mask
from streaming_pipeline import StreamExtractor
import paired_pipeline as pp

ROOT = Path(__file__).resolve().parents[1]


def test_grid_and_bad_geometry():
    import json
    config = json.loads((ROOT / "configs/placement-search.json").read_text())
    mounts = grid(config)
    assert len(mounts) == 81
    assert len({tuple(m.values()) for m in mounts}) == 81
    config["grid"]["upper_fraction"] = [1.0]
    try:
        grid(config)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid fraction accepted")


def test_source_cap_and_fold_isolation():
    rows = [(i, Path(f"{p}.csv"), (p, "EAH", 0)) for i, p in enumerate(["A01", "A01", "B01", "C01"])]
    limited = select_sources(rows, 2)
    assert {r[2][0] for r in limited} == {"A01", "B01"}
    assert np.array_equal(training_mask(np.array(["A", "B", "C"]), "B"), [True, False, True])
    archive_name = PATTERN.match("A3EAH0_1.csv")
    assert archive_name and f"{archive_name[1]}{int(archive_name[2]):02d}" == "A03"


def test_actual_causal_feature_path():
    side = "L"
    upper = ROOT / "data/phytmo/inertial/upper/A/Larm/A01EAH0_1.csv"
    forearm = ROOT / "data/phytmo/inertial/upper/A/Lforearm/A01EAH0_1.csv"
    pair = pp.aligned_pair(pp.read_inertial(str(upper)), pp.read_inertial(str(forearm)))
    with StreamExtractor() as extractor:
        features = extractor(np.clip(pair, -3, 3))
    assert features.ndim == 2 and features.shape[1] == 61 and len(features) >= 1
    assert np.isfinite(features).all()


if __name__ == "__main__":
    test_grid_and_bad_geometry()
    test_source_cap_and_fold_isolation()
    test_actual_causal_feature_path()
    print("placement_model_sweep tests passed")
