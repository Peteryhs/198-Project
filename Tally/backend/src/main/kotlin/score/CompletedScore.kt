package com.tally.app.backend.score

import com.tally.app.contract.Side
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import org.json.JSONArray
import org.json.JSONObject

internal data class ScorerInfo(val modelSha256: Map<Side, String>, val scorerSha256: String, val exerciseClasses: List<String>)
internal data class CompletedScore(val record: JSONObject, val localInfo: ScorerInfo? = null)

internal suspend fun scoreCompletedSet(
    geminiKey: String?,
    gemini: suspend (String) -> JSONObject,
    local: suspend () -> CompletedScore,
): CompletedScore {
    if (geminiKey == null) return local()
    val failure = try {
        return CompletedScore(gemini(geminiKey))
    } catch (error: GeminiScorer.GeminiError) {
        error.status
    }
    currentCoroutineContext().ensureActive()
    return local().also { score ->
        val diagnostics = score.record.optJSONArray("diagnostics") ?: JSONArray()
        score.record.put("diagnostics", diagnostics.put("gemini_call_status=$failure"))
    }
}
