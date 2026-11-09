# Linear prototype exports

These are accelerometer-only modelling prototypes. Each classifier consumes **one** sensor's
31-feature repetition vector. There is no gyro, magnetometer, multi-sensor fusion or joint-angle
input. The classifiers can evaluate a supplied feature vector; the Python repetition detector
is offline and has not been ported to the board.

| Folder | Training sensor streams | Acceleration preprocessing |
| --- | --- | --- |
| `realtime-linear` | All four placements, one recording at a time | Original values |
| `realtime-linear-clipped` | All four placements, one recording at a time | Hard clipping to ±3 g before segmentation |
| `realtime-linear-larm` | Left upper arm only | Original values |
| `realtime-linear-larm-clipped` | Left upper arm only | Hard clipping to ±3 g before segmentation |

Use the known-placement clipped export as the starting candidate for an upper-arm ±3 g prototype.
This choice follows the sensor contract; it is not a clinical performance claim. Other placements
and sensor mounting orientations need their own validation. See `docs/MODELLING-REPORT.md` for
the LOSO scores, class floors and measured export sizes.

`realtime_model.h` contains both heads with scaling folded into float32 affine coefficients.
The feature order is `duration_s`, then **statistic-major**: mean x/y/z, std x/y/z, min x/y/z,
max x/y/z, range x/y/z, RMS x/y/z, skew x/y/z, excess kurtosis x/y/z, mean-square energy x/y/z,
and mean-centered zero-crossing rate x/y/z. This matches `harness.window_features`, rather than
the historical metadata's axis-major wording. Features assume nominal 100 Hz, calibrated units g.

`rt_predict_rep(features, exercise_probabilities, &wrong_score)` returns zero for invalid input
or non-finite logits; callers must abstain and disregard outputs on failure. Exercise class order
is EAH, EFE, SQZ. A successful call returns three softmax values and one sigmoid score. Average
these **probabilities**, not logits, over a series. Use argmax for its exercise and a 0.5 threshold
for its correct/wrong label (0 correct, 1 wrong). Only the series verdict has been evaluated.

The quality fit propagates the series label to each detected segment with equal total weight per
recording. Individual scores have no repetition-level ground truth or calibration guarantee.
`rt_error_category()` always returns `not enough evidence to say`. No error category is inferred.

All exports are final fits on their complete respective training populations; the independent
evaluation is in `loso_folds.csv` / `loso_predictions.csv`, not training-set scores. Metadata records
the range operation and placement. The raw rebuild folders also retain the exact derived feature
matrices and manifests, so they can be passed back to the pipeline with `--features-root`.

The header needs a C math library providing `expf`. Cortex-M4 object compilation and host numerical
parity passed. Board linking, linked math-library size, peak RAM and device timing are unmeasured.
The proposed RAM buffer and causal detector are not implemented by this header.
