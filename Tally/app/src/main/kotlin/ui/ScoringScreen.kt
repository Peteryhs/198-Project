package com.tally.app.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** Indeterminate on purpose: the scorer reports no progress, so no percentage is shown. */
@Composable
fun ScoringScreen() = TallyScreenFrame("Scoring", actions = null) { viewport ->
    Column(
        viewport.verticalScroll(rememberScrollState()).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
    ) {
        ScoringLoadingIndicator()
        Text(
            "Crunching the numbers…",
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun ScoringLoadingIndicator() {
    val transition = rememberInfiniteTransition(label = "scoring indicator")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(durationMillis = 3_600, easing = LinearEasing)),
        label = "rotation and shape morph",
    )
    val color = MaterialTheme.colorScheme.primary
    val path = remember { Path() }
    val points = remember { FloatArray(48) }
    Canvas(Modifier.size(144.dp).semantics { progressBarRangeInfo = ProgressBarRangeInfo.Indeterminate }) {
        val cycle = rotation
        val phase = (2 * PI * cycle).toFloat()
        val flower = (1f - cos(phase)) / 2f
        val radius = minOf(size.width, size.height) * 0.39f
        for (i in 0 until points.size step 2) {
            val angle = (2 * PI * i / points.size).toFloat()
            val r = radius * (1f + 0.12f * (1f - flower) * cos(4f * angle) + 0.19f * flower * cos(5f * angle))
            points[i] = center.x + r * cos(angle)
            points[i + 1] = center.y + r * sin(angle)
        }
        path.reset()
        path.moveTo((points[0] + points[points.size - 2]) / 2f, (points[1] + points.last()) / 2f)
        for (i in 0 until points.size step 2) {
            val next = (i + 2) % points.size
            path.quadraticTo(
                points[i], points[i + 1],
                (points[i] + points[next]) / 2f, (points[i + 1] + points[next + 1]) / 2f,
            )
        }
        path.close()
        rotate(cycle * 360f) { drawPath(path, color) }
    }
}

@Preview(showBackground = true, heightDp = 720)
@Composable
private fun ScoringPreview() = TallyTheme { ScoringScreen() }
