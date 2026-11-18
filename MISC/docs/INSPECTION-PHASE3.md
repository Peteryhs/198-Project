# Local signal inspection

From the repository root, start the server in the pinned modelling environment:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/inspection_server.py
```

Open [the local workbench](http://127.0.0.1:8765). This session used
`/tmp/tally-round2-env/bin/python` in place of `uv run --locked python`; no dependencies were added.
The raw dataset must be present at `data/phytmo/inertial/upper`; an alternate root and port can be
passed with `--root` and `--port`. Stop with Ctrl-C. It serves only the three UI files and its
recording-selection/preview APIs, binds loopback, and writes no datasets. Saving preview JSON is an
explicit browser download.

## Working example

The default source is `A/Larm/A01EAH0_1.csv` and its matching forearm recording. Settings come from
[`configs/augmentation-example.json`](../configs/augmentation-example.json). Select an arrangement,
adjust maximum independent rotation/noise/seed, and choose **Apply preview**. The transformation
runs in Python using the same public API as the training experiment. Six panels share the same g
scale and record-relative time; solid lines show measured/resampled inputs, dashed lines show the
transformed signal, red marks show contact with the configured rails. Vertical lines show original
and transformed C detector completion events, which are not validated repetition boundaries.
Play, pause, reset and scrub through the recording. Failed timestamp acceptance or invalid settings
clear the old traces and display an error; missing files/poses never become invented samples.

The provenance panel/download includes the whole-series label origin, both source IDs and SHA-256
hashes, volunteer, configuration version/hash, exact seed and sampled rotation matrices, timing
assumptions and validation status. No preview changes its movement-quality label or trains a model.
The interface deliberately has no diagnostic quality verdict.

## What the motion view means

- **Illustrative loop:** two generic links and four mount alternatives. Its angles and phase are
  not inferred from the acceleration. Changing candidates changes hypothetical physical placement
  in the diagram; it does not translate measured signals to an unrecorded site.
- **Measured optical boards:** available when a matching file is in the retained local optical
  subset. Board positions and quaternions are measured PHYTMO data, decimated to a 20 Hz preview.
  The display projects the measured poses into an oblique 2D view; it draws assumed 0.30/0.25 m
  segments along local board X and candidate offsets on assumed 0.045/0.035 m radii. Those lengths,
  axes-to-anatomy mapping and board-to-chip origins are uncalibrated. The shared replay control
  advances the optical recording's own start-relative clock; it **does not establish alignment
  with the acceleration traces**. Invalid or out-of-range optical frames show “unavailable.”

The calibrated relationships are limited to the deterministic numerical transformation of measured
acceleration in g, regular relative-time interpolation under the existing aligner contract, and the
recorded optical board pose values. No anatomical joint angle, sensor-origin calibration, movement
quality, optical/IMU synchronization or ADXL335 transfer fidelity is established by the display.

## Verification

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --locked python scripts/test_inspection_server.py
node --check tools/inspection/inspection.js
# Optional QA; Playwright is not required to run the tool.
node tools/inspection/verify.cjs
```

The browser test accepts `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH`, `INSPECTION_URL` and
`INSPECTION_QA_OUT` overrides. Exact values used on this machine:

```sh
PLAYWRIGHT_MODULE=/usr/lib/chatgpt/resources/cua_node/lib/node_modules/playwright \
CHROMIUM_PATH=/home/peter/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome \
node tools/inspection/verify.cjs
```

[`inspection-tests.log`](runs/phase3/inspection-tests.log) records numerical preview parity,
seed reproducibility, timing/lineage, missing optical frames, source/path constraints, invalid
requests and origin/size/type rejection. [`inspection-browser.log`](runs/phase3/inspection-browser.log)
records desktop 1440×900 and mobile 390×844 interaction checks: mount switching, measured optical
view, replay/pause/reset, parameter changes, export, invalid seed and recovery, no horizontal
overflow or browser exceptions. Desktop and mobile screenshots were opened and visually inspected;
the canvas plots and mount drawing were nonblank, labels contained, and controls accessible.
Screenshots and a working exported preview remain local under ignored `data/phase3-inspection/`.

The visual contract was a compact editor/inspection surface, using the repository's ink/paper/clay
palette. There is no application framework, network data upload, site publishing or Arduino UI.
