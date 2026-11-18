package com.tally.app.backend.calib

import com.tally.app.contract.BodyHold
import com.tally.app.contract.CalPose
import com.tally.app.contract.CalibrationInfo

/**
 * Per-channel ADXL335 line: g = (mV − [offsetMv]) / [mvPerG]. The only place mV becomes g.
 *
 * Two producers exist:
 *  - [fromBodyHolds] the on-arm body-hold calibration (four fit holds, one check hold, repeated anchors),
 *    ported from tally-research/08-experiments/protocol/on_arm_redesign. This is the shipping path.
 *  - [fromPoses] the legacy six-axis capture, kept only so stored calibrations and old tests still load.
 */
internal data class Calibration(
    val info: CalibrationInfo,
    val offsetMv: FloatArray,
    val mvPerG: FloatArray,
    /** Row-major 3x3 `R_sensor<-functional` per mount (upper, forearm). Null for nominal/legacy. */
    val frames: List<FloatArray>? = null,
    /** "bench" when gains were measured on the board, "nominal" when they are the assumed 330 mV/g. */
    val gainSource: String = "nominal",
    /** Unmeasured limits and failed checks retained with a marginal calibration. */
    val reasons: List<String> = emptyList(),
) {
    init {
        require(offsetMv.size == 6 && mvPerG.size == 6)
        require(offsetMv.all { it.isFinite() && (frames != null || it in 500f..2500f) } &&
            mvPerG.all { it.isFinite() && it in 100f..500f })
        require(frames == null || (frames.size == 2 && frames.all { f -> f.size == 9 && f.all { it.isFinite() } }))
    }

    fun toG(mv: Int, channel: Int): Float = (mv - offsetMv[channel]) / mvPerG[channel]

    /** A nominal calibration never licenses a g-based quality verdict. */
    val usable: Boolean get() = !info.nominal && gainSource == "bench" && reasons.isEmpty()

    companion object {
        // Documented nominal ADXL335 values at 3.3 V; six-pose calibration replaces these.
        fun nominal() = Calibration(CalibrationInfo("nominal", true, 0), FloatArray(6) { 1650f }, FloatArray(6) { 330f })

        /** The five holds the on-arm flow needs. */
        val REQUIRED_HOLDS = listOf(
            BodyHold.HANG, BodyHold.FORWARD_PALM_UP, BodyHold.SIDE_PALM_FORWARD, BodyHold.OVERHEAD,
            BodyHold.CHECK,
        )

        /**
         * Fit offsets and the two functional frames from the on-arm body holds.
         *
         * [holds] values are the per-channel mean of the accepted hold, in millivolts, upper x/y/z then
         * forearm x/y/z. Gains stay nominal because no bench measurement exists in this app; the
         * calibration is therefore never 'usable' for a g-based verdict on its own.
         *
         * Refuses missing/invalid holds and degenerate geometry. Absolute scale checks cannot certify
         * nominal gains: retain their diagnostics and save as marginal instead of discarding the holds.
         */
        fun fromBodyHolds(holds: Map<BodyHold, FloatArray>, now: Long): Calibration {
            for (h in REQUIRED_HOLDS) {
                val values = holds[h] ?: error("${bodyAction(h)}: capture this hold before saving.")
                require(values.size == 6 && values.all { it.isFinite() && it in 0f..3300f }) {
                    "${bodyAction(h)}: invalid readings; repeat this hold."
                }
            }
            val gain = OnArmMath.MV_PER_G_NOMINAL
            val fitHolds = listOf(
                BodyHold.HANG, BodyHold.FORWARD_PALM_UP, BodyHold.SIDE_PALM_FORWARD, BodyHold.OVERHEAD,
            )
            val reasons = mutableListOf("Per-device gains and absolute scale are unmeasured; using nominal 330 mV/g.")
            val offsets = FloatArray(6)
            val frames = ArrayList<FloatArray>(2)
            for (mount in 0 until 2) {
                val ch = mount * 3
                val points = fitHolds.map { h ->
                    val m = holds.getValue(h)
                    doubleArrayOf(m[ch] / gain, m[ch + 1] / gain, m[ch + 2] / gain)
                }
                val sphere = OnArmMath.sphereFit(points)
                    ?: error("${fitHolds.joinToString { bodyAction(it) }}: repeat these holds with distinct positions; calibration could not be fitted.")
                if (!sphere.radiusOk) reasons.add("${if (mount == 0) "Upper arm" else "Forearm"}: fitted radius ${sphere.radiusG} at nominal gain is outside the documented 1 ± ${OnArmMath.RADIUS_TOL_G} g check; true gain is unmeasured.")
                for (axis in 0 until 3) offsets[ch + axis] = (sphere.center[axis] * gain).toFloat()
                check((ch until ch + 3).all { offsets[it].isFinite() }) {
                    "${fitHolds.joinToString { bodyAction(it) }}: invalid fit; repeat these holds."
                }
                if ((ch until ch + 3).any { offsets[it] !in 500f..2500f }) {
                    reasons.add("${if (mount == 0) "Upper arm" else "Forearm"}: fitted offset outside the legacy 500–2500 mV check; per-device offset range is unmeasured.")
                }

                val hang = corrected(holds.getValue(BodyHold.HANG), ch, offsets, gain)
                val forward = corrected(holds.getValue(BodyHold.FORWARD_PALM_UP), ch, offsets, gain)
                val frame = OnArmMath.functionalFrame(hang, forward)
                    ?: error("${bodyAction(BodyHold.HANG)} and ${bodyAction(BodyHold.FORWARD_PALM_UP)}: repeat with more separated positions.")
                frames.add(OnArmMath.flatten(frame))

                val check = corrected(holds.getValue(BodyHold.CHECK), ch, offsets, gain)
                val norm = Math.sqrt(check[0] * check[0] + check[1] * check[1] + check[2] * check[2])
                if (!norm.isFinite() || Math.abs(norm - 1.0) > OnArmMath.RADIUS_TOL_G) {
                    reasons.add("${bodyAction(BodyHold.CHECK)} (${if (mount == 0) "upper arm" else "forearm"}): norm $norm at nominal gain is outside the documented 1 ± ${OnArmMath.RADIUS_TOL_G} g check; absolute scale is unmeasured.")
                }
            }
            return Calibration(
                CalibrationInfo("body-$now", false, now),
                offsets,
                FloatArray(6) { gain.toFloat() },
                frames,
                gainSource = "nominal",
                reasons = reasons,
            )
        }

        fun bodyAction(hold: BodyHold): String = when (hold) {
            BodyHold.HANG -> "Let your arm hang down by your side"
            BodyHold.FORWARD_PALM_UP -> "Arm straight forward, palm up"
            BodyHold.SIDE_PALM_FORWARD -> "Arm out to the side, palm forward"
            BodyHold.OVERHEAD -> "Arm above your head, elbow straight"
            BodyHold.CHECK -> "Forearm resting on the table, palm up"
        }

        private fun corrected(meanMv: FloatArray, ch: Int, offsets: FloatArray, gain: Double) =
            doubleArrayOf(
                (meanMv[ch] - offsets[ch]) / gain,
                (meanMv[ch + 1] - offsets[ch + 1]) / gain,
                (meanMv[ch + 2] - offsets[ch + 2]) / gain,
            )

        fun fromPoses(poses: Map<CalPose, FloatArray>, now: Long): Calibration {
            require(CalPose.entries.all { poses[it]?.size == 6 }) { "Capture all six poses" }
            val offsets = FloatArray(6)
            val scales = FloatArray(6)
            repeat(6) { ch ->
                val plus = poses.getValue(CalPose.entries[(ch % 3) * 2])[ch]
                val minus = poses.getValue(CalPose.entries[(ch % 3) * 2 + 1])[ch]
                offsets[ch] = (plus + minus) / 2f
                scales[ch] = (plus - minus) / 2f
                require(offsets[ch].isFinite() && offsets[ch] in 500f..2500f && scales[ch] in 100f..500f) {
                    "Invalid calibration for channel $ch; orient both sensors together in each pose"
                }
            }
            return Calibration(CalibrationInfo("six-pose-$now", false, now), offsets, scales)
        }
    }
}
