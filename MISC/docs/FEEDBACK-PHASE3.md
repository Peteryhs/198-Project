# Phase 3 — timing feedback gate (2026-11-07)

## Decision and scope

This phase adds a small portable C rule for prescribed repetition **duration only**. It emits a
fixed tempo message only when the caller supplies a valid target for the same exercise, a valid
measured duration, and an independently validated repetition boundary with a nonempty evidence ID
and scope. The caller must also mark the target as prescribed and identify the prescription version.
The rule checks that `min_seconds <= target_seconds <= max_seconds`; range endpoints are inclusive.
Missing, invalid, unvalidated, or mismatched inputs abstain with a reason code.

The current causal stream detector does not validate anatomical repetition starts or ends. Its
boundaries cannot be passed as independently validated evidence merely because it detected a
cycle. The new layer is deliberately separate from that detector. The C API checks an explicit
caller attestation and carries the provenance through the result; it cannot authenticate the video,
rater, prescription, or the caller's attestation. The JSON config is a **test-only example** with an
explicit placeholder prescription ID, not an approved exercise target or patient setting.

Tempo here means elapsed duration compared with a target range. It does not establish safe form,
exercise quality, anatomical range of motion, posture, effort, grip, force, pain, or the cause of a
deviation. ROM, posture, effort, and grip are enumerated only so the API can explicitly abstain on
them. It cannot emit a binary correct/wrong verdict or combine an unsupported deviation into a
second cue. If a caller reports simultaneous timing and unsupported deviations, only the timing
input is eligible; unsupported categories remain unavailable. This API has not been integrated into
firmware or a patient-facing app.

## Why the first feedback target is timing

The existing round-two error protocol found series labels but no independently labelled repetition
mechanisms or validated anatomical boundaries. It explicitly rejects inferring ROM from an
acceleration envelope and weakness from low acceleration. Duration is the one measured quantity that
can be directly compared with a clinician-prescribed duration without relabelling a sensor pattern
as a cause. Even then, a false timing explanation is possible when boundaries are wrong, which is
why boundary evidence is a hard input gate.

Primary sources opened for this decision:

* Rawashdeh, Reimann & Uhl (2022), [Highly-Individualized Physical Therapy Instruction beyond the
  Clinic Using Wearable Inertial Sensors](https://uknowledge.uky.edu/rehabsci_facpub/129/), abstract,
  lines 27–31: individualized, specialist-defined exercises and real-time correction are described;
  the reported feasibility demonstration covered two exercises performed by one healthy individual.
  That is useful precedent for prescribed targets, but it does not validate these sensors, our
  accelerometer-only boundary detector, or this rule.
* Argent et al. (2021), [The Importance of Real-World Validation of Machine Learning Systems in
  Wearable Exercise Biofeedback Platforms: A Case Study](https://www.mdpi.com/1424-8220/21/7/2346),
  sections 2.2.4–2.5 (PDF lines 202–215, 292–301): two physiotherapists independently reviewed video
  and resolved disagreements; segmentation was measured against manual boundaries; classification
  was evaluated both with manual and automatic segmentation. Sections 3.2 and 4 (lines 321–335,
  459–475) report lower segmentation performance on clinical recordings and discuss label
  subjectivity, population/environment differences, and limits of offline evaluation. This supports
  keeping boundary and feedback evaluation separate. Their clinical exercises and IMU setup differ;
  their performance numbers do not transfer to this project.
* Lee et al. (2023), [Design, Development, and Evaluation of an Interactive Personalized Social Robot
  to Monitor and Coach Post-Stroke Rehabilitation Exercises](https://arxiv.org/abs/2305.07632),
  sections 4.4–4.5 (PDF pp. 10–11) combine ML scores with therapist-derived rules and use consecutive
  frame voting; section 5.3 (p. 13) describes a ten-person healthy-user pilot with instructed
  compensation trials; section 6.1–6.2 and discussion (pp. 14–18) report rule tuning and real-world
  performance. Two therapists separately annotated component labels (p. 12, Cohen's kappa 0.65).
  This is a different RGB/Kinect+robot system and its demo labels include instructed conditions; it
  does not validate our accelerometer boundaries or turn an instruction into an observed outcome.
* Giggins, Sweeney & Caulfield (2014), [Rehabilitation exercise assessment using inertial sensors: a
  cross-sectional analytical study](https://link.springer.com/article/10.1186/1743-0003-11-158),
  methods lines 110–126: a physiotherapist labelled repetition correctness and the most severe error;
  the authors explicitly did not establish intra-rater reliability and removed errors that their
  sensor setup could not classify (lines 119–120). Discussion lines 164–168 describes class imbalance
  and excluded labels. The study motivates exercise-specific evidence, but its single-rater labels,
  three 9-axis lower-limb sensors, and most-severe-label reduction are limitations for our use.
* Bouchouras et al. (2026), [Interpretable Machine Learning Distinguishes Correct from Incorrect
  Rehabilitation Movement with Fewer Wearable Sensors](https://www.mdpi.com/2076-3417/16/10/4592),
  sections 2.8–2.9, 3.2 and 4 (publisher search-indexed full text; direct page open returned HTTP
  429): interpretable feature summaries feed an offline replay policy that requires persistent
  consecutive-window deviations and selected task-specific thresholds under an at-most-10% false
  trigger constraint on correct repetitions. Authors say clinician validation of summaries is
  future work; this is a small instructed-error benchmark, not live or external clinical validation.
  Their “approximately 9%” false cue result is not a threshold to reuse here.

## Boundary and false-feedback evidence plan

The proposed annotation pilot in `ROUND2-ERROR-PROTOCOL.md` is still a later, larger proposal, not
an accepted sample-size guarantee. Before considering it, run a **timing-first feasibility pilot**:
3 volunteers × 3 exercises (EAH/EFE/SQZ) × 4 supervisor-approved timing conditions (within target,
faster, slower, interrupted/unobservable) × 4 repetitions × 2 blocks (before and after self-remount)
= **288 annotated repetitions**. Collect video and sensor data with a visible synchronization event.
Two raters independently mark start/end and uncertainty while blinded to instructed condition and
output; store the **assigned instruction condition separately** from independently **observed
outcomes** (correctness, visible timing, and each visible deviation as separate multi-label fields).
Do not turn the instruction into ground truth: participants may not perform it as requested, and a
deviation may be absent or unobservable. Preserve disagreements, and adjudicate only for a reference label. The supervisor defines
comfortable timing targets and acceptable bands per exercise before collection. Stop or replace any
condition that is not safe or observable. This pilot measures boundary agreement, target applicability,
false tempo cues, abstention on interrupted/unobservable cycles, and remount effects; it does not train
a classifier or demonstrate clinical benefit. Report per-exercise boundary differences, raw agreement,
Cohen's kappa with participant-bootstrap intervals where labels support it, false-cue rate, coverage,
and abstention rate. Continue to the 1,440-repetition proposal only if the video protocol, raters,
prescriptions, and synchronization are workable. Three volunteers and 288 repetitions are a
feasibility budget, **not a sufficient-N claim**; expand based on reliability and between-person and
remount variability.

The hybrid literature is a design precedent, not evidence to attach a classifier trigger here. Lee et
al. combine participant-adapted learned scores with therapist-derived rules and temporal voting, but
their rule thresholds needed tuning and their healthy-user enactments do not substitute for observed
patient outcomes. Giggins et al. used clinician labels but selected only the most severe error and
did not establish intra-rater reliability. Bouchouras et al. explicitly enforced a false-trigger cap
in offline replay yet state that clinical validation remains future work. Phase 3 therefore uses
only a prescribed timing range plus an externally validated boundary; it does not combine the learned
exercise model with an error trigger. For every trial, keep (1) instructed condition, (2) independent
observation, and (3) adjudicated reference distinct; include multiple observed deviations and
`uncertain/not observable` rather than collapsing them to the assigned condition or a single cause.

Replay fixtures in `docs/runs/phase3/feedback-cases.json` contain hand-checked synthetic expected
outputs only. Their evidence IDs deliberately say `fixture`; they are not actual validated
boundaries. Before real replay, an annotation record must identify the source clip, exercise and
prescription version, independent-rater/adjudication status, and scope of the start/end judgment.
False feedback must count against every validated repetition; unobservable, partial, invalid, or
disputed boundaries should be reported as abstentions rather than discarded from coverage.

## Footprint budget and measurement

Before coding, the accepted one-pair estimate in `docs/runs/round2/target-size.json` was 24,728 B
total against 32,768 B RAM, with 8,040 B headroom. The proposed change was one scalar comparison
function with no persistent state, loop, sample buffer, classifier, or transcendental function. I
expected no added persistent RAM and less than 300 B of target text; this was a budget estimate, not
a measurement.

After coding, `feedback-target.log` (recreated by `python scripts/measure_feedback_target.py`)
records a Cortex-M4F `-Oz` unity-object comparison of the
existing left causal pair pipeline with and without `feedback.c`, using the same freestanding flags
and compiler as `scripts/measure_round2_target.py`. Baseline allocated object bytes: 17,034 B
(2,546 text/rodata/exidx + 14,488 B BSS). With feedback: 17,615 B (3,127 + 14,488 B). Increment:
**581 B allocated target object, 0 B BSS, and a compiler-estimated 16 B feedback stack frame**.
The target ABI record sizes from `llvm-nm -S` are 28 B for `FeedbackConfig`, 28 B for
`FeedbackMeasurement`, and 48 B for `FeedbackResult` (104 B total if caller retains all three at
once, excluding any caller-owned strings). The existing conservative total is therefore 24,832 B
including those 104 B, leaving 7,936 B of 32,768 B RAM after the existing reserves. The added
16-byte function frame fits inside the existing 4,096 B stack reserve. The evidence and prescription
strings are borrowed pointers, not copied or allocated by this module; caller-owned dynamic strings
would add their own memory cost.
This is object accounting, not a linked firmware image or measured high-water mark. Existing
unresolved `__aeabi_memclr4`, `expf`, `fmaxf`, `fminf`, and `sqrtf` remain; feedback adds none.
No on-device execution timing was measured. The function has no input-dependent loops and uses
fixed validation branches and scalar comparisons; board timing and patient-facing latency remain
unknown.

## Reproduction and verification

Feedback tests and fixture replay:

```sh
python scripts/test_feedback.py
python scripts/feedback_replay.py
```

The test suite compiles the C module as a host shared library and checks both inclusive range edges,
fast/slow outcomes, null pointers, invalid flags, nonfinite target/lower/upper/measured values,
inconsistent targets, each unsupported category, exercise mismatch, missing evidence, and
unvalidated boundaries. Replay prints the measured duration, target and inclusive bounds,
prescription ID, boundary evidence ID/scope, cue/reason and fixed message. The replay is fixture-level
behavior, not evidence of detector or rater validity.

The independent stored-export verification was rerun without altering `verify_round2.py`, its
assertions, exports, or accepted models:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/tally-round2-env/bin/python -u scripts/verify_round2.py
```

The exact output is retained in `docs/runs/phase3/feedback-verify-round2.log`. It completes with
exact saved coefficient matches for all 10 valid models, zero C probability-decision differences,
and every stored LOSO decision unchanged. Maximum probability errors are printed in the log and
remain below the verifier's asserted `3e-5` parity bound. The previously reported left causal coefficient
drift does not recur in this locked environment; no assertion was weakened or export regenerated.

## Limits and next decision

The code only makes a measured duration comparable to a supplied prescribed range. It has no
independent boundary validator and cannot certify its own evidence metadata. Do not enable it until a
supervisor has set the actual exercise prescription and a separately validated source supplies
boundary evidence. No patient study, real video annotation, false-cue evaluation, clinical review,
firmware integration, full linked-image measurement, or board timing test was performed in this
phase.
