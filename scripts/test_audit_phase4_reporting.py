"""Small known-value checks for the independent reporting audit."""
import statistics

from audit_phase4_reporting import close, known_value_checks


def test_known_values():
    assert known_value_checks()
    assert close(0.42460026917629085 * (1 - 0.08317143582024189), 0.3892856551392375)
    # Reduction between separate medians differs from the median paired reduction.
    baseline, calibrated = [1., 100.], [0.5, 99.]
    between_medians = 100 * (1 - statistics.median(calibrated) / statistics.median(baseline))
    median_paired = statistics.median([100 * (1 - b / a) for a, b in zip(baseline, calibrated)])
    assert between_medians != median_paired
    assert close(between_medians, 100 * .75 / 50.5) and close(median_paired, 25.5)


if __name__ == "__main__":
    test_known_values()
    print("independent reporting-audit known-value checks passed")
