# Small form model result

PASS — the exported models retain the measured overall LOSO accuracy and fit a real UNO R4 Minima link. The production paired firmware is unchanged; the linked sketch is a conservative resource probe.

## Measured accuracy

All results use all thirty subject-held-out folds, all training rows, and the pinned environment. Repetition verdicts average P(wrong) over repetitions before applying `>= 0.5`; windows are scored per window. Final HGB fits and LOSO use finite float32 features. The export is refitted on all subjects. No per-repetition correctness or error type is inferred.

| Model | Correct / evaluated | LOSO | EAH | EFE | SQZ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selected rep HGB, 15 leaves × 50 iterations | 1222 / 1368 | 89.327485% | 92.887931% | 88.888889% | 86.228814% |
| Selected window HGB, 15 leaves × 100 iterations | 24219 / 29871 | 81.078638% | 84.034882% | 81.541039% | 76.696329% |
| Rerun repetition logistic baseline | 1183 / 1368 | 86.476608% | 89.008621% | 88.657407% | 81.991525% |
| Rerun reference rep RF | 1208 / 1368 | 88.304094% | 93.750000% | 85.185185% | 85.805085% |
| Rerun reference window RF | 24178 / 29871 | 80.941381% | 83.674325% | 80.279174% | 77.975528% |

Commands producing these measurements:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/train_small.py --baselines
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .venv/bin/python scripts/train_small.py --fit
```

See `fit.json`, `baselines.json` and their prediction archives. Baseline refits reproduce the reference family directly; no prior JSON accuracy is used as evidence.

| Exact loss vs rerun reference RF (percentage points; negative means improvement) | Overall | EAH | EFE | SQZ |
| --- | ---: | ---: | ---: | ---: |
| rep | -1.023392 | +0.862069 | -3.703704 | -0.423729 |
| window | -0.137257 | -0.360557 | -1.261865 | +1.279199 |

The selected HGB gains 2.850877 points over the rerun logistic baseline: 79 small-only correct versus 40 logistic-only correct, exact paired McNemar p=0.000445311. The compact RF also retains the requested edge: 2.119883 points, 86/57 discordances, p=0.018891135; its larger node count and lower accuracy favour HGB. These paired p-values are descriptive after candidate selection, not independent confirmatory tests.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/small_forest_candidates.py --compare-probabilities docs/runs/small-model/forest-best-predictions.npz --output tmp/forest-mcnemar.json
```

The overall one-point tolerance does no work for either selected model. The stricter explicit window hard floor is enforced rather than the softer tolerance target. Window SQZ regresses despite the overall gain; a per-exercise nonregression rule would need Peter’s decision. Repetition EAH also regresses; exact losses are above.

## Measured footprint and parity

| Model | Trees | Nodes | Cortex-M4F .text | .rodata | .ARM.exidx | .data / .bss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rep | 50 | 1450 | 212 B | 13150 B | 8 B | 0 / 0 B |
| window | 100 | 2900 | 212 B | 26300 B | 8 B | 0 / 0 B |

Combined model objects: **39,890 B** against the enforced **120,000 B** ceiling, including inference, constant arrays and exception indices. These per-model figures are **object sizes, not linked flash**. They exclude resolved libm; the real link below includes it. Packed separate arrays consume nine bytes per node plus tree-root indices. This is the measured smaller-fit route; the installed emlearn converter rejects HistGradientBoostingClassifier, so these boosted models use the measured custom walker. C99 inference allocates no heap and uses `expf` for the boosted sigmoid; integer quantisation was unnecessary.

Real `arduino-cli compile --fqbn arduino:renesas_uno:minima`: **96,164 / 262,144 B flash**, **22,824 / 32,768 B static RAM**. The entire linked probe is below even the model-only ceiling. It contains the actual existing sketch, tally app, feedback, paired model/runtime, both new models, statistic extraction, Serial, and an additional single-sensor ring and feature vector. It proves co-residency; it does not replace the paired production classifier or validate real-time classification.

```sh
.venv/bin/python scripts/measure_small_target.py
```

The converter limitation is reproducible (the final command intentionally raises `ValueError: Unknown model type`):

```sh
uv pip install --python .venv/bin/python emlearn==0.23.2 setuptools==84.2.1
.venv/bin/python -c 'import emlearn, joblib; emlearn.convert(joblib.load("model/small/form_rep.joblib"))'
```

The script records the exact generated sketch, compile command, compiler stack frames, unresolved object symbols, CLI/core versions, and linker output in `target.json` / `target.log`. It downloads nothing. Recreate the local CLI/core if needed:

```sh
mkdir -p tmp/small-arduino
curl -fL https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Linux_64bit.tar.gz -o tmp/small-arduino/arduino-cli.tar.gz
tar -xzf tmp/small-arduino/arduino-cli.tar.gz -C tmp/small-arduino
tmp/small-arduino/arduino-cli core update-index
tmp/small-arduino/arduino-cli core install arduino:renesas_uno@1.6.0
```

RAM arithmetic: `300 × 3 × sizeof(float) = 3,600 B` for the three-second ring; `31 × sizeof(float) = 124 B` for the reusable feature vector. Inference adds no mutable static RAM. The measured existing `TallyApp` already includes its paired ring and occupies 14,584 B. All linked static allocations total 22,824 B; adding a provisional 4,096 B stack/interrupt reserve gives 26,920 B and 5,848 B remaining. The latter is arithmetic, not measured stack high-water. Each model’s compiler local frame is recorded; libm/core dynamic stack remains unmeasured.

| C vs sklearn on deployment float32 inputs | Real rows | Max absolute probability deviation | Label agreement |
| --- | ---: | ---: | ---: |
| rep | 24632 | 1.808066946e-07 | 100.0% |
| window | 29871 | 2.335598968e-07 | 100.0% |

All repetition-series labels also agree. sklearn and C receive the same float32 real rows. Thresholds are rounded downward onto that grid to preserve `<=`; leaf scores use float32. This fixes a failed initial float64-to-C export. Exploratory float64 HGB scores below are not deployment scores. Source feature extraction is Python float64 then cast; the resource-probe C feature extractor and online repetition boundaries are not end-to-end accuracy validated.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .venv/bin/python scripts/verify_small_export.py --rows 0 --report docs/runs/small-model/parity.json
uv pip install --python .venv/bin/python pytest==8.4.2
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .venv/bin/python -m pytest scripts/test_small_export.py -q
```

Golden real rows, exact split-boundary rounding, invalid input rejection and both byte/node budget failures pass. A deliberately undersized export also failed before writing a model directory (`budget-rejection.log`):

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .venv/bin/python scripts/train_small.py --fit --budget-bytes 1 --output tmp/must-not-exist
test ! -e tmp/must-not-exist
```

## Rejected candidates

Every fitted candidate is listed below. Exact hyperparameters, feature indices, per-exercise results and individual rerun commands are in `boost-candidates.json` / `forest-candidates.json`. Candidates share the same held-out volunteers; no file-level split or training-row cap was used. Fixed reduced-feature sets were chosen without held-out importance fitting.

| HGB candidate | Input | LOSO | Nodes | Decision |
| --- | --- | ---: | ---: | --- |
| rep-hgb-l7-n50-lr0.15-l20.0 | float64 | 88.961988% | 650 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l7-n100-lr0.15-l20.0 | float64 | 88.888889% | 1300 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l7-n200-lr0.15-l20.0 | float64 | 89.181287% | 2600 | exploratory precision; superseded by deployment rerun |
| window-hgb-l7-n50-lr0.15-l20.0 | float64 | 80.512872% | 650 | below acceptance / strict floor |
| window-hgb-l7-n100-lr0.15-l20.0 | float64 | 80.713736% | 1300 | below acceptance / strict floor |
| window-hgb-l7-n200-lr0.15-l20.0 | float64 | 81.055204% | 2600 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l15-n50-lr0.15-l20.0 | float64 | 89.400585% | 1450 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l15-n100-lr0.15-l20.0 | float64 | 89.181287% | 2900 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l15-n150-lr0.15-l20.0 | float64 | 89.035088% | 4350 | exploratory precision; superseded by deployment rerun |
| window-hgb-l15-n50-lr0.15-l20.0 | float64 | 80.921295% | 1450 | exploratory precision; superseded by deployment rerun |
| window-hgb-l15-n100-lr0.15-l20.0 | float64 | 81.078638% | 2900 | exploratory precision; superseded by deployment rerun |
| window-hgb-l15-n150-lr0.15-l20.0 | float64 | 81.011684% | 4350 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l3-n25-lr0.15-l20.0 | float64 | 86.622807% | 125 | below acceptance / strict floor |
| rep-hgb-l3-n50-lr0.15-l20.0 | float64 | 88.304094% | 250 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l3-n100-lr0.15-l20.0 | float64 | 89.108187% | 500 | exploratory precision; superseded by deployment rerun |
| rep-hgb-l7-n50-lr0.15-l20.0-f13 | float64 | 87.500000% | 650 | reduced features lose accuracy |
| rep-hgb-l15-n50-lr0.15-l20.0-float32 | float32 | 89.327485% | 1450 | selected deployment fit |
| window-hgb-l15-n100-lr0.15-l20.0-float32 | float32 | 81.078638% | 2900 | selected deployment fit |

| Forest candidate | Features | LOSO | Nodes | Rejection |
| --- | --- | ---: | ---: | --- |
| rep_rf12d7 | all | 86.988304% | 2234 | below acceptance / strict floor |
| rep_rf12d8 | all | 87.573099% | 3552 | less accurate and/or larger than selected HGB |
| rep_rf24d7 | all | 87.280702% | 4470 | below acceptance / strict floor |
| rep_et24d7 | all | 83.771930% | 3562 | below acceptance / strict floor |
| window_rf12d7 | all | 80.040842% | 2308 | below acceptance / strict floor |
| window_rf12d8 | all | 80.442570% | 3602 | below acceptance / strict floor |
| window_rf24d7 | all | 80.248401% | 4586 | below acceptance / strict floor |
| window_et24d7 | all | 77.630478% | 3546 | below acceptance / strict floor |
| rep_rf16d8 | all | 87.792398% | 4678 | less accurate and/or larger than selected HGB |
| rep_rf24d8 | all | 87.792398% | 6992 | less accurate and/or larger than selected HGB |
| rep_rf8d9 | all | 88.084795% | 3194 | less accurate and/or larger than selected HGB |
| rep_rf12d9 | all | 88.596491% | 4950 | less accurate and/or larger than selected HGB |
| rep_rf8d10 | all | 88.011696% | 4524 | less accurate and/or larger than selected HGB |
| window_rf8d9 | all | 80.081015% | 3686 | below acceptance / strict floor |
| window_rf12d9 | all | 80.399049% | 5430 | below acceptance / strict floor |
| window_rf8d10 | all | 79.890195% | 5104 | below acceptance / strict floor |
| rep_rf12d8_no_redundant | no_redundant | 88.157895% | 3478 | less accurate and/or larger than selected HGB |
| rep_rf16d8_no_redundant | no_redundant | 87.792398% | 4656 | less accurate and/or larger than selected HGB |

Repetition logistic regression is rejected as the shipped fit at 86.476608% because it misses the repetition acceptance threshold. It remains the measured simple baseline. We did not train an MLP, GRU or exercise-conditioned ensemble: a passing compact fit already exists under the unchanged feature and pooling contract. No new LOSO score is claimed for these untested families. Integer threshold quantisation was not needed after measuring the float32 export.

## Self-critique and confidence

The most likely statistical error is selection optimism: hyperparameters were chosen using these same LOSO folds, with no nested selection or untouched cohort. Overlapping windows also make per-window results dependent; volunteers, not windows, define held-out folds. The recorded paired significance tests do not correct for the search.

**Measured, high confidence for reproduction:** dataset inventory, subject split, LOSO counts, full-cohort node counts, C parity on all extracted deployment rows, object sections, real core link/static RAM, and rejection of overbudget exports. Rerun commands and raw outputs are retained here.

**Estimated or untested:** stack/interrupt reserve, timing, physical-board execution, online segmentation parity, feature extraction accuracy in the resource probe, and transfer to new people/sensors. The flash result is linked, not estimated; runtime RAM safety and field accuracy remain provisional.

Only the additive `model/small` artefacts and new metadata entry are deployable exports from this task. Existing large joblibs and paired firmware are unchanged. No push or production model switch is part of this work.
