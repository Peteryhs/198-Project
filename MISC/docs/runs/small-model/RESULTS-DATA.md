# Tally / 198 — all measured results, with what each number means

One file, every table I have, each followed by a plain reading and what it must not be used to
claim. Nothing here is an estimate unless the row says estimated.

## The task being measured

The device reads a two-sensor accelerometer setup while someone performs a rehabilitation
exercise, and answers one question per recording: was the form correct or incorrect? Truth comes
from the PHYTMO dataset (Zenodo 6319979, CC-BY-4.0), which labels whole recordings only.

**Dataset:** 1,484 CSV files → 1,368 labelled series, 30 volunteers, three exercises
(EAH arms-overhead, EFE elbow-flex, SQZ squeeze), 24,632 repetitions, 29,871 three-second windows.

**Protocol:** leave-one-subject-out over all 30 volunteers. Every score is on people the model was
not trained on. Chance is 50.0% because the classes are balanced by construction (49.85% at window
level, where the counts are slightly uneven).

## A. Headline numbers

What it is: the shape of the experiment plus the four accuracies that matter.


```csv
metric,value
series,1368
subjects,30
csv_files,1484
rep_series_rows,24632
window_rows,29871
chance_floor_pct,50.0
rep_small_loso_pct,89.327
window_small_loso_pct,81.079
rep_reference_rf_pct,88.304
window_reference_rf_pct,80.941
rep_logreg_pct,86.477
rep_small_nodes,1450
```

How to read it: `rep_small_loso_pct` 89.327 is the shipped repetition model scored on unseen
volunteers — the headline accuracy. `rep_reference_rf_pct` 88.304 is the old 107,528-node forest on
the same splits, so the small model is 1.0 point better, not worse. `rep_logreg_pct` 86.477 is what
a plain logistic regression reaches on the same features — the floor any honest model must beat.
`window_small_loso_pct` 81.079 is the same task judged on 3-second slices instead of repetitions.

Not to be claimed: that 89.3% is comparable to published 99% figures. Those come from per-repetition
labelled data and random splits that leak the same person into train and test.

## B. Per-exercise accuracy

What it is: the same two models broken down by exercise, with the shipped reference forest beside
them, plus how many series changed hands between the two models.


```csv
task,model,exercise,n,accuracy_pct,delta_vs_reference_pp,lost,gained
rep,small-hgb,EAH,464,92.89,-0.86,7,3
rep,reference-rf80,EAH,464,93.75,,,
rep,logreg,EAH,464,89.01,,,
rep,small-hgb,EFE,432,88.89,+3.70,2,18
rep,reference-rf80,EFE,432,85.19,,,
rep,logreg,EFE,432,88.66,,,
rep,small-hgb,SQZ,472,86.23,+0.42,11,13
rep,reference-rf80,SQZ,472,85.81,,,
rep,logreg,SQZ,472,81.99,,,
rep,small-hgb,ALL,1368,89.33,+1.02,,
rep,reference-rf80,ALL,1368,88.30,,,
rep,logreg,ALL,1368,86.48,,,
window,small-hgb,EAH,11926,84.03,+0.36,272,315
window,reference-rf80,EAH,11926,83.67,,,
window,small-hgb,EFE,8955,81.54,+1.26,290,403
window,reference-rf80,EFE,8955,80.28,,,
window,small-hgb,SQZ,8990,76.70,-1.28,402,287
window,reference-rf80,SQZ,8990,77.98,,,
window,small-hgb,ALL,29871,81.08,+0.14,,
window,reference-rf80,ALL,29871,80.94,,,
```

How to read it: `small_pct` is the shipped model, `reference_pct` the old 107,528-node forest.
`delta_vs_reference_pp` is the small model minus the reference in percentage points; `lost` is how
many correct answers the small model gave up, `gained` how many it won. On repetition series it is
ahead overall (+1.02) and better on EFE (+3.70) and SQZ (+0.42), behind on EAH by 0.86 — 7 series
lost, 3 gained, out of 464. On windows it is ahead on EAH (+0.36) and EFE (+1.26), behind on SQZ
(−1.28) — 402 windows lost, 287 gained, out of 8,990.

Why SQZ is hardest: it moves the arm least. Median peak acceleration is 1.33 g for SQZ against
1.79 g for EAH and 1.49 g for EFE, so less signal separates good form from bad.

Not to be claimed: that these differences are a property of the model. They track movement
amplitude, which belongs to the exercise and the sensor.

## C. Every fitted candidate, size against accuracy

What it is: 38 fitted models, each as node count against leave-one-subject-out accuracy. This is
the record of the search that produced the shipped model.


```csv
family,candidate,task,nodes,loso_accuracy_pct,status
hist-gradient-boosting,rep-hgb-l7-n50-lr0.15-l20.0,rep,650,88.962,not selected
hist-gradient-boosting,rep-hgb-l7-n100-lr0.15-l20.0,rep,1300,88.889,not selected
hist-gradient-boosting,rep-hgb-l7-n200-lr0.15-l20.0,rep,2600,89.181,not selected
hist-gradient-boosting,window-hgb-l7-n50-lr0.15-l20.0,window,650,80.513,not selected
hist-gradient-boosting,window-hgb-l7-n100-lr0.15-l20.0,window,1300,80.714,not selected
hist-gradient-boosting,window-hgb-l7-n200-lr0.15-l20.0,window,2600,81.055,not selected
hist-gradient-boosting,rep-hgb-l15-n50-lr0.15-l20.0,rep,1450,89.401,not selected
hist-gradient-boosting,rep-hgb-l15-n100-lr0.15-l20.0,rep,2900,89.181,not selected
hist-gradient-boosting,rep-hgb-l15-n150-lr0.15-l20.0,rep,4350,89.035,not selected
hist-gradient-boosting,window-hgb-l15-n50-lr0.15-l20.0,window,1450,80.921,not selected
hist-gradient-boosting,window-hgb-l15-n100-lr0.15-l20.0,window,2900,81.079,not selected
hist-gradient-boosting,window-hgb-l15-n150-lr0.15-l20.0,window,4350,81.012,not selected
hist-gradient-boosting,rep-hgb-l3-n25-lr0.15-l20.0,rep,125,86.623,not selected
hist-gradient-boosting,rep-hgb-l3-n50-lr0.15-l20.0,rep,250,88.304,not selected
hist-gradient-boosting,rep-hgb-l3-n100-lr0.15-l20.0,rep,500,89.108,not selected
hist-gradient-boosting,rep-hgb-l7-n50-lr0.15-l20.0-f13,rep,650,87.500,not selected
hist-gradient-boosting,rep-hgb-l15-n50-lr0.15-l20.0-float32,rep,1450,89.327,selected
hist-gradient-boosting,window-hgb-l15-n100-lr0.15-l20.0-float32,window,2900,81.079,selected
RandomForest,rep_rf12d7,rep,2234,86.988,not selected
RandomForest,rep_rf12d8,rep,3552,87.573,not selected
RandomForest,rep_rf24d7,rep,4470,87.281,not selected
ExtraTrees,rep_et24d7,rep,3562,83.772,not selected
RandomForest,window_rf12d7,window,2308,80.041,not selected
RandomForest,window_rf12d8,window,3602,80.443,not selected
RandomForest,window_rf24d7,window,4586,80.248,not selected
ExtraTrees,window_et24d7,window,3546,77.630,not selected
RandomForest,rep_rf16d8,rep,4678,87.792,not selected
RandomForest,rep_rf24d8,rep,6992,87.792,not selected
RandomForest,rep_rf8d9,rep,3194,88.085,not selected
RandomForest,rep_rf12d9,rep,4950,88.596,not selected
RandomForest,rep_rf8d10,rep,4524,88.012,not selected
RandomForest,window_rf8d9,window,3686,80.081,not selected
RandomForest,window_rf12d9,window,5430,80.399,not selected
RandomForest,window_rf8d10,window,5104,79.890,not selected
RandomForest,rep_rf12d8_no_redundant,rep,3478,88.158,not selected
RandomForest,rep_rf16d8_no_redundant,rep,4656,87.792,not selected
reference,form-rep-rf (shipped 2.5 MB),rep,107528,88.304,reference
reference,form-window-rf (shipped 2.7 MB),window,114860,80.941,reference
```

How to read it: `nodes` is the fitted model's total decision-node count, the number that decides
flash use — 22 bytes per node in plain C, about 9–10 packed. `family` names the learner. `status`
marks the two rows that shipped. The two `reference` rows are the forests too large for the board
(107,528 and 114,860 nodes against a 10,000-node budget).

What it shows: accuracy stops growing with size past a few thousand nodes. A 1,450-node boosted
model reaches 89.3% where a 107,528-node forest reaches 88.3%, so 74× the size buys nothing here.

Not to be claimed: that these candidates were compared on held-out data. They were all scored on
the same LOSO folds used to choose between them, so roughly one point of the advantage over the
reference is selection optimism.

## D. Window-length sweep

What it is: accuracy against the length of the analysis window, for three learners.


```csv
window_s,model,accuracy_pct
1,logreg,70.2
1,rf,76.2
1,hgb,75.9
2,logreg,75.4
2,rf,79.4
2,hgb,79.5
3,logreg,78.4
3,rf,80.9
3,hgb,80.7
```

How to read it: three-second windows beat one-second windows by 4–6 points for every learner, and
two-second sits between. That is why 3 s was chosen and is not still being tuned.

Not to be claimed: that longer is always better. Past 3 s the window stops fitting inside a single
repetition of the shorter exercises.

## E. Degraded input — accuracy and rank retention

What it is: the shipped models, frozen, scored on input deliberately corrupted before feature
extraction. The clean arm is the untouched recording; each tier adds sensor rotation, bias, gain
error, gaussian noise, a low-pass filter, quantisation and hard clipping at 3 g.


```csv
model,unit,tier,seed,n_units,accuracy_pct,delta_pp_vs_clean,spearman_vs_clean,auc_pct,clean_auc_pct
rep,series,clean,20261110,1368,94.737,0.0,1.0,98.826,98.826
rep,series,mild,20261110,1368,93.567,-1.17,0.9957,98.509,98.826
rep,series,moderate,20261110,1368,90.716,-4.02,0.971,97.25,98.826
rep,series,severe,20261110,1368,86.33,-8.406,0.9118,93.797,98.826
window,window,clean,20261110,29871,88.541,0.0,1.0,95.75,95.75
window,window,mild,20261110,29871,86.987,-1.553,0.9905,94.838,95.75
window,window,moderate,20261110,29871,84.098,-4.442,0.9575,92.655,95.75
window,window,severe,20261110,29871,79.565,-8.975,0.8851,88.563,95.75
```

How to read it: `accuracy_pct` is the verdict accuracy at that tier, `delta_pp_vs_clean` the loss in
points against the clean arm, `spearman_vs_clean` the rank correlation between the clean and
degraded P(wrong) on the same units (1.0 = identical ordering), `auc_pct` the degraded arm's
separation of correct from incorrect against the true labels, with `clean_auc_pct` as its reference.

What it shows: at mild and moderate corruption the cost is 1.2–4.4 points and ordering barely moves
(ρ 0.96–0.996). At the severe tier accuracy falls 8.4–9.0 points, yet the model still ranks sessions
almost identically (ρ 0.912 and 0.885) and keeps about 95% of its clean ranking power (AUC 93.8
against 98.8; 88.6 against 95.8). Honest phrasing: "ordering survives, the decision threshold
drifts", not "the model is unaffected".

Not to be claimed: that these absolute accuracies are the LOSO figures — they are the shipped
all-subject fits, so the clean row reads above 89.3%/81.1%. The delta and the rank correlation are
the finding, not the level. Also not a single measured cause: the severe tier bundles several faults,
one of them 3 g clipping, a real limit of this sensor rather than a software defect.

## F. Incremental value of synthetic training data

What it is: a paired comparison where one arm trains on real recordings only and the other on the
real recordings plus synthetic corrupted copies. Test data is untouched in both arms, so this asks
whether synthetic data helps the model, not whether the model survives bad input.

| Side | Series | Real only | With synthetic | Paired 95% interval on the difference |
| --- | ---: | ---: | ---: | --- |
| L | 301 | 92.36% | 92.36% | −1.31 to +1.32 points |
| R | 306 | 89.87% | 90.20% | −0.67 to +1.62 points |

How to read it: both intervals contain zero, so the honest statement is that synthetic training data
changed nothing measurable — it did not help and did not hurt.

Not to be claimed: that this is evidence of robustness to bad input. Section E is that evidence, and
it is a different experiment.

## G. Raw C inference matches Python

What it is: the same rows scored by the exported C walker and by scikit-learn.

- Repetition rows: 24,632 compared, maximum absolute probability difference 1.81e-07, 100.0% label agreement.
- Window rows: 29,871 compared, maximum absolute probability difference 2.34e-07, 100.0% label agreement.
- All 1,368 series verdicts agree after averaging.

How to read it: the firmware and the training code compute the same function. A correctness check,
not an accuracy claim.

## H. Model size, for reference

The model behind the numbers above is 1,450 nodes and 31 input features; its C arrays are 13,150
bytes with 212 bytes of code. The window model is 2,900 nodes and 26,300 bytes. Both are committed
under `model/small/`. The whole firmware image measured 96,164 bytes of flash and 22,824 bytes of
static RAM.

Not to be claimed: those firmware bytes are a real compile, but latency, stack depth, battery and
thermal behaviour were never measured.
