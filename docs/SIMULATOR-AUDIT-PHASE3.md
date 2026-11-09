# Simulator audit — phase 3

## Decision and validation gate

The round-two two-link simulator passed analytic physics checks but failed its predeclared empirical
distribution gate: **0 of 84 statistics passed**. Preserve that result and the earlier criteria. No
synthetic classifier response is accuracy evidence.

Before this optical replay, the measured-site calibration gate was specified: fit clock mapping and
board-to-chip extrinsics using people A–D only; then evaluate E without further fitting. Pass requires
every held-out paired record to have an identifiable shared clock with residual lag ≤10 ms and a
measured board-to-chip transform. The gate fails before model/candidate evaluation. PHYTMO provides
device uptime for IMU files and frame-relative time for optical files, but no shared clock map or
start event between them. It gives the optical pose of the mounting board, but not chip-to-board
translation and rotation. The descriptor says the four IMUs were synchronized via motion events;
that does not establish the missing optical/IMU clock. A per-file lag or transform fitted on E would
be held-out calibration, so none was attempted. See the [PHYTMO descriptor](https://pmc.ncbi.nlm.nih.gov/articles/PMC9166805/)
and [round-two research memo](ROUND2-RESEARCH.md).

The 10 ms clock prerequisite is one 100 Hz sample, an engineering alignment requirement rather
than an anatomical boundary accuracy claim. It does not replace the original envelope/frequency/
peak/duration/HF median-ratio [0.75, 1.33] and normalized-Wasserstein ≤0.5 gate. Those distribution
criteria remain unchanged; prerequisites failed before a valid calibrated replay could reach them.

Missing calibration metadata is not proof that calibration is mathematically impossible. This
phase did not independently establish a transferable clock/origin calibration; a future anchored
capture or separately justified training-only estimator could address it. A periodic lag fit alone
would not independently validate clock synchronization.

The code therefore reports **descriptive, non-clocked distributions** from optical board poses and
matched raw inertial files. It does not claim measured-chip replay, validation, or placement ranking.
Time-domain optical/IMU correlations cannot be computed without the shared clock.

## Why the constructed simulator failed

The analytic checks established correct specific-force sign and units for static gravity and an
accelerating pendulum. They did not validate exercise realism. `scripts/limb_simulation.py` prescribes
planar two-link movement as a small sum of harmonics; fixes amplitudes by exercise; uses one period
per held-out fold derived from other volunteers; and assumes an unmeasured 20 Hz filter, fixed bias,
white noise, ideal clipping and quantization. It omits participant geometry, out-of-plane movement,
soft tissue, mount slip, force/load, pain and hardware response. Those are illustrative assumptions.

In round two, for example, the nominal left forearm had a repeated envelope value of 2.3273 g,
dominant frequency 0.8 Hz, and peak median 2.8585 g. Recorded p10/p50/p90 values were 0.6433/1.2523/1.7137 g,
0.3/0.5/0.6 Hz, and 1.3567/1.7925/2.2354 g, respectively. Fixed harmonics and one period per
exercise made synthetic rows too concentrated and too energetic. Full statistics are preserved in
[round-two simulation results](runs/round2/simulation.json) and its [log](runs/round2/simulation.log).

## Optical replay and placement hypotheses

[placements.json](../simulation/placements.json) defines four distinct hypotheses: an exterior-lateral
midpoint, proximal lateral, distal lateral, and proximal anterolateral pair. Fraction is distance from
the proximal joint divided by assumed segment length; surface angle is 0° lateral and 90° anterior.
PHYTMO establishes exterior-lateral upper-limb placement but does **not** give the midpoint or
joint-distance fraction. The anatomical distances (acromion, lateral epicondyle, ulnar styloid) are
explicitly hypotheses.

The optical board origin is treated as a hypothetical lateral-midpoint surface reference. Position
offsets use assumed segment lengths of 0.30/0.25 m (upper/forearm) and surface radii 0.045/0.035 m;
none are participant measurements. Board local X is treated as the segment long axis. The surface
offset from the lateral reference is `[longitudinal, radius*(cos(theta)-1), radius*sin(theta)]`.
Geometry stress changes both length and radius by ±20%; surface stress is ±15°. These variations
explore mechanics, not accuracy or patient comfort.

The deterministic subset contains **30 optical files from five people** (A01–E01; one person per age
band), each side where available. It is a small preselected subset, not all 30 volunteers. The replay
produced 1,440 rows; no optical files were rejected. Valid spans/coverage are in the JSON. Raw inertial
distributions were available for 52/60 upper and 58/60 forearm side-record pairs in the central
lateral hypothesis; the other 10 pairs had repeated/nonmonotonic device timestamps and are listed
with reasons. The descriptive A–D/E split for this tiny subset is not independent validation: no
calibration parameters were fit and the measured-site gate failed.

For the central lateral hypothesis, per-record dynamic RMS distributions (p10/p50/p90, g) were:

| Segment / identical usable source cohort | Optical board-pose replay | Matched inertial recordings | Inertial fraction clipped at ±3 g (p50) |
| --- | --- | --- | ---: |
| Upper / 52 | 0.139 / 0.301 / 0.520 | 0.091 / 0.262 / 0.524 | 0 |
| Forearm / 58 | 0.311 / 0.408 / 0.578 | 0.278 / 0.403 / 0.569 | 0 |

Delivery review corrected this table's first draft: it used all 60 virtual records against the
52/58 usable inertial records. Both columns now use precisely the same eligible source rows;
the full-60 mechanical candidate summaries remain separately identified in the JSON. The
saved-result audit asserts this cohort equality. No historical round-two result or gate changed.

The central-hypothesis dominant-frequency p10/p50/p90 values were 0.20/0.40/0.60 Hz optical vs
0.20/0.50/0.71 Hz inertial for upper arm, and 0.20/0.50/0.81 vs 0.20/0.50/1.12 Hz for forearm.
Median high-frequency energy fractions were 0.036/0.028 optical vs 0.064/0.049 inertial,
respectively. The median per-file inertial fraction at ±3 g was 0 for both; maximum was 0.00018
upper and 0.0018 forearm. Frequency/high-frequency metrics use each source's longest contiguous
span to avoid stitching across gaps.

The medians are similar in this subset. This is only an unaligned distribution check: the optical
signal differentiates board positions, assumes geometry and axes, and does not include chip
extrinsics; the inertial signal includes the physical sensor chain. Dominant-frequency and
high-frequency-energy distributions, per-axis percentiles, clipping fraction, valid coverage, and
each row's alignment/missing-data limitation are retained in the JSON. Optical and inertial
temporal correlations are unavailable. No classifier was fit or queried; no simulated or clinical
quality score was produced.

Exploratory mount-error summaries change only modestly in aggregate: for example, the lateral
midpoint upper-arm RMS median is 0.297 g at assumed nominal geometry and 0.283–0.297 g across the
combined ±20% geometry/±15° surface stress cases. Across placements, upper/forearm central medians
span 0.293–0.306 g and 0.399–0.415 g. These values depend on assumed radius, segment length and
board-origin placement. They are not validated mechanics or evidence to rank patient placements;
per-person spread is much larger than the candidate differences in this small subset.

The predeclared E holdout was shown separately as a descriptive check, not a gate result: with one
person (E01), upper RMS p10/p50/p90 was 0.067/0.272/0.543 g optical and 0.059/0.286/0.501 g inertial
(10 matched side-records); forearm was 0.328/0.469/0.589 and 0.346/0.461/0.609 g (11 matched
side-records). These are not independent generalization evidence.

## Reproduction and checks

From the repository root with the pinned environment:

```sh
/tmp/tally-round2-env/bin/python scripts/test_placement_replay.py
/tmp/tally-round2-env/bin/python scripts/placement_replay.py --out docs/runs/phase3/simulation-placement.json
```

The test checks schema bounds, static 1 g, analytic translational acceleration, off-axis centripetal
acceleration, invalid timing/geometry, and preservation of missing spans. The complete command output
is in [simulation-placement.log](runs/phase3/simulation-placement.log); the JSON contains per-record
statistics, held-out E descriptive rows, per-axis values, coverage, clipping and any rejected pairs.

## Primary sources

- García-de-Villa et al., [PHYTMO dataset descriptor](https://pmc.ncbi.nlm.nih.gov/articles/PMC9166805/): placement, axis convention, data layout, acquisition/synchronization, timestamp semantics, optical board definition.
- [Round-two research memo](ROUND2-RESEARCH.md): primary MuJoCo sensor documentation and sensor-chain assumptions.
