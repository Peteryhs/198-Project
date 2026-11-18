package com.tally.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.material3.LocalContentColor
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.floor

/**
 * The split angle on a 12 × 12 unit grid: a 4 × 7 vertical bar at the upper left, a 7 × 4 horizontal bar at
 * the lower right, one unit of break at the bend in both directions. The unit snaps to whole pixels.
 */
@Composable
fun TallyMark(size: Dp = 32.dp, color: Color = LocalContentColor.current, modifier: Modifier = Modifier) {
    Canvas(modifier.size(size).semantics { contentDescription = "Tally" }) {
        val unit = floor(this.size.minDimension / 12f).coerceAtLeast(1f)
        drawRect(color, Offset(0f, 0f), Size(4 * unit, 7 * unit))
        drawRect(color, Offset(5 * unit, 8 * unit), Size(7 * unit, 4 * unit))
    }
}
