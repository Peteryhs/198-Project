package com.jeevan.tally.ui

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.IosShare
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.jeevan.tally.exercise.SavedSet
import com.jeevan.tally.exercise.SetReport.percent
import com.jeevan.tally.exercise.SetStore
import com.jeevan.tally.export.SetExporter
import com.jeevan.tally.ui.theme.ReadoutSmall
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import androidx.compose.ui.platform.LocalConfiguration

/** Loads saved sets for the Exercise tab. Reloads whenever [refreshKey] changes. */
@Composable
fun rememberSavedSets(context: Context, refreshKey: Any?): State<List<SavedSet>?> =
    produceState<List<SavedSet>?>(null, refreshKey) {
        value = runCatching { withContext(Dispatchers.IO) { SetStore(File(context.filesDir, "sets")).list() } }.getOrDefault(emptyList())
    }

/** The Exercise tab body, emitted into HomeScreen's LazyColumn. */
fun LazyListScope.exerciseSection(context: Context, sets: List<SavedSet>?, wide: Boolean, onStartSet: () -> Unit, onOpenSet: (String) -> Unit, instructorView: Boolean = false) {
    item {
        val start: @Composable (Modifier) -> Unit = { modifier ->
            Surface(modifier, color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.extraLarge) {
                Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Icon(Icons.Filled.FitnessCenter, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(32.dp))
                    Text("Ready when you are", style = MaterialTheme.typography.titleLargeEmphasized)
                    Text("Choose your exercise. Tally will guide you through setup.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                    TallyAction(onClick = onStartSet, shapes = ButtonDefaults.shapes(), modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
                        Text("Begin exercise")
                    }
                }
            }
        }
        if (wide && instructorView) Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            ArduinoConnectionBar(context, Modifier.weight(1f)); start(Modifier.weight(1f))
        } else Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            start(Modifier.fillMaxWidth())
            if (instructorView) ArduinoConnectionBar(context)
        }
    }
    item { Text("Saved sessions", style = MaterialTheme.typography.titleMediumEmphasized) }
    when {
        sets == null -> item { LoadingRows("Loading saved sessions") }
        sets.isEmpty() -> item {
            Text("Finished sets you save appear here.", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        else -> itemsIndexed(sets, key = { _, set -> set.id }) { index, set ->
            SavedSetRow(set, Modifier.animateItem(
                fadeInSpec = tween(180, delayMillis = index.coerceAtMost(4) * 30),
                placementSpec = spring(stiffness = Spring.StiffnessLow),
            )) { onOpenSet(set.id) }
        }
    }
}

@Composable
private fun SavedSetRow(set: SavedSet, modifier: Modifier, onClick: () -> Unit) {
    val s = set.summary
    val scheme = MaterialTheme.colorScheme
    val press = remember { MutableInteractionSource() }
    ListItem(modifier = modifier.pressScale(press).clickable(
        interactionSource = press, indication = LocalIndication.current, onClick = onClick,
    ),
        content = { Text(set.name) },
        supportingContent = {
            Column {
                Text("${s.counted}/${s.prescription.targetCount} reps · efficiency ${percent(s.efficiency)} · samples ${percent(s.coverage)}", style = ReadoutSmall)
                Text(SimpleDateFormat("MMM d, yyyy · HH:mm", LocalConfiguration.current.locales[0]).format(Date(s.startedAtMillis)))
            }
        },
        leadingContent = { Icon(Icons.Filled.FitnessCenter, null, tint = scheme.primary) },
        trailingContent = { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null) },
        colors = ListItemDefaults.colors(containerColor = scheme.surface))
    HorizontalDivider(color = scheme.outlineVariant)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetDetailScreen(id: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val scheme = MaterialTheme.colorScheme
    val store = remember { SetStore(File(context.filesDir, "sets")) }
    val scope = rememberCoroutineScope()
    var deleteDialog by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val set by produceState<SavedSet?>(null, id) {
        value = runCatching { withContext(Dispatchers.IO) { store.load(id) } }.getOrElse { error = "This set could not be opened."; null }
    }
    BackHandler(onBack = onBack)
    if (deleteDialog) AlertDialog(onDismissRequest = { deleteDialog = false }, title = { Text("Delete this set?") },
        text = { Text("Its summary and repetition log are removed from this device. Shared copies are not affected.") },
        confirmButton = { TextButton(onClick = {
            deleteDialog = false
            scope.launch { withContext(Dispatchers.IO) { store.delete(id) }; onBack() }
        }) { Text("Delete", color = scheme.error) } },
        dismissButton = { TextButton(onClick = { deleteDialog = false }) { Text("Cancel") } })
    Scaffold(containerColor = scheme.surface, topBar = {
        TopAppBar(title = { Text(set?.name ?: "Set") },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            actions = {
                IconButton(enabled = set != null, onClick = {
                    val current = set ?: return@IconButton
                    runCatching { context.startActivity(android.content.Intent.createChooser(SetExporter.share(context, current), "Share set report")) }
                        .onFailure { error = "Could not share. ${it.localizedMessage.orEmpty()}" }
                }) { Icon(Icons.Filled.IosShare, "Share report") }
                IconButton(enabled = set != null, onClick = { deleteDialog = true }) { Icon(Icons.Filled.DeleteOutline, "Delete set") }
            },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = scheme.surfaceContainer, titleContentColor = scheme.onSurface,
                navigationIconContentColor = scheme.onSurface, actionIconContentColor = scheme.onSurface))
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp), horizontalAlignment = Alignment.Start) {
            error?.let { Text(it, color = scheme.error) }
            val current = set
            if (current == null && error == null) LoadingRows("Loading session")
            if (current != null) {
                Text(SimpleDateFormat("EEEE, MMM d, yyyy · HH:mm", LocalConfiguration.current.locales[0]).format(Date(current.summary.startedAtMillis)),
                    style = MaterialTheme.typography.bodyMedium, color = scheme.onSurfaceVariant)
                SetSummaryView(current.summary, current.reps)
            }
        }
    }
}
