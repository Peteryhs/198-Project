"""Small known-value check for evidence summaries and static figure generation."""
import tempfile
from pathlib import Path

from phase4_figures import calibration_figures, placement_figures, plain_language_figures


def main():
    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp)
        report = {"folds": [{"rows": [
            {"person": "A01", "primary_train_mapped": {"baseline": {"rmse_g": 1}, "calibrated": {"rmse_g": .5}}},
            {"person": "B01", "primary_train_mapped": {"baseline": {"rmse_g": 100}, "calibrated": {"rmse_g": 99}}},
            {"person": "C01", "primary_train_mapped": {"error": "unavailable"}}
        ]}]}
        summary = calibration_figures(report, output)["primary_train_mapped"]
        assert summary == dict(records=2, people=2, baseline_median_rmse_g=50.5,
                               calibrated_median_rmse_g=49.75,
                               reduction_between_medians_percent=100*(1-49.75/50.5))
        rows = [dict(side="L", upper_fraction=uf, forearm_fraction=ff, upper_surface_deg=us,
                     forearm_surface_deg=fs, quality_series_label_agreement_all_denominator=.6,
                     quality_majority_floor_all_denominator=.5)
                for uf in [.3, .5, .7] for ff in [.3, .5, .7] for us in [0, 45, 90] for fs in [0, 45, 90]]
        placement_figures({"rows": rows}, output)
        plain_language_figures({'calibration_gate': {'matched_waveform': {
            'baseline_dynamic_rmse_g_mean': .4, 'calibrated_dynamic_rmse_g_mean': .3,
            'relative_improvement': .25, 'n_dynamic_active_records': 50}}}, output)
        for name in ["calibration-agreement", "placement-map-L", "calibration-simple", "mounting-reference"]:
            assert (output / (name + ".png")).stat().st_size > 1024
            assert "<svg" in (output / (name + ".svg")).read_text()
    print("Figure checks: exact matched-cohort median summary, unavailable-row exclusion and 81-site plot generation passed")


if __name__ == "__main__":
    main()
