# Embedded feasibility notes

Checked 2026-11-07 for the UNO R4 Minima. This is a feasibility review, not a hardware result.

## Board and options

Arduino specifies the UNO R4 Minima as a Renesas RA4M1 with 48 MHz Cortex-M4, 256 kB flash,
32 kB SRAM and six analog inputs ([Arduino board page](https://docs.arduino.cc/hardware/uno-r4-minima),
opened 2026-11-07). The host `.joblib` forest exceeds flash as stored and needs a separate C
representation; that file size alone does not measure a converted/pruned forest's cost
([model README](../model/README.md)).

CMSIS-NN is a plausible option for a *neural-network* design: Arm documents Cortex-M4 DSP support
and int8/int16 kernels ([CMSIS-NN 6.0 docs](https://arm-software.github.io/CMSIS_6/v6.0.0/NN/index.html),
opened 2026-11-07). It is not needed for a linear classifier; use direct C multiply-accumulate code.
The Arduino Renesas core board configuration targets `cortex-m4`, hard-float, 48 MHz and declares
the flash/RAM limits ([ArduinoCore-renesas boards.txt](https://github.com/arduino/ArduinoCore-renesas/blob/main/boards.txt),
opened 2026-11-07).

TFLM upstream currently lists Arm Cortex-M as a CI-tested architecture, but Arduino and Renesas as
community platforms ([TFLM README](https://github.com/tensorflow/tflite-micro/blob/main/README.md),
opened 2026-11-07). Its Arduino library calls itself officially supported for Arduino, while its
compatibility section says the library is designed for Nano 33 BLE Sense and only says the model
framework should work on most Cortex-M boards ([TFLM Arduino library README](https://github.com/tensorflow/tflite-micro-arduino-examples),
opened 2026-11-07). Therefore this is not evidence of official UNO R4 Minima support. TFLM's own
porting guide says new targets need a board SDK/toolchain, compiler/linker setup and peripheral
integration, and documents a Cortex-M/CMSIS-NN path ([TFLM porting guide](https://github.com/tensorflow/tflite-micro/blob/main/docs/new_platform_support.md),
opened 2026-11-07). The repository's existing note says its R4 gate required a patch; the compile
size numbers there are project-reported compile-time figures, not independently reproduced here.

## Tiny linear model arithmetic

An illustrative two-head linear model with 31 inputs and four outputs total (three recognition
scores plus one quality score) needs 124 weights and four biases: 128 float32 values, or 512 bytes.
Evaluation is 124 multiply-accumulates plus four bias adds. If one conservatively budgets 10,000
cycles for these operations, 48 MHz gives 0.21 ms. Both size and latency are arithmetic estimates,
not compiler or device measurements; no trained two-head artifact existed at this pre-training
review. The subsequent exports and object measurements are in [the report](MODELLING-REPORT.md).
The quality probability needs a sigmoid only if probability calibration/pooling is
required; a single binary verdict can threshold the logit without `expf`. Recognition needs argmax
over its three scores.

The existing learned task is more complicated than the example: the exported model predicts a
correct/wrong score **per repetition**, then averages repetition probabilities to classify a
series. There is no recognition classifier in the artifacts; don't describe the example above as
the current model.

## Feature extraction and RAM are the real porting work

Current feature contract is 100 Hz, three axes, ten statistics per axis, plus repetition duration
(31 floats) ([model metadata](../model/metadata.json)). A per-repetition feature accumulator can
compute mean, variance, min/max, RMS and energy online with small state. Mean-centered zero
crossings need the eventual mean and therefore buffering or a second pass. Exact skew/kurtosis
need higher moments; their numerical match needs validation. Segmentation is a larger
gap: Python detrends magnitude using a centered 201-sample moving average, chooses a prominence
threshold from the whole recording's 90th percentile, and uses peak distance/prominence rules
([scripts/reps.py](../scripts/reps.py)). This has look-ahead/global-statistics behavior, so a causal
streaming implementation needs a deliberate algorithm and validation against the Python reference.
An alternative is buffering a bounded repetition and processing it after detection. At 100 Hz, a
2-second three-axis float buffer is 2,400 bytes; 12 channels would be 9,600 bytes. These are
illustrative buffer costs, not a known maximum repetition duration. Current data's rep counts range
from 6 to 46 in the logged series, and no maximum sample length for a single repetition is stated.

The project design also has four accelerometers (12 analog signals) but the UNO R4 has six analog
inputs. That requires a multiplexer or a sensor/interface change before MCU classification is the
main blocker; see [context](CONTEXT-AND-CONSTRAINTS.md).

## Local toolchain inspection

Read-only checks from `/home/peter/work/198-Project` on 2026-11-07:

```text
$ command -v arduino-cli
(no output; command not found)
$ arduino-cli version
/bin/bash: arduino-cli: command not found
$ command -v arm-none-eabi-gcc
(no output; command not found)
$ arm-none-eabi-gcc --version
/bin/bash: arm-none-eabi-gcc: command not found
$ command -v gcc
/usr/bin/gcc
$ gcc --version | head -1
gcc (GCC) 15.3.1 20260722 (Red Hat 15.3.1-1)
```

So a full Arduino firmware link could not be performed using those board tools; none were
installed. A subsequent freestanding Clang Cortex-M4 object compile succeeded, as documented in
[the report](MODELLING-REPORT.md). No board was available, and no device timing, RAM or power was
measured. The original `.joblib` files are forests rather than portable linear coefficients.

## Further current tooling check

Opened on 2026-11-07: [TFLM memory-management documentation](https://github.com/tensorflow/tflite-micro/blob/main/docs/memory_management.md)
shows a recording-allocator example with **9,568 B total arena = 7,744 B head + 1,824 B tail**.
This is a documented example, not our measurement, not a complete application footprint and not an
UNO R4 result. It demonstrates why tensor arena, framework, input buffers and application state
must be counted separately; a small arena alone does not establish fit on a 32 KiB board.
[emlearn's model-cost documentation](https://emlearn.readthedocs.io/en/latest/model_optimization.html)
(current documentation, opened) provides target-compilation size tooling for C exports and warns
that execution-time estimation without the target is limited. A bounded tree or direct linear C
model avoids an interpreter, but its actual linked target application still needs measurement.
No independently verified 2025–2026 measured, complete UNO R4 rehabilitation application was found.

For the selected two-head contract, exercise probabilities must be softmaxed **before** averaging
across repetitions; quality uses sigmoid **before** averaging. That adds three `expf` calls plus
one `expf` per repetition. The illustrative 10,000-cycle MAC/logit allowance above is not a
measurement or guarantee of the total classifier latency, and excludes an unmeasured math-library
cost and softmax/sigmoid normalization/divisions. It also excludes feature extraction, detection,
ADC acquisition and display work.
