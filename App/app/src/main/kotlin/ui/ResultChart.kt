package com.tally.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.tally.app.contract.SetResult
import java.util.Locale

/** Draws only the collected chart points and the scorer's exact repetition windows. */
@Composable
fun ResultChart(result: SetResult) {
    val chart = result.chart ?: return
    if (chart.samples.size < 2) return
    val startS = chart.samples.first().timeS
    val endS = chart.samples.last().timeS
    if (endS <= startS) return
    val upperPath = remember(chart.samples) { Path() }
    val forearmPath = remember(chart.samples) { Path() }
    val axisMax = remember(chart.samples) { chartAxisMaximum(chart.samples) }
    val dashed = remember { PathEffect.dashPathEffect(floatArrayOf(8f, 5f)) }
    var selectedRepIndex by remember(result.id, chart.reps) {
        mutableIntStateOf(chart.reps.firstOrNull()?.index ?: -1)
    }
    val selectedSpan = chart.reps.firstOrNull { it.index == selectedRepIndex }
    val selectedRep = result.reps.firstOrNull { it.index == selectedRepIndex }
    val selectedPosition = chart.reps.indexOfFirst { it.index == selectedRepIndex }
    val colors = MaterialTheme.colorScheme
    val traceColor = colors.onSurface

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionLabel("Your movement")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Upper arm · solid line", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium)
            Text("Forearm · dashed line", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium,
                textAlign = TextAlign.End)
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(
                Modifier.width(42.dp).height(176.dp).padding(vertical = 2.dp),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    "${formatG(axisMax)} g", style = MaterialTheme.typography.labelSmall,
                )
                Text("0 g", style = MaterialTheme.typography.labelSmall)
            }
            Canvas(
                Modifier.weight(1f).height(176.dp)
                    .border(1.dp, colors.outline, MaterialTheme.shapes.small)
                    .pointerInput(chart) {
                        detectTapGestures { tap ->
                            selectedRepIndexAt(
                                tap.x / size.width, startS, endS, chart.reps,
                            )?.let { selectedRepIndex = it }
                        }
                    }
                    .semantics {
                        contentDescription = "Upper arm and forearm movement over time." +
                            if (chart.reps.isEmpty()) "" else " Shaded sections mark reps."
                    },
            ) {
                drawLine(traceColor.copy(alpha = 0.28f), Offset(0f, size.height / 2), Offset(size.width, size.height / 2), 1.dp.toPx())
                drawLine(traceColor, Offset(0f, size.height), Offset(size.width, size.height), 1.dp.toPx())
                chart.reps.forEach { span ->
                    val left = chartX(span.startS, startS, endS, size.width)
                    val right = chartX(span.endS, startS, endS, size.width)
                    val rect = androidx.compose.ui.geometry.Rect(left, 0f, right, size.height)
                    drawRect(colors.surfaceVariant.copy(alpha = if (span.index == selectedRepIndex) 0.62f else 0.28f), rect.topLeft, rect.size)
                    if (span.index == selectedRepIndex)
                        drawRect(traceColor, rect.topLeft, rect.size, style = Stroke(1.5.dp.toPx()))
                }
                upperPath.reset()
                forearmPath.reset()
                chart.samples.forEachIndexed { index, sample ->
                    val x = chartX(sample.timeS, startS, endS, size.width)
                    val upperY = size.height * (1f - sample.upperArmG / axisMax)
                    val forearmY = size.height * (1f - sample.forearmG / axisMax)
                    if (index == 0) {
                        upperPath.moveTo(x, upperY)
                        forearmPath.moveTo(x, forearmY)
                    } else {
                        upperPath.lineTo(x, upperY)
                        forearmPath.lineTo(x, forearmY)
                    }
                }
                drawPath(upperPath, traceColor, style = Stroke(2.dp.toPx()))
                drawPath(forearmPath, traceColor, style = Stroke(2.dp.toPx(), pathEffect = dashed))
            }
        }
        Row(Modifier.fillMaxWidth().padding(start = 42.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(formatTime(startS), style = MaterialTheme.typography.labelSmall)
            Text(formatTime(endS), style = MaterialTheme.typography.labelSmall)
        }
        if (selectedSpan != null && selectedPosition >= 0) {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Rep ${selectedSpan.index} of ${chart.reps.size}", style = MaterialTheme.typography.titleSmall)
                val verdict = selectedRep?.let { if (it.wrong) "Wrong" else "Correct" } ?: "Result unavailable"
                val exercise = selectedRep?.exercise?.let(::exerciseWords) ?: "Exercise not identified"
                Text("$verdict · $exercise", style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
                Text("${formatTime(selectedSpan.startS)}–${formatTime(selectedSpan.endS)}", style = MaterialTheme.typography.bodySmall)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(
                    enabled = selectedPosition > 0,
                    onClick = { selectedRepIndex = chart.reps[selectedPosition - 1].index },
                ) { Text("Previous rep", style = MaterialTheme.typography.labelLarge) }
                TextButton(
                    enabled = selectedPosition < chart.reps.lastIndex,
                    onClick = { selectedRepIndex = chart.reps[selectedPosition + 1].index },
                ) { Text("Next rep", style = MaterialTheme.typography.labelLarge) }
            }
        }
    }
}

private fun formatG(value: Float) = String.format(Locale.ROOT, "%.1f", value)
private fun formatTime(value: Double) = String.format(Locale.ROOT, "%.2f s", value)
