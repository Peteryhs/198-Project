package com.jeevan.tally.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jeevan.tally.exercise.*
import com.jeevan.tally.exercise.SetReport.duration
import com.jeevan.tally.exercise.SetReport.percent
import com.jeevan.tally.exercise.SetReport.seconds
import com.jeevan.tally.export.SetExporter
import com.jeevan.tally.recording.ExerciseSetSession
import com.jeevan.tally.recording.ExerciseSetSession.CalibrationStep
import com.jeevan.tally.recording.ExerciseSetSession.Phase
import com.jeevan.tally.sensors.ArduinoLink
import com.jeevan.tally.ui.theme.ReadoutMedium
import kotlinx.coroutines.delay
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExerciseScreen(session: ExerciseSetSession, onBack: () -> Unit) {
    val context = LocalContext.current
    val scheme = MaterialTheme.colorScheme
    val store = remember { SetStore(File(context.filesDir, "sets")) }
    var leaveDialog by remember { mutableStateOf(false) }
    var resetDialog by remember { mutableStateOf(false) }
    var saveDialog by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    val linkStatus by ArduinoLink.status.collectAsState()
    val unsaved = session.phase != Phase.SETUP && session.savedName == null && (session.summary?.counted ?: 0) > 0
    val view = LocalView.current
    DisposableEffect(session.phase, view) {
        val previous = view.keepScreenOn
        if (session.phase == Phase.RUNNING) view.keepScreenOn = true
        onDispose { view.keepScreenOn = previous }
    }
    fun leave() { if (unsaved) leaveDialog = true else onBack() }
    BackHandler { leave() }

    if (leaveDialog) AlertDialog(onDismissRequest = { leaveDialog = false }, title = { Text("Leave this set?") },
        text = { Text("The repetitions logged so far have not been saved.") },
        confirmButton = { TextButton(onClick = { leaveDialog = false; onBack() }) { Text("Discard", color = scheme.error) } },
        dismissButton = { TextButton(onClick = { leaveDialog = false }) { Text("Stay") } })
    if (resetDialog) AlertDialog(onDismissRequest = { resetDialog = false }, title = { Text("Reset the count?") },
        text = { Text("This discards the current set and its repetition log. Saved sets are not affected.") },
        confirmButton = { TextButton(onClick = { resetDialog = false; session.reset() }) { Text("Reset", color = scheme.error) } },
        dismissButton = { TextButton(onClick = { resetDialog = false }) { Text("Cancel") } })
    if (saveDialog) {
        val exercise = session.prescription?.exercise?.label ?: "Set"
        var name by remember { mutableStateOf("$exercise · ${SimpleDateFormat("MMM d, HH:mm", Locale.getDefault()).format(Date())}") }
        AlertDialog(onDismissRequest = { saveDialog = false }, title = { Text("Save set") },
            text = { OutlinedTextField(name, { name = it.take(80) }, label = { Text("Name") }, singleLine = true) },
            confirmButton = { TextButton(enabled = name.isNotBlank(), onClick = { saveDialog = false; session.save(store, name) }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { saveDialog = false }) { Text("Cancel") } })
    }
    if (session.calibrationStep != CalibrationStep.IDLE) CalibrationDialog(session)

    Scaffold(containerColor = scheme.surface, topBar = {
        TopAppBar(title = { Text("Exercise set") },
            subtitle = { Text(session.prescription?.exercise?.label ?: "Set up", color = scheme.onPrimary, maxLines = 1) },
            navigationIcon = { IconButton(onClick = ::leave) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            actions = {
                if (session.phase != Phase.SETUP) {
                    IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, "Set actions") }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        DropdownMenuItem(text = { Text("Calibrate") }, leadingIcon = { Icon(Icons.Filled.Tune, null) },
                            enabled = session.phase == Phase.PAUSED, onClick = { menu = false; session.startCalibration() })
                        DropdownMenuItem(text = { Text("Reset count") }, leadingIcon = { Icon(Icons.Filled.RestartAlt, null) },
                            onClick = { menu = false; resetDialog = true })
                    }
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = scheme.primary, titleContentColor = scheme.onPrimary,
                navigationIconContentColor = scheme.onPrimary, actionIconContentColor = scheme.onPrimary))
    }, bottomBar = {
        if (session.phase != Phase.SETUP) Surface(color = scheme.surfaceContainerLow) {
            Row(Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                when (session.phase) {
                    Phase.SETUP -> Unit
                    Phase.RUNNING, Phase.PAUSED -> {
                        Button(onClick = { if (session.phase == Phase.RUNNING) session.pause() else session.resume() },
                            enabled = session.phase == Phase.RUNNING || linkStatus == ArduinoLink.Status.CONNECTED,
                            modifier = Modifier.weight(1f).heightIn(min = 56.dp), shapes = ButtonDefaults.shapes()) {
                            Icon(if (session.phase == Phase.RUNNING) Icons.Filled.Pause else Icons.Filled.PlayArrow, null, Modifier.size(20.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(if (session.phase == Phase.RUNNING) "Pause" else "Resume")
                        }
                        FilledTonalButton(onClick = session::finish, modifier = Modifier.heightIn(min = 56.dp), shape = MaterialTheme.shapes.large) {
                            Icon(Icons.Filled.Flag, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Finish")
                        }
                    }
                    Phase.FINISHED -> {
                        Button(onClick = { saveDialog = true }, enabled = session.savedName == null && !session.busy,
                            modifier = Modifier.weight(1f).heightIn(min = 56.dp), shapes = ButtonDefaults.shapes()) {
                            Icon(Icons.Filled.Save, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp))
                            Text(if (session.savedName == null) "Save set" else "Saved")
                        }
                        FilledTonalButton(onClick = {
                            val set = session.snapshot(session.savedName ?: "Unsaved set") ?: return@FilledTonalButton
                            runCatching { context.startActivity(android.content.Intent.createChooser(SetExporter.share(context, set), "Share set report")) }
                                .onFailure { session.message = "Could not share. ${it.localizedMessage.orEmpty()}" }
                        }, modifier = Modifier.heightIn(min = 56.dp), shape = MaterialTheme.shapes.large) {
                            Icon(Icons.Filled.IosShare, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Share")
                        }
                    }
                }
            }
        }
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            session.message?.let { message ->
                Surface(color = scheme.surfaceContainerLowest, shape = MaterialTheme.shapes.medium, border = BorderStroke(1.dp, scheme.outlineVariant)) {
                    Row(Modifier.padding(start = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(message, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f).padding(vertical = 12.dp)
                            .semantics { liveRegion = LiveRegionMode.Polite })
                        IconButton(onClick = { session.message = null }) { Icon(Icons.Filled.Close, "Dismiss message", Modifier.size(16.dp)) }
                    }
                }
            }
            when (session.phase) {
                Phase.SETUP -> SetupPane(session)
                Phase.RUNNING, Phase.PAUSED -> LivePane(session)
                Phase.FINISHED -> FinishedPane(session)
            }
        }
    }
}

// ---- Setup ---------------------------------------------------------------------------------

@Composable
private fun SetupPane(session: ExerciseSetSession) {
    val scheme = MaterialTheme.colorScheme
    val boardConfig by ArduinoLink.boardConfig.collectAsState()
    var exercise by rememberSaveable { mutableStateOf(boardConfig?.exercise ?: Exercise.EFE) }
    var count by rememberSaveable { mutableStateOf(boardConfig?.targetCount ?: 10) }
    var pacePrescribed by rememberSaveable { mutableStateOf(boardConfig?.hasTempo ?: false) }
    var min by rememberSaveable { mutableStateOf(boardConfig?.minSeconds?.toString() ?: "") }
    var target by rememberSaveable { mutableStateOf(boardConfig?.targetSeconds?.toString() ?: "") }
    var max by rememberSaveable { mutableStateOf(boardConfig?.maxSeconds?.toString() ?: "") }
    var rxId by rememberSaveable { mutableStateOf(boardConfig?.prescriptionId ?: "") }
    val prescription = runCatching {
        if (pacePrescribed) Prescription(exercise, count, min.toFloat(), target.toFloat(), max.toFloat(), rxId.trim())
        else Prescription(exercise, count, prescriptionId = rxId.trim())
    }

    SourceCard(session)

    Text("Prescription", style = MaterialTheme.typography.titleMedium)
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        Exercise.entries.forEachIndexed { i, e ->
            SegmentedButton(selected = exercise == e, onClick = { exercise = e },
                shape = SegmentedButtonDefaults.itemShape(i, Exercise.entries.size), icon = {}) {
                Text(when (e) { Exercise.EAH -> "Arms up"; Exercise.EFE -> "Elbow flex"; Exercise.SQZ -> "Squeeze" },
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
    Text(exercise.label, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Target repetitions", style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
        FilledTonalIconButton(onClick = { count = (count - 1).coerceAtLeast(1) }) { Icon(Icons.Filled.Remove, "Fewer") }
        Text("$count", style = ReadoutMedium, modifier = Modifier.padding(horizontal = 16.dp).semantics { contentDescription = "$count repetitions" })
        FilledTonalIconButton(onClick = { count = (count + 1).coerceAtMost(999) }) { Icon(Icons.Filled.Add, "More") }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("Prescribed pace", style = MaterialTheme.typography.bodyLarge)
            Text("Seconds per repetition, from the instructor. There is no default range.",
                style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
        }
        Switch(checked = pacePrescribed, onCheckedChange = { pacePrescribed = it })
    }
    if (pacePrescribed) Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        PaceField("Min s", min, { min = it }, Modifier.weight(1f))
        PaceField("Target s", target, { target = it }, Modifier.weight(1f))
        PaceField("Max s", max, { max = it }, Modifier.weight(1f))
    }
    OutlinedTextField(rxId, { rxId = it.filter { c -> c != ',' && c != '\n' }.take(47) }, label = { Text("Prescription ID (optional)") },
        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium)
    prescription.exceptionOrNull()?.let {
        Text(if (it is NumberFormatException) "Enter all three pace values." else it.message.orEmpty(),
            color = scheme.error, style = MaterialTheme.typography.bodySmall)
    }

    CalibrationCard(session)

    Button(onClick = { prescription.getOrNull()?.let(session::start) }, enabled = prescription.isSuccess,
        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp), shapes = ButtonDefaults.shapes()) {
        Icon(Icons.Filled.PlayArrow, null, Modifier.size(20.dp)); Spacer(Modifier.width(8.dp)); Text("Start set")
    }
}

@Composable
private fun PaceField(label: String, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier) {
    OutlinedTextField(value, { onChange(it.filter { c -> c.isDigit() || c == '.' }.take(5)) }, label = { Text(label) },
        singleLine = true, modifier = modifier, shape = MaterialTheme.shapes.medium,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
}

/** Says who is counting: the board firmware, the app's estimate, or nobody yet. */
@Composable
private fun SourceCard(session: ExerciseSetSession) {
    val scheme = MaterialTheme.colorScheme
    val status by ArduinoLink.status.collectAsState()
    val board by ArduinoLink.boardStatus.collectAsState()
    var now by remember { mutableStateOf(System.nanoTime() / 1_000_000) }
    LaunchedEffect(Unit) { while (true) { delay(1000); now = System.nanoTime() / 1_000_000 } }
    val streaming = session.lastFrameMillis?.let { now - it < 2000 } == true
    val (title, body) = when {
        status != ArduinoLink.Status.CONNECTED -> "No board connected" to "Connect from the Exercise tab. Sets can still be set up now."
        board != null -> "The board is counting" to "Tally logs the firmware's count, pace, faults and end-of-set model verdict. Board state: ${board!!.state.label.lowercase()}."
        streaming -> "Arm-pair data is arriving" to "The firmware is not counting yet, so Tally estimates repetitions from the two sensors. Calibrate first."
        else -> "Connected, no arm-pair data" to "The board must send TALLY status lines or synchronized time_ms,upper xyz,forearm xyz rows."
    }
    Surface(color = scheme.surfaceContainerLow, shape = MaterialTheme.shapes.extraLarge) {
        Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            StatusLed(if (board != null || streaming) com.jeevan.tally.ui.theme.StatusConnected else com.jeevan.tally.ui.theme.StatusOff,
                board != null || streaming, Modifier.padding(top = 6.dp))
            Column {
                Text(title, style = MaterialTheme.typography.titleSmall)
                Text(body, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun CalibrationCard(session: ExerciseSetSession) {
    val scheme = MaterialTheme.colorScheme
    val c = session.calibration
    Surface(color = scheme.surfaceContainerLowest, shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, scheme.outlineVariant)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Tune, null, tint = scheme.primary)
                Text("Calibration", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f).padding(start = 10.dp))
                OutlinedButton(onClick = session::startCalibration, shapes = ButtonDefaults.shapes()) { Text(if (c == null) "Calibrate" else "Recalibrate") }
            }
            Text(c?.let { "Measuring ${it.signal.label.lowercase()} over a ${it.rangeDegrees.toInt()}° range. Reps reaching 80% of it count as full." }
                ?: "Hold the start position, then the end position, for two seconds each. Needed for the app's own count; the board calibrates with its own button.",
                style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
            session.calibrationError?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = scheme.error) }
        }
    }
}

@Composable
private fun CalibrationDialog(session: ExerciseSetSession) {
    val (title, body) = when (session.calibrationStep) {
        CalibrationStep.REST_GET_READY -> "Start position" to "Get into the start position and keep the arm still."
        CalibrationStep.REST_HOLD -> "Hold still" to "Measuring the start position…"
        CalibrationStep.END_GET_READY -> "End position" to "Move to the end of the movement, as far as the exercise goes, and keep still."
        CalibrationStep.END_HOLD -> "Hold still" to "Measuring the end position…"
        CalibrationStep.IDLE -> "" to ""
    }
    AlertDialog(onDismissRequest = {}, title = { Text(title) }, text = {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
            Text(body, style = MaterialTheme.typography.bodyLarge)
            Text("${session.calibrationCountdown}", fontFamily = FontFamily.Monospace, fontSize = 56.sp, fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 16.dp).semantics { liveRegion = LiveRegionMode.Assertive })
        }
    }, confirmButton = {}, dismissButton = { TextButton(onClick = session::cancelCalibration) { Text("Cancel") } })
}

// ---- Live ----------------------------------------------------------------------------------

@Composable
private fun LivePane(session: ExerciseSetSession) {
    val scheme = MaterialTheme.colorScheme
    val s = session.summary ?: return
    val board by ArduinoLink.boardStatus.collectAsState()
    val p = s.prescription

    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(if (session.phase == Phase.PAUSED) "Paused" else "Repetitions", style = MaterialTheme.typography.labelLarge,
            color = if (session.phase == Phase.PAUSED) scheme.tertiary else scheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.Bottom, modifier = Modifier.semantics(mergeDescendants = true) {
            contentDescription = "${s.counted} of ${p.targetCount} repetitions"; liveRegion = LiveRegionMode.Polite
        }) {
            Text("${s.counted}".padStart(2, '0'), fontFamily = FontFamily.Monospace, fontSize = 88.sp, fontWeight = FontWeight.Medium,
                style = MaterialTheme.typography.displayLarge)
            Text(" / ${p.targetCount}", style = MaterialTheme.typography.headlineSmall, color = scheme.onSurfaceVariant,
                modifier = Modifier.padding(bottom = 18.dp))
        }
        LinearProgressIndicator(progress = { s.completion.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth().padding(top = 4.dp))
        Text(s.source.label, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
    }

    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        StatTile("Pace", seconds(s.lastPace), if (p.hasTempo) String.format(Locale.US, "%.1f–%.1f s", p.minSeconds, p.maxSeconds) else "per rep", Modifier.weight(1f))
        StatTile("Efficiency", percent(s.efficiency), "${s.effectiveReps} effective", Modifier.weight(1f))
        StatTile("Active", duration(s.activeSeconds), "${s.pauseCount} pauses", Modifier.weight(1f))
    }

    board?.cue?.takeIf { it != TempoCue.ABSTAIN }?.let { cue ->
        AssistChip(onClick = {}, label = { Text(cue.label) }, leadingIcon = { Icon(Icons.Filled.Speed, null) })
    }

    if (s.source == CountSource.APP) {
        if (session.calibration == null) {
            Text("Calibrate to let the app count. Pause, then use Calibrate in the menu.", color = scheme.error, style = MaterialTheme.typography.bodySmall)
        } else {
            Text("Range of motion", style = MaterialTheme.typography.titleSmall)
            RangeMeter(session.progress, session.progressTrace)
            Text("A rise past 40% starts a repetition and a return below 20% completes it. Peaks of 80% or more count as full.",
                style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
        }
    }

    DataQualityRow(s)

    if (session.reps.isNotEmpty()) {
        Text("Latest repetitions", style = MaterialTheme.typography.titleSmall)
        Surface(color = scheme.surfaceContainerLowest, shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, scheme.outlineVariant)) {
            Column(Modifier.padding(horizontal = 16.dp)) {
                session.reps.takeLast(8).asReversed().forEachIndexed { i, rep ->
                    if (i > 0) HorizontalDivider(color = scheme.outlineVariant)
                    RepRow(rep)
                }
            }
        }
    }
}

@Composable
private fun StatTile(label: String, value: String, note: String, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    Surface(modifier, color = scheme.surfaceContainerLowest, shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, scheme.outlineVariant)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = scheme.onSurfaceVariant)
            Text(value, style = ReadoutMedium, maxLines = 1)
            Text(note, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant, maxLines = 1)
        }
    }
}

/** The calibrated range as a bar, with the exit / entry / full thresholds marked, plus a five-second trace. */
@Composable
private fun RangeMeter(progress: Float, trace: List<Float>) {
    val scheme = MaterialTheme.colorScheme
    val track = scheme.surfaceContainerHighest
    val fill = scheme.primary
    val mark = scheme.tertiary
    val config = remember { CounterConfig() }
    Canvas(Modifier.fillMaxWidth().height(56.dp).semantics { contentDescription = "Range ${(progress * 100).toInt()} percent" }) {
        val barTop = size.height - 14.dp.toPx()
        val barH = 14.dp.toPx()
        val scale = 1.2f  // leave room past the calibrated end
        fun x(f: Float) = size.width * (f / scale).coerceIn(0f, 1f)
        if (trace.size >= 2) {
            val traceH = barTop - 6.dp.toPx()
            for (i in 1 until trace.size) {
                val x0 = size.width * (i - 1) / (trace.size - 1)
                val x1 = size.width * i / (trace.size - 1)
                drawLine(scheme.outline, Offset(x0, traceH * (1 - (trace[i - 1] / scale).coerceIn(0f, 1f))),
                    Offset(x1, traceH * (1 - (trace[i] / scale).coerceIn(0f, 1f))), strokeWidth = 2.dp.toPx())
            }
        }
        drawRoundRect(track, Offset(0f, barTop), Size(size.width, barH), CornerRadius(barH / 2))
        drawRoundRect(fill, Offset(0f, barTop), Size(x(progress), barH), CornerRadius(barH / 2))
        listOf(config.exitFraction, config.enterFraction, config.fullFraction).forEach { f ->
            drawLine(mark, Offset(x(f), barTop - 4.dp.toPx()), Offset(x(f), barTop + barH), strokeWidth = 2.dp.toPx())
        }
    }
}

@Composable
private fun DataQualityRow(s: SetSummary) {
    val scheme = MaterialTheme.colorScheme
    val faults = s.faultNames
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(if (faults.isEmpty()) Icons.Filled.CheckCircle else Icons.Filled.ErrorOutline, null,
            tint = if (faults.isEmpty()) scheme.primary else scheme.error, modifier = Modifier.size(18.dp))
        Text(buildString {
            append("Samples ").append(percent(s.coverage))
            append(" · gaps ").append(s.timingGaps)
            if (s.clippedSamples > 0) append(" · clipped ").append(s.clippedSamples)
            if (faults.isNotEmpty()) append(" · ").append(faults.joinToString(", "))
        }, style = MaterialTheme.typography.bodySmall, color = if (faults.isEmpty()) scheme.onSurfaceVariant else scheme.error)
    }
}

// ---- Finished ------------------------------------------------------------------------------

@Composable
private fun FinishedPane(session: ExerciseSetSession) {
    val scheme = MaterialTheme.colorScheme
    val s = session.summary ?: return
    var observed by rememberSaveable { mutableStateOf(s.observedCount?.toString() ?: "") }
    Text(if (session.savedName != null) "Saved as ${session.savedName}" else "Set finished", style = MaterialTheme.typography.headlineSmall)

    Surface(color = scheme.surfaceContainerLow, shape = MaterialTheme.shapes.extraLarge) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("How many did you actually do?", style = MaterialTheme.typography.titleSmall)
            Text("Count it yourself or ask the instructor. Tally compares it with its own count to measure counting error.",
                style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
            OutlinedTextField(observed, { value ->
                observed = value.filter(Char::isDigit).take(4)
                session.setObservedCount(observed.toIntOrNull())
            }, label = { Text("Observed repetitions") }, singleLine = true, enabled = session.savedName == null,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), shape = MaterialTheme.shapes.medium)
        }
    }

    SetSummaryView(s, session.reps)

    OutlinedButton(onClick = session::reset, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), shapes = ButtonDefaults.shapes()) {
        Text(if (session.savedName == null) "Discard and start a new set" else "Start a new set")
    }
}
