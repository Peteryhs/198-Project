"""Plot saved calibration and placement evidence; no model fitting or parameter selection."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, CLAY, GREY = "#1c1917", "#9a3b12", "#8c8279"


def save(figure, output, name):
    svg = output / (name + ".svg")
    figure.savefig(svg, bbox_inches="tight")
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    figure.savefig(output / (name + ".png"), dpi=150, bbox_inches="tight")
    plt.close(figure)


def plain_language_figures(report, output):
    wave = report['calibration_gate']['matched_waveform']
    fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
    values = [wave['baseline_dynamic_rmse_g_mean'], wave['calibrated_dynamic_rmse_g_mean']]
    bars = ax.barh(['Before calibration', 'After calibration'], values, color=[GREY, CLAY], height=.5)
    for bar, value in zip(bars, values):
        ax.text(value+.008, bar.get_y()+bar.get_height()/2, f'{value:.3f} g', va='center')
    ax.set(xlim=(0,.55), xlabel='Average dynamic acceleration error (g); lower is better')
    ax.invert_yaxis()
    ax.spines[['top','right']].set_visible(False)
    fig.suptitle(f"{100*wave['relative_improvement']:.1f}% less error, but validation still fails\n"
                 f"{wave['n_dynamic_active_records']} matched active sensor recordings; training-derived timing", fontsize=14)
    save(fig, output, 'calibration-simple')

    fig, ax = plt.subplots(figsize=(9, 6), layout='constrained')
    ax.plot([0,0,0], [1,.5,.08], color='#d6cec6', lw=45, solid_capstyle='round', zorder=0)
    for y, label in [(1,'Shoulder'),(.5,'Elbow'),(.08,'Wrist')]:
        ax.scatter([0],[y],s=120,color=INK)
        ax.text(-.12,y,label,ha='right',va='center',fontsize=12)
    for top, length, segment in [(1,.5,'upper arm'),(.5,.42,'forearm')]:
        for fraction in [.3,.5,.7]:
            y=top-length*fraction
            ax.scatter([0],[y],s=150,color=CLAY if fraction==.5 else GREY,zorder=3)
            ax.text(.10,y,f'{fraction:.0%} of {segment}',va='center',fontsize=12)
    ax.text(.65,.78,'Starting reference\nMiddle of each segment\nLateral surface\nMark sensor orientation',fontsize=14,va='center',color=CLAY)
    ax.text(.65,.32,'Search completed\n9 sites per sensor\n81 paired positions\n0°, 15°, 30° rotation stress',fontsize=14,va='center')
    ax.set(xlim=(-.45,1.8),ylim=(0,1.1),aspect='equal')
    ax.axis('off')
    fig.suptitle('Where the virtual sensors were moved\nReference proposal only; no optimal real-arm position established',fontsize=15)
    fig.text(.5,.015,'Side-view schematic; 0° / 45° / 90° circumferential surfaces were also varied. Anatomy is illustrative.',ha='center',fontsize=10)
    save(fig, output, 'mounting-reference')


def calibration_figures(report, output):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), layout="constrained")
    summary = {}
    for ax, track, title in zip(axes, ["primary_train_mapped", "oracle_diagnostic"],
                               ["Training-derived clock mapping", "Gyro-assisted timing: diagnostic"]):
        pairs = []
        people = set()
        for fold in report["folds"]:
            for row in fold["rows"]:
                result = row.get(track, {})
                if result.get("baseline") and result.get("calibrated"):
                    pairs.append([result["baseline"]["rmse_g"], result["calibrated"]["rmse_g"]])
                    people.add(row["person"])
        if not pairs:
            ax.text(.5, .5, "No matched waveform comparisons", ha="center", transform=ax.transAxes)
            continue
        values = np.asarray(pairs)
        limit = float(values.max()) * 1.05
        ax.scatter(values[:, 0], values[:, 1], s=12, alpha=.4, color=CLAY)
        ax.plot([0, limit], [0, limit], color=GREY, lw=1)
        ax.set(xlim=(0, limit), ylim=(0, limit), xlabel="Baseline waveform RMSE (g)",
               ylabel="Calibrated waveform RMSE (g)", title=title)
        ax.set_aspect("equal")
        medians = np.median(values, axis=0)
        summary[track] = dict(records=len(values), people=len(people), baseline_median_rmse_g=float(medians[0]),
                              calibrated_median_rmse_g=float(medians[1]),
                              reduction_between_medians_percent=float(100 * (1 - medians[1] / medians[0])) if medians[0] else None)
    fig.suptitle("Same-record held-out waveform agreement\nBelow the diagonal means lower error; clock assistance does not establish blind validation", fontsize=13)
    save(fig, output, "calibration-agreement")
    return summary


def waveform_figure(report, output):
    # The first available source is deterministic, rather than the best-looking improvement.
    examples = sorted({row["cache"] for fold in report["folds"] for row in fold["rows"] if row.get("cache")})
    if not examples:
        return None
    path = Path(examples[0])
    with np.load(path, allow_pickle=False) as saved:
        time = saved["time_s"] - saved["time_s"][0]
        keep = time <= 12
        metadata = json.loads(str(saved["metadata_json"]))
        fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True, layout="constrained")
        for k, ax in enumerate(axes):
            for field, label, color, dash in [("baseline_g", "Baseline replay", GREY, "--"),
                                             ("calibrated_g", "Calibrated replay", CLAY, "-"),
                                             ("real_g", "Measured accelerometer", INK, "-")]:
                values = saved[field][:, k].copy()
                values[np.r_[False, np.diff(time) > .015]] = np.nan
                ax.plot(time[keep], values[keep], label=label, color=color, ls=dash, lw=1)
            ax.set_ylabel(f"{'XYZ'[k]} (g)")
            ax.grid(axis="y", color="#dedbd7", lw=.6)
        axes[0].legend(loc="upper right", fontsize=9)
        axes[-1].set_xlabel("Seconds from comparison-window start")
        fig.suptitle(f"First available held-out source: {metadata['person']} / {metadata['exercise']} / {metadata['side']} {metadata['segment']}\nTraining-derived clock mapping; first 12 seconds; no test-record alignment fit", fontsize=12)
        save(fig, output, "waveform-example")
    return dict(path=str(path), metadata=metadata, selection="lexicographically first available primary-track cache")


def placement_figures(report, output):
    rows = report["rows"]
    for side in "LR":
        selected = [r for r in rows if r["side"] == side and r.get("remount_rotation_deg", 0) == 0]
        if not selected:
            continue
        surfaces_u = sorted({r["upper_surface_deg"] for r in selected})
        surfaces_f = sorted({r["forearm_surface_deg"] for r in selected})
        fractions_u = sorted({r["upper_fraction"] for r in selected})
        fractions_f = sorted({r["forearm_fraction"] for r in selected})
        fig, axes = plt.subplots(len(surfaces_u), len(surfaces_f), figsize=(10, 10),
                                 squeeze=False, layout="constrained")
        for i, us in enumerate(surfaces_u):
            for j, fs in enumerate(surfaces_f):
                ax = axes[i, j]
                matrix = np.full((len(fractions_u), len(fractions_f)), np.nan)
                for row in selected:
                    if row["upper_surface_deg"] == us and row["forearm_surface_deg"] == fs:
                        matrix[fractions_u.index(row["upper_fraction"]), fractions_f.index(row["forearm_fraction"])] = 100 * row["quality_series_label_agreement_all_denominator"]
                image = ax.imshow(matrix, cmap="cividis", vmin=0, vmax=100, origin="lower")
                ax.set_xticks(range(len(fractions_f)), [f"{100*f:.0f}%" for f in fractions_f])
                ax.set_yticks(range(len(fractions_u)), [f"{100*f:.0f}%" for f in fractions_u])
                ax.set_title(f"Upper surface {us:g}° / forearm {fs:g}°", fontsize=10)
                for u in range(len(fractions_u)):
                    for f in range(len(fractions_f)):
                        value = matrix[u, f]
                        if np.isfinite(value):
                            ax.text(f, u, f"{value:.1f}", ha="center", va="center", fontsize=12,
                                    color="black" if value > 50 else "white")
                if i == len(surfaces_u) - 1:
                    ax.set_xlabel("Forearm distance from elbow")
                if j == 0:
                    ax.set_ylabel("Upper-arm distance from shoulder")
        fig.colorbar(image, ax=axes, shrink=.75, label="Series-label agreement (%); abstentions count as failures")
        floor = selected[0]["quality_majority_floor_all_denominator"] * 100
        fig.suptitle(f"{side} pair: virtual placement sensitivity — UNVALIDATED DOMAIN\nFrozen real-trained models; training-majority predictor {floor:.1f}%; not real-placement accuracy", fontsize=13)
        save(fig, output, f"placement-map-{side}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, default=Path("docs/runs/phase4/calibration.json"))
    parser.add_argument("--placements", type=Path, default=Path("docs/runs/phase4/placement-sweep.json"))
    parser.add_argument("--out", type=Path, default=Path("docs/figures/phase4"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    calibration = json.loads(args.calibration.read_text())
    plain_language_figures(calibration, args.out)
    summary = calibration_figures(calibration, args.out)
    example = waveform_figure(calibration, args.out)
    placement_figures(json.loads(args.placements.read_text()), args.out)
    result = dict(calibration=summary, example=example,
                  plotting_environment=dict(matplotlib=matplotlib.__version__, numpy=np.__version__),
                  interpretation="Plots summarize saved evidence only; no new model fits or site selection")
    (args.out / "figure-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
