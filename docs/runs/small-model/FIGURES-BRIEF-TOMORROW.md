# Figures for tomorrow's progress talk — four charts, Tally brand, minimal

Nothing outside these four figures is needed. The old `FIGURES-BRIEF.md` is deleted; this file
replaces it.

## The talk's argument, which the four figures carry

Not "we made the model smaller". It is: we judge complete repetitions rather than arbitrary time
slices, we reach 89% on people the model has never seen from 30 volunteers of data, degraded sensor
input barely moves it, and all of it fits the board with room to spare.

## Brand: the product is Tally

- **The product is called Tally.** An older brand sheet that called it "form" was stale and has
  been deleted from this repository. Do not use "form" anywhere, and do not look for a brand sheet
  in `docs/`.
- The palette lives with the Android app, in `Tally/app/src/main/res/values/colors.xml`. Read it;
  do not modify anything under `Tally/`:

  | Token | Hex | Use in a figure |
  | --- | --- | --- |
  | `tally_ink` | `#26372C` | type, axes, the existing model |
  | `tally_paper` | `#F5F1E8` | figure ground |
  | `tally_clay` | `#995438` | the one accent: new model, budget line, key number |
  | `tally_oat` | `#D9C9A8` | hairlines, free space, the old model as a secondary mark |
  | `tally_white` | `#FFFFFF` | only if a panel needs to sit apart |

- The mark is the split-angle glyph in
  `Tally/app/src/main/res/drawable/ic_launcher_foreground.xml`: three blocks, path data
  `M40,26 h13 v34 h-13 z M40,60 h11 v11 h-11 z M55,66 h18 v14 h-18 z`, 108-unit viewport, ink on
  paper. Redraw it as vector — do not screenshot it.
- **Every figure carries the lockup bottom right**: that mark plus the wordmark `Tally`, about
  130–160 px wide. Nothing else goes in that corner.
- **Peter will paste a reference image.** If he does, sample its colours with a real pixel read and
  match them; if the pasted image disagrees with `colors.xml`, the pasted image wins and you say so
  with the hexes you sampled. If no image has been pasted, use the table above and say that.
- Type: a warm serif for the short claim line and Inter for every number and label. Neither Inter
  nor a display serif is installed on fedora and matplotlib is not in `.venv`; install them, then
  report the `fc-match` output proving what rendered. A silent fallback is a failed figure.

## Minimal, without exception

- One claim per figure, as a single short line at the top. No subtitle, no explanatory sentence.
- At most three text labels inside the plot area, annotations included.
- Two colours: Ink plus either Clay or Ash. Never three series.
- No legend, no gridlines beyond faint horizontal hairlines at 8% Ink, no frames, no shadows,
  no gradients, no pie charts, no value label on every bar.
- Five ticks maximum per axis, no minor ticks, units in the axis label only.
- 1600 × 900 at 2× PNG, Paper ground, margins at least 15% of the canvas.

## Chart 1 — repetitions are the right unit

Data: `docs/runs/small-model/figures/per-exercise.csv`, rows where `exercise = ALL`.

- Three bars, series-level: 3 s windows, reference RF (Ink), 80.9%; per-repetition logistic
  regression (Ash), 86.5%; per-repetition model (Clay), 89.3%. Y axis 60–95, not 0–100, and say
  so in the caption.
- One label: `+8.4 points` with a thin Clay bracket between the window bar and the Clay bar.
- Claim line: **Judging whole repetitions, not time slices.**

## Chart 2 — high accuracy from a model that fits

Data: `docs/runs/small-model/figures/candidates-size-vs-accuracy.csv`.

- x `nodes` log scale, y `loso_accuracy_pct`. Ash dots for rejected candidates, Clay for the two
  selected, Ink for the reference forests.
- Clay dashed vertical at 10,000 nodes. Three labels: `1,450 nodes · 89.3%`, `107,528 nodes ·
  88.3%`, and `120 kB` on the line.
- Claim line: **Same accuracy at 1/70th the size.**

## Chart 3 — it survives bad sensor data

This chart does not exist yet; you have to run the experiment. It is the one figure with new work.

Method, fixed:

1. Hold the committed models fixed: `model/small/form_rep.joblib` and
   `model/small/form_window.joblib`. No retraining.
2. Degrade only the held-out **test** input, using `scripts/augmentation_pipeline.py
   --generate-only` with the field set in `configs/augmentation-example.json` (orientation up to
   15°, bias ±0.02 g, gain, gaussian noise, one-pole low-pass at 20 Hz, ADC step 0.001017 g,
   clipping at 3 g). Build four tiers by scaling one axis of severity at a time: clean, mild,
   moderate, severe — say exactly what you scaled in the report. Fixed seed, recorded in the CSV.
3. Score each tier with the unchanged feature extraction and models, per-repetition probabilities
   mean-pooled to a series verdict, exactly as `scripts/verify_small_export.py` does.
4. Report per tier, in `docs/runs/small-model/figures/robustness.csv`:
   `tier, seed, n_series, accuracy_pct, delta_pp_vs_clean, spearman_vs_clean, auc_vs_clean`.
   `spearman_vs_clean` is the rank correlation between the clean-arm and degraded-arm P(wrong)
   across the same held-out series: that is the "still ranks them in the same order" claim.
5. Figure: two small panels side by side — accuracy % per tier, and Spearman per tier. Ash to Clay
   across tiers, one line each, tier names on x, three labels total.
6. Claim line: **Degraded input, same ordering.** Print the numbers you measured, even if they are
   bad. If accuracy falls more than 5 points or Spearman drops below 0.8 at the severe tier, say so
   in the report and soften the claim line; do not hide the tier.

## Chart 4 — and it fits on the board

Data: `docs/runs/small-model/figures/footprint.csv`.

- One horizontal stacked bar of 262,144 B: empty sketch 38,984 (Ink), both model objects 39,890
  (Clay), residual 17,290 (Ash, app code + paired runtime + libm, derived), then free 165,980
  (Paper with a hairline). The three used segments total 96,164 — label that once, at the segment.
- A second, much shorter bar underneath: RAM 22,824 of 32,768.
- Caption: only 96,164 B is a linked measurement; object sizes and the residual are not.
- Claim line: **Runs with 63% of flash still free.**

## Captions

- Every figure: "LOSO over 30 volunteers · 1,368 series · chance 49.9%".
- Charts 1 and 2: these hyperparameters were selected on the same LOSO folds they are scored on, so
  roughly one point of the gain is optimistic. One sentence, in the caption.
- Chart 1's unit caveat is mandatory: the window number is per-window, the per-rep number is the
  mean over a series' repetitions.

## Hand back

The four PNGs, the plotting script plus the robustness experiment script, `robustness.csv`, the
`fc-match` output, the hexes sampled from the pasted image, and three lines on anything that did
not match this brief.
