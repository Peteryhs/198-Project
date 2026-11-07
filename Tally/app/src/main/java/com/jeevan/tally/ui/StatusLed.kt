package com.jeevan.tally.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * A small panel-light dot, the one recurring motion in the app: it pulses only while
 * something is actually live (pulsing = pulsing). Idle/error states hold steady so the
 * animation always means something rather than decorating every state equally.
 */
@Composable
fun StatusLed(color: Color, pulsing: Boolean, modifier: Modifier = Modifier, size: androidx.compose.ui.unit.Dp = 8.dp) {
    val alpha = if (pulsing) {
        val transition = rememberInfiniteTransition(label = "led-pulse")
        val a by transition.animateFloat(
            initialValue = 1f,
            targetValue = 0.35f,
            animationSpec = infiniteRepeatable(
                animation = tween(700),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "led-pulse-alpha",
        )
        a
    } else {
        1f
    }

    androidx.compose.foundation.layout.Box(
        modifier = modifier
            .size(size)
            .alpha(alpha)
            .background(color, CircleShape),
    )
}
