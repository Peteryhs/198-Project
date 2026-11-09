# PHYTMO baseline and method notes

Working notes for the ECE 198 exercise-monitoring project. Every number here came from a
command in this folder or from a paper/dataset read live; estimates are labelled.

## 1. Dataset

| Fact | Value |
| --- | --- |
| Host | Zenodo, DOI 10.5281/zenodo.6319979 |
| Licence | CC-BY-4.0 |
| Archive | one `PHYTMO.zip`, 3,694,420,037 bytes (3.4 GiB) |
| Contents | 7,171 zip members, 7,075 of them CSV |
| Folders | `inertial/{upper,lower}`, `optical raw`, `optical interp`, `features_extraction.m` |
| Used here | `inertial/upper` only: 1,484 CSV, 598 MB on disk |
| Labelled files | 1,368 (684 correct `0`, 684 wrong `1`) |
| Segments | `Larm`, `Lforearm`, `Rarm`, `Rforearm` |
| Exercises | EAH (arms over head), EFE (elbow flex), SQZ (squeeze) |
| Volunteers | 30, in five age bands A-E |

CSV columns, read from a real file, 100 Hz:

```
Time (s), Gyroscope X/Y/Z (deg/s), Accelerometer X/Y/Z (g), Magnetometer X/Y/Z (uT)
```

Label granularity: **per file**, i.e. one label for a whole series of at least 8 repetitions.
There is no per-repetition ground truth in this dataset.

## 2. What the paper actually did

PHYTMO itself is a data descriptor: no ML method, and "No custom code was used to generate or
process the data". The method is in the companion paper, *Simultaneous exercise recognition and
evaluation in prescribed routines* (arXiv 2401.12857, Expert Systems with Applications 199:116990).

- Sliding windows of 100 / 200 / 300 samples (1 / 2 / 3 s) at 50% overlap.
- **Four time-domain features per axis**: mean, standard deviation, maximum, minimum. With four
  IMUs x six signals that is 96 features per window.
- Classifiers: SVM (linear, polynomial, Gaussian), decision tree, random forest, KNN, ELM, MLP.
- Validation: 30-fold leave-one-subject-out; hyperparameters tuned on 24 volunteers with 5 held
  for validation and one left for testing.
- Reported: 88.4% (single classifier over all exercises) and 91.4% (correct-only recognition).
  Two-stage: 96.2% exercise recognition, then 93.6-100% evaluation per exercise.
- They report their own weakest class as SQZ.

Their Zenodo package ships `features_extraction.m`, which computes **79 features per sensor**
(FFT coefficients, DCT, spectral entropy, inter-axis and vector-norm correlations, quartiles,
skewness, kurtosis, ...). The paper does not use it. That is free headroom.

## 3. Our baseline (this folder)

`harness.py`: 1/2/3 s windows at 50% overlap, 10 features per axis (mean, std, min, max, range,
rms, skew, kurtosis, energy, zero-crossing rate), leave-one-subject-out over all 30 volunteers,
three classical models. Task is pooled across the three upper-limb exercises: correct vs wrong.

Random floor is 50.1% (classes are balanced by construction).

| Window | Model | Accuracy | EAH | EFE | SQZ |
| --- | --- | --- | --- | --- | --- |
| 1 s | logreg | 0.702 | 0.733 | 0.678 | 0.684 |
| 1 s | RF | 0.762 | 0.786 | 0.751 | 0.741 |
| 1 s | HGB | 0.759 | 0.787 | 0.750 | 0.732 |
| 2 s | logreg | 0.754 | 0.786 | 0.750 | 0.716 |
| 2 s | RF | 0.794 | 0.824 | 0.778 | 0.773 |
| 2 s | HGB | 0.795 | 0.831 | 0.788 | 0.754 |
| 3 s | logreg | 0.784 | 0.813 | 0.792 | 0.738 |
| 3 s | **RF** | **0.809** | 0.840 | 0.798 | 0.779 |
| 3 s | HGB | 0.807 | 0.839 | 0.811 | 0.759 |

Adding the gyroscope, same task and split:

| Window | Model | Accuracy | EAH | EFE | SQZ |
| --- | --- | --- | --- | --- | --- |
| 2 s | HGB | 0.814 | 0.851 | 0.813 | 0.768 |
| 3 s | HGB | **0.832** | 0.868 | 0.840 | 0.778 |

**The gyroscope is worth about 2 points** (0.809 -> 0.832). The activity-recognition literature
puts the accel-only penalty at 8+ F1 points, so for exercise *quality* on this dataset the
accelerometer carries nearly all the signal. Two consequences:

1. An accelerometer-only device is defensible here, which is good news for the built design.
2. The binding hardware risk moves to the sensor's range, not its axes.

Window length matters more than the model: 1 s -> 3 s is worth 4.7 points on RF, while swapping
logreg for a gradient-boosted forest at 3 s is worth 2.3.

## 4. Hardware reality, measured by compiling

Compiled with `arduino-cli` against `arduino:renesas_uno` 1.6.0 for `arduino:renesas_uno:minima`:

- An empty Serial sketch: 38,984 B flash / 3,940 B RAM.
- The official Arduino TFLite Micro library **refuses to build** for this board:
  `peripherals.h:61: #error "unsupported board"` (its `library.properties` also depends on
  ArduinoBLE and Arduino_LSM9DS1). After patching the board gates and removing the nRF52840
  glue files it links: 77,540 B flash / 7,444 B RAM with the sine demo.
- `tflite::AllOpsResolver` **overflows flash by 32,116 bytes**. Use `MicroMutableOpResolver` only.
- Headroom after TFLM: ~180 KB flash, ~25 KB RAM. RAM is the wall: a 12-channel x 256-sample
  window is 12,288 B in float and 6,144 B in int16.
- The R4 core ships no CMSIS-DSP (`arm_math`), so any FFT has to be vendored.
- Pin budget: four 3-axis analog sensors need 12 analog inputs; the board has 6 (`A0-A5`).
  This is a hardware decision (external mux, or digital IMUs on I2C/SPI), not a software one.
- ADXL335 with the standard 0.1 uF filter caps has ~50 Hz bandwidth, fine for 100 Hz sampling of
  slow rehab motion. At 5 V reference and 14-bit, one LSB is 1.02 mg against a ~1.34 mg sensor
  noise floor, so 14-bit is matched and more resolution buys nothing.

Nothing above was measured on a real board. No board is attached to this machine.

## 4b. Sensor range is the real problem (measured on the dataset)

`saturation.py` takes the peak |acceleration| per axis, per file, across all 1,368 labelled
upper-limb series:

| Exercise | n | median peak | p90 | over 1.5 g | over 2.0 g | **over 3.0 g** | over 6.0 g |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EAH | 464 | 1.79 g | 4.12 g | 71.8% | 37.3% | **19.4%** | 3.7% |
| EFE | 432 | 1.49 g | 3.61 g | 49.3% | 27.8% | **13.9%** | 2.5% |
| SQZ | 472 | 1.33 g | 2.08 g | 34.1% | 10.8% | **3.0%** | 0.4% |
| all | 1368 | 1.52 g | 3.27 g | 51.7% | 25.1% | **12.0%** | 2.2% |

An ADXL335 saturates at 3 g, so **12% of the recorded series would clip** (near 1 in 5 for arms
over head). A typical rep is fine - the median peak is only 1.5 g - but the fast ones are not,
and a clipped rep is indistinguishable from a badly performed one, which is exactly the thing the
model is supposed to judge. This is a stronger argument than the missing gyroscope, which costs
about 2 points.

Consequence for the BOM: a part with a wider range also tends to be a digital IMU on I2C or SPI,
which removes the 12-channels-on-6-ADC-pins problem at the same time. Worth deciding before
anything is ordered.

## 4c. Repetition segmentation (feasibility check)

`reps.py` detrends the accelerometer magnitude, takes a prominence floor from each file's own
90th percentile and picks peaks at least 1.2 s apart.

| Exercise | median series length | median reps detected | median inter-peak gap |
| --- | --- | --- | --- |
| EAH | 38 s | 20 | 1.84 s |
| EFE | 28 s | 15 | 1.67 s |
| SQZ | 26 s | 15 | 1.62 s |

Median over the whole dataset is 16 reps per series (min 6, max 46), 24,632 repetitions in total
across all 1,368 series. An earlier 200-file sample gave 25 / 20 / 16 because it covered only the
first age band and used a worse detector.

**The detector was validated, and the first version was wrong.** A hand-rolled greedy peak picker
under-counted EFE and SQZ by roughly 2x: its inter-peak interval disagreed with an independent
period estimate (autocorrelation of the same detrended signal) by 107% and 122%. Replacing it with
`scipy.signal.find_peaks` at a 1.2 s minimum distance and a prominence floor from each file's own
90th percentile brings the disagreement to 6-16% and drops the interval coefficient of variation
from 0.46-0.76 to 0.22-0.25. Both the detector and the check are in `reps.py`.

## 4d. Per-repetition scoring beats sliding windows

`mil.py` cuts each series into repetitions, extracts the same 10 features per axis from each
repetition, and trains under the series label. Leave-one-subject-out over 30 subjects, bag-level
accuracy (the only level with ground truth):

| Method | Accuracy | EAH | EFE | SQZ |
| --- | --- | --- | --- | --- |
| 3 s sliding windows (best model) | 0.809 | 0.840 | 0.811 | 0.779 |
| **Repetitions, mean over reps (logistic regression)** | **0.865** | 0.890 | 0.887 | 0.820 |
| **Repetitions, mean over reps (random forest, exported)** | **0.883** | n/a | n/a | n/a |
| Repetitions, max pooling (MIL) | 0.811 | 0.834 | 0.875 | 0.729 |

The random forest arm was added when the model was exported for the repository (`train_export.py`);
it reuses the identical features and pooling and only changes the classifier, so its 88.3% is
directly comparable to the 86.5% beside it. Per-exercise splits were not recorded for that arm.

**Why the forest wins, and whether it really does.** `why_rf.py`, same folds, same features,
per-series predictions compared on the discordant pairs: the forest is right where logistic
regression is wrong 83 times, and wrong where it is right 58 times. Exact McNemar p = 0.043 — real,
but only just past the conventional line, so treat it as "slightly better", not "clearly better".
The mechanism is the shape of the decision boundary: logistic regression fits one hyperplane
through 31 features, while a forest asks threshold questions and combines them, e.g. "duration
above 1.4 s AND shoulder skewness high -> wrong". The features it leans on are the ones where
threshold logic beats a weighted sum: `x_skew` (0.109), `x_max` (0.083), `x_mean` (0.067),
`y_max` (0.066), `y_min` (0.060), `x_zcr` (0.048), `y_std` (0.046), `z_kurt` (0.042). Skewness and
kurtosis describe the *shape* of a repetition, and a linear model can only weight them, not branch
on them.

Random floor is 0.500. **Segmenting into repetitions and averaging the per-rep predictions is
worth +5.6 points over windows**, with the same accelerometer-only data and no extra labels. That
puts an accel-only build at 86.5%, against the paper's 93.6-100% with gyro, magnetometer and one
model per exercise.

The result is robust to the detector fix: the broken detector gave 0.869, the validated one gives
0.865. Coarse segmentation is enough to get the benefit, which is a good sign for a device that
will segment on a 48 MHz micro.

Max-pooling MIL loses to plain averaging, which says something about the labels: these series are
labelled by *how the whole set was performed* (a consistently bad pattern), not by a single bad
repetition. Max pooling assumes "one bad rep makes the bag bad", and that inductive bias is wrong
here. If the team later wants "which repetition was bad", that needs attention pooling or
hand-labelled reps, not max.



## 4e. Keeping the raw samples does not help at this data size

`raw_vs_features.py`, 3 s windows, accelerometer only, same 30-subject LOSO, floor 50.1%:

| Model | Input | Accuracy |
| --- | --- | --- |
| random forest | 30 summary features | 80.9% |
| dense net | 30 summary features | 80.5% |
| dense net | 900 raw samples, in order | 75.2% |
| dense net | 900 raw samples, shuffled | 74.9% |
| logistic regression | 900 raw samples, in order | 60.1% |

- Passing the raw window instead of summaries **cost 5.3 points**. 900 inputs against 1,368
  labelled series is too much freedom.
- Reordering the samples changed the result by **0.3 points**, so the dense net was not using
  sequence even when it was handed it.
- The proven win stays per-repetition segmentation: **+5.6 points**, no architecture change.

Caveats that must travel with these numbers: this is a dense net, not an RNN or a 1D CNN; a
convolution has local-structure priors that a dense layer does not. The dense nets stopped at 80
iterations without converging, so treat 75.2% as indicative rather than final. A real sequence
model remains untested here.

The lesson is not "sequence models are bad". It is that at 1,368 series, extra model capacity buys
nothing, and the cheap structural win (segment into repetitions) outperforms the expensive
architectural one.

## 5. Where to improve on the paper

1. **Per-repetition scoring.** Their label is per file, so they score a whole series. The published
   recipes for turning series labels into per-rep output are multiple-instance learning over
   repetition segments (arXiv 2005.04185), weakly supervised temporal action localisation
   (arXiv 2602.01850), and segment-based TAL (arXiv 2311.15831, repo `mariusbock/tal_for_har`).
   This is the largest gain: it is a capability the paper does not have.
2. **Use the features they shipped but did not use.** Their own `features_extraction.m` has 79
   features per sensor; the paper used 4.
3. **Synthetic repetitions with auto-labels.** `ai-for-sensor-data-analytics-ulm/imu_augment_sim`
   (arXiv 2505.24415) lifted the hardest class from 0.66 to 0.87 LOSO macro-F1 by scaling real
   trajectories per quality class and re-labelling with tuned rule thresholds. The OpenSim half
   needs orientations, which one accelerometer cannot give; the scaling half does not.
4. **Train one model across exercises** with supervised contrastive loss instead of one model per
   exercise (arXiv 2403.02772). Directly relevant: only 6 exercises exist here.
5. **Cross-subject adaptation** rather than more model capacity: test-time normalisation
   (arXiv 2310.18562, repo `Claydon-Wang/OFTTA`) or a handful of patient-specific repetitions.

Do not spend the project on self-supervised IMU pretraining: it needs a large heterogeneous
unlabelled corpus, which this dataset is not.

## 6. Reproduce

```bash
cd ~/work/phytmo
unzip -o -q PHYTMO.zip 'inertial/upper/*' -d data
~/.hermes/bin/uv run --no-project --with numpy --with scikit-learn \
  python harness.py --windows 100 200 300
~/.hermes/bin/uv run --no-project --with numpy --with scikit-learn \
  python harness.py --channels accgyro --windows 200 300
```

Feature matrices are cached in `cache/` by channel set, exercise set, window size and overlap, so
re-running the model grid does not re-read the CSVs.
