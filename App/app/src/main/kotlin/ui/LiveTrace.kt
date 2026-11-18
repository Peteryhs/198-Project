package com.tally.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.tally.app.contract.LiveRing

private const val MAX_POINTS = 1000
private const val RANGE_G = 3f
private const val DEFAULT_FRAME_INTERVAL_NS = 100_000_000L

/**
 * Live sensor trace. One FloatArray and one Path are reused for every frame; the ring is read at most once per
 * display frame and only when the received sample count changes. Upper arm is channels 0–2, forearm 3–5.
 */
@Composable
fun LiveTrace(ring: LiveRing, receivedSamples: Int, modifier: Modifier = Modifier) {
    val points = minOf(MAX_POINTS, ring.capacitySamples)
    val buffer = remember(ring) { FloatArray(points * 6) }
    val path = remember { Path() }
    val latestReceived by rememberUpdatedState(receivedSamples)
    var count by remember { mutableIntStateOf(0) }
    var totalSamples by remember { mutableLongStateOf(0L) }
    var incomingSamples by remember { mutableIntStateOf(0) }
    var scrollStart by remember { mutableFloatStateOf(0f) }
    var revealBatch by remember { mutableStateOf(false) }
    var frameAtNanos by remember { mutableLongStateOf(0L) }
    var frameIntervalNanos by remember { mutableLongStateOf(DEFAULT_FRAME_INTERVAL_NS) }
    var displayAtNanos by remember { mutableLongStateOf(0L) }
    LaunchedEffect(ring) {
        var receivedAt = 0L
        var previousCount = 0
        var previousTotal = 0L
        var seenTotal = -1
        while (true) {
            withFrameNanos { now ->
                val reported = latestReceived
                if (reported != seenTotal) {
                    val previousScroll = liveScrollOffset(
                        scrollFraction(now, frameAtNanos, frameIntervalNanos),
                        totalSamples >= points && !revealBatch, scrollStart,
                    )
                    val newCount = ring.copyLatest(buffer, points)
                    val wasFilling = previousCount < points
                    val added = when {
                        newCount == 0 || newCount < previousCount || reported < previousTotal -> {
                            previousTotal = maxOf(reported.toLong(), newCount.toLong())
                            0
                        }
                        seenTotal == -1 -> {
                            previousTotal = maxOf(reported.toLong(), newCount.toLong())
                            0
                        }
                        else -> {
                            val samples = (reported - previousTotal).coerceIn(0L, points.toLong()).toInt()
                            previousTotal = reported.toLong()
                            samples
                        }
                    }
                    frameIntervalNanos = if (receivedAt == 0L) DEFAULT_FRAME_INTERVAL_NS
                        else (now - receivedAt).coerceIn(20_000_000L, 500_000_000L)
                    receivedAt = now
                    frameAtNanos = now
                    totalSamples = previousTotal
                    incomingSamples = added
                    revealBatch = wasFilling
                    scrollStart = if (newCount == 0 || newCount < previousCount || seenTotal == -1 || wasFilling)
                        0f else previousScroll - added
                    count = newCount
                    previousCount = newCount
                    seenTotal = reported
                }
                // Once interpolation finishes, the canvas stays unchanged until another batch arrives.
                displayAtNanos = minOf(now, frameAtNanos + frameIntervalNanos)
            }
        }
    }
    val dashed = remember { PathEffect.dashPathEffect(floatArrayOf(18f, 10f)) }
    val dotted = remember { PathEffect.dashPathEffect(floatArrayOf(3f, 9f)) }
    val colors = MaterialTheme.colorScheme
    val traceColors = listOf(colors.primary, colors.secondary, colors.tertiary)
    Column(modifier, verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
        for (segment in 0..1) {
            SectionLabel(if (segment == 0) "Upper arm" else "Forearm")
            Canvas(
                Modifier.fillMaxWidth().height(120.dp).border(1.dp, colors.outline, MaterialTheme.shapes.small).padding(8.dp)
                    .semantics { contentDescription = "Live ${if (segment == 0) "upper arm" else "forearm"} trace" }
            ) {
                drawLine(colors.outline, Offset(0f, size.height / 2), Offset(size.width, size.height / 2), 1f)
                val progress = scrollFraction(displayAtNanos, frameAtNanos, frameIntervalNanos)
                val scroll = liveScrollOffset(
                    progress, totalSamples >= points && !revealBatch, scrollStart,
                )
                val windowStart = (totalSamples - points).coerceAtLeast(0)
                val revealRight = if (revealBatch && count > 0) {
                    ((liveRevealFrontier(totalSamples, incomingSamples, progress) - windowStart - scroll) *
                        (size.width / (points - 1)) + 1.dp.toPx()).coerceIn(0f, size.width)
                } else size.width
                clipRect(right = revealRight) {
                    for (axis in 0..2) {
                        trace(path, buffer, count, points, totalSamples, scroll, segment * 3 + axis)
                        val effect = when (axis) { 0 -> null; 1 -> dashed; else -> dotted }
                        drawPath(path, traceColors[axis], style = Stroke(width = 2.dp.toPx(), pathEffect = effect))
                    }
                }
            }
        }
        FlowRow(
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            listOf("X · solid", "Y · dashed", "Z · dotted").forEachIndexed { axis, label ->
                androidx.compose.material3.Text(
                    label,
                    color = traceColors[axis],
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            androidx.compose.material3.Text("Scale ±3 g", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

private fun DrawScope.trace(
    path: Path, buffer: FloatArray, count: Int, points: Int, totalSamples: Long, scrollSamples: Float, channel: Int,
) {
    path.reset()
    if (count < 2) return
    val step = size.width / (points - 1)
    val half = size.height / 2
    val oldest = totalSamples - count
    val windowStart = (totalSamples - points).coerceAtLeast(0)
    for (i in 0 until count) {
        val x = ((oldest + i - windowStart).toFloat() - scrollSamples) * step
        val y = half - (buffer[i * 6 + channel].coerceIn(-RANGE_G, RANGE_G) / RANGE_G) * half
        if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
    }
}
