package com.tally.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/** The one filled action on a screen, full width and at least 64 dp tall. */
@Composable
fun PrimaryAction(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Button(
        onClick, Modifier.fillMaxWidth().heightIn(min = 64.dp), enabled = enabled,
        shape = MaterialTheme.shapes.extraLarge,
        colors = ButtonDefaults.buttonColors(
            disabledContainerColor = colors.primaryContainer,
            disabledContentColor = colors.onPrimaryContainer,
        ),
    ) { Text(text, style = MaterialTheme.typography.titleMedium) }
}

/** A full-width outlined action. */
@Composable
fun SecondaryAction(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    OutlinedButton(
        onClick, Modifier.fillMaxWidth().heightIn(min = 56.dp), enabled = enabled,
        shape = MaterialTheme.shapes.extraLarge, border = BorderStroke(2.dp, colors.outline),
        colors = ButtonDefaults.outlinedButtonColors(contentColor = colors.onSurface, disabledContentColor = colors.onSurface),
    ) { Text(text, style = MaterialTheme.typography.labelLarge) }
}
