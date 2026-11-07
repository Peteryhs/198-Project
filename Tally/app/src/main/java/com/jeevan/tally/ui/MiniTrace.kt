package com.jeevan.tally.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.dp
import com.jeevan.tally.sensors.SensorSample

/** A tiny, chrome-free trace of the magnitude channel — the "is this alive" glance on a home tile. */
@Composable
fun MiniTrace(history: List<SensorSample>, color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier = modifier.size(width = 72.dp, height = 32.dp)) {
        if (history.size < 2) return@Canvas
        val magnitudeIndex = history.first().values.size - 1
        val values = history.map { it.values.getOrElse(magnitudeIndex) { 0f } }
        var minV = values.min()
        var maxV = values.max()
        if (minV == maxV) {
            minV -= 1f
            maxV += 1f
        }
        val w = size.width
        val h = size.height
        val n = values.size
        var prev: Offset? = null
        for (i in values.indices) {
            val x = w * i / (n - 1).toFloat()
            val y = h - ((values[i] - minV) / (maxV - minV)) * h
            val p = Offset(x, y)
            if (prev != null) drawLine(color, prev, p, strokeWidth = 2.5f, cap = StrokeCap.Round)
            prev = p
        }
    }
}
