# Patient results and package layout

The app package and installed application ID are now `com.tally.app`. Backend and contract packages use that prefix too. Kotlin source files live directly under each module's `src/main/kotlin`, with functional folders such as `ui`, `link` and `session`. Kotlin package declarations do not require matching nested directories.

Changing the application ID creates a separate Android installation. Existing history and calibration stay in the old app's private storage; this change does not migrate or delete them.

## Patient view

The result screen shows the estimated verdict, exercise name and rep count. Each rep shows its own verdict and exercise. The Close button returns home beside the export action. Details starts collapsed and retains probabilities, class codes, diagnostics, timing and all recorded provenance.

The display names follow the exercises in the [PHYTMO dataset paper](https://www.nature.com/articles/s41597-022-01387-2): arms raised overhead, elbow bend and straighten, and squeezing. The original model codes remain in Details.

The system bars use the app's Paper background and dark icons. Text styles inherit component content colors; the selected arm label uses White on Ink. Predictive navigation has explicit horizontal transitions for either gesture edge. The recording leave-confirmation behavior remains intact.

## Movement charts

The new optional `SetResult.chart` carries recorded upper-arm and forearm acceleration magnitudes with their sample timestamps, plus the scorer's rep positions. The Python bridge uses the validated segmentation functions for display metadata and checks its window durations against the scoring result. The reference scorer files and model arithmetic remain unchanged.

**Documented — `backend/src/main/python/tally_app.py`:** chart reduction retains actual extrema for both sensors and limits the display to at most `1200` points. It does not filter or replace the samples used for scoring. Rep positions use recorded timestamps rather than accumulated, rounded durations. Magnitudes include gravity; that explanation is in Details. Raw frames and exported recordings remain available.

New results store and reload the chart with the verdict. Older results without chart data remain readable and show a chart-unavailable message. Demo results include an explicitly simulated chart. The graph supports tapping a rep or selecting it with Previous rep / Next rep buttons.

Live traces animate between received batches, including while the visible window fills. Animation uses the received sample count rather than assuming a fixed packet size. It changes display motion only.

## Checks

**Measured — `py -B backend/tools/pipeline_checks.py`, successful run `backend/build/pipeline-checks/run-1794872613279641100`:** `32` JVM tests and `7` Python tests passed. The full host path captures both arm sides, runs the real scorer, verifies rep-to-chart alignment, and persists/reloads the result. A prediction-equivalence test confirms chart metadata does not change the validated scorer's output. Namespace, chart serialization, display selection and sample-boundary checks pass too.

**Measured:** after the last display-motion adjustment, the cached Kotlin CLI compiled `ChartMath.kt` and `ChartDisplayTest.kt`, and `org.junit.runner.JUnitCore com.tally.app.ChartDisplayTest` passed all `4` tests. This includes finishing a scroll after delayed packets so the newest point is revealed.

No APK build, rendered-screen inspection or phone gesture test ran. Status-bar appearance, contrast on the actual display, animation smoothness, chart touch behavior and predictive-back gestures still need hardware verification. The existing Wi-Fi wire contract is unchanged.
