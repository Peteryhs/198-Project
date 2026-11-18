package com.tally.app.ui

import com.tally.app.contract.ChartSample
import com.tally.app.contract.RepSpan
import kotlin.math.ceil

internal fun chartAxisMaximum(samples: List<ChartSample>): Float {
    val maxG = samples.maxOf { maxOf(it.upperArmG, it.forearmG) }
    return if (maxG <= 0f) 0.5f else ceil(maxG * 2f) / 2f
}

internal fun chartX(timeS: Double, startS: Double, endS: Double, width: Float): Float =
    ((timeS - startS) / (endS - startS) * width).toFloat()

internal fun selectedRepIndexAt(
    positionFraction: Float, startS: Double, endS: Double, reps: List<RepSpan>,
): Int? {
    if (!positionFraction.isFinite() || endS <= startS) return null
    val time = startS + (endS - startS) * positionFraction.coerceIn(0f, 1f)
    return reps.firstOrNull { time >= it.startS && time <= it.endS }?.index
}

internal fun scrollFraction(nowNanos: Long, frameNanos: Long, intervalNanos: Long): Float {
    if (frameNanos <= 0L || intervalNanos <= 0L) return 0f
    return ((nowNanos - frameNanos).coerceAtLeast(0).toDouble() / intervalNanos).coerceIn(0.0, 1.0).toFloat()
}

internal fun liveScrollOffset(progress: Float, enabled: Boolean, startOffset: Float): Float =
    if (enabled) startOffset * (1f - progress) else 0f

internal fun liveRevealFrontier(totalSamples: Long, incomingSamples: Int, progress: Float): Float =
    if (incomingSamples <= 0) totalSamples - 1f else totalSamples - incomingSamples - 1f + incomingSamples * progress
