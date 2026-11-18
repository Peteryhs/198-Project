package com.tally.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.tally.app.contract.SetResult
import java.util.Locale

@Composable
fun ResultScreen(
    result: SetResult,
    message: String?,
    onClose: () -> Unit = {},
    onRescore: (() -> Unit)? = null,
    onExport: () -> Unit,
) =
    TallyScreen("Results · ${sideWords(result.side)}", actions = {
        val colors = MaterialTheme.colorScheme
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(
                onClick = onClose,
                modifier = Modifier.weight(1f).heightIn(min = 56.dp),
                shape = MaterialTheme.shapes.extraLarge,
                border = BorderStroke(2.dp, colors.outline),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = colors.onSurface),
            ) { Text("Close", style = MaterialTheme.typography.labelLarge) }
            Button(
                onClick = onExport,
                modifier = Modifier.weight(1f).heightIn(min = 56.dp),
                shape = MaterialTheme.shapes.extraLarge,
            ) { Text("Export CSV", style = MaterialTheme.typography.labelLarge) }
        }
    }) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(verdictWords(result.status, result.wrong, result.wrongExercise), style = MaterialTheme.typography.displayMedium)
            val summary = listOfNotNull(
                result.exercise?.let(::exerciseWords),
                if (result.status == "scored") "${result.reps.size} ${if (result.reps.size == 1) "rep" else "reps"}" else null,
            )
            if (summary.isNotEmpty()) {
                Text(summary.joinToString(" · "), style = MaterialTheme.typography.titleMedium)
            }
            Text(dateWords(result.startedAtEpochMs), style = MaterialTheme.typography.bodyMedium)
            if (result.status == "scored") Text("Estimated from sensor data", style = MaterialTheme.typography.bodySmall)
        }
        if ("partial_device_lost" in result.diagnostics) Body("Only part of your set was recorded.")
        if ("no_movement" in result.diagnostics) Body("No movement was detected, so no reps were counted.")
        if (message != null) Body(message)
        ResultChart(result)
        if (onRescore != null) SecondaryAction("Score again", onClick = onRescore)
        Details(result)
    }

/** A stored set with no result yet, for example one interrupted by the app closing during scoring. */
@Composable
fun NoResultScreen(label: String, loading: Boolean, message: String?, action: String, onScore: () -> Unit) =
    TallyScreen(label, actions = {
        if (!loading) PrimaryAction(action, onClick = onScore)
    }) {
        Text(if (loading) "Loading" else "No result yet", style = MaterialTheme.typography.displaySmall)
        if (message != null) Body(message)
    }

/** One rep as the scorer reported it: index, window duration, class code and p(wrong), with the 0.5 threshold. */
@Composable
private fun RepRow(vararg cells: String) {
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    Row(Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
        cells.forEachIndexed { i, cell ->
            Text(cell, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(if (i == 3) 1.6f else 1f))
        }
    }
}

@Composable
private fun Details(result: SetResult) {
    var open by rememberSaveable { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SecondaryAction(if (open) "Hide details" else "Show details") { open = !open }
        AnimatedVisibility(open, enter = expandVertically(), exit = shrinkVertically()) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Body(scoringPathWords(result.provenance.modelKind))
                result.exercise?.let { Body(exerciseCheckWords(it, result.intendedExercise)) }
                if (result.status == "scored") {
                    Body(unvalidatedWords)
                    if (!result.provenance.modelKind.startsWith("gemini-")) Body(modelOriginWords)
                }
                if (result.reps.isNotEmpty()) Column {
                    SectionLabel("Repetitions")
                    RepRow("Rep", "Duration", "Class", "p(wrong)")
                    result.reps.forEach { rep ->
                        RepRow(
                            rep.index.toString(), String.format(Locale.ROOT, "%.2f s", rep.durationS), rep.exercise,
                            String.format(Locale.ROOT, "%.3f %s", rep.pWrong, if (rep.wrong) "wrong" else "ok"),
                        )
                    }
                }
                Fact("Set identifier", result.id.raw.toString())
                Fact("Status code", result.status)
                Fact("Exercise class code", result.exercise ?: "Unavailable")
                Fact("Intended exercise", result.intendedExercise ?: "Not specified")
                Fact("Set verdict", when { result.wrongExercise -> "wrong exercise"; result.wrong == true -> "wrong"
                    result.wrong == false -> "correct"; else -> "unknown" })
                Fact("Mean p(wrong)", result.meanPWrong?.let(::probability) ?: "Unavailable")
                Fact("Measured sample rate", result.measuredRateHz?.let { String.format(Locale.ROOT, "%.1f Hz", it) } ?: "Unavailable")
                SectionLabel("Diagnostics")
                if (result.diagnostics.isEmpty()) Body("None") else result.diagnostics.forEach { Body(it) }
                SectionLabel("Recording information")
                with(result.provenance) {
                    Fact("Model kind", modelKind)
                    Fact("Model sha256 (${result.side.name})", modelSha256)
                    Fact("Scorer sha256", scorerSha256)
                    Fact("Git revision", gitRev)
                    Fact("Firmware version", fwVersion.toString())
                    Fact("Device MAC", mac)
                    Fact("Calibration id", calibrationId)
                    Fact("App version", appVersion)
                }
            }
        }
    }
}

@Preview(showBackground = true, heightDp = 1400)
@Composable
private fun ResultPreview() = TallyTheme { ResultScreen(fakeAfterOneSet().result, null) {} }
