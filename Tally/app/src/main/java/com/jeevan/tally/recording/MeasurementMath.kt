package com.jeevan.tally.recording

import com.jeevan.tally.sensors.SensorSample
import kotlin.math.abs
import kotlin.math.sqrt

data class AxisStatistics(val min: Double, val max: Double, val mean: Double, val rms: Double, val deviation: Double)
fun axisStatistics(samples: List<SensorSample>, axis: Int): AxisStatistics? {
    var count = 0
    var min = Double.POSITIVE_INFINITY
    var max = Double.NEGATIVE_INFINITY
    var mean = 0.0
    var squared = 0.0
    var squaredDeviation = 0.0
    for (sample in samples) {
        val value = sample.values.getOrNull(axis)?.toDouble() ?: continue
        if (!value.isFinite()) continue
        count++
        min = minOf(min, value)
        max = maxOf(max, value)
        squared += value * value
        // Welford's update avoids subtracting large, nearly equal sums.
        val delta = value - mean
        mean += delta / count
        squaredDeviation += delta * (value - mean)
    }
    if (count == 0) return null
    return AxisStatistics(min, max, mean, sqrt(squared / count), sqrt(squaredDeviation / count))
}

/** Returns the inclusive time window from a timestamp-ordered snapshot of a recording. */
internal fun samplesInWindow(samples: List<SensorSample>, start: Float, end: Float): List<SensorSample> {
    if (start > end) return emptyList()

    fun boundary(time: Float, includeEqual: Boolean): Int {
        var low = 0
        var high = samples.size
        while (low < high) {
            val mid = low + (high - low) / 2
            val timestamp = samples[mid].t
            if (timestamp < time || (includeEqual && timestamp == time)) low = mid + 1
            else high = mid
        }
        return low
    }

    return samples.subList(boundary(start, includeEqual = false), boundary(end, includeEqual = true))
}

data class PlotBounds(val min: Float, val max: Float)
fun plotBounds(samples: List<SensorSample>, axes: Set<Int>): PlotBounds {
    var min = Double.POSITIVE_INFINITY
    var max = Double.NEGATIVE_INFINITY
    for (sample in samples) {
        for (axis in axes) {
            val value = sample.values.getOrNull(axis)?.toDouble() ?: continue
            if (!value.isFinite()) continue
            min = minOf(min, value)
            max = maxOf(max, value)
        }
    }
    if (!min.isFinite()) return PlotBounds(-1f, 1f)
    val pad = if (min == max) maxOf(abs(min) * 0.1, 1.0) else (max - min) * 0.1
    return PlotBounds((min - pad).coerceAtLeast(-Float.MAX_VALUE.toDouble()).toFloat(),
        (max + pad).coerceAtMost(Float.MAX_VALUE.toDouble()).toFloat())
}
fun nearestSample(samples: List<SensorSample>, time: Float): SensorSample? = samples.minByOrNull { abs(it.t - time) }
