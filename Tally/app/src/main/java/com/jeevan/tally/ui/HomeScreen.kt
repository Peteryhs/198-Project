package com.jeevan.tally.ui

import android.content.Context
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Science
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jeevan.tally.ExperimentRegistry
import com.jeevan.tally.ExperimentEntry
import com.jeevan.tally.sensors.ArduinoLink
import com.jeevan.tally.recording.*
import com.jeevan.tally.ui.theme.ReadoutSmall
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import androidx.compose.ui.platform.LocalLocale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    context: Context,
    onSelect: (String) -> Unit,
    onOpenRecording: (String, String) -> Unit,
    onStartSet: () -> Unit = {},
    onOpenSet: (String) -> Unit = {},
) {
    // 2 = Exercise, 0 = Experiments, 1 = Recordings. Exercise is the project's main job, so it opens first.
    var section by rememberSaveable { mutableStateOf(2) }
    var recordings by remember { mutableStateOf<List<RecordingInfo>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var loadError by remember { mutableStateOf(false) }
    var retry by remember { mutableStateOf(0) }
    var showHelp by remember { mutableStateOf(false) }
    val scheme = MaterialTheme.colorScheme
    val experimentsScroll = rememberLazyListState()
    val recordingsScroll = rememberLazyListState()
    val exerciseScroll = rememberLazyListState()
    val sets by rememberSavedSets(context, section)
    LaunchedEffect(retry) {
        loading = true; loadError = false
        try { recordings = withContext(Dispatchers.IO) { RecordingStore(File(context.filesDir, "recordings")).list() } }
        catch (_: Exception) { loadError = true }
        finally { loading = false }
    }
    if (showHelp) AlertDialog(onDismissRequest = { showHelp = false }, title = { Text("Connect an Arduino") },
        text = { Text("Join the same Wi-Fi network as your board. Enter its IP address and port, then connect.\n\nExercise counts repetitions and logs each set. Experiments shows raw sensor channels. The board must run a compatible Tally sketch.") },
        confirmButton = { TextButton(onClick = { showHelp = false }) { Text("Done") } })
    BoxWithConstraints {
        val wide = maxWidth >= 600.dp
        Scaffold(containerColor = scheme.surface, bottomBar = {
            if (!wide) NavigationBar(containerColor = scheme.surfaceContainer, tonalElevation = 0.dp) {
                NavigationBarItem(selected = section == 2, onClick = { section = 2 }, icon = { Icon(Icons.Filled.FitnessCenter, null) }, label = { Text("Exercise") })
                NavigationBarItem(selected = section == 0, onClick = { section = 0 }, icon = { Icon(Icons.Filled.Science, null) }, label = { Text("Experiments") })
                NavigationBarItem(selected = section == 1, onClick = { section = 1 }, icon = { Icon(Icons.Filled.FolderOpen, null) }, label = { Text("Recordings") })
            }
        }, topBar = {
            TopAppBar(title = {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    TallyMark(color = scheme.onPrimary, size = 20.dp)
                    Text("Tally", style = MaterialTheme.typography.titleLarge)
                }
            }, actions = { TextButton(onClick = { showHelp = true }, colors = ButtonDefaults.textButtonColors(contentColor = scheme.onPrimary)) { Text("Setup help") } }, colors = TopAppBarDefaults.topAppBarColors(containerColor = scheme.primary, titleContentColor = scheme.onPrimary, navigationIconContentColor = scheme.onPrimary, actionIconContentColor = scheme.onPrimary))
        }) { padding ->
            Row(Modifier.fillMaxSize().padding(padding)) {
                if (wide) NavigationRail(containerColor = scheme.surfaceContainer, modifier = Modifier.fillMaxHeight()) {
                    NavigationRailItem(selected = section == 2, onClick = { section = 2 }, icon = { Icon(Icons.Filled.FitnessCenter, null) }, label = { Text("Exercise") })
                    NavigationRailItem(selected = section == 0, onClick = { section = 0 }, icon = { Icon(Icons.Filled.Science, null) }, label = { Text("Experiments") })
                    NavigationRailItem(selected = section == 1, onClick = { section = 1 }, icon = { Icon(Icons.Filled.FolderOpen, null) }, label = { Text("Recordings") })
                }
                LazyColumn(Modifier.weight(1f), state = when (section) { 0 -> experimentsScroll; 1 -> recordingsScroll; else -> exerciseScroll }, contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
                    item {
                        Text(when (section) { 0 -> "Experiments"; 1 -> "Recordings"; else -> "Exercise" }, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { heading() })
                        Text(when (section) { 0 -> "Raw Arduino channels"; 1 -> "Saved on this device"; else -> "Count repetitions and log every set" },
                            style = MaterialTheme.typography.bodyMedium, color = scheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
                    }
                    if (section == 2) {
                        exerciseSection(context, sets, wide, onStartSet, onOpenSet)
                    } else if (section == 0) {
                        if (wide) item {
                            Row(horizontalArrangement = Arrangement.spacedBy(24.dp), verticalAlignment = Alignment.Top) {
                                ArduinoConnectionBar(context, Modifier.weight(1f))
                                Column(Modifier.weight(1.2f)) { SensorList(context, onSelect) }
                            }
                        } else {
                            item { ArduinoConnectionBar(context) }
                            item { SensorList(context, onSelect) }
                        }
                    } else {
                        if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
                        if (loadError) item {
                            Column {
                                Text("Recordings could not be loaded.", color = scheme.error)
                                TextButton(onClick = { retry++ }) { Text("Try again") }
                            }
                        }
                        if (!loading && recordings.isEmpty() && !loadError) item {
                            Surface(color = scheme.surfaceContainerLow, shape = MaterialTheme.shapes.large) {
                                Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Icon(Icons.Filled.FolderOpen, null, tint = scheme.primary, modifier = Modifier.size(40.dp))
                                    Text("No saved recordings", style = MaterialTheme.typography.titleLarge)
                                    Text("Record a run, then tap Save to keep it here.", style = MaterialTheme.typography.bodyMedium, color = scheme.onSurfaceVariant)
                                    FilledTonalButton(onClick = { section = 0 }) { Text("Open experiments") }
                                }
                            }
                        }
                        items(recordings, key = { it.id }) { recording ->
                            ListItem(modifier = Modifier.animateItem().clickable { onOpenRecording(recording.experimentId, recording.id) },
                                content = { Text(recording.name) },
                                supportingContent = { Column {
                                    Text("${recording.count} samples · ${"%.1f".format(recording.elapsed)} s", style = ReadoutSmall)
                                    Text(SimpleDateFormat("MMM d, yyyy · HH:mm", LocalLocale.current.platformLocale).format(Date(recording.savedAt)))
                                } }, leadingContent = { Icon(Icons.Filled.FolderOpen, null) },
                                trailingContent = { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null) },
                                colors = ListItemDefaults.colors(containerColor = scheme.surface))
                            HorizontalDivider(color = scheme.outlineVariant)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SensorList(context: Context, onSelect: (String) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val plugs by ArduinoLink.plugs.collectAsState()
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Sensors", style = MaterialTheme.typography.titleMediumEmphasized, modifier = Modifier.semantics { heading() })
            Text("${plugs.size} channels", style = MaterialTheme.typography.labelMedium, color = scheme.onSurfaceVariant)
        }
        Surface(color = scheme.surfaceContainerLow, shape = MaterialTheme.shapes.large) {
            Column {
                plugs.map(::ExperimentEntry).forEachIndexed { index, entry ->
                    val stream = remember(entry.spec) { entry.factory(context.applicationContext) }
                    if (index > 0) HorizontalDivider(Modifier.padding(horizontal = 20.dp), color = scheme.outlineVariant)
                    ListItem(modifier = Modifier.clickable { onSelect(entry.id) }.padding(vertical = 4.dp),
                        content = { Text(stream.title, style = MaterialTheme.typography.titleMedium) },
                        supportingContent = { Text("${entry.spec.axisCount} ${if (entry.spec.axisCount == 1) "axis" else "axes"} · ${entry.spec.unit}") },
                        leadingContent = {
                            Icon(entry.icon, null, tint = entry.accent, modifier = Modifier.size(24.dp))
                        }, trailingContent = { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null) },
                        colors = ListItemDefaults.colors(containerColor = scheme.surfaceContainerLow))
                }
            }
        }
    }
}
