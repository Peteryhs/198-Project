package com.jeevan.tally.ui

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jeevan.tally.recording.nearestSample
import com.jeevan.tally.recording.plotBounds
import com.jeevan.tally.sensors.SensorSample
import com.jeevan.tally.ui.theme.*
import kotlin.math.abs

fun measurementText(value: Double): String = when {
    !value.isFinite() -> "—"
    abs(value) >= 100000 || (abs(value) < 0.001 && value != 0.0) -> "%.2e".format(value)
    else -> "%.3f".format(value)
}

/** Numeric axes and inspection share the same coordinate transform as the plotted traces. */
@Composable
fun LiveChart(
    history: List<SensorSample>,
    axisColors: List<Color>,
    windowSeconds: Float = 10f,
    modifier: Modifier = Modifier,
    axes: Set<Int> = setOf(0, 1, 2, 3),
    endTime: Float? = null,
    selected: SensorSample? = null,
    onSelect: (SensorSample?) -> Unit = {},
    chartHeight: Dp = 280.dp,
    interactive: Boolean = true,
) {
    val surfaceColor = MaterialTheme.colorScheme.surfaceContainerLowest
    val gridColor = MaterialTheme.colorScheme.outlineVariant
    val labelColor = MaterialTheme.colorScheme.onSurfaceVariant
    val primaryColor = MaterialTheme.colorScheme.primary
    val span = windowSeconds.coerceAtLeast(0.1f)
    val end = (endTime ?: history.lastOrNull()?.t ?: span).coerceAtLeast(span)
    val start = (end - span).coerceAtLeast(0f)
    val visible = history.filter { it.t in start..end }
    val bounds = plotBounds(visible, axes)
    Box(modifier.fillMaxWidth().height(chartHeight).background(surfaceColor)) {
        Canvas(Modifier.fillMaxSize().semantics {
            contentDescription = "Time graph, ${"%.1f".format(start)} to ${"%.1f".format(end)} seconds, ${axes.size} visible traces."
        }.pointerInput(visible, start, end, interactive) {
            if (interactive) detectTapGestures { point ->
                val left = 62.dp.toPx(); val right = size.width - 16.dp.toPx()
                if (point.x in left..right && right > left) {
                    val t = start + (point.x - left) / (right - left) * span
                    onSelect(nearestSample(visible, t))
                }
            }
        }) {
            val left = 62.dp.toPx(); val top = 18.dp.toPx()
            val right = size.width - 16.dp.toPx(); val bottom = size.height - 36.dp.toPx()
            val width = right - left; val height = bottom - top
            if (width <= 0 || height <= 0) return@Canvas
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = labelColor.toArgb(); textSize = 10.sp.toPx()
                typeface = android.graphics.Typeface.create("monospace", android.graphics.Typeface.NORMAL)
            }
            fun x(t: Float) = left + ((t - start) / span) * width
            fun y(v: Float) = bottom - ((v.toDouble() - bounds.min) / (bounds.max.toDouble() - bounds.min) * height).toFloat()
            for (i in 0..4) {
                val py = top + height * i / 4f
                drawLine(gridColor, Offset(left, py), Offset(right, py), 1.dp.toPx())
                val value = bounds.max.toDouble() - (bounds.max.toDouble() - bounds.min) * i / 4
                val label = if (abs(value) >= 10000 || (abs(value) < 0.01 && value != 0.0)) "%.0e".format(value) else "%.1f".format(value)
                paint.textAlign = Paint.Align.RIGHT
                drawContext.canvas.nativeCanvas.drawText(label, left - 8.dp.toPx(), py + 3.dp.toPx(), paint)
            }
            for (i in 0..4) {
                val px = left + width * i / 4f
                drawLine(gridColor, Offset(px, top), Offset(px, bottom), 1.dp.toPx())
                paint.textAlign = when (i) { 0 -> Paint.Align.LEFT; 4 -> Paint.Align.RIGHT; else -> Paint.Align.CENTER }
                drawContext.canvas.nativeCanvas.drawText("%.1f".format(start + span * i / 4f), px, bottom + 18.dp.toPx(), paint)
            }
            paint.textAlign = Paint.Align.CENTER
            drawContext.canvas.nativeCanvas.drawText("Time (s)", (left + right) / 2, size.height - 2.dp.toPx(), paint)
            if (bounds.min < 0 && bounds.max > 0) drawLine(labelColor.copy(alpha = 0.25f), Offset(left, y(0f)), Offset(right, y(0f)), 1.dp.toPx())
            axes.forEach { axis ->
                val path = Path()
                var previousSegment: Int? = null
                visible.forEach { sample ->
                    val value = sample.values.getOrNull(axis)
                    if (value == null || !value.isFinite()) { previousSegment = null }
                    else {
                        if (previousSegment == sample.segment) path.lineTo(x(sample.t), y(value)) else path.moveTo(x(sample.t), y(value))
                        previousSegment = sample.segment
                    }
                }
                drawPath(path, axisColors.getOrElse(axis) { primaryColor }, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 1.6.dp.toPx(), cap = StrokeCap.Round,
                    pathEffect = when ((axis / 4) % 4) {
                        1 -> PathEffect.dashPathEffect(floatArrayOf(8.dp.toPx(), 4.dp.toPx()))
                        2 -> PathEffect.dashPathEffect(floatArrayOf(2.dp.toPx(), 4.dp.toPx()))
                        3 -> PathEffect.dashPathEffect(floatArrayOf(8.dp.toPx(), 3.dp.toPx(), 2.dp.toPx(), 3.dp.toPx()))
                        else -> null
                    }))
                if (visible.size == 1) visible.first().values.getOrNull(axis)?.let { drawCircle(axisColors[axis], 3.dp.toPx(), Offset(x(visible.first().t), y(it))) }
            }
            selected?.takeIf { it.t in start..end }?.let { sample ->
                drawLine(labelColor, Offset(x(sample.t), top), Offset(x(sample.t), bottom), 1.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx())))
                axes.forEach { axis -> sample.values.getOrNull(axis)?.let { value ->
                    drawCircle(surfaceColor, 5.dp.toPx(), Offset(x(sample.t), y(value)))
                    drawCircle(axisColors[axis], 3.dp.toPx(), Offset(x(sample.t), y(value)))
                } }
            }
        }
        if (visible.isEmpty()) Text(if (history.isEmpty()) "No measurements yet" else "No samples in this interval",
            style = MaterialTheme.typography.bodyMedium, color = labelColor,
            modifier = Modifier.align(Alignment.Center).background(surfaceColor).padding(10.dp))
    }
}
