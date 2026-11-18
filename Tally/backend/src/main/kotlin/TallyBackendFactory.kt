package com.tally.app.backend

import android.content.Context
import com.tally.app.backend.log.TallyLog
import com.tally.app.backend.score.GeminiCallStatus
import com.tally.app.contract.TallyBackend
import kotlinx.coroutines.flow.StateFlow

object TallyBackendFactory {
    private var instance: TallyBackend? = null

    /**
     * Diagnostics live behind the factory so `app` never imports backend internals.
     * SeamTest enforces that: the app may reference TallyBackendFactory and nothing else from `backend`.
     */
    fun installLog(context: Context) = TallyLog.install(context)
    fun logCrash(thread: Thread, error: Throwable) = TallyLog.crash(thread, error)
    fun logSnapshot(): String = TallyLog.snapshot()

    /** The current or most recent Gemini request status. */
    fun geminiStatus(): StateFlow<String?> = GeminiCallStatus.text
    fun logCrashSnapshot(): String? = TallyLog.crashSnapshot()

    /** [passphrase] is the device AP's WPA2 credential; null or blank joins an open Tally network. */
    @Synchronized fun create(context: Context, passphrase: String? = null): TallyBackend =
        instance ?: AndroidTallyBackend(context.applicationContext, passphrase).also { instance = it }

    /** Blank means the device's AP is open; otherwise a WPA2 passphrase, checked by `link.wifiPassphraseOrOpen`. */
    suspend fun configurePassphrase(passphrase: String) {
        val backend = synchronized(this) { instance as? AndroidTallyBackend }
            ?: error("Create the real backend before configuring its Wi-Fi passphrase")
        backend.configurePassphrase(passphrase)
    }
}
