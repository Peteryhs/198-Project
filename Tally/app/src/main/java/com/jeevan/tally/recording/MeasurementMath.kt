package com.jeevan.tally.recording

import com.jeevan.tally.sensors.SensorSample
import kotlin.math.abs
import kotlin.math.sqrt

data class AxisStatistics(val min: Double, val max: Double, val mean: Double, val rms: Double, val deviation: Double)
fun axisStatistics(samples: List<SensorSample>, axis: Int): AxisStatistics? {
    val values = samples.mapNotNull { it.values.getOrNull(axis)?.takeIf(Float::isFinite)?.toDouble() }
    if (values.isEmpty()) return null
    val mean = values.average()
    return AxisStatistics(values.min(), values.max(), mean, sqrt(values.sumOf { it * it } / values.size),
        sqrt(values.sumOf { (it - mean) * (it - mean) } / values.size))
}

data class PlotBounds(val min: Float, val max: Float)
fun plotBounds(samples: List<SensorSample>, axes: Set<Int>): PlotBounds {
    val values = samples.flatMap { sample -> axes.mapNotNull { sample.values.getOrNull(it)?.takeIf(Float::isFinite) } }
    if (values.isEmpty()) return PlotBounds(-1f, 1f)
    val min = values.min().toDouble(); val max = values.max().toDouble()
    val pad = if (min == max) maxOf(abs(min) * 0.1, 1.0) else (max - min) * 0.1
    return PlotBounds((min - pad).coerceAtLeast(-Float.MAX_VALUE.toDouble()).toFloat(),
        (max + pad).coerceAtMost(Float.MAX_VALUE.toDouble()).toFloat())
}
fun nearestSample(samples: List<SensorSample>, time: Float): SensorSample? = samples.minByOrNull { abs(it.t - time) }
