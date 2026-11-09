"""Descriptive matched signal checks; not validation against real remounts or ADXL335."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.signal import welch


def metrics(x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or x.shape[1] != 6 or len(x) < 100 or not np.isfinite(x).all():
        raise ValueError("Expected a finite paired 100 Hz signal of at least one second")
    magnitudes = np.linalg.norm(x.reshape(-1, 2, 3), axis=2)
    segments = []
    for segment in range(2):
        signal = x[:, segment * 3:segment * 3 + 3]
        magnitude = magnitudes[:, segment]
        hz, power = welch(magnitude, fs=100, nperseg=min(len(x), 1000))
        _, axis_power = welch(signal, fs=100, nperseg=min(len(x), 1000), axis=0)
        axis_power = axis_power.sum(axis=1)
        band = (hz >= .15) & (hz <= 3)
        total = axis_power[hz > 0].sum()
        segments.append(dict(axis_p10_p50_p90_g=np.percentile(signal, [10, 50, 90], axis=0).T.tolist(),
                             magnitude_envelope_g=float(np.ptp(np.percentile(magnitude, [5, 95]))),
                             dominant_hz=float(hz[band][np.argmax(power[band])]) if power[band].sum() > 1e-20 else None,
                             hf_fraction=float(axis_power[(hz >= 5) & (hz <= 40)].sum() / total) if total > 1e-20 else 0.,
                             rail_fraction=float(np.mean(np.abs(signal) >= 3 - 1e-6))))
    correlation = (float(np.corrcoef(magnitudes.T)[0, 1])
                   if np.all(magnitudes.std(axis=0) > 1e-10) else None)
    return dict(segments=segments, upper_forearm_magnitude_correlation=correlation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/phase3-augmentation/augmentation-example"))
    parser.add_argument("--out", type=Path, default=Path("docs/runs/phase3/augmentation-fidelity.json"))
    args = parser.parse_args()
    rows = []
    for side in "LR":
        for line in (args.root / side / "augmentation-manifest.jsonl").read_text().splitlines():
            item = json.loads(line)
            with np.load(item["artifact"], allow_pickle=False) as artifact:
                original = np.clip(artifact["original_g"], -3, 3)
                changed = artifact["augmented_g"]
                assert original.shape == changed.shape
                assert np.allclose(np.diff(artifact["time_s"]), .01)
                rows.append(dict(side=side, source_id=item["source_id"], subject=item["subject"],
                                 original=metrics(original), transformed=metrics(changed)))
    summaries = []
    for side in "LR":
        selected = [row for row in rows if row["side"] == side]
        for segment in range(2):
            summary = dict(side=side, segment=segment, recordings=len(selected))
            for key in ["magnitude_envelope_g", "dominant_hz", "hf_fraction", "rail_fraction"]:
                for kind in ["original", "transformed"]:
                    values = [row[kind]["segments"][segment][key] for row in selected
                              if row[kind]["segments"][segment][key] is not None]
                    summary[f"{kind}_{key}_p10_p50_p90"] = np.percentile(values, [10, 50, 90]).tolist() if values else None
            summaries.append(summary)
    report = dict(source="matched source/augmentation signal diagnostics; not physical remount validation",
                  criteria="Descriptive checks declared before this diagnostic run; no threshold selection or model tuning. No physical acceptance claim without independently measured remount/ADXL335 references.",
                  rows=rows, summaries=summaries,
                  interpretation="Per-axis quantiles, envelopes, spectra, clipping and within-pair magnitude correlation quantify transformation effects only. Mathematical correctness, physical fidelity and downstream usefulness remain separate questions.")
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    for row in summaries:
        print(json.dumps(row))
    print(f"{len(rows)} matched pairs; all retained source subjects represented; physical transfer remains unvalidated")


if __name__ == "__main__":
    main()
