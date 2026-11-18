package com.tally.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.unit.dp

/** Every screen: mark and section label at the top, scrolling content, one action area pinned at the bottom. */
@Composable
fun TallyScreen(
    label: String,
    actions: (@Composable ColumnScope.() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) = TallyScreenFrame(label, actions) { modifier ->
    Column(
        modifier.verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp),
        content = content,
    )
}

@Composable
internal fun TallyScreenFrame(
    label: String,
    actions: (@Composable ColumnScope.() -> Unit)?,
    content: @Composable (Modifier) -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    Surface(color = colors.surface, contentColor = colors.onSurface, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.safeDrawingPadding(), horizontalAlignment = Alignment.CenterHorizontally) {
            Column(Modifier.widthIn(max = 720.dp).fillMaxWidth().weight(1f)) {
                Row(Modifier.padding(horizontal = 24.dp, vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                    TallyMark(size = 24.dp)
                    Spacer(Modifier.width(12.dp))
                    SectionLabel(label)
                }
                HorizontalDivider(Modifier.padding(horizontal = 24.dp), color = colors.outlineVariant)
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    content(Modifier.fillMaxSize())
                    if (actions != null) {
                        Spacer(
                            Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(24.dp)
                                .background(Brush.verticalGradient(listOf(colors.surface.copy(alpha = 0f), colors.surface))),
                        )
                    }
                }
                if (actions != null) {
                    Column(
                        Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        content = actions,
                    )
                }
            }
        }
    }
}

/** Plain-language paragraph. */
@Composable
fun Body(text: String, modifier: Modifier = Modifier) =
    Text(text, style = MaterialTheme.typography.bodyLarge, modifier = modifier)
