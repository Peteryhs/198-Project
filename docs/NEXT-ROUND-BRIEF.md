# Codex brief #2 — simulation, sensor placement, error inference

Round two. Written 2026-11-07 after an independent review of round one. Nothing here states the
answer; it states what stands, what is broken, and what must be resolved by you.

---

You are continuing work on Tally, a physics-ish simulator's worth of unanswered questions, and a
model that has to keep running on an 8-bit-era budget of 32 kB of RAM. Read this whole brief first.
Read `docs/QA-REVIEW-2026-11-07.md` second — that is an independent review of your last round, run
by someone who reran your code on a different machine.

## What already stands, and must not be redone

Your previous round is accepted. Specifically, these were reproduced independently:

- Quality, weighted linear, unclipped, leave-one-subject-out over 30 volunteers: **86.99%**,
  reproduced to four decimal places.
- The learning curve (10 / 20 / 29 training volunteers) reproduced exactly.
- `scripts/test_realtime_pipeline.py` passes.
- The C export matches the Python refit with **zero** coefficient difference — under the pinned
  versions. Under a newer scikit-learn the same check fails by up to 0.399, so the export is
  faithful but the environment is not enforced. That is fix 3 below.
- The honesty is good and should continue: the error head returns an explicit unavailable string
  rather than reusing the quality score.

Do not re-derive the baseline, do not retune it, do not rebuild the data fetch.

## Fix these three first, before any new work

1. **The sensor pair is never modelled.** The device's entire premise is two sensors on one limb —
   one on the upper segment, one on the lower — so that the angle between them can be measured.
   Every model in `model/` consumes a single segment's 31 features, and the all-placement arm treats
   each recording independently. Nothing in the repository fuses an upper-arm and a forearm stream
   into one decision. Until that exists, the model is not testing the device we are building.
2. **Nothing is actually real-time.** `realtime_model.h` takes 31 features that are already
   computed, and the segmentation is offline and non-causal: a repetition is only scored once it has
   finished. There is no streaming detector and no on-device feature extraction, so their flash and
   RAM costs are unknown. "Real-time" is currently a label on a batch pipeline.
3. **The environment pin is not enforced.** `scripts/requirements-modelling.txt` states the versions
   but nothing reads them, so a fresh `uv run` resolves newer libraries and breaks the export
   assertion. Fix it so a reader cannot silently reproduce different coefficients.

## What this round is for

Four things, in this order. Each needs a written position before code.

### A. A simulation you can defend

Build a semi-realistic simulation of two accelerometers mounted on a limb, and use it to test the
model. Research first: there may be an environment worth borrowing rather than writing, and if one
exists, borrowing it beats inventing physics.

Requirements that decide whether the simulation is worth anything:

- **It must be validated against the real recordings before you trust a number that comes out of
  it.** State the statistics you compared (envelope, dominant frequency, peak acceleration
  distribution, per-repetition duration) and show the comparison. A simulator that produces smooth
  arcs with no high-frequency content will make any model look fine and mean nothing.
- **It must be able to represent wrong performance**, not just clean performance, or it cannot test
  a quality model at all. Say how you generate a shallow repetition, a fast one, a weak one, a
  misaligned one.
- **Accelerometer only, at ±3 g, 100 Hz, with noise and saturation.** The deployed part is an
  ADXL335. A simulation at ±16 g with no clipping is testing a different device.
- **Say what the simulation cannot represent.** That list is more useful than a confident number.

Note also: the archive we downloaded holds only the inertial folders. The published dataset also
contains optical motion-capture folders — rigid-body positions and orientations recorded
simultaneously for the same volunteers. Whether those are a better starting point than physics you
write yourself is your call to make and defend, but you must make it explicitly rather than
defaulting.

### B. Sensor placement

Determine where the two sensors should go, and prove it with numbers rather than intuition. The
recordings give you four body segments; a pair can be formed two ways per limb. Report the quality
and exercise accuracy for each configuration you can actually measure, and state what the data
cannot distinguish because it was never recorded at that position.

Then answer the harder question: is there a placement that is better for a patient who will put the
band on themselves, badly, every morning? Placement error is a real failure mode and it is not in
any dataset we have.

### C. What the patient did wrong

This is the output the whole product exists for, and it is the one the labels cannot teach.
The dataset says a series was wrong; it never says how. Your previous round handled that honestly by
refusing. Keep refusing if refusing is still right — but first establish whether it must be:

- Is there any signal in these recordings that separates error mechanisms, even without labels —
  and how would you know, absent ground truth?
- What is the minimum labelled data that would make this learnable, and the cheapest way for a team
  of students to collect it? Be specific: how many repetitions, how many people, what instruction
  sheet, what inter-rater protocol.
- If you propose a rule-based or deviation-based explanation instead of a learned one, state plainly
  that it is a heuristic, on what physical quantity it keys, and how you would validate it.

Any output of the form "you did X wrong" must carry its evidence. A model's own confidence is not
evidence. Fabricated error categories are worse than the honest refusal you shipped last time.

### D. Keep it on the board

Every model you propose this round must have a credible path onto the Arduino UNO R4 Minima:
256 kB flash, 32 kB of RAM, 48 MHz Cortex-M4F, six analog pins, 14-bit ADC. Report:

- parameter bytes and a measured C object size for the target, as you did last round;
- **the cost of computing the features on-device**, which nobody has measured yet — the statistics
  per axis, the buffer they need, and the segmentation;
- the latency from "repetition ends" (or better, "mid-repetition") to "answer shown", with the
  arithmetic shown, or an honest "not measured".

If pair fusion or a richer model breaks the budget, say so and propose the smaller thing that fits.
A model that cannot fit is not a result.

## Rules for the whole round

- Leave-one-subject-out over volunteers, always, with the majority-class floor printed beside every
  accuracy. Never tune on a test fold.
- Every number in the report comes from a command you ran; paste the command and its output. Label
  estimates as estimates, and simulations as simulations.
- Never mix a simulated score with a real-data score in the same table without naming which is
  which in the row itself.
- Keep the existing models and their numbers working. Add rows, do not overwrite history.
- Do not commit the dataset, any archive, or anything above 50 MB.
- Do not push, open a pull request, or comment on the repository. Work on a branch, one commit per
  fix or feature, and report the hashes.
- Do not touch the firmware sketch unless your change requires it, and say why if it does.

## Report back with

1. The three fixes, each with the commit that closes it and the check that proves it.
2. A research memo on simulators, placement and error inference, with links you actually opened and
   the claims you could not verify.
3. The plan for A–D, with rejected alternatives, confidence marks, and decisions that are ours.
4. A results table where every row says whether it came from real recordings or from the simulation.
5. What is still unproven, and the single next experiment you would run.
6. Decisions for the owner.

Ask before you assume. If the repository does not match this description, stop and say so.
