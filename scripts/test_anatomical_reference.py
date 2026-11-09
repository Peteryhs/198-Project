import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from anatomical_reference import fixed_center, paired_center


def main():
    config = json.loads(Path("configs/anatomy-reference.json").read_text())
    random = np.random.default_rng(13)
    ru = Rotation.random(400, random_state=random).as_matrix()
    rf = Rotation.random(400, random_state=random).as_matrix()
    shoulder = np.array([.2, 1.6, .3])
    offset = np.array([.02, -.18, .01])
    pu = shoulder - ru @ offset
    fit = fixed_center(ru, pu, config)
    assert np.allclose(fit["board_to_center_m"], offset, atol=1e-10)
    assert np.allclose(fit["world_center_m"], shoulder, atol=1e-10)
    assert fit["conditioning_screen_passed"] and fit["residual_screen_passed"]
    elbow = random.normal(size=(400, 3))
    uf, ff = np.array([.02, .14, .01]), np.array([-.01, -.12, .02])
    fit = paired_center(ru, elbow - ru @ uf, rf, elbow - rf @ ff, config)
    assert np.allclose(fit["upper_board_to_center_m"], uf, atol=1e-10)
    assert np.allclose(fit["forearm_board_to_center_m"], ff, atol=1e-10)
    angle = np.linspace(-1, 1, 400)
    hinge = Rotation.from_rotvec(np.c_[angle, np.zeros((400, 2))]).as_matrix()
    identity = np.broadcast_to(np.eye(3), hinge.shape)
    fit = paired_center(identity, elbow - identity @ uf, hinge, elbow - hinge @ ff, config)
    assert fit["rank"] == 5 and not fit["conditioning_screen_passed"]
    assert fit["constraint_rms_m"] < 1e-10
    try:
        fixed_center(ru[:2], pu[:2], config)
    except ValueError:
        pass
    else:
        raise AssertionError("insufficient geometry samples accepted")
    print("Anatomy constraint checks: known fixed/shared center recovery, mobile joint, hinge-axis non-identifiability and missing-data rejection passed")


if __name__ == "__main__":
    main()
