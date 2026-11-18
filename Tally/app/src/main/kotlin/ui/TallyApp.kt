package com.tally.app.ui

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.activity.BackEventCompat
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.navigation.NavController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument

import com.tally.app.backend.TallyBackendFactory
import com.tally.app.contract.LinkState
import com.tally.app.contract.SessionState
import com.tally.app.contract.SetId
import com.tally.app.contract.SetResult
import com.tally.app.contract.Side
import com.tally.app.contract.TallyBackend
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private fun SetId.route() = raw.toLong()
private fun idArg(name: String) = listOf(navArgument(name) { type = NavType.LongType })
private fun NavController.home() = popBackStack("home", inclusive = false)
private fun NavController.replaceWith(route: String) = navigate(route) { popUpTo("home") }

/**
 * One NavHost for the app. Backend calls run in [scope], which outlives the activity, so a rotation or
 * leaving a screen never cancels a stop, start or scoring call halfway through.
 */
@Composable
fun TallyApp(
    backend: TallyBackend,
    scope: CoroutineScope,
    darkMode: Boolean,
    onDarkModeChange: (Boolean) -> Unit,
    wifiPassphrase: String?,
    onWifiPassphraseChange: (String) -> Unit,
    configurePassphrase: suspend (String) -> Boolean,
    geminiKey: String,
    onGeminiKeyChange: (String) -> Unit,
    geminiStatus: String?,
) {
    val nav = rememberNavController()
    val link by backend.link.collectAsState()
    val session by backend.session.collectAsState()
    val calibration by backend.calibration.collectAsState()
    // (set id, phone time first seen recording). Kept here so leaving and returning to Record keeps the clock.
    var recordingStart by rememberSaveable { mutableStateOf<Pair<Long, Long>?>(null) }
    // Keep progress with this backend across navigation; never restore it onto a new backend.
    var captured by remember(backend) { mutableStateOf(0) }
    var capturing by remember(backend) { mutableStateOf(false) }
    var calibrationMessage by remember(backend) { mutableStateOf<String?>(null) }

    NavHost(
        nav,
        startDestination = "home",
        enterTransition = { slideInHorizontally { it } },
        exitTransition = { slideOutHorizontally { -it } },
        popEnterTransition = { slideInHorizontally { -it } },
        popExitTransition = { slideOutHorizontally { it } },
        predictivePopEnterTransition = { swipeEdge ->
            slideInHorizontally { width -> if (swipeEdge == BackEventCompat.EDGE_RIGHT) width else -width }
        },
        predictivePopExitTransition = { swipeEdge ->
            slideOutHorizontally { width -> if (swipeEdge == BackEventCompat.EDGE_RIGHT) -width else width }
        },
    ) {
        composable("home") {
            val sets by remember(backend) { backend.history() }.collectAsState(emptyList())
            HomeScreen(
                sets, setInProgress = session is SessionState.Recording || session is SessionState.Scoring,
                onStart = {
                    when (val s = session) {
                        is SessionState.Scoring -> nav.navigate("scoring/${s.id.route()}")
                        is SessionState.Recording -> nav.navigate("record")
                        else -> nav.navigate(if (link is LinkState.Connected) "record" else "connect")
                    }
                },
                onOpen = { nav.navigate("result/${it.route()}") },
                onSettings = { nav.navigate("settings") },
            )
        }
        composable("settings") {
            var showDiagnostics by rememberSaveable { mutableStateOf(false) }
            SettingsScreen(
                darkMode = darkMode,
                onDarkModeChange = onDarkModeChange,
                geminiKey = geminiKey,
                onGeminiKeyChange = onGeminiKeyChange,
                geminiStatus = geminiStatus,
                onCalibrate = { nav.navigate("calibration") },
                onDiagnostics = { showDiagnostics = true },
                onClose = { nav.popBackStack() },
            )
            if (showDiagnostics) DiagnosticsDialog(onDismiss = { showDiagnostics = false })
        }
        composable("connect") {
            var message by remember { mutableStateOf<String?>(null) }
            var connecting by remember { mutableStateOf(false) }
            var connectionFailed by rememberSaveable { mutableStateOf(false) }
            val fromCalibration = remember { nav.previousBackStackEntry?.destination?.route == "calibration" }
            val connect = rememberConnect(
                backend, scope, wifiPassphrase, configurePassphrase,
                setConnecting = { connecting = it },
                setFailed = { connectionFailed = it },
                report = { message = it },
            )
            ConnectScreen(
                link, message,
                onConnect = { if (!connecting) connect() },
                onContinue = { if (fromCalibration) nav.popBackStack() else nav.replaceWith("record") },
                continueLabel = if (fromCalibration) "Back to calibration" else "Continue",
                passphrase = wifiPassphrase.orEmpty(),
                onPassphraseChange = onWifiPassphraseChange,
                connectEnabled = wifiPassphrase != null && !connecting,
                connectionFailed = connectionFailed && !connecting,
            )
        }
        composable("record") {
            RecordRoute(backend, scope, nav, link, session, recordingStart) { recordingStart = it }
        }
        composable("scoring/{id}", idArg("id")) { entry ->
            val id = SetId(entry.arguments!!.getLong("id").toUInt())
            ScoringRoute(backend, scope, nav, id, session)
        }
        composable("result/{id}", idArg("id")) { entry ->
            val id = SetId(entry.arguments!!.getLong("id").toUInt())
            ResultRoute(backend, scope, nav, id, session)
        }
        composable("calibration") {
            CalibrationScreen(
                calibration, link, captured, capturing, calibrationMessage,
                onCapture = { hold ->
                    if (capturing) return@CalibrationScreen
                    capturing = true
                    calibrationMessage = null
                    scope.launch {
                        backend.captureBodyHold(hold)
                            .onSuccess { captured += 1 }
                            .onFailure { calibrationMessage = it.message ?: "Capture failed. Try the hold again." }
                        capturing = false
                    }
                },
                onSave = {
                    if (capturing) return@CalibrationScreen
                    capturing = true
                    calibrationMessage = null
                    scope.launch {
                        backend.saveBodyCalibration()
                            .onSuccess { captured = 0; calibrationMessage = "Calibration saved." }
                            .onFailure { calibrationMessage = it.message ?: "Could not save calibration. Try again." }
                        capturing = false
                    }
                },
                onRepeat = { captured = 0; calibrationMessage = null },
                onConnect = { nav.navigate("connect") },
            )
        }
    }
}

/**
 * The app's own log, newest last, plus any crash recorded in a previous run. Copy puts both on the
 * clipboard so the owner can paste them into chat without adb or a computer.
 */
@Composable
private fun DiagnosticsDialog(onDismiss: () -> Unit) {
    val context = LocalContext.current
    val text = remember {
        val crash = TallyBackendFactory.logCrashSnapshot()
        buildString {
            if (crash != null) append("=== last crash ===\n").append(crash).append('\n')
            append("=== this session ===\n").append(TallyBackendFactory.logSnapshot())
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Diagnostics", style = MaterialTheme.typography.headlineSmall) },
        text = {
            Text(
                text,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier
                    .heightIn(max = 420.dp)
                    .verticalScroll(rememberScrollState()),
            )
        },
        confirmButton = {
            TextButton({
                context.getSystemService(ClipboardManager::class.java)
                    .setPrimaryClip(ClipData.newPlainText("Tally diagnostics", text))
            }) { Text("Copy", style = MaterialTheme.typography.labelLarge) }
        },
        dismissButton = {
            TextButton(onDismiss) { Text("Close", style = MaterialTheme.typography.labelLarge) }
        },
        containerColor = MaterialTheme.colorScheme.surfaceContainer,
        titleContentColor = MaterialTheme.colorScheme.onSurface,
        textContentColor = MaterialTheme.colorScheme.onSurface,
    )
}

/** Requests the Wi-Fi permission the backend needs (Android 13+: nearby devices; older: location), then connects. */
@Composable
private fun rememberConnect(
    backend: TallyBackend,
    scope: CoroutineScope,
    passphrase: String?,
    configurePassphrase: suspend (String) -> Boolean,
    setConnecting: (Boolean) -> Unit,
    setFailed: (Boolean) -> Unit,
    report: (String?) -> Unit,
): () -> Unit {
    val context = LocalContext.current
    val permission = if (Build.VERSION.SDK_INT >= 33) Manifest.permission.NEARBY_WIFI_DEVICES
        else Manifest.permission.ACCESS_FINE_LOCATION
    val connect = {
        if (passphrase != null) {
            setConnecting(true)
            setFailed(false)
            report(null)
            scope.launch {
                try {
                    if (!configurePassphrase(passphrase)) {
                        report(if (passphrase.isBlank()) "Could not clear the saved Wi-Fi password."
                            else "Could not save the Wi-Fi password on this phone.")
                    }
                    backend.connect().getOrThrow()
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    setFailed(true)
                    if (error is IllegalArgumentException) report("Check the Wi-Fi password and try again.")
                } finally {
                    setConnecting(false)
                }
            }
        }
        Unit
    }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) connect() else {
            setFailed(true)
            report("Allow Wi-Fi access for Tally in Android settings.")
        }
    }
    return {
        // A blank password is valid: it means the device's AP is open.
        if (ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED) connect()
        else launcher.launch(permission)
    }
}

@Composable
private fun RecordRoute(
    backend: TallyBackend, scope: CoroutineScope, nav: NavController, link: LinkState, session: SessionState,
    recordingStart: Pair<Long, Long>?, onRecordingStart: (Pair<Long, Long>) -> Unit,
) {
    var ownId by rememberSaveable { mutableStateOf<Long?>(null) }
    var side by rememberSaveable { mutableStateOf(Side.L) }
    var intended by rememberSaveable { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var confirmAbort by remember { mutableStateOf(false) }
    var confirmLeave by remember { mutableStateOf(false) }

    LaunchedEffect(session) {
        if (session is SessionState.Recording && ownId == null) ownId = session.id.route()
        when {
            session is SessionState.Scoring && session.id.route() == ownId -> nav.replaceWith("scoring/$ownId")
            session is SessionState.Done && session.result.id.route() == ownId -> nav.replaceWith("result/$ownId")
        }
    }

    val failed = (session as? SessionState.Failed)?.takeIf { it.id.route() == ownId }
    when {
        session is SessionState.Recording -> {
            val fallback = remember(session.id) { System.currentTimeMillis() }
            val startedAt = recordingStart?.takeIf { it.first == session.id.route() }?.second ?: fallback
            SideEffect { if (recordingStart?.first != session.id.route()) onRecordingStart(session.id.route() to fallback) }
            var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
            LaunchedEffect(Unit) { while (true) { now = System.currentTimeMillis(); delay(250) } }
            BackHandler { confirmLeave = true }
            RecordingScreen(session, now - startedAt, link, backend.live, message,
                onStop = { scope.launch { backend.stopSet().onFailure { message = "Couldn’t stop the set. Try again." } } },
                onAbort = { confirmAbort = true })
        }
        failed != null -> SetFailedScreen(failed,
            onScorePartial = { scope.launch { backend.scorePartial(failed.id).onFailure { message = "Couldn’t score the partial set." } } },
            onRescore = null, onHome = { nav.home() }, message = message)
        session is SessionState.Scoring && session.id.route() == ownId -> ScoringScreen()
        else -> RecordSetupScreen(side, link, message, busy, onSide = { side = it },
            onStart = {
                busy = true; message = null
                scope.launch {
                    backend.startSet(side, intended).onSuccess { ownId = it.route() }.onFailure {
                        message = if (backend.calibration.value == null) "Open Settings and calibrate the sensors before starting."
                            else "Couldn’t start the set. Check the connection and try again."
                    }
                    busy = false
                }
            },
            onConnect = { nav.navigate("connect") }, intended = intended, onIntended = { intended = it })
    }

    if (confirmAbort) InkDialog(
        title = "Abort this set?", text = "Recording stops and the set is not scored.",
        confirm = "Abort set", dismiss = "Keep recording",
        onConfirm = { confirmAbort = false; scope.launch { backend.abortSet().onFailure { message = "Couldn’t abort the set. Try again." } } },
        onDismiss = { confirmAbort = false })
    if (confirmLeave) InkDialog(
        title = "Leave this screen?", text = "Recording continues. You can come back from the home screen.",
        confirm = "Leave", dismiss = "Stay",
        onConfirm = { confirmLeave = false; nav.home() }, onDismiss = { confirmLeave = false })
}

@Composable
private fun ScoringRoute(backend: TallyBackend, scope: CoroutineScope, nav: NavController, id: SetId, session: SessionState) {
    var message by remember(id) { mutableStateOf<String?>(null) }
    val failed = (session as? SessionState.Failed)?.takeIf { it.id == id }
    when {
        failed != null -> SetFailedScreen(failed,
            onScorePartial = { scope.launch { backend.scorePartial(id).onFailure { message = "Couldn’t score the partial set." } } },
            onRescore = { scope.launch { backend.rescore(id).onFailure { message = "Couldn’t score this set. Try again." } } },
            onHome = { nav.home() }, message = message)
        (session as? SessionState.Scoring)?.id == id -> ScoringScreen()
        else -> LaunchedEffect(id) { nav.replaceWith("result/${id.route()}") }
    }
}

@Composable
private fun ResultRoute(backend: TallyBackend, scope: CoroutineScope, nav: NavController, id: SetId, session: SessionState) {
    val context = LocalContext.current
    var result by remember(backend, id) { mutableStateOf<SetResult?>(null) }
    var loading by remember(backend, id) { mutableStateOf(true) }
    var busy by remember(backend, id) { mutableStateOf(false) }
    var message by remember(backend, id) { mutableStateOf<String?>(null) }
    LaunchedEffect(backend, id, session) {
        runCatching { (session as? SessionState.Done)?.result?.takeIf { it.id == id } ?: backend.result(id) }
            .onSuccess { result = it }
            .onFailure { message = "Couldn’t load this set." }
        loading = false
    }
    val scoring = busy || (session as? SessionState.Scoring)?.id == id
    val partial = (session as? SessionState.Failed)?.takeIf { it.id == id && it.partialScorable }
    val score: () -> Unit = {
        if (!busy && (session as? SessionState.Scoring)?.id != id) {
            busy = true
            message = null
            scope.launch {
                try {
                    (if (partial != null) backend.scorePartial(id) else backend.rescore(id))
                        .onSuccess { result = it }
                        .onFailure { message = "Couldn’t score this set. Try again." }
                } finally { busy = false }
            }
        }
    }
    if (scoring) {
        ScoringScreen()
        return
    }
    val shown = result
    if (shown != null) ResultScreen(shown, message, onClose = { nav.home() },
        onRescore = score) {
        scope.launch {
            runCatching {
                val uri = backend.exportCsv(id).getOrThrow()
                context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND)
                    .setType("text/csv").putExtra(Intent.EXTRA_STREAM, Uri.parse(uri))
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), "Export set ${id.raw}"))
            }.onFailure { message = "Couldn’t export the CSV. Try again." }
        }
    } else {
        NoResultScreen("Set ${id.raw}", loading, message,
            if (partial != null) "Score the partial set" else "Score this set", score)
    }
}

@Composable
private fun InkDialog(title: String, text: String, confirm: String, dismiss: String, onConfirm: () -> Unit, onDismiss: () -> Unit) =
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title, style = MaterialTheme.typography.headlineSmall) },
        text = { Text(text, style = MaterialTheme.typography.bodyLarge) },
        confirmButton = { TextButton(onConfirm) { Text(confirm, style = MaterialTheme.typography.labelLarge) } },
        dismissButton = { TextButton(onDismiss) { Text(dismiss, style = MaterialTheme.typography.labelLarge) } },
        containerColor = MaterialTheme.colorScheme.surfaceContainer,
        titleContentColor = MaterialTheme.colorScheme.onSurface,
        textContentColor = MaterialTheme.colorScheme.onSurface,
    )
