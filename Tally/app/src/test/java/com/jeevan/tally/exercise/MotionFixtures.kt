package com.jeevan.tally.exercise

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * Synthetic elbow-flexion frames at 100 Hz: the upper arm hangs still while the forearm rotates
 * in one plane. Gravity only, so the geometry is exact and the expected counts are known.
 */
object MotionFixtures {
    data class Frame(val ms: Long, val values: FloatArray)

    val upper = floatArrayOf(0f, -1f, 0f)

    fun frameAt(ms: Long, forearmDegrees: Double): Frame {
        val r = forearmDegrees * PI / 180
        return Frame(ms, floatArrayOf(upper[0], upper[1], upper[2], sin(r).toFloat(), (-cos(r)).toFloat(), 0f))
    }

    /** Holds a fixed angle for [seconds]. */
    fun hold(startMs: Long, seconds: Double, degrees: Double): List<Frame> =
        (0 until (seconds * 100).toInt()).map { frameAt(startMs + it * 10L, degrees) }

    /** One smooth raise-and-return to [peakDegrees] taking [seconds]. */
    fun rep(startMs: Long, seconds: Double, peakDegrees: Double): List<Frame> {
        val n = (seconds * 100).toInt()
        return (0 until n).map { i -> frameAt(startMs + i * 10L, peakDegrees * (1 - cos(2 * PI * i / n)) / 2) }
    }

    /** Concatenates segments back to back on one 10 ms clock. */
    fun sequence(vararg segments: (Long) -> List<Frame>): List<Frame> {
        val out = mutableListOf<Frame>()
        var t = 0L
        for (segment in segments) {
            val frames = segment(t)
            out += frames
            t = (frames.lastOrNull()?.ms ?: (t - 10)) + 10
        }
        return out
    }

    fun calibration(): Calibration {
        val rest = (AngleMath.pose(hold(0, 1.0, 0.0).map { it.values }) as PoseResult.Ok).pose
        val end = (AngleMath.pose(hold(0, 1.0, 90.0).map { it.values }) as PoseResult.Ok).pose
        return (AngleMath.calibrate(rest, end) as CalibrationResult.Ok).calibration
    }
}
