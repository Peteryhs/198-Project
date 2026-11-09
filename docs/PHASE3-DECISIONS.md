# Phase three — research and decisions

Recorded 2026-11-07 before the new implementation and held-out experiment results.
Start state: `57aa2b6`, `codex/simulation-placement`, with untracked `output/` and `tmp/`.
Work branch: `codex/modelling-augmentation-feedback`. Those directories, historical exports,
raw recordings and firmware are preserved. No push, PR or repository comment is authorized.

## Decisions

1. **Reuse the measured paired pipeline, fixed 61-feature linear heads and subject folds.**
   Train measurement perturbations only on the other volunteers and test untouched recordings.
   Never generate a movement-quality category from the fact that a signal was transformed.
   Fixed model dimensions preserve the 992 B coefficient budget; host augmentation adds no
   on-device buffer. Confidence: high in the protocol, unknown in downstream benefit until run.
2. **Audit the failed simulation instead of relaxing its gate.** Check rigid-body specific force,
   frames, site translation, trajectory derivatives and the optical data's timing/origins.
   Prefer optical rigid-body replay to invented exercise arcs, but validate at recorded sites
   before extrapolating to physical mounts. Preserve the original [round-two gate](ROUND2-PLAN.md).
   If calibration is not identifiable, deliver four physically defined exploratory candidates
   with mechanical sensitivity and explicit unavailable real-site classification. Confidence:
   medium in mechanics, low in PHYTMO-to-ADXL335 fidelity.
3. **Separate observable feedback from the quality classifier.** A prescribed-duration rule can
   fire independently of a correct/wrong prediction, but only with valid boundaries and an actual
   prescription. Current C peak-confirmation intervals are not validated anatomical repetitions:
   their default feedback is abstention. No ROM, grip, weakness, posture or effort head.
   Confidence: high in the scope restriction; patient usefulness remains unmeasured.
4. **Use a local standard-library server and ordinary HTML/canvas.** Display the exact Python
   transformation, seed and label lineage. No new UI framework or reconstructed joint angles.
   A mount schematic/animation is explicitly illustrative, never calibrated to acceleration.
5. **Preserve exact export assertions.** Independently rerun in the pinned single-thread numerical
   environment; investigate any drift rather than refreshing coefficients or widening tolerances.

## Opened primary engineering sources

- Analog Devices, **ADXL335 Rev. B (2010)**: opened specifications p. 3 and applications pp. 11–12,
  especially bandwidth/noise, aliasing and ratiometric response. The output range, gain, reference
  and filtering require measured settings; post-hoc digital clipping/filtering of another rig
  cannot reproduce all analog behavior. [Manufacturer PDF](https://www.analog.com/media/en/technical-documentation/data-sheets/ADXL335.pdf).
- García-de-Villa et al., **PHYTMO descriptor (2022)**: opened methods, acquisition and data records,
  pp. 2–10. Whole-series correctness and optical rigid-body pose are useful; they do not supply
  repetition mechanisms or a verified chip-origin/clock calibration for this continuation.
  [Full descriptor](https://arxiv.org/pdf/2401.12868).
- **MuJoCo official XML reference**, accessed 2026-11-07, accelerometer section: the site determines
  the sensor origin and axes. This supports independent site/rigid-body tests, not an empirical
  claim about exercise distributions. [Sensor reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html#sensor-accelerometer).

The feedback literature audit, opened methods/evaluation sections, dates and modality/label limits
are in [FEEDBACK-PHASE3.md](FEEDBACK-PHASE3.md). The simulator audit records its additional sources.

## Rejected alternatives

- Tuning smooth simulated arcs to classifier confidence: neither signal fidelity nor quality truth.
- Applying acceleration-only translations or timestamp-only speed changes: unobserved angular
  motion and dynamic acceleration would be invented. Signal time warps, if later used, need a
  separately labelled approximation and a fidelity experiment.
- Fitting test-person lag, gain, placement or thresholds: leaks validation into calibration.
- Ranking four unrecorded sites by one weighted score: no validated weights or physical outcomes.
- A large diagnostic model/UI framework: no independent error labels or project need.

## Visual contract

- Surface: local engineering editor/inspection tool.
- User job: inspect mounts, replay signals and verify transformation/provenance.
- Reference family: editor canvas with developer-tool density.
- Design source: existing `docs/brand/BRAND.md` ink/paper/clay tokens; system sans fonts, Tally name
  follows the current brief (the historical brand sheet uses “form”).
- Density/layout: compact header; diagram/controls beside stacked shared-axis traces; provenance below.
- CRUD create mode: none; controls produce an ephemeral preview, no dataset editing.
- Required states: loading, missing recording, invalid parameters, paused/playing, unavailable
  calibrated motion, clipping and no detected boundaries.
- Forbidden tells: fabricated joint angles, candidate classification scores, success badges for
  unlabeled quality, decorative metric cards, unlabeled synthetic traces or auto-playing motion.
- Verification: browser desktop/mobile screenshots, nonblank canvases, control/replay/error checks,
  numeric parity with the Python augmentation and HTTP boundary tests.

This is an engineering research tool; calibration, annotation and bench validation remain
requirements before patient-facing feedback or physical placement recommendations.
