package com.jeevan.tally.ui

import androidx.activity.compose.BackHandler
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.lerp
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.jeevan.tally.ExperimentEntry
import com.jeevan.tally.export.CsvExporter
import com.jeevan.tally.recording.*
import com.jeevan.tally.sensors.ArduinoLink
import com.jeevan.tally.sensors.SensorSample
import com.jeevan.tally.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExperimentScreen(entry: ExperimentEntry, session: ExperimentSession, recordingId: String? = null, onBack: () -> Unit) {
    val context = LocalContext.current
    val stream = remember(entry.id) { entry.factory(context.applicationContext) }
    SideEffect { session.recordingSpec = entry.spec }
    val store = remember { RecordingStore(File(context.filesDir, "recordings")) }
    val scope = rememberCoroutineScope()
    val status by ArduinoLink.status.collectAsState()
    val plugs by ArduinoLink.plugs.collectAsState()
    val connected = status == ArduinoLink.Status.CONNECTED
    val matchingPlug = connected && plugs.any { it == entry.spec }
    val history = session.samples
    var tab by rememberSaveable { mutableStateOf(0) }
    var menu by remember { mutableStateOf(false) }
    var timing by remember { mutableStateOf(false) }
    var saveDialog by remember { mutableStateOf(false) }
    var leaveDialog by remember { mutableStateOf(false) }
    var clearDialog by remember { mutableStateOf(false) }
    var expanded by rememberSaveable { mutableStateOf(false) }
    var exporting by remember { mutableStateOf(false) }
    var saveAndLeave by remember { mutableStateOf(false) }
    val darkSurface = MaterialTheme.colorScheme.surface.luminance() < 0.3f
    val colors = remember(entry.id, darkSurface) { stream.axisColorsHex.map {
        val channel = Color(android.graphics.Color.parseColor(it))
        if (darkSurface) lerp(channel, Color.White, 0.3f) else channel
    } }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val view = LocalView.current
    LaunchedEffect(recordingId) { if (recordingId != null) session.load(store, recordingId, entry.id) }
    DisposableEffect(lifecycle, session) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP && session.active) {
                session.pause()
                session.message = "Paused while the app was in the background."
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    DisposableEffect(session.active, view) {
        val previous = view.keepScreenOn
        if (session.active) view.keepScreenOn = true
        onDispose { view.keepScreenOn = previous }
    }
    fun leave() { session.pause(); if (session.dirty) leaveDialog = true else onBack() }
    BackHandler(enabled = !expanded) { if (!session.busy) leave() }
    fun export() {
        if (history.isEmpty() || session.active || exporting) return
        val snapshot = history.toList()
        exporting = true
        scope.launch {
            try {
                val intent = withContext(Dispatchers.IO) { CsvExporter.export(context, stream.title, stream.axisNames, snapshot) }
                context.startActivity(android.content.Intent.createChooser(intent, "Export ${stream.title}"))
            } catch (e: Exception) { session.message = "Export failed. ${e.localizedMessage.orEmpty()}" }
            finally { exporting = false }
        }
    }
    if (leaveDialog) AlertDialog(onDismissRequest = { leaveDialog = false }, title = { Text("Save this recording?") },
        text = { Text("${history.size} measurements have not been saved. Save them to reopen and inspect later.") },
        confirmButton = { TextButton(onClick = { leaveDialog = false; saveAndLeave = true; saveDialog = true }) { Text("Save recording") } },
        dismissButton = { Row { TextButton(onClick = { leaveDialog = false }) { Text("Cancel") }; TextButton(onClick = { leaveDialog = false; onBack() }) { Text("Discard", color = MaterialTheme.colorScheme.error) } } })
    if (clearDialog) AlertDialog(onDismissRequest = { clearDialog = false }, title = { Text("Clear measurements?") },
        text = { Text(if (session.dirty) "This run has unsaved measurements. Save or export them first if you need to keep them." else "This clears the current workspace. Your saved recordings will remain available.") },
        confirmButton = { TextButton(onClick = { session.clear(); clearDialog = false }) { Text("Clear", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { clearDialog = false }) { Text("Cancel") } })
    if (saveDialog) {
        var name by remember { mutableStateOf("${stream.title} · ${SimpleDateFormat("MMM d, HH:mm", Locale.getDefault()).format(Date())}") }
        AlertDialog(onDismissRequest = { saveDialog = false; saveAndLeave = false }, title = { Text("Save recording") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Stored on this device. Export CSV to share a copy.", style = MaterialTheme.typography.bodyMedium)
                OutlinedTextField(name, { name = it.take(80) }, label = { Text("Recording name") }, singleLine = true)
            } }, confirmButton = { TextButton(enabled = name.isNotBlank(), onClick = {
                saveDialog = false
                session.save(store, entry.id, name) { if (saveAndLeave) onBack(); saveAndLeave = false }
            }) { Text("Save") } }, dismissButton = { TextButton(onClick = { saveDialog = false; saveAndLeave = false }) { Text("Cancel") } })
    }
    if (timing) TimingDialog(session, onDismiss = { timing = false })
    if (expanded) Dialog(onDismissRequest = { expanded = false }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.surfaceContainerLowest) {
            Column(Modifier.safeDrawingPadding().padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stream.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                    IconButton(onClick = { expanded = false }) { Icon(Icons.Filled.Close, "Close expanded graph") }
                }
                Box(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                    GraphPanel(history, colors, stream.axisNames, stream.unit, session.active, expanded = true)
                }
            }
        }
    }
    Scaffold(containerColor = MaterialTheme.colorScheme.surface, topBar = {
        TopAppBar(title = { Text(stream.title) },
            subtitle = { Text(session.savedName ?: "Arduino · Wi-Fi", color = MaterialTheme.colorScheme.onPrimary, maxLines = 1) }, navigationIcon = { IconButton(onClick = { if (!session.busy) leave() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to experiments") } },
            actions = {
                IconButton(onClick = { menu = true }, enabled = !session.busy) { Icon(Icons.Filled.MoreVert, "Experiment actions") }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Export CSV") }, leadingIcon = { Icon(Icons.Filled.IosShare, null) }, enabled = history.isNotEmpty() && !session.active && !exporting,
                        onClick = { menu = false; export() })
                    DropdownMenuItem(text = { Text("Clear measurements") }, leadingIcon = { Icon(Icons.Filled.DeleteOutline, null) }, enabled = history.isNotEmpty() && !session.active,
                        onClick = { menu = false; clearDialog = true })
                }
            }, colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.primary, titleContentColor = MaterialTheme.colorScheme.onPrimary, navigationIconContentColor = MaterialTheme.colorScheme.onPrimary, actionIconContentColor = MaterialTheme.colorScheme.onPrimary))
    }, bottomBar = {
        Surface(color = MaterialTheme.colorScheme.surfaceContainerLow) {
            Column(Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Timer, null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
                    Text(if (session.duration == 0) "Manual · ${session.startDelay} s delay" else "${session.duration} s run · ${session.startDelay} s delay",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f).padding(start = 8.dp))
                    TextButton(onClick = { timing = true }, enabled = !session.active && !session.busy) { Text("Configure") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = { if (session.active) session.pause() else session.start(stream) },
                        enabled = !session.busy && (session.active || matchingPlug), modifier = Modifier.weight(1f).heightIn(min = 56.dp), shapes = ButtonDefaults.shapes(
                            shape = if (session.active) MaterialTheme.shapes.large else MaterialTheme.shapes.extraLarge,
                            pressedShape = MaterialTheme.shapes.medium)) {
                        Icon(if (session.active) Icons.Filled.Pause else Icons.Filled.PlayArrow, null, Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(if (session.countdown > 0) "Cancel countdown" else if (session.running) "Pause" else if (history.isEmpty()) "Record" else "Resume")
                    }
                    FilledTonalButton(onClick = { saveAndLeave = false; saveDialog = true }, enabled = history.isNotEmpty() && !session.active && !session.busy,
                        shape = MaterialTheme.shapes.large, modifier = Modifier.heightIn(min = 50.dp)) {
                        Icon(Icons.Filled.Save, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Save")
                    }
                }
            }
        }
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                StatusLed(if (session.running) StatusConnected else if (session.countdown > 0) StatusConnecting else StatusOff, session.running)
                Text(when { session.countdown > 0 -> "Starts in ${session.countdown} s"; session.running -> "Recording"; history.isNotEmpty() -> "Paused"; else -> "Ready" },
                    modifier = Modifier.weight(1f).padding(start = 8.dp), style = MaterialTheme.typography.labelLarge)
                Text("${history.size} samples  /  ${"%.1f".format(session.elapsed)} s", style = ReadoutSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            PrimaryTabRow(selectedTabIndex = tab, containerColor = MaterialTheme.colorScheme.surface) {
                listOf("Graph", "Readings", "Statistics").forEachIndexed { i, label -> Tab(selected = tab == i, onClick = { tab = i }, text = { Text(label) }) }
            }
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                if (session.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                session.message?.let { message ->
                    Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest, shape = RoundedCornerShape(8.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                        Row(Modifier.padding(start = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(message, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f).padding(vertical = 12.dp))
                            IconButton(onClick = { session.message = null }) { Icon(Icons.Filled.Close, "Dismiss message", Modifier.size(16.dp)) }
                        }
                    }
                }
                if (connected && !matchingPlug) Text("This board has no matching plug definition. You can review this recording; open the current channel from Experiments to record again.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                if (!connected && history.isEmpty()) Text("Connect a board from Experiments to start measuring.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (session.running && session.elapsed - session.lastReceived > 3f) Text("Waiting for sensor data. Check that your sketch is sending this channel.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                when (tab) {
                    0 -> {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Time series", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                            IconButton(onClick = { expanded = true }) { Icon(Icons.Filled.OpenInFull, "Expand graph", Modifier.size(20.dp)) }
                        }
                        GraphPanel(history, colors, stream.axisNames, stream.unit, session.active)
                    }
                    1 -> {
                        Text(if (session.running) "Latest sample" else "Last captured sample", style = MaterialTheme.typography.titleSmall)
                        ReadingTable(history.lastOrNull(), stream.axisNames, colors, stream.unit)
                        Text("Values are sent by your Arduino. Verify units and calibration in the sketch.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    2 -> StatisticsPanel(history, stream.axisNames, stream.unit)
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                var details by rememberSaveable { mutableStateOf(false) }
                TextButton(onClick = { details = !details }, contentPadding = PaddingValues(0.dp)) {
                    Icon(if (details) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore, null)
                    Text("Experiment notes")
                }
                if (details) {
                    Text(if (entry.id == "accelerometer") "Keep the sensor still to establish a baseline. Move it along one axis at a time. Gravity may be included, depending on your sketch." else if (entry.id == "gyroscope") "Rotate the sensor around one axis at a time. Compare clockwise and counterclockwise motion with the sensor held in the same orientation." else "Check the plug’s units, axis order, and calibration against the board configuration before interpreting measurements.", style = MaterialTheme.typography.bodyMedium)
                    Text("Values and units come from the plug definition. Legacy motion plugs also include vector magnitude. Tally does not convert your board's units. Pauses are excluded from elapsed time and shown as separate graph segments. Recording stops at 20,000 samples.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TimingDialog(session: ExperimentSession, onDismiss: () -> Unit) {
    var duration by remember { mutableStateOf(session.duration) }
    var delay by remember { mutableStateOf(session.startDelay) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Recording setup") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Duration", style = MaterialTheme.typography.titleSmall)
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf(0, 10, 30, 60).forEachIndexed { index, seconds ->
                    SegmentedButton(selected = duration == seconds, onClick = { duration = seconds },
                        shape = SegmentedButtonDefaults.itemShape(index, 4), icon = {}) {
                        Text(if (seconds == 0) "Manual" else "$seconds s")
                    }
                }
            }
            Text("Start delay", style = MaterialTheme.typography.titleSmall)
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf(0, 3, 5).forEachIndexed { index, seconds ->
                    SegmentedButton(selected = delay == seconds, onClick = { delay = seconds },
                        shape = SegmentedButtonDefaults.itemShape(index, 3), icon = {}) {
                        Text(if (seconds == 0) "None" else "$seconds s")
                    }
                }
            }
            Text("Each resumed run uses these settings. The screen stays awake while recording.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }, confirmButton = { TextButton(onClick = { session.duration = duration; session.startDelay = delay; onDismiss() }) { Text("Apply") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
private fun GraphPanel(history: List<SensorSample>, colors: List<Color>, names: List<String>, unit: String, active: Boolean, expanded: Boolean = false) {
    var axes by remember(names) { mutableStateOf(names.indices.take(3).toSet()) }
    var window by rememberSaveable { mutableStateOf(10f) }
    var position by remember { mutableStateOf<Float?>(null) }
    var selected by remember { mutableStateOf<SensorSample?>(null) }
    LaunchedEffect(active, history.size) { if (active || history.isEmpty()) { position = null; selected = null } }
    val last = history.lastOrNull()?.t ?: 0f
    val span = if (window == 0f) last.coerceAtLeast(1f) else window
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(unit, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Surface(shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), color = MaterialTheme.colorScheme.surfaceContainerLowest) {
            LiveChart(history, colors, span, axes = axes, endTime = position, selected = selected,
                onSelect = { selected = it }, chartHeight = if (expanded) 350.dp else 270.dp, interactive = !active)
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            names.forEachIndexed { axis, name -> FilterChip(selected = axis in axes,
                onClick = { axes = if (axis in axes && axes.size > 1) axes - axis else axes + axis },
                label = { Text(if (name == "magnitude") "Magnitude" else name.uppercase()) },
                leadingIcon = { Box(Modifier.size(8.dp)) { StatusLed(colors[axis], false, size = 8.dp) } }) }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Window", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(end = 10.dp))
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(5f, 10f, 30f, 0f).forEach { seconds -> FilterChip(selected = window == seconds,
                    onClick = { window = seconds; position = null; selected = null }, label = { Text(if (seconds == 0f) "All" else "${seconds.toInt()} s") }) }
            }
        }
        if (!active && last > span) {
            Text("Review earlier measurements", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Slider(value = (position ?: last).coerceIn(span, last), onValueChange = { position = it; selected = null }, valueRange = span..last)
        }
        if (selected != null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Sample at ${"%.3f".format(selected!!.t)} s", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                TextButton(onClick = { selected = null }) { Text("Dismiss") }
            }
            ReadingTable(selected, names, colors, unit, axes)
        } else Text(if (active) "Following incoming data. Pause to inspect individual samples." else "Tap the graph to inspect a sample. Toggle traces to compare axes.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ReadingTable(sample: SensorSample?, names: List<String>, colors: List<Color>, unit: String, axes: Set<Int> = names.indices.toSet()) {
    Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest, shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Text(unit, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 14.dp))
            axes.sorted().forEachIndexed { index, axis ->
                if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(Modifier.fillMaxWidth().padding(vertical = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                    StatusLed(colors[axis], false, size = 8.dp)
                    Text(names[axis].replaceFirstChar { it.uppercase() }, Modifier.weight(1f).padding(start = 12.dp), style = MaterialTheme.typography.bodyMedium)
                    Text(sample?.values?.getOrNull(axis)?.let { measurementText(it.toDouble()) } ?: "—", style = ReadoutLarge)
                }
            }
        }
    }
}

@Composable
private fun StatisticsPanel(history: List<SensorSample>, names: List<String>, unit: String) {
    var axis by rememberSaveable { mutableStateOf(0) }
    Text("Summary", style = MaterialTheme.typography.titleSmall)
    Text("All ${history.size} captured samples · $unit", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        names.forEachIndexed { i, name -> FilterChip(selected = axis == i, onClick = { axis = i }, label = { Text(name.replaceFirstChar { it.uppercase() }) }) }
    }
    val stats = axisStatistics(history, axis)
    Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest, shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(horizontal = 16.dp)) {
            listOf("Minimum" to stats?.min, "Maximum" to stats?.max, "Mean" to stats?.mean, "RMS" to stats?.rms, "Standard deviation" to stats?.deviation).forEachIndexed { index, (label, value) ->
                if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(Modifier.fillMaxWidth().padding(vertical = 16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(label, style = MaterialTheme.typography.bodyMedium)
                    Text(value?.let(::measurementText) ?: "—", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Medium, color = MaterialTheme.colorScheme.onSurface)
                }
            }
        }
    }
    Text("RMS describes signal magnitude. Standard deviation measures spread around the mean (population definition).", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}
