"""Known-geometry and invalid-input checks for sensor-location follow-up."""
import csv
import tempfile
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from sensor_location_followup import _fit_side


def main():
    random = np.random.default_rng(271)
    n = 600
    ru, rf = Rotation.random(n, random_state=random), Rotation.random(n, random_state=random)
    shoulder = np.array([0.1, 1.4, -0.2])
    shoulder_offset, elbow_offset, fore_offset = (np.array([0.01, -0.15, 0.02]),
                                                    np.array([0.01, 0.15, 0.02]),
                                                    np.array([-0.01, 0.13, 0.01]))
    pu = shoulder - ru.apply(np.broadcast_to(shoulder_offset, (n, 3)))
    elbow = pu + ru.apply(np.broadcast_to(elbow_offset, (n, 3)))
    pf = elbow - rf.apply(np.broadcast_to(fore_offset, (n, 3)))
    headers = [['metadata'], [], ['', 'Type'] + ['Rigid Body'] * 14,
               ['', 'Name'] + ['thigh2'] * 7 + ['shin2'] * 7, ['', 'ID'] + ['x'] * 14,
               ['', ''] + ['Rotation'] * 4 + ['Position'] * 3 + ['Rotation'] * 4 + ['Position'] * 3,
               ['Frame', 'Time'] + ['X', 'Y', 'Z', 'W', 'X', 'Y', 'Z'] * 2]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'A3Calib.csv'
        with path.open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerows(headers)
            for i in range(n):
                writer.writerow([i, i / 100, *ru.as_quat()[i], *pu[i], *rf.as_quat()[i], *pf[i]])
        config = {"sample_stride": 2, "split_minimum_samples": 40,
                  "fit_config": {"minimum_samples": 40, "minimum_singular_value_ratio": 0.02,
                                 "maximum_constraint_rms_m": 0.02, "maximum_board_to_joint_distance_m": 0.60}}
        row = _fit_side(path, 'L', config)
        assert row['person'] == 'A03'
        assert all(half['joint_screens_pass'] for half in row['halves'])
        assert np.allclose(row['halves'][0]['shoulder']['board_to_center_m'], shoulder_offset, atol=1e-10)
        assert np.allclose(row['halves'][1]['elbow']['forearm_board_to_center_m'], fore_offset, atol=1e-10)
        try:
            _fit_side(path.with_name('bad.csv'), 'L', config)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid Calib filename accepted')
    print('Sensor-location follow-up checks: exact split-half center recovery, A03 normalization and filename rejection passed')


if __name__ == '__main__':
    main()
