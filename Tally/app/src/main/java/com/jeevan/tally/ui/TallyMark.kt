package com.jeevan.tally.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * The brand's logo mark: two blocks forming a split-angle glyph — a tall bar and a
 * small notch beneath it. Drawn on a Canvas rather than shipped as a bitmap so it
 * stays crisp at any size and can take either ink-on-paper or paper-on-ink.
 */
@Composable
fun TallyMark(color: Color, modifier: Modifier = Modifier, size: androidx.compose.ui.unit.Dp = 22.dp) {
    Canvas(modifier = modifier.size(size)) {
        val unit = this.size.width / 10f
        drawRect(color, topLeft = Offset(unit * 1f, 0f), size = Size(unit * 2.4f, unit * 6.2f))
        drawRect(color, topLeft = Offset(unit * 1f, unit * 6.9f), size = Size(unit * 2f, unit * 2f))
        drawRect(color, topLeft = Offset(unit * 3.6f, unit * 7.5f), size = Size(unit * 3.4f, unit * 2.5f))
    }
}
