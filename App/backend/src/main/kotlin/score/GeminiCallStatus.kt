package com.tally.app.backend.score

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Last Gemini call outcome, so the UI can say whether the request actually went through.
 * Lives in `backend` and is read through [com.tally.app.backend.TallyBackendFactory] so the app
 * module never imports backend internals (SeamTest enforces that).
 */
object GeminiCallStatus {
    private val mutable = MutableStateFlow<String?>(null)
    val text: StateFlow<String?> = mutable.asStateFlow()

    fun report(value: String) { mutable.value = value }
}
