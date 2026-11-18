package com.tally.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.tally.app.contract.BodyHold
import com.tally.app.contract.CalibrationInfo
import com.tally.app.contract.LinkState

/**
 * Paired references, remaining fit directions, independent check, then the same references again.
 * See tally-research/08-experiments/protocol/on_arm_redesign/MOTION-NOISE-ENVIRONMENT.md §6.
 */
private val plan = listOf(
    BodyHold.HANG, BodyHold.FORWARD_PALM_UP,
    BodyHold.SIDE_PALM_FORWARD, BodyHold.OVERHEAD,
    BodyHold.CHECK, BodyHold.HANG, BodyHold.FORWARD_PALM_UP,
)

/** [captured] counts holds already accepted, in [plan] order; the contract has no query for it. */
@Composable
fun CalibrationScreen(
    calibration: CalibrationInfo?,
    link: LinkState,
    captured: Int,
    capturing: Boolean,
    message: String?,
    onCapture: (BodyHold) -> Unit,
    onSave: () -> Unit,
    onConnect: () -> Unit,
    onRepeat: () -> Unit = {},
) {
    val current = plan.getOrNull(captured)
    val colors = MaterialTheme.colorScheme
    TallyScreen("Calibration", actions = {
        when {
            capturing -> PrimaryAction(if (current == null) "Saving" else "Capturing", enabled = false) {}
            link !is LinkState.Connected && current != null -> PrimaryAction("Connect first", onClick = onConnect)
            current == null -> PrimaryAction("Save calibration", onClick = onSave)
            else -> PrimaryAction("Capture this hold") { onCapture(current) }
        }
        if (current == null && !capturing) SecondaryAction("Repeat holds", onClick = onRepeat)
    }) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SectionLabel(if (current == null) "All holds captured" else "Hold ${captured + 1} of ${plan.size}")
            Text(current?.let(::bodyHoldWords) ?: "Ready to save", style = MaterialTheme.typography.displaySmall)
        }
        Body(
            if (current == null) "Save to use these measurements for new sets. Sensor gains still use starting values."
            else "Keep both straps on. Stay still for about three seconds, then tap Capture. Stop if the position is uncomfortable."
        )
        if (capturing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = colors.primary, trackColor = colors.primaryContainer)
        if (message != null) Body(message)
        if (captured == 0 && !capturing && message == null) {
            val status = when {
                calibration == null -> "No calibration loaded"
                calibration.nominal -> "Using starting values"
                else -> "Saved calibration active"
            }
            Text(status, style = MaterialTheme.typography.bodyMedium, color = colors.onSurfaceVariant)
        }
    }
}

@Preview(showBackground = true, heightDp = 1200)
@Composable
private fun CalibrationPreview() {
    val f = fakeAfterOneSet()
    TallyTheme {
        CalibrationScreen(f.backend.calibration.value, f.backend.link.value, 3, false, null, {}, {}, {})
    }
}
