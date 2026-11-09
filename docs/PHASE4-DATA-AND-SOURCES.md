# Phase 4 data and source audit

All optical references in this phase come from the **same published PHYTMO study** as the inertial
training data. They are not five new captures and require no hardware from the user. The previous
five-person optical subset was a local download choice, not the extent of the published dataset.

Primary sources opened: García-de-Villa et al., 2022, [dataset descriptor](https://arxiv.org/pdf/2401.12868),
methods/data records pp. 3–10; [original release](https://zenodo.org/records/6319979), DOI
10.5281/zenodo.6319979. The descriptor explains board poses, coordinate conventions, calibration
movements, independent recording devices and interpolation. Optical camera precision describes the
camera system; it does not establish virtual accelerometer fidelity, anatomical landmark accuracy,
or optical-to-IMU synchronization. The virtual-IMU method linked in the pre-run memo was opened
previously; a repeat fetch of [Sensors 2021, 21(2), 427](https://www.mdpi.com/1424-8220/21/2/427)
returned HTTP 429 during final verification. No new conclusion depends on that repeat fetch.

## Archive findings and corrections

The archive has 390 upper rigid-body files in each optical representation: 360 exercise trials
and **30 upper `Calib` trials**. Earlier discussion that upper optical calibration takes were
unavailable was incorrect. This phase downloads and inspects them. The first exercise series has
180 person/exercise/quality conditions; 171 have a local inertial counterpart. Those 171 cover
all 30 volunteers and form the fixed source cohort, rather than treating nine unavailable pairs
as observed outcomes. Only the first series is used for this experiment.

| Local reference set | Files | Uncompressed bytes |
| --- | ---: | ---: |
| Raw first-series exercise | 171 | 905,388,248 |
| Matching interpolated exercise | 171 | 886,032,367 |
| Raw-folder upper Calib | 30 | 347,680,006 |
| Interpolated upper Calib | 30 | 326,064,692 |
| Total | 402 | 2,465,165,313 |

Every local file was independently checked against the archive central-directory size and CRC32.
Downloads use HTTP ranges, preserve archive paths, and never overwrite an existing mismatched file.
Raw data and sample caches remain ignored by Git. Saved transfer-byte counters describe that
particular incremental invocation; they are **not a cumulative bandwidth total**.

Two naming issues materially affect selection:

- Raw optical participant A03 uses names beginning `A3`. Canonical identity is normalized to A03
  for matching and held-out folds; exact source paths remain unchanged. A strict two-digit selector
  would incorrectly omit one volunteer and six exercise files.
- The raw-folder A01 calibration file is named `A01Calib_interp.csv`. This suffix is flagged.
  Its missing samples differ from the corresponding interpolated-folder file, so the suffix alone
  is not a reliable representation label.

`thigh`, `shin`, `thigh2`, `shin2` in the upper exports are board names, not proof that these are
leg measurements. The published upper-limb rig mapping is used by `placement_replay.read_board`.
Only rigid-body Position/Rotation columns are selected; extra calibration marker-error columns
are excluded.

## Missing data and time origins

The shared-frame audit contains 201 raw/interpolated pairs (171 exercises + 30 calibration takes).
**92 files start at a nonzero optical frame/time.** The replay preserves this time origin; resetting
each export to zero would hide cropping and change alignment. Optical capture metadata does not
supply the independent IMU device uptime clock mapping.

Across shared frames, interpolation fills 10,230 / 42,700 / 59,277 / 82,506 raw-invalid frames for
the four board tracks respectively (1,011,053 common frames per track). Raw per-file median valid
fractions are about 1.0000 / 0.9996 / 0.9999 / 0.9996. High medians must not hide individual gaps.
The raw/interpolated coverage audit is descriptive; the main calibration and placement run uses
the raw-folder exercise cohort, preserves missing spans, and discards differentiation edges.

171 optical trials × four boards yields 684 possible sensor-record pairs. The waveform experiment
retains 653 and rejects 31 for invalid/nonmonotonic inertial samples; all 30 people remain.
The paired classifier has its own strict measured-data retention rules. Its training sources,
171-source virtual-test denominator, and waveform-comparison cohort are kept distinct.

## What is and is not anatomically known

The optical system gives each mounting board's 3D position and rotation. It does not directly give
the accelerometer chip origin or independently measured shoulder/elbow/wrist landmarks. Upper
Calib poses support functional rigid-body constraint fits, documented in
[the anatomy method](PHASE4-ANATOMY-METHOD.md). No upper wrist reference establishes full forearm
length. The anatomy audit remains descriptive and is not inserted into held-out calibration fits.

## Reproduction

Use the pinned Python environment with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`:

```sh
python scripts/phase4_reference_data.py --kind raw --report docs/runs/phase4/data-raw-archive.json
python scripts/phase4_reference_data.py --kind interp --match-raw-cohort --report docs/runs/phase4/data-interp-archive.json
python scripts/phase4_reference_data.py --kind raw --calibration-only --report docs/runs/phase4/data-raw-calibration.json
python scripts/phase4_reference_data.py --kind interp --calibration-only --report docs/runs/phase4/data-interp-calibration.json
python scripts/phase4_reference_data.py --audit-coverage
python scripts/verify_phase4_results.py
```

Catalogue manifests, CRC values and original paths are in `docs/runs/phase4/data-*.json`.
`data-coverage.json` retains every crop origin and missing-frame count. `verification.json` records
the independent offline file checks. Running fetch commands again verifies existing files and
updates invocation-specific transfer metadata; it does not recreate the original transfer history.
