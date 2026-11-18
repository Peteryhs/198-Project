package com.tally.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.tally.app.contract.LinkState
import com.tally.app.contract.LiveRing
import com.tally.app.contract.SessionState
import com.tally.app.contract.SetId
import com.tally.app.contract.Side

/** Before start: side selector. */
@Composable
fun RecordSetupScreen(
    side: Side,
    link: LinkState,
    message: String?,
    busy: Boolean,
    onSide: (Side) -> Unit,
    onStart: () -> Unit,
    onConnect: () -> Unit,
    intended: String? = null,
    onIntended: (String?) -> Unit = {},
) = TallyScreen("Record", actions = {
    if (link is LinkState.Connected) PrimaryAction(if (busy) "Starting" else "Start set", enabled = !busy, onClick = onStart)
    else PrimaryAction("Connect first", onClick = onConnect)
}) {
    val colors = MaterialTheme.colorScheme
    val segmentColors = SegmentedButtonDefaults.colors(
        activeContainerColor = colors.primary, activeContentColor = colors.onPrimary, activeBorderColor = colors.primary,
        inactiveContainerColor = colors.surface, inactiveContentColor = colors.onSurface, inactiveBorderColor = colors.outline,
    )
    Text("Sensor arm", style = MaterialTheme.typography.headlineMedium)
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        Side.entries.forEachIndexed { i, s ->
            SegmentedButton(
                selected = s == side, onClick = { onSide(s) },
                shape = SegmentedButtonDefaults.itemShape(i, Side.entries.size),
                modifier = Modifier.heightIn(min = 56.dp),
                colors = segmentColors,
            ) { Text(sideWords(s), style = MaterialTheme.typography.labelLarge) }
        }
    }
    Text("Exercise (optional)", style = MaterialTheme.typography.headlineMedium)
    val choices = listOf(
        null to "None",
        "EAH" to "Overhead",
        "EFE" to "Elbow bend",
        "SQZ" to "Squeeze",
    )
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        choices.forEach { (code, label) ->
            FilterChip(
                selected = code == intended,
                onClick = { onIntended(code) },
                label = { Text(label) },
            )
        }
    }
    if (message != null) Body(message)
}

/** During a set: elapsed time, samples, link health and the live trace. No rep count and no verdict. */
@Composable
fun RecordingScreen(
    recording: SessionState.Recording,
    elapsedMs: Long,
    link: LinkState,
    ring: LiveRing,
    message: String?,
    onStop: () -> Unit,
    onAbort: () -> Unit,
) = TallyScreen("Recording · ${sideWords(recording.side)}", actions = {
    PrimaryAction("Stop and score", onClick = onStop)
    SecondaryAction("Abort set", onClick = onAbort)
}) {
    Column {
        SectionLabel("Elapsed")
        Text(elapsed(elapsedMs), style = MaterialTheme.typography.displayMedium)
    }
    if (recording.linkStallMs > 0 || link is LinkState.Lost) {
        Body("Trying to reconnect…")
    } else if (recording.samples == 0) {
        Body("Waiting for sensor readings…")
    }
    LiveTrace(ring, recording.samples)
    if (message != null) Body(message)
}

/** A set that ended without a result, during recording or scoring. */
@Composable
fun SetFailedScreen(
    failed: SessionState.Failed,
    onScorePartial: () -> Unit,
    onRescore: (() -> Unit)?,
    onHome: () -> Unit,
    message: String?,
) = TallyScreen("Set ${failed.id.raw}", actions = {
    when {
        failed.partialScorable -> { PrimaryAction("Score the partial set", onClick = onScorePartial); SecondaryAction("Back to history", onClick = onHome) }
        onRescore != null -> { PrimaryAction("Try scoring again", onClick = onRescore); SecondaryAction("Back to history", onClick = onHome) }
        else -> PrimaryAction("Back to history", onClick = onHome)
    }
}) {
    Text("Set not scored", style = MaterialTheme.typography.headlineLarge)
    when {
        failed.partialScorable -> Body("Your received samples are saved. Score them as a partial set.")
        onRescore != null -> Body("Your set is saved. Try scoring it again.")
    }
    if (message != null) Body(message)
}

@Preview(showBackground = true, heightDp = 700)
@Composable
private fun SetupPreview() {
    val f = fakeAfterOneSet()
    TallyTheme { RecordSetupScreen(Side.L, f.backend.link.value, null, false, {}, {}, {}) }
}

@Preview(showBackground = true, heightDp = 1100)
@Composable
private fun RecordingPreview() {
    val f = fakeAfterOneSet()
    TallyTheme { RecordingScreen(SessionState.Recording(SetId(2u), Side.L, 1000, 0), 10_000, f.backend.link.value, f.backend.live, null, {}, {}) }
}

@Preview(showBackground = true)
@Composable
private fun FailedPreview() = TallyTheme { SetFailedScreen(SessionState.Failed(SetId(2u), "aborted", false), {}, null, {}, null) }
