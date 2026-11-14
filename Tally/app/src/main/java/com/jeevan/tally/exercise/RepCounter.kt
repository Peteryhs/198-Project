package com.jeevan.tally.exercise

import kotlin.math.PI
import kotlin.math.acos
import kotlin.math.sqrt

/**
 * App-side repetition estimate for one upper-arm + forearm pair, following the project README:
 * two sensors on one limb give the angle between its segments, a repetition is the limb rising
 * and returning, and a hysteresis band stops one motion from counting twice.
 *
 * Input frames are six accelerations in g: upper x/y/z then forearm x/y/z (the order in the
 * board's documented CSV row). Angles come from gravity, so they are only meaningful for
 * movements slow enough that gravity dominates — true of the CCCARE exercises, not of fast swings.
 *
 * This is an estimate with no validated repetition boundaries. The board firmware's own count
 * (TALLY frames) always takes precedence when it is available.
 */
data class CounterConfig(
    /** Progress (0 = rest pose, 1 = end pose) a movement must reach to count. */
    val enterFraction: Float = 0.40f,
    /** Progress the limb must fall back below before the repetition completes. */
    val exitFraction: Float = 0.20f,
    /** Peak progress at or above which a repetition is "full"; below it is "shallow". */
    val fullFraction: Float = 0.80f,
    /** Movements shorter than this are treated as jitter. */
    val minMovementSeconds: Float = 0.4f,
    /** First-order low-pass cutoff applied to every channel. */
    val cutoffHz: Float = 5f,
    /** The end pose must differ from rest by at least this much on the chosen signal. */
    val minRangeDegrees: Float = 15f,
    /** Largest per-channel standard deviation accepted while holding a calibration pose. */
    val stillnessG: Float = 0.06f,
    /** Shortest calibration hold accepted. */
    val minPoseFrames: Int = 50,
) {
    init {
        require(exitFraction in 0f..1f && enterFraction in 0f..1f && fullFraction in 0f..1.5f)
        require(exitFraction < enterFraction && enterFraction <= fullFraction)
        require(minMovementSeconds >= 0f && cutoffHz > 0f && minRangeDegrees > 0f)
    }
}

enum class AngleSignal(val label: String) {
    UPPER_TILT("Upper-arm tilt"),
    FOREARM_TILT("Forearm tilt"),
    JOINT("Angle between segments"),
}

/** Mean gravity direction of each segment while a pose is held. */
data class Pose(val upper: List<Float>, val forearm: List<Float>)

data class Calibration(val rest: Pose, val end: Pose, val signal: AngleSignal, val rangeDegrees: Float)

sealed interface PoseResult {
    data class Ok(val pose: Pose) : PoseResult
    data class Failed(val reason: String) : PoseResult
}

sealed interface CalibrationResult {
    data class Ok(val calibration: Calibration) : CalibrationResult
    data class Failed(val reason: String) : CalibrationResult
}

object AngleMath {
    fun angleDegrees(a: List<Float>, b: List<Float>): Float {
        val dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
        val na = sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
        val nb = sqrt(b[0] * b[0] + b[1] * b[1] + b[2] * b[2])
        if (na < 1e-6f || nb < 1e-6f) return Float.NaN
        return (acos((dot / (na * nb)).coerceIn(-1f, 1f)) * 180.0 / PI).toFloat()
    }

    /** The three candidate angles, all measured from the rest pose. */
    fun features(upper: List<Float>, forearm: List<Float>, rest: Pose): Map<AngleSignal, Float> = mapOf(
        AngleSignal.UPPER_TILT to angleDegrees(upper, rest.upper),
        AngleSignal.FOREARM_TILT to angleDegrees(forearm, rest.forearm),
        AngleSignal.JOINT to kotlin.math.abs(angleDegrees(upper, forearm) - angleDegrees(rest.upper, rest.forearm)),
    )

    /** Averages a held pose and rejects it if the limb was moving. */
    fun pose(frames: List<FloatArray>, config: CounterConfig = CounterConfig()): PoseResult {
        if (frames.size < config.minPoseFrames) return PoseResult.Failed("Hold the position a little longer.")
        if (frames.any { it.size != 6 || !it.all(Float::isFinite) }) return PoseResult.Failed("The sensors sent an invalid sample.")
        val mean = FloatArray(6) { k -> frames.sumOf { it[k].toDouble() }.div(frames.size).toFloat() }
        val worstStd = (0 until 6).maxOf { k ->
            sqrt(frames.sumOf { (it[k] - mean[k]).toDouble().let { d -> d * d } } / frames.size)
        }
        if (worstStd > config.stillnessG) return PoseResult.Failed("The arm moved during the hold. Keep it still and try again.")
        val upper = mean.slice(0..2)
        val forearm = mean.slice(3..5)
        if (upper.norm() < 0.3f || forearm.norm() < 0.3f) {
            return PoseResult.Failed("A sensor reads almost no gravity. Check its wiring and power.")
        }
        return PoseResult.Ok(Pose(upper, forearm))
    }

    /** Picks whichever angle changes most between rest and end pose; that is the motion being exercised. */
    fun calibrate(rest: Pose, end: Pose, config: CounterConfig = CounterConfig()): CalibrationResult {
        val (signal, range) = features(end.upper, end.forearm, rest).maxBy { it.value }.toPair()
        if (!range.isFinite() || range < config.minRangeDegrees) {
            return CalibrationResult.Failed("The end position is too close to the start (${range.toInt()}°). Move through the full range and hold.")
        }
        return CalibrationResult.Ok(Calibration(rest, end, signal, range))
    }

    private fun List<Float>.norm() = sqrt(this[0] * this[0] + this[1] * this[1] + this[2] * this[2])
}

/** A completed repetition as seen by [RepCounter]. */
data class DetectedRep(val endT: Float, val movementSeconds: Float, val peakFraction: Float, val full: Boolean)

class RepCounter(val calibration: Calibration, private val config: CounterConfig = CounterConfig()) {
    private var filtered: FloatArray? = null
    private var lastT = 0f
    /** Like tally_resume: a repetition can only start after the limb has been seen at rest. */
    private var armed = false
    private var inRep = false
    private var risingFrom: Float? = null
    private var repStart = 0f
    private var peak = 0f

    /** Latest progress between the rest pose (0) and the end pose (1); for live display. */
    var progress = 0f
        private set

    /** Drops any half-finished movement, e.g. on pause, so it cannot complete across the gap. */
    fun reset() {
        filtered = null
        armed = false
        inRep = false
        risingFrom = null
        peak = 0f
        progress = 0f
    }

    fun push(t: Float, raw: FloatArray): DetectedRep? {
        if (raw.size != 6 || !raw.all(Float::isFinite) || !t.isFinite()) return null
        val state = filtered
        val dt = t - lastT
        lastT = t
        val current = if (state == null || dt <= 0f || dt > 0.25f) {
            raw.copyOf()  // first sample, or a gap long enough that the old state means nothing
        } else {
            val rc = 1f / (2f * PI.toFloat() * config.cutoffHz)
            val alpha = dt / (rc + dt)
            FloatArray(6) { k -> state[k] + alpha * (raw[k] - state[k]) }
        }
        filtered = current
        val angle = AngleMath.features(current.slice(0..2), current.slice(3..5), calibration.rest)[calibration.signal]
            ?: return null
        if (!angle.isFinite()) return null
        progress = angle / calibration.rangeDegrees

        if (!inRep) {
            if (progress < config.exitFraction) { risingFrom = null; armed = true }
            else if (risingFrom == null) risingFrom = t
            if (armed && progress >= config.enterFraction) {
                inRep = true
                repStart = risingFrom ?: t
                peak = progress
            }
            return null
        }
        if (progress > peak) peak = progress
        if (progress >= config.exitFraction) return null
        inRep = false
        risingFrom = null
        val movement = t - repStart
        if (movement < config.minMovementSeconds) return null
        return DetectedRep(t, movement, peak, peak >= config.fullFraction)
    }
}
