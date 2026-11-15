package com.jeevan.tally.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
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
    val scrollState = rememberScrollState()
    var setupStep by rememberSaveable { mutableStateOf(0) }
    var leaveDialog by remember { mutableStateOf(false) }
    var resetDialog by remember { mutableStateOf(false) }
    var saveDialog by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    val linkStatus by ArduinoLink.status.collectAsState()
    val unsaved = session.phase != Phase.SETUP && session.savedName == null
    LaunchedEffect(session.phase) { if (session.phase == Phase.SETUP) setupStep = 0 }
    LaunchedEffect(setupStep, session.phase) { scrollState.scrollTo(0) }
    val haptics = LocalHapticFeedback.current
    LaunchedEffect(session.phase) {
        if (session.phase == Phase.FINISHED) haptics.performHapticFeedback(HapticFeedbackType.LongPress)
    }
    val view = LocalView.current
    DisposableEffect(session.phase, view) {
        val previous = view.keepScreenOn
        if (session.phase == Phase.RUNNING) view.keepScreenOn = true
        onDispose { view.keepScreenOn = previous }
    }
    fun leave() {
        if (session.phase == Phase.SETUP && setupStep > 0) setupStep--
        else if (unsaved) leaveDialog = true
        else onBack()
    }
    BackHandler { leave() }

    if (leaveDialog) AlertDialog(onDismissRequest = { leaveDialog = false }, title = { Text("Leave this set?") },
        text = { Text("This set and its measurements have not been saved.") },
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
            subtitle = { Text(session.prescription?.exercise?.label ?: "Set up", color = scheme.onSurfaceVariant, maxLines = 1) },
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
            colors = TopAppBarDefaults.topAppBarColors(containerColor = scheme.surfaceContainer, titleContentColor = scheme.onSurface,
                navigationIconContentColor = scheme.onSurface, actionIconContentColor = scheme.onSurface))
    }, bottomBar = {
        if (session.phase != Phase.SETUP) Surface(color = scheme.surfaceContainerLow) {
            Row(Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                when (session.phase) {
                    Phase.SETUP -> Unit
                    Phase.RUNNING, Phase.PAUSED -> {
                        TallyAction(onClick = { if (session.phase == Phase.RUNNING) session.pause() else session.resume() },
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
                        TallyAction(onClick = { saveDialog = true }, enabled = session.savedName == null && !session.busy,
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
        Column(Modifier.fillMaxSize().padding(padding).imePadding().verticalScroll(scrollState).padding(24.dp),
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
                Phase.SETUP -> SetupPane(session, setupStep) { setupStep = it }
                Phase.RUNNING, Phase.PAUSED -> LivePane(session)
                Phase.FINISHED -> FinishedPane(session) { resetDialog = true }
            }
        }
    }
}

// ---- Setup ---------------------------------------------------------------------------------

@Composable
private fun SetupPane(session: ExerciseSetSession, step: Int, onStep: (Int) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val haptics = LocalHapticFeedback.current
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

    val context = LocalContext.current
    val status by ArduinoLink.status.collectAsState()
    AnimatedContent(targetState = step, transitionSpec = { fadeIn() togetherWith fadeOut() },
        label = "Setup step title") { currentStep ->
        Text(when (currentStep) { 0 -> "Connect your board"; 1 -> "Plan your set"; else -> "Get ready" },
            style = MaterialTheme.typography.headlineMedium)
    }
    Text("Step ${step + 1} of 3", style = MaterialTheme.typography.labelLarge, color = scheme.onSurfaceVariant)
    LinearProgressIndicator(progress = { (step + 1) / 3f }, modifier = Modifier.fillMaxWidth())

    if (step == 0) {
        Text("Turn on your board and join its Wi-Fi network.", style = MaterialTheme.typography.bodyLarge)
        ArduinoConnectionBar(context)
        TallyAction(onClick = { onStep(1) }, enabled = status == ArduinoLink.Status.CONNECTED,
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Text("Continue") }
        TextButton(onClick = { onStep(1) }, modifier = Modifier.fillMaxWidth()) { Text("Set up first, connect later") }
        return
    }
    if (step == 2) {
        Text("${exercise.label} · $count repetitions", style = MaterialTheme.typography.titleLarge)
        if (status != ArduinoLink.Status.CONNECTED) {
            Text("Connect your board to record this set.", style = MaterialTheme.typography.bodyLarge)
            ArduinoConnectionBar(context)
        } else CalibrationCard(session)
        session.calibration?.let {
            Text("Calibration complete. Start when you are ready.", color = scheme.primary,
                style = MaterialTheme.typography.bodyLarge)
        }
        TallyAction(onClick = { prescription.getOrNull()?.let(session::start) },
            enabled = prescription.isSuccess && status == ArduinoLink.Status.CONNECTED &&
                (session.calibration != null || ArduinoLink.boardStatus.collectAsState().value != null),
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
            Icon(Icons.Filled.PlayArrow, null); Spacer(Modifier.width(8.dp)); Text("Start set")
        }
        TextButton(onClick = { onStep(1) }, modifier = Modifier.fillMaxWidth()) { Text("Edit exercise") }
        return
    }

    Text("Choose your exercise", style = MaterialTheme.typography.titleMedium)
    Column {
        Exercise.entries.forEach { option ->
            val press = remember { MutableInteractionSource() }
            Surface(onClick = {
                if (exercise != option) haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                exercise = option
            }, interactionSource = press, modifier = Modifier.fillMaxWidth().pressScale(press).semantics {
                role = Role.RadioButton
                selected = exercise == option
            },
                shape = MaterialTheme.shapes.medium,
                color = if (exercise == option) scheme.secondaryContainer else scheme.surface) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = exercise == option, onClick = null)
                    Text(option.label, style = MaterialTheme.typography.bodyLarge,
                        modifier = Modifier.padding(start = 12.dp))
                }
            }
        }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Target repetitions", style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
        FilledTonalIconButton(enabled = count > 1, onClick = { count = (count - 1).coerceAtLeast(1) }, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Remove, "Fewer") }
        Text("$count", style = ReadoutMedium, modifier = Modifier.padding(horizontal = 16.dp).semantics { contentDescription = "$count repetitions" })
        FilledTonalIconButton(enabled = count < 999, onClick = { count = (count + 1).coerceAtMost(999) }, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Add, "More") }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("Prescribed pace", style = MaterialTheme.typography.bodyLarge)
            Text("Seconds per repetition, from the instructor. There is no default range.",
                style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
        }
        Switch(checked = pacePrescribed, onCheckedChange = {
            haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
            pacePrescribed = it
        },
            modifier = Modifier.semantics { contentDescription = "Prescribed pace" })
    }
    AnimatedVisibility(visible = pacePrescribed,
        enter = expandVertically(spring(Spring.DampingRatioMediumBouncy, Spring.StiffnessLow)) + fadeIn(),
        exit = shrinkVertically(spring(stiffness = Spring.StiffnessLow)) + fadeOut(),
    ) {
        BoxWithConstraints {
            if (maxWidth < 360.dp || LocalDensity.current.fontScale > 1.3f) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    PaceField("Minimum seconds", min, { min = it }, Modifier.fillMaxWidth())
                    PaceField("Target seconds", target, { target = it }, Modifier.fillMaxWidth())
                    PaceField("Maximum seconds", max, { max = it }, Modifier.fillMaxWidth())
                }
            } else Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                PaceField("Min s", min, { min = it }, Modifier.weight(1f))
                PaceField("Target s", target, { target = it }, Modifier.weight(1f))
                PaceField("Max s", max, { max = it }, Modifier.weight(1f))
            }
        }
    }
    var showPrescriptionId by rememberSaveable { mutableStateOf(rxId.isNotEmpty()) }
    if (!showPrescriptionId) TextButton(onClick = { showPrescriptionId = true }) { Text("Add prescription ID") }
    if (showPrescriptionId) OutlinedTextField(rxId, { rxId = it.filter { c -> c != ',' && c != '\n' }.take(47) }, label = { Text("Prescription ID (optional)") },
        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium)
    prescription.exceptionOrNull()?.let {
        Text(if (it is NumberFormatException) "Enter all three pace values." else it.message.orEmpty(),
            color = scheme.error, style = MaterialTheme.typography.bodySmall)
    }

    TallyAction(onClick = { onStep(2) }, enabled = prescription.isSuccess,
        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Text("Continue to calibration") }
    TextButton(onClick = { onStep(0) }, modifier = Modifier.fillMaxWidth()) { Text("Back to connection") }

}

@Composable
private fun PaceField(label: String, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier) {
    OutlinedTextField(value, { onChange(it.filter { c -> c.isDigit() || c == '.' }.take(5)) }, label = { Text(label) },
        singleLine = true, modifier = modifier, shape = MaterialTheme.shapes.medium,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
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
            Text(c?.let { "Ready to measure your movement across a ${it.rangeDegrees.toInt()}° range." }
                ?: "Tap Calibrate, then follow the two poses on screen. Keep your arm still while each pose is measured.",
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
        Surface(color = scheme.secondaryContainer, shape = MaterialTheme.shapes.medium) {
            Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Speed, null, Modifier.size(20.dp))
                Text(cue.label, style = MaterialTheme.typography.titleSmall)
            }
        }
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
private fun FinishedPane(session: ExerciseSetSession, onDiscard: () -> Unit) {
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

    OutlinedButton(onClick = { if (session.savedName == null) onDiscard() else session.reset() }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), shapes = ButtonDefaults.shapes()) {
        Text(if (session.savedName == null) "Discard and start a new set" else "Start a new set")
    }
}
