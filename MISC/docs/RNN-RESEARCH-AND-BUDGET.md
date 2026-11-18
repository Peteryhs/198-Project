# Tiny recurrent baseline: research and resource budget

## Scope and evidence limits

This note sizes a single causal, one-layer recurrent baseline for comparison on the existing real recordings. It does not establish a deployable firmware build or board timing. The target UNO R4 Minima specification is 32 kB SRAM, 256 kB flash, a 48 MHz Cortex-M4 with FPU, and six analog inputs ([Arduino board page](https://docs.arduino.cc/hardware/uno-r4-minima); [official datasheet](https://docs.arduino.cc/resources/datasheets/ABX00080-datasheet.pdf)).

The existing project estimate reserves 24,832 B of 32,768 B for one causal pair pipeline, leaving 7,936 B; it includes 14,488 B BSS and explicit core/stack/display/interrupt reserves. It is a pre-link estimate, not a measured firmware RAM high-water mark or timing result ([Phase 3 report](PHASE3-REPORT.md)). The current paired classifier has 992 B of float32 coefficients. Do not add parameter bytes to the 24,832 B total without first establishing whether those coefficients are already included and whether the new weights reside in flash or SRAM.

The source labels are exercise identity and whole-recording correct/incorrect. They are not independently observed per-cycle form labels. Assigning those series labels to detected cycles produces inherited pseudo-labels, not per-cycle ground truth. Therefore cycle-level quality scores can support only a weak proxy comparison and cannot validate individual repetitions, name error mechanisms, or establish clinical correctness. Cycle detection boundaries also have not been independently verified as anatomical repetitions. Keep volunteer and source-recording identity intact, split by subject, and pool cycle probabilities to a whole-recording prediction.

## Frozen candidate for comparison

- Input: six paired acceleration channels at 25 Hz.
- Recurrent block: one causal, unidirectional PyTorch `GRU(input_size=6, hidden_size=8, num_layers=1, bias=True)`.
- Per-cycle head input: final 8-value hidden state concatenated with the measured cycle-duration scalar (9 values).
- Shared linear head: four logits (three exercise classes and one binary quality logit). Apply softmax to the exercise logits and sigmoid to the quality logit once per detected cycle. Mean the four probabilities over cycles to obtain the whole-recording output.
- Reset the hidden state at the start of each detected cycle; no future samples or bidirectional pass.
- The duration is an observed input to the head, not a predicted target. The quality output is trained from the inherited recording label, so treat it as a series-label proxy at cycle level.

PyTorch documents GRU input and recurrent matrices with three hidden-size gate rows and separate input/recurrent biases. For 6 inputs and 8 hidden values, the recurrent block has `3×8×6 + 3×8×8 + 2×3×8 = 384` parameters. The 9-to-4 affine head has `9×4 + 4 = 40` parameters. Total: **424 float32 parameters = 1,696 B**. This is 704 B (about 71%) larger than the existing 992 B coefficient set if both are stored as float32. A replacement deployment would replace that classifier’s weights rather than add the two sets, subject to the actual linker placement. PyTorch's GRU gate layout and its candidate-gate equation are documented in the [official GRU reference](https://docs.pytorch.org/docs/2.9/generated/torch.nn.GRU.html).

For the same width and head, a vanilla tanh `torch.nn.RNN(6, 8)` has `8×6 + 8×8 + 2×8 = 128` recurrent parameters, plus the 40 head parameters: **168 parameters = 672 B**. It uses 112 recurrent MAC/frame and 8 tanh activations/frame, then the same 36 head MAC/cycle. The GRU costs 3× recurrent parameters and MACs to provide reset/update gates. The selected GRU is a single bounded candidate for temporal comparison; these resource counts alone do not predict a score advantage. PyTorch's vanilla RNN equation, weight shapes and causal `bidirectional=False` option are described in the [official RNN reference](https://docs.pytorch.org/docs/2.9/generated/torch.nn.RNN.html).

## Per-step arithmetic and working state

The dominant arithmetic per input frame is `3×8×6 + 3×8×8 = 336` multiply-accumulates (MACs) for the two GRU matrix products. The 9-to-4 head adds 36 MACs once per completed cycle. Each frame also needs 16 sigmoid and 8 tanh gate activations, plus elementwise gate arithmetic. The cycle head needs one 3-class softmax and one quality sigmoid. Biases, activation implementation, probability normalization, and pooling are additional operations. Thus 336 MAC/frame is an operation-count estimate, not a latency measurement. At 25 Hz this corresponds to 8,400 recurrent MAC/s; it does not prove the full sensing and firmware loop meets a timing deadline.

The recurrent model itself has 8 float32 hidden values (32 B). One 6-channel input frame is 24 B if held in scratch. A straightforward implementation may also require up to three 8-value gate vectors (96 B), plus temporary scalar/output values; a hand-coded kernel can reuse scratch, but its actual stack frame and target binary must be measured. Four float32 whole-recording probability sums require 16 B, plus a cycle count. These are model-local figures only; do not count the existing sample/cycle ring twice.

The current paired stream state includes a 14,400 B raw buffer and totals 14,488 B state according to the project measurements. Retaining that same C cycle buffer makes the comparison’s model-local working state small relative to the existing stream state: 32 B hidden state, at most 96 B simple gate scratch, 16 B probability accumulators and a counter. Add the 1,696 B weights only if copied into SRAM; `const` weights can remain in flash, but linker output must confirm placement. As a rough scenario only, if the existing 24,832 B one-pair RAM reserve excludes these new model allocations, copying weights into SRAM and allowing 132 B model state/scratch would bring that estimate to about 26,660 B. If parameters stay in flash, the analogous SRAM addition is about 132 B and the flash addition is 1,696 B. These figures may overlap existing stack or model reserves and are not a linked result. Keeping the current classifier for an A/B build may add its 992 B too, depending on how the build already stores it. A full incremental SRAM total cannot be claimed until the C implementation is compiled and linked with the actual Arduino core and board configuration.

This estimate assumes frame-at-a-time recurrence and the already-retained C cycle buffer. Buffering a new sequence tensor in the inference path is unnecessary and would spend extra RAM. A later streaming path that consumes frames as they arrive could reduce cycle storage only after revisiting the detector, features, and cycle reporting interface; this comparison does not change that pipeline.

## References

- PyTorch 2.9 GRU parameter shapes and equations: [torch.nn.GRU](https://docs.pytorch.org/docs/2.9/generated/torch.nn.GRU.html).
- Arduino UNO R4 Minima capacity and clock specification: [board documentation](https://docs.arduino.cc/hardware/uno-r4-minima), [datasheet](https://docs.arduino.cc/resources/datasheets/ABX00080-datasheet.pdf).
- Repository pipeline memory estimates and limits: [Phase 3 report](PHASE3-REPORT.md), [continuation context](TALLY-CONTINUATION-PROMPT.md).

No target latency, whole-firmware fit, or physical-board execution is established by these arithmetic budgets.

## Post-run implementation measurement

The actual research integration deliberately retains a 3,600 B grouped-cycle workspace to reuse the
accepted detector/cycle buffer directly. The frame-at-a-time estimates above are not the implemented
probe's complete footprint. LLVM reports 18,296 B static state for detector, feature output and that
workspace; adding the earlier 10,240 B system reserves gives a provisional 28,536 B one-pair scenario.
This does not include a linked Arduino core measurement or measured math/helper stack. The known
wrapper/GRU/sigmoid frames sum to 504 B, inside the assumed stack reserve, before unresolved helper
frames. Do not add these frames again on top of an already included stack reserve.

The post-run [C probe](runs/phase6-rnn/c-probe.md) and [experiment report](TINY-RNN-REPORT.md) supersede
model-local estimates for describing this implementation. No buffer optimization or two-pair deployment
was established. The recurrent candidate did not outperform the accepted model, so there is no
accuracy result justifying production replacement or extra deployment work at this point.
