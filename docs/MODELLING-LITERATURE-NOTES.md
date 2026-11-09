# Literature notes: weak labels and rehabilitation quality

Checked 2026-11-07. Full papers or dataset records were opened at the linked sources; entries identify when only a dataset record, rather than its related conference paper, was reviewed.

## Conclusions for Tally

PHYTMO supplies exercise identity and one correct/incorrect label per series; it has no per-repetition correctness or error-type labels. The present model can predict exercise and repetition quality probabilities, but its rep scores inherit each series label. Its error-category response is a fixed “not enough evidence to say,” not a learned third head. No source below validates a three-head exercise/quality/error model with error labels absent. MIL pooling can yield latent temporal scores, but they are not verified rep correctness. Collect per-rep and error-type labels before making those claims. Preserve subject-disjoint evaluation; PHYTMO uses 30-subject LOSO.

## Primary sources

### Supervised contrastive quality assessment (2024)

Mark Karlov et al., “Rehabilitation Exercise Quality Assessment through Supervised Contrastive Learning with Hard and Soft Negatives,” *Medical & Biological Engineering & Computing* (2024), DOI [10.1007/s11517-024-03177-x](https://doi.org/10.1007/s11517-024-03177-x). [Full paper, v2](https://arxiv.org/html/2403.02772v2) — opened.

This is supervised skeleton analysis, not wearable IMU or weak-series-label learning. Its 8-layer ST-GCN uses exercise identity and explicit per-rep correctness labels to form contrastive pairs, then compares reps with exercise-specific correct references. Data: UI-PRMD (10 subjects, 10 exercises, 10 correct and 10 incorrect reps each), IRDS (15 patients + 14 controls, 9 exercises), and KIMORE (5 exercises, clinical scores 0–50; 70 samples/exercise). Main UI-PRMD/IRDS results use a 3:1 train/validation split; subject grouping is unspecified. A separate UI-PRMD experiment uses 5-fold CV, also without stated subject grouping. Mean accuracy is .994 without/.998 with the rotation-invariant descriptor on UI-PRMD, and .992 without/.9902 with it on IRDS. High scores are not comparable to PHYTMO LOSO; split-unit uncertainty matters.

### Simulation-based IMU augmentation (2025/2026 preprint)

Andreas Spilz et al., “Boosting Automatic Exercise Evaluation Through Musculoskeletal Simulation-Based IMU Data Augmentation,” [arXiv:2505.24415v2](https://arxiv.org/html/2505.24415v2) — full text opened. Submitted 2025; v2 dated 2026; publication status unverified.

Four lower-body datasets use quaternion orientations from multi-IMU systems: RD (~760 reps/19 people), RGS (~720/18), deep squat (~600/15), hurdle step (~620/15). RD/RGS have instructed error variants; squat/step use three physiotherapists’ FMS ratings (1–3), with label disagreement. Augmentation alters orientations, checks inverse kinematics, and assigns rule-based labels tuned over 10 million threshold combinations—not trajectory scaling. LOSO holds out a subject; remaining subjects split 80/20 train/validation (19/18/15/15 folds). Real-only → augmented-training mean macro-F1: RD .79±.23→.79±.19; RGS .79±.23→.84±.15; squat .66±.39→.87±.23; step .57±.32→.60±.24. It requires rep labels and richer orientation data; results do not transfer directly to upper-limb accelerometer-only PHYTMO.

### Weak supervision on IMU streams (2026 preprint)

Pei Li et al., “WS-IMUBench: Can Weakly Supervised Methods from Audio, Image, and Video Be Adapted for IMU-based Temporal Action Localization?”, arXiv:2602.01850 (2026). [Full paper HTML](https://arxiv.org/abs/2602.01850) — opened; preprint metadata includes an ACM placeholder.

This directly studies sequence-label MIL: temporal segments are instances, and sequence-level activity-presence labels supervise pooled predictions. Seven methods are evaluated on seven IMU datasets with three seeds; LOSO on six, while XRFV2 uses four selected subjects for LOSO plus its in-domain split. LOSO segment mAP (tIoU .3–.7) reaches 65.07% DCASE/RWHAR and 63.29% RSKP/WEAR. Their median action durations are ~621s and ~43s, vs 2.6s for Opportunity, where weak methods struggle. XRFV2 OICR mAP is 17.42% cross-subject vs 67.88% intra-subject. Labels are action presence, not exercise correctness; no rehab reps or error types are tested. Its strongest cases are temporally unlike Tally repetitions.

### Inertial temporal localization with boundaries (2024)

Marius Bock et al., “Temporal Action Localization for Inertial-based Human Activity Recognition,” *ACM IMWUT* 8(4), Article 174 (2024), DOI [10.1145/3699770](https://doi.org/10.1145/3699770). [Full paper PDF](https://kristofvl.github.io/usi/pdf/ubi_imwut24b.pdf) and [code](https://github.com/mariusbock/tal_for_har) — opened.

TAL predicts activity class and start/end boundaries using temporal annotations. The study evaluates six HAR datasets with 1-second windows at 50% overlap and LOSO; offline TAL often beats window classifiers, but the authors find it less suited to immediate small-window classification. It has no weak series labels, rep-quality targets, or error labels. The existing findings doc should not cite this as a method for deriving reps from PHYTMO series labels; WS-IMUBench above is the direct weak-label precedent.

### REHAB24-6 dataset (2024/2025)

Černek et al., “REHAB24-6: A multi-modal dataset of physical rehabilitation exercises.” [MUNI dataset record](https://www.muni.cz/en/research/publications/2562137) and [dataset record](https://explore.openaire.eu/search/dataset?pid=10.5281%2Fzenodo.13305825) — records opened; related full conference paper not reviewed.

The records describe 10 people, six exercises, 65 recordings, and 1,072 reps with start/end boundaries and binary correctness, supervised by a physiotherapist. Data are video and 2D/3D motion-capture skeletons, not IMUs. The records do not specify an official subject-wise split; no split or accuracy should be attributed to the paper from these records. This offers rep-quality ground truth absent from PHYTMO, but only ten subjects and a different modality.

### GAITEX dataset (2025)

Andreas Spilz et al., “GAITEX: Human motion dataset of impaired gait and rehabilitation exercises using inertial and optical sensors,” *Scientific Data* 13, 11 (2025), DOI [10.1038/s41597-025-06439-x](https://doi.org/10.1038/s41597-025-06439-x). [Full paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12775516/) — opened.

GAITEX has nine Xsens IMUs, optical motion capture, rep boundaries, and movement variants for 19 healthy adults. Two lower-limb therapy exercises include correct and three instructed error variants, ten reps each. Authors caution these labels reflect the instructed condition, video-verified, rather than independent quality ratings. The descriptor gives no benchmark split or model metrics. This is a wearable rep-annotation resource, not published accuracy evidence; its population, sensor count, and body region differ from Tally.

### KneE-PAD dataset (2025)

Panagiotis Kasnesis et al., “A Knee Rehabilitation Exercises Dataset for Postural Assessment using Wearable Devices,” *Scientific Data* (2025), DOI [10.1038/s41597-025-04963-4](https://doi.org/10.1038/s41597-025-04963-4). [Paper and dataset record](https://zenodo.org/records/17313606) — opened.

The descriptor reports 2,086 short (~4.2s) files from 31 curated knee patients, three lower-limb exercises, eight sEMG/IMU sensors, and two incorrect variants per exercise. This is rep/file-level error-variant data, not continuous rep localization. Use the paper’s split only after checking its methods; the record alone does not establish subject-disjoint evaluation. Lower-limb and multi-sensor data limit transfer to PHYTMO.

### PhysiQ (2022 comparator)

Hanchen David Wang and Meiyi Ma, “PhysiQ: Off-site Quality Assessment of Exercise in Physical Therapy,” *ACM IMWUT* 6(4), Article 208 (2022), DOI [10.1145/3570349](https://doi.org/10.1145/3570349). [Full paper PDF](https://meiyima.github.io/papers/IMWUT22_PhysiQ.pdf) — opened.

PhysiQ uses smartwatch motion from 31 people doing three shoulder exercises. It evaluates range of motion, stability, and repetition with experimenter-supervised ROM labels, algorithm-derived stability targets, and repetition segmentation. Evaluation includes leave-one-person-out and sliding-window comparisons. Its explicit targets and within-person relative-quality setup do not show that series labels alone identify incorrect reps or error types.

## Corrections to existing claims

- `docs/RESEARCH-FINDINGS.md` §5 misstates Bock et al. as a recipe for deriving reps from series labels; it uses temporal annotations. Cite WS-IMUBench for weak-label method precedent and state the task mismatch.
- The same section describes arXiv:2505.24415 as trajectory scaling; it uses musculoskeletal orientation simulation, inverse kinematics, and tuned rule labels. Its quaternion inputs and lower-limb task differ from PHYTMO.
- The §5 description of arXiv:2403.02772 should state it is supervised per-rep skeleton quality with identity labels, not weakly supervised series labels. Attention pooling alone likewise cannot validate rep correctness.
- No reviewed source supports a learned error-category head without error labels. Do not compare unrelated datasets’ metrics directly with PHYTMO’s bag-level LOSO accuracy.
