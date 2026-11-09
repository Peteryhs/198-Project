# QA review — round two (simulation, placement, error inference), 2026-11-07

Independent check of the 11 commits imported from `output/round2-commits.bundle` onto
`codex/simulation-placement`. Rerun from a clean locked environment on the same machine, different
interpreter session. Numbers below are mine unless marked otherwise.

## What I verified

| Claim | Result |
| --- | --- |
| Eleven commits import cleanly onto `788facd` | yes, fast-forward, tree clean after reset |
| Environment gate refuses a wrong stack | yes — refuses Python 3.14 / numpy 2.5.4 / sklearn 1.9.1 with an explicit message |
| Paired L offline export: coefficients + stored LOSO | passes |
| Paired R offline export: coefficients + stored LOSO | passes, quality 88.89% / floor 50.65% |
| Paired L causal export: coefficients | **fails, 4.77e-07 in `exercise_coef`** (see fix 1) |
| Simulation rejected on the empirical gate | confirmed, 0 of 84 comparisons passed |
| One limb pair fits RAM | confirmed: 24,728 B estimate of 32,768 B, 8,040 B headroom |
| Two simultaneous limb pairs fit RAM | confirmed **not**: 33,040 B estimated |
| Paired cohort size | 269 of 1,368 series in the common cohort; 301/342 and 306/342 retained per side |

## The three results that change what we do

1. **The pair is worth it, measured.** On the identical 269-series common cohort: left pair 91.08%
   quality, left upper alone 88.85%, left forearm alone 86.99%. Same for the right (90.71 / 87.36 /
   88.48). So the second sensor is worth +2.2 to +4.1 points, and the forearm alone is the weaker
   placement. That is the first quantitative argument for the two-sensor design.
2. **Mounting error is the dominant risk, not model choice.** Rotating held-out real recordings to
   simulate a bad remount: 15 deg costs ~0-3.7 points, 30 deg costs 3.7-13, 60 deg costs 19.7-25.
   A patient who straps the band on crooked every morning loses more accuracy than any model upgrade
   on this list would gain.
3. **Left versus right is indistinguishable.** Left-minus-right quality difference +0.37 points,
   subject-bootstrap 95% interval [-3.3, +4.3]. Do not claim one arm is better.

## Correction, same day

The first version of this file listed three must-fixes. **Two were wrong and are retracted.**

- The MuJoCo command **is** documented. `docs/MODELLING-ENVIRONMENT.md:40` gives
  `uv run --locked --extra simulation python scripts/verify_round2.py` and explains why. My earlier
  claim came from reading a truncated command output instead of opening the file.
- The results table **does** carry cohort size, in a `series` column: 301 / 306 per row.

One real defect remains, below. The lesson is mine: verify a documentation claim by opening the
document, not by reading a failed command's tail.

## Must fix before this round is accepted

1. **`scripts/verify_round2.py` fails on its own assertion.** `verify_paired_export.py:18` asserts
   the coefficient error is *exactly* zero. The two offline exports pass; a fresh refit of the causal
   left export lands at 4.77e-07 in one float32 coefficient and the run aborts before it ever checks
   the causal right. Everywhere else the project tolerates 1e-6 for probabilities, so the assert is
   over-strict rather than the model being wrong — but as it stands the documented verification does
   not complete, which contradicts the report's "all ten valid exports passed coefficient, C parity
   and stored LOSO checks".

## Worth a one-line note, not a fix

- The results table gives 301 / 306 series per row but never says those are a timing-filtered subset
  of the same 1,368 recordings used in the sections above it. A reader can put 92.36% beside 86.99%
  without noticing the cohorts differ. The round-two report explains it; a clause in the table would
  too.

## Decisions this creates for the owner

- **One limb or two.** A single limb pair fits RAM with 8 KB to spare; both limbs at once does not.
  If the device must watch both arms, the plan needs int16 ADC buffers or time-sharing, neither of
  which is implemented.
- **Remount robustness versus model accuracy.** The 30-degree numbers say the money is in the strap,
  a repeatable placement jig, or a calibration step — not in a better classifier.

## What is still unmeasured

Physical ADXL335 noise, calibration and saturation; real acquisition simultaneity across six analog
channels; MCU feature/libm/ADC/display timing; the true repetition-end-to-display latency; any
error-mechanism accuracy (still no labels).
