package com.jeevan.tally.ui

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

@Composable
internal fun Modifier.pressScale(interactionSource: MutableInteractionSource): Modifier {
    val pressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        if (pressed) 0.96f else 1f,
        animationSpec = spring(Spring.DampingRatioMediumBouncy, Spring.StiffnessMedium),
        label = "Press scale",
    )
    return graphicsLayer { scaleX = scale; scaleY = scale }
}

@Composable
internal fun TallyAction(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shapes: ButtonShapes = ButtonDefaults.shapes(),
    content: @Composable RowScope.() -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val haptics = LocalHapticFeedback.current
    Button(
        onClick = {
            haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
            onClick()
        },
        modifier = modifier.pressScale(interaction),
        enabled = enabled,
        shapes = shapes,
        interactionSource = interaction,
        content = content,
    )
}

@Composable
internal fun LoadingRows(label: String) {
    val transition = rememberInfiniteTransition(label = "Loading sheen")
    val sweep by transition.animateFloat(
        initialValue = -0.35f, targetValue = 1.35f,
        animationSpec = infiniteRepeatable(tween(1050)),
        label = "Sheen position",
    )
    val colors = MaterialTheme.colorScheme
    val shape = MaterialTheme.shapes.large
    Column(
        Modifier.fillMaxWidth().semantics { contentDescription = label },
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        repeat(3) { index ->
            val center = (sweep - index * 0.1f).coerceIn(0f, 1f)
            Box(Modifier.fillMaxWidth().height(56.dp).clip(shape).background(
                Brush.horizontalGradient(
                    (center - 0.25f).coerceAtLeast(0f) to colors.surfaceContainerHigh,
                    center to colors.surfaceContainerHighest,
                    (center + 0.25f).coerceAtMost(1f) to colors.surfaceContainerHigh,
                ),
            ))
        }
    }
}
