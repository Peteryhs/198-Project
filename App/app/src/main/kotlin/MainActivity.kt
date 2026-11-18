package com.tally.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import com.tally.app.backend.TallyBackendFactory
import com.tally.app.contract.TallyBackend
import com.tally.app.ui.TallyApp
import com.tally.app.ui.TallyTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as TallyApplication
        setContent {
            val darkMode = app.darkMode
            TallyTheme(darkMode = darkMode) {
                val background = MaterialTheme.colorScheme.background.toArgb()
                LaunchedEffect(darkMode, background) {
                    val bars = if (darkMode) SystemBarStyle.dark(background)
                        else SystemBarStyle.light(background, background)
                    enableEdgeToEdge(statusBarStyle = bars, navigationBarStyle = bars)
                }
                val backend = produceState<TallyBackend?>(null) {
                    value = withContext(Dispatchers.IO) { app.backend }
                }.value
                if (backend == null) {
                    Surface(Modifier.fillMaxSize()) {
                        Box(contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                    }
                    return@TallyTheme
                }
                val geminiStatus by TallyBackendFactory.geminiStatus().collectAsState()
                TallyApp(
                    backend = backend,
                    scope = app.scope,
                    darkMode = darkMode,
                    onDarkModeChange = app::applyDarkMode,
                    wifiPassphrase = app.wifiPassphrase,
                    onWifiPassphraseChange = app::editWifiPassphrase,
                    configurePassphrase = app::configureAndRememberPassphrase,
                    geminiKey = app.geminiKey,
                    onGeminiKeyChange = app::applyGeminiKey,
                    geminiStatus = geminiStatus,
                )
            }
        }
    }
}
