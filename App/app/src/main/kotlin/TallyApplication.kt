package com.tally.app

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.tally.app.backend.TallyBackendFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class TallyApplication : Application() {
    val backend by lazy { TallyBackendFactory.create(this) }
    private val settings by lazy { getSharedPreferences("settings", MODE_PRIVATE) }
    private val scoringSettings by lazy { getSharedPreferences("debug", MODE_PRIVATE) }
    private val wifiPassphraseStore by lazy { WifiPassphraseStore(this) }

    var darkMode by mutableStateOf(false)
        private set
    var geminiKey by mutableStateOf("")
        private set
    var wifiPassphrase by mutableStateOf<String?>(null)
        private set

    /** UI-initiated backend calls run here so they survive activity recreation. */
    val scope = MainScope()

    override fun onCreate() {
        super.onCreate()
        TallyBackendFactory.installLog(this)
        // Record the crash before the process dies: without this a failure on a phone with no adb leaves nothing.
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            TallyBackendFactory.logCrash(thread, error)
            previous?.uncaughtException(thread, error)
        }
        darkMode = settings.getBoolean("dark_mode", false)
        geminiKey = scoringSettings.getString("gemini_api_key", "").orEmpty()
        scope.launch {
            val saved = withContext(Dispatchers.IO) { wifiPassphraseStore.load() }
            if (wifiPassphrase == null) wifiPassphrase = saved
        }
    }

    fun applyDarkMode(enabled: Boolean) {
        darkMode = enabled
        settings.edit().putBoolean("dark_mode", enabled).apply()
    }

    fun applyGeminiKey(key: String) {
        geminiKey = key
        scoringSettings.edit().putString("gemini_api_key", key).apply()
    }

    fun editWifiPassphrase(passphrase: String) {
        wifiPassphrase = passphrase
    }

    suspend fun configureAndRememberPassphrase(passphrase: String): Boolean {
        TallyBackendFactory.configurePassphrase(passphrase)
        return withContext(Dispatchers.IO) { wifiPassphraseStore.save(if (passphrase.isBlank()) "" else passphrase) }
    }
}
