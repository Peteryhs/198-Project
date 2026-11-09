# Error mechanisms: position before analysis code

**Decision: keep `not enough evidence to say` for mechanism. Confidence high.** The series label
can validate correct/wrong classification. It cannot validate a named cause, a repetition verdict
or a claim that low acceleration means weak effort. The paper lists common deviations in prose;
there is no mapping from a file/repetition to those mechanisms. Two local accelerometers also
cannot establish trunk compensation, opposite-arm effort, pain or grip force.

## What the existing data can test

Use causal-cycle duration, upper/forearm acceleration-magnitude envelopes and their correlation.
Compare a held-out series with correct-series references from the other volunteers of the same
exercise. Predeclare median/MAD references and absolute robust-z >3 as an exploratory deviation
flag. Print the actual measured quantity, units, reference median/scale and deviation; always keep
mechanism unavailable. Count flag overlap and flag frequencies by series correctness. These
statistics can show non-specific heterogeneity; even perfect clusters would not identify causes
without independent labels. Reject naming clusters, saliency maps, confidence-as-evidence, and
synthetically labelling reduced amplitude as clinical weakness. No new error classifier is proposed.

An eventual phrase such as “cycle duration differs from your prescribed target” would be a
**heuristic** on elapsed time, not an error-type model. A measured acceleration envelope is not
range of motion. A tilt deviation is invalid during unknown translational acceleration. No
patient-facing explanation is enabled by this round. This analysis is host-only, not another
on-board model. Validate any future phrase against the prescription and independently annotated
video, testing false explanations and abstentions on held-out people/remounts.

## Minimum useful annotation pilot (proposal, not a proven sufficient sample size)

There is no defensible numerical minimum that guarantees learnability before measuring label
reliability, effect size and person/remount variability. Budget **12 volunteers × 3 exercises ×
5 conditions × 8 repetitions = 1,440 repetitions**, half before and half after a participant
removes/replaces the two bands. This is a feasibility pilot, not a clinical accuracy claim. Use
LOSO over all 12 people; preprocessing, feature/rule thresholds and any later tuning use only
training people (nested subject folds if tuning becomes necessary). Plot learning curves after
annotation; collect more people, rather than many repetitions from one person, if subject variance
remains high. No patients or unsupervised deliberate faults are needed for the feasibility pilot.

Five planned conditions: comfortable correct execution; visibly reduced excursion; faster tempo;
changed movement plane; interrupted/paused cycle. Approve and operationally define each separately
for EAH/EFE/SQZ; if a condition is unobservable for that exercise, replace it with a safe observable
condition before collecting and record the change. This is a proposed instruction-balanced design,
not a fabricated PHYTMO taxonomy. Do not use “weak” as a target without a separately measured force/
resistance outcome and a clinically agreed definition. Same-motion different-load counterexamples
should be retained as an identifiability check, not relabelled from accelerometer confidence.

## Printable instruction/record sheet

Participant code; session/date; exercise; left/right limb; measured sensor locations from landmarks;
strap photo and orientation marks; ADC calibration/reference/filter settings; remount block; trial
order; instruction condition; approved comfortable range R and target period T (set by supervisor,
not supplied by this code); stop/decline field; video/sensor filenames; sync-event timestamps;
observed completion/uncertainty; prescription version; rater IDs; adjudication notes.

Demonstrate the exercise and the approved condition. Record four repetitions per condition, remove
and self-replace bands using the intended patient instructions, repeat the four repetitions. Balance
condition order across people; include the correct condition in each block. Use a visible LED/event
in sensor logs and two ordinary phones (front and lateral views with a frame-rate/timebase recorded)
to establish boundaries and viewing ambiguity. A supervisor approves comfortable actions and the
instruction sheet; the team obtains consent for the recordings and controls access to video.

## Inter-rater protocol

Two raters first agree a codebook using separate practice clips. They independently annotate
randomized clips, blinded to instructions, model output and each other's labels. Record start/end,
correctness, each visible mechanism as a multi-label field, and “not observable/uncertain”; instructed
condition is stored separately from observed outcome. Annotate continuous elapsed time and visible
excursion landmarks where available. Report raw agreement, per-category confusion, Cohen's kappa
with participant-bootstrap intervals, and boundary-time differences. Preserve disagreements;
resolve through a third reviewer or documented consensus for the training reference. A target
agreement of 0.8 is a planning gate, not a measured result; categories failing reliability remain
unavailable. Check false causal explanations against counterexamples, remounts and load changes.

## Student cost and what would count as success

Use the existing board/two sensors, phones, tape markers and a shared annotation spreadsheet or
free video tool. Estimated collection allocation: 45 minutes per person, 9 total person-session
hours; two raters at 10 seconds per repetition each need 8 rater-hours, plus codebook/adjudication.
These are planning estimates, with arithmetic printed by the analysis command, not observed times
or a price quote. The first success criterion is reliable observation and timing, then a model/rule
that beats its per-category majority floor on held-out people and abstains on unobservable causes.
