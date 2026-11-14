package com.jeevan.tally.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.jeevan.tally.exercise.*
import com.jeevan.tally.exercise.SetReport.duration
import com.jeevan.tally.exercise.SetReport.percent
import com.jeevan.tally.exercise.SetReport.seconds
import com.jeevan.tally.ui.theme.ReadoutLarge
import com.jeevan.tally.ui.theme.ReadoutMedium
import java.util.Locale

/** Every logged metric for one set, grouped the way an instructor reads it. */
@Composable
fun SetSummaryView(summary: SetSummary, reps: List<Rep>, modifier: Modifier = Modifier) {
    val p = summary.prescription
    Column(modifier, verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            HeadlineTile("Repetitions", "${summary.counted}", "of ${p.targetCount} · ${percent(summary.completion)}", Modifier.weight(1f))
            HeadlineTile("Efficiency", percent(summary.efficiency),
                if (summary.efficiency == null) "no range or pace evidence" else "${summary.effectiveReps} of ${summary.loggedReps} reps effective",
                Modifier.weight(1f))
        }

        MetricGroup("Repetitions") {
            Metric("Exercise", p.exercise.label)
            Metric("Counted by", summary.source.label)
            Metric("Full range", "${summary.fullReps}")
            Metric("Shallow", "${summary.shallowReps}")
            Metric("Range efficiency", percent(summary.rangeEfficiency), "full ÷ reps with a range reading")
        }

        MetricGroup("Pace") {
            Metric("Prescribed", if (p.hasTempo) String.format(Locale.US, "%.1f–%.1f s per rep", p.minSeconds, p.maxSeconds) else "Not prescribed")
            Metric("Last / mean", "${seconds(summary.lastPace)} / ${seconds(summary.meanPace)}")
            Metric("Fastest / slowest", "${seconds(summary.fastestPace)} / ${seconds(summary.slowestPace)}")
            Metric("On pace · fast · slow", "${summary.onTarget} · ${summary.tooFast} · ${summary.tooSlow}")
            Metric("Pace adherence", percent(summary.paceAdherence))
            Metric("Reps per minute", summary.repsPerMinute?.let { String.format(Locale.US, "%.1f", it) } ?: "n/a")
        }

        MetricGroup("Session") {
            Metric("Active time", duration(summary.activeSeconds), "pauses excluded")
            Metric("Pauses", "${summary.pauseCount}")
            Metric("Calibration", summary.calibrationSignal?.let { "${it.label}, ${summary.calibrationRangeDegrees?.toInt()}°" } ?: "Not calibrated in app")
            if (summary.boardRestarts > 0) Metric("Board restarts", "${summary.boardRestarts}", "count kept cumulative")
        }

        MetricGroup("Design targets") {
            Metric("Counting error", summary.errorsPer10?.let { String.format(Locale.US, "%.1f per 10", it) } ?: "Enter the observed count",
                "target ≤ ${DesignTargets.MAX_ERRORS_PER_10_REPS.toInt()} per 10", summary.meetsCountingTarget)
            Metric("Samples recorded", percent(summary.coverage),
                "${summary.samplesReceived} of ${summary.expectedSamples} at $NOMINAL_HZ Hz · target ≥ ${(DesignTargets.MIN_COVERAGE * 100).toInt()}%",
                summary.meetsCoverageTarget)
            Metric("Continuous run", duration(summary.activeSeconds), "of ${(DesignTargets.CONTINUOUS_RUN_SECONDS / 60).toInt()} min target",
                if (summary.continuousRunFraction >= 1f) true else null)
        }

        MetricGroup("Data quality") {
            Metric("Timing gaps", "${summary.timingGaps}", "longer than $MAX_SAMPLE_GAP_MS ms")
            Metric("Clipped samples", "${summary.clippedSamples}", "at or beyond ±3 g")
            Metric("Dropped samples", "${summary.droppedSamples}")
            Metric("Faults", summary.faultNames.ifEmpty { listOf("None") }.joinToString(", "))
        }

        MetricGroup("Model assessment") {
            val a = summary.assessment
            if (a == null) {
                Metric("Status", "Unavailable", "the board reports one after a fault-free set of 3+ cycles")
            } else {
                Metric("Likely exercise", "${a.likelyExercise.label} (${percent(a.exerciseProbability[a.likelyExercise.ordinal])})")
                Metric("Series label", if (a.seriesLabelIncorrect) "Incorrect" else "Correct",
                    String.format(Locale.US, "mean P(incorrect) %.2f · study label, not a clinical judgment", a.pIncorrect))
            }
        }

        if (reps.isNotEmpty()) {
            MetricGroup("Repetition log") {
                reps.asReversed().forEachIndexed { i, rep ->
                    if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    RepRow(rep)
                }
            }
        }
        Text("Repetition boundaries come from a detector, not validated observation. Treat pace and range as estimates.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun RepRow(rep: Rep, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    Row(modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("#${rep.index}", style = ReadoutMedium, modifier = Modifier.width(44.dp))
        Text(seconds(rep.paceSeconds), style = ReadoutMedium, modifier = Modifier.width(64.dp))
        Text(when (rep.full) { true -> "Full"; false -> "Shallow"; null -> "—" },
            style = MaterialTheme.typography.bodyMedium,
            color = if (rep.full == false) scheme.tertiary else scheme.onSurface, modifier = Modifier.weight(1f))
        Text(when (rep.cue) {
            TempoCue.ON_TARGET -> "On pace"; TempoCue.TOO_FAST -> "Too fast"; TempoCue.TOO_SLOW -> "Too slow"; TempoCue.ABSTAIN -> ""
        }, style = MaterialTheme.typography.labelLarge,
            color = if (rep.cue == TempoCue.TOO_FAST || rep.cue == TempoCue.TOO_SLOW) scheme.tertiary else scheme.onSurfaceVariant)
    }
}

@Composable
private fun HeadlineTile(label: String, value: String, note: String, modifier: Modifier = Modifier) {
    Surface(modifier, color = MaterialTheme.colorScheme.surfaceContainerLowest, shape = MaterialTheme.shapes.large,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = ReadoutLarge)
            Text(note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun MetricGroup(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.semantics { heading() })
        Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest, shape = MaterialTheme.shapes.large,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp), content = content)
        }
    }
}

/** One label/value line. [meets] colours the value when it is a pass/fail against a target. */
@Composable
private fun Metric(label: String, value: String, note: String? = null, meets: Boolean? = null) {
    val scheme = MaterialTheme.colorScheme
    Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(1f).padding(end = 12.dp)) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            if (note != null) Text(note, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
        }
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold,
            color = when (meets) { true -> scheme.primary; false -> scheme.error; null -> scheme.onSurface })
        if (meets != null) Text(if (meets) "  ✓" else "  ✗", color = if (meets) scheme.primary else scheme.error,
            style = MaterialTheme.typography.bodyMedium)
    }
}
