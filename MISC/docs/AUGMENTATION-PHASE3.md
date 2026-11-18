# Raw acceleration augmentation — phase three

The augmentation CLI is an offline, versioned transform for synchronized, paired acceleration in g. It can apply bounded per-sensor orientation, fixed three-axis bias/gain, seeded Gaussian noise, a causal first-order low-pass filter, ADC-step quantization and per-axis hard clipping. It preserves the sample count and 100 Hz cadence. Unknown config fields are rejected; time warping, translations, and movement or fault synthesis are unsupported.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /tmp/tally-round2-env/bin/python scripts/augmentation_pipeline.py \
  data/phytmo/inertial/upper --config configs/augmentation-example.json \
  --out data/phase3-augmentation
```

The configured LOSO experiment fixes the paired C feature contract at 100 Hz and ±3 g. Other clip values are available only with `--generate-only`; they cannot silently alter the model evaluation contract. The transform API is `validate_config(config)`, `transform(x, config, seed)`, and `transform_with_provenance(x, config, seed)`. Output files under ignored `data/phase3-augmentation/` include the transformed raw pair, original raw pair, relative time axis, exact sampled rotation matrices, config and source hashes, counterpart file, measured label origin, C-feature coverage, and per-item validation. `example.json` exposes `time_s`, `original_g`, `augmented_g`, `boundaries_s`, `provenance`, and `config` for local visual inspection.

## Evaluation protocol

For each recorded side, the measured and augmented training arms share the same accepted real series, all 30 volunteer folds, C detector/features, fixed `C=1` heads, subject labels, and held-out test inputs. The augmented arm retains each full original series and adds one deterministic transformed copy per source. The source series' total training weight remains one, divided equally among its original and successfully transformed copies; cycle count cannot give one series more weight. Augmentation is generated from raw acceleration before ±3 g clipping. Each test fold contains only its unmodified real recordings. Per-subject intervals resample volunteers (2,000 draws, fixed seed); test scores are not used to select a config.

Source records rejected by pair/timestamp checks or the C minimum-cycle rule remain listed with their reason in `results.json`. Transformed samples that fail the three-cycle check are also listed. Each generated artifact and its manifest entry identify source/counterpart raw CSV SHA-256, aligned-pair SHA-256 and its hash scope, config SHA-256, config version, seed, realized parameters, label origin (`measured series label inherited by transformed copy`), transformation status, validation checks, and training-fold use. LOSO audits list every train/test subject and test source ID, with 29 training subjects, one distinct held-out subject, and all 30 subjects tested. The prediction CSV includes quality and exercise outputs from both arms for independent score checks.

## Full-cohort result

| Side | Real series / seen | Quality floor | Real-only quality → augmented | Quality paired 95% interval | Exercise floor | Real-only exercise → augmented | Exercise paired 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| L | 301 / 342 (88.01%) | 50.17% | 92.36% → 92.36% | [-1.31, +1.32] pp | 34.55% | 98.01% → 98.67% | [0.00, +1.64] pp |
| R | 306 / 342 (89.47%) | 50.65% | 89.87% → 90.20% | [-0.67, +1.62] pp | 33.99% | 97.06% → 97.06% | [0.00, 0.00] pp |

Intervals are the subject-block bootstrap of augmented minus real-only correctness. The exercise majority-class floors are 34.55% (L) and 33.99% (R). Per-subject retained counts, both class floors, all 30 folds, rejected source IDs, predictions and provenance are in the adjacent run artifacts and `data/phase3-augmentation/augmentation-example/{L,R}/results.json`.

This single illustrative configuration produced small, uncertain changes; the intervals include no change for both quality comparisons and right exercise. It is not evidence that augmentation improves the model. Settings derive from engineering assumptions recorded in `ROUND2-RESEARCH.md`, not a calibration of these sensors. The causal first-order digital filter approximates a one-pole bandwidth, and fixed bias/noise/quantization do not capture full hardware behavior. No movement class, translation, pathology, muscle effort, anatomical angle, or clinical error label is synthesized. Repetition labels remain inherited pseudo-labels from the measured series.

Run output and all fold/rejection detail: [augmentation.log](runs/phase3/augmentation.log), [left results](runs/phase3/augmentation-L.json), and [right results](runs/phase3/augmentation-R.json). The raw generated examples are local, ignored artifacts.

## Three distinct validation questions

1. **Implementation correctness:** `scripts/test_augmentation_pipeline.py` checks known transforms,
   gravity-vector norm/rotation, bias/gain, saturation, quantization, causal filtering, deterministic
   seeds, bad inputs and volunteer exclusion. `scripts/verify_phase3_results.py` independently
   recomputes saved task scores, matches real-only decisions to accepted paired exports, checks
   every recorded train/test subject split and source-file hash, and regenerates representative
   saved NPZ examples bit for bit. [Independent audit](runs/phase3/results-audit.log).
2. **Physical/data fidelity:** no actual ADXL335 remount reference exists. The post-experiment
   `scripts/augmentation_fidelity.py` diagnostic compares all 607 matched original/transformed pairs:
   per-axis quantiles, magnitude envelopes, frequency/HF energy, rail contact and within-pair
   magnitude correlation. This descriptive check was specified before running it; it has no fitted
   threshold and did not choose the augmentation configuration. Median left-forearm envelope was
   0.738→0.733 g, dominant frequency 0.7→0.7 Hz, and 5–40 Hz axis-energy fraction 0.0322→0.0270.
   The filter deliberately changes spectral content. Similar aggregate statistics do not establish
   real remount distributions, analog transfer, aliasing or label validity under a different rig.
   [Diagnostics and all rows](runs/phase3/augmentation-fidelity.json),
   [stdout](runs/phase3/augmentation-fidelity.log). Physical fidelity remains **unvalidated**.
3. **Downstream usefulness:** the matched untouched-real LOSO comparison above shows no convincing
   quality benefit. It measures series verdicts, never repetition-quality or fault-category accuracy.

Generate examples without training:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/augmentation_pipeline.py \
  data/phytmo/inertial/upper --config configs/augmentation-example.json \
  --out data/phase3-generation --generate-only
```

Reproduce the diagnostic and audit after the full experiment:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/verify_phase3_results.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/test_augmentation_fidelity.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/augmentation_fidelity.py
```

Measurement variation inherits the source series label because it changes how the same movement
is measured, not the movement instruction or observed outcome. That inheritance is conditional on
the sensor model assumptions and does not validate new hardware. Movement tempo/excursion changes
are explicitly refused: changing timestamps alone misses dynamic acceleration, and a transformed
movement has no defensible new correctness label here. Physical locations are configured separately
in `simulation/placements.json`, whose unvalidated optical replay cannot supply training labels.
