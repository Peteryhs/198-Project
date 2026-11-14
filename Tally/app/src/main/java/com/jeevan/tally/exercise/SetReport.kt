package com.jeevan.tally.exercise

import com.jeevan.tally.export.CsvFormatter.csvCell
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** The instructor-facing summary of one set, as plain text (share sheet) and CSV (spreadsheet). */
object SetReport {
    fun percent(value: Float?) = value?.let { "${(it * 100).toInt()}%" } ?: "n/a"
    fun seconds(value: Float?) = value?.let { String.format(Locale.US, "%.1f s", it) } ?: "n/a"
    fun duration(seconds: Float): String {
        val total = seconds.toInt().coerceAtLeast(0)
        return if (total >= 60) "${total / 60} min ${total % 60} s" else "$total s"
    }

    private fun tempoText(p: Prescription) = if (p.hasTempo)
        String.format(Locale.US, "%.1f–%.1f s per rep (target %.1f s)", p.minSeconds, p.maxSeconds, p.targetSeconds) else "not prescribed"

    private fun verdict(ok: Boolean?) = when (ok) { true -> "meets target"; false -> "below target"; null -> "not measured" }

    /** One row per metric: (metric, value, design target or prescription). */
    fun rows(set: SavedSet): List<Triple<String, String, String>> {
        val s = set.summary
        val p = s.prescription
        val rows = mutableListOf(
            Triple("Exercise", p.exercise.label, ""),
            Triple("Prescription ID", p.prescriptionId.ifEmpty { "none" }, ""),
            Triple("Repetitions counted", s.counted.toString(), "target ${p.targetCount}"),
            Triple("Completion", percent(s.completion), "100%"),
            Triple("Counted by", s.source.label, ""),
            Triple("Efficiency (full range and on pace)", percent(s.efficiency), "${s.effectiveReps} of ${s.loggedReps} logged reps"),
            Triple("Full-range reps", s.fullReps.toString(), ""),
            Triple("Shallow reps", s.shallowReps.toString(), ""),
            Triple("Range efficiency", percent(s.rangeEfficiency), ""),
            Triple("Prescribed pace", tempoText(p), ""),
            Triple("Reps on pace", s.onTarget.toString(), ""),
            Triple("Reps too fast", s.tooFast.toString(), ""),
            Triple("Reps too slow", s.tooSlow.toString(), ""),
            Triple("Pace adherence", percent(s.paceAdherence), ""),
            Triple("Mean pace", seconds(s.meanPace), "per rep"),
            Triple("Fastest / slowest pace", "${seconds(s.fastestPace)} / ${seconds(s.slowestPace)}", ""),
            Triple("Reps per minute", s.repsPerMinute?.let { String.format(Locale.US, "%.1f", it) } ?: "n/a", ""),
            Triple("Active time", duration(s.activeSeconds), "excludes pauses"),
            Triple("Pauses", s.pauseCount.toString(), ""),
            Triple("Samples recorded", "${s.samplesReceived} of ${s.expectedSamples} expected", "at $NOMINAL_HZ Hz"),
            Triple("Data coverage", percent(s.coverage), "≥ ${(DesignTargets.MIN_COVERAGE * 100).toInt()}%: ${verdict(s.meetsCoverageTarget)}"),
            Triple("Timing gaps (> $MAX_SAMPLE_GAP_MS ms)", s.timingGaps.toString(), ""),
            Triple("Clipped samples (±3 g)", s.clippedSamples.toString(), ""),
            Triple("Dropped samples", s.droppedSamples.toString(), ""),
            Triple("Faults", s.faultNames.ifEmpty { listOf("none") }.joinToString("; "), ""),
            Triple("Continuous run", duration(s.activeSeconds), "of ${(DesignTargets.CONTINUOUS_RUN_SECONDS / 60).toInt()} min target"),
            Triple("Calibration", s.calibrationSignal?.let { "${it.label}, ${s.calibrationRangeDegrees?.toInt()}° range" } ?: "not calibrated in app", "${s.calibrationEvents} calibration events"),
            Triple("Observed count", s.observedCount?.toString() ?: "not entered", ""),
            Triple("Counting error", s.errorsPer10?.let { String.format(Locale.US, "%.1f per 10 reps", it) } ?: "n/a",
                "≤ ${DesignTargets.MAX_ERRORS_PER_10_REPS.toInt()} per 10: ${verdict(s.meetsCountingTarget)}"),
        )
        val a = s.assessment
        if (a == null) rows += Triple("Model assessment", "unavailable", "needs ≥ 3 cycles and no faults on the board")
        else {
            rows += Triple("Model exercise guess", "${a.likelyExercise.label} (${percent(a.exerciseProbability[a.likelyExercise.ordinal])})", "")
            rows += Triple("Model series label", if (a.seriesLabelIncorrect) "incorrect" else "correct",
                String.format(Locale.US, "mean P(incorrect) %.2f; not a clinical judgment", a.pIncorrect))
        }
        return rows
    }

    fun toText(set: SavedSet): String = buildString {
        val s = set.summary
        val date = SimpleDateFormat("MMM d, yyyy HH:mm", Locale.getDefault()).format(Date(s.startedAtMillis))
        appendLine("Tally set: ${set.name}")
        appendLine(date)
        appendLine()
        for ((metric, value, note) in rows(set)) {
            append(metric).append(": ").append(value)
            if (note.isNotEmpty()) append(" (").append(note).append(')')
            appendLine()
        }
        appendLine()
        appendLine("Repetition boundaries come from a detector, not from validated observation. Treat pace and range as estimates.")
    }

    fun toCsv(set: SavedSet): String = buildString {
        appendLine("metric,value,note")
        for ((metric, value, note) in rows(set)) appendLine("${csvCell(metric)},${csvCell(value)},${csvCell(note)}")
        appendLine()
        appendLine("rep,completed_at_s,pace_s,movement_s,peak_range_pct,range,pace_check")
        for (r in set.reps) {
            appendLine(listOf(
                r.index.toString(),
                String.format(Locale.US, "%.2f", r.t),
                r.paceSeconds?.let { String.format(Locale.US, "%.2f", it) }.orEmpty(),
                r.movementSeconds?.let { String.format(Locale.US, "%.2f", it) }.orEmpty(),
                r.peakRangeFraction?.let { (it * 100).toInt().toString() }.orEmpty(),
                when (r.full) { true -> "full"; false -> "shallow"; null -> "" },
                r.cue.label,
            ).joinToString(",") { csvCell(it) })
        }
    }
}
