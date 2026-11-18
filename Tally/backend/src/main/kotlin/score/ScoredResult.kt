package com.tally.app.backend.score

import com.tally.app.contract.Provenance
import com.tally.app.contract.RepResult
import com.tally.app.contract.SetId
import com.tally.app.contract.SetResult
import com.tally.app.contract.Side
import com.tally.app.contract.ChartSample
import com.tally.app.contract.RepSpan
import com.tally.app.contract.SetChart
import org.json.JSONArray
import org.json.JSONObject

/** The same scorer-to-UI conversion is exercised by the host pipeline and the Android backend. */
internal fun JSONObject.toSetResult(
    id: SetId, side: Side, startedAtEpochMs: Long, provenance: Provenance,
): SetResult {
    val reps = optJSONArray("repetitions") ?: JSONArray()
    val diagnostics = optJSONArray("diagnostics") ?: JSONArray()
    return SetResult(
        id, side, startedAtEpochMs, getString("status"),
        // tally_app._decide: wrong when any rep is wrong or the class is not the intended exercise.
        when (optString("verdict")) { "wrong", "wrong_exercise" -> true; "correct" -> false; else -> null },
        nullableDouble("mean_p_wrong"), nullableString("exercise"),
        List(reps.length()) { i -> reps.getJSONObject(i).let {
            RepResult(it.getInt("rep_index"), it.getString("verdict") == "wrong",
                it.getDouble("p_wrong"), it.getString("exercise"), it.getDouble("duration_s"))
        } },
        List(diagnostics.length()) { diagnostics.getString(it) }, nullableDouble("measured_rate_hz"), provenance,
        optJSONObject("chart")?.toSetChart(), nullableString("intended_exercise"),
    )
}

private fun JSONObject.nullableDouble(key: String): Double? = if (isNull(key) || !has(key)) null else getDouble(key)
private fun JSONObject.nullableString(key: String): String? = if (isNull(key) || !has(key)) null else getString(key)

internal fun JSONObject.toSetChart(): SetChart {
    val samples = getJSONArray("samples")
    val reps = getJSONArray("reps")
    return SetChart(
        List(samples.length()) { i -> samples.getJSONObject(i).let {
            ChartSample(it.getDouble("time_s"), it.getDouble("upper_arm_g").toFloat(), it.getDouble("forearm_g").toFloat())
        } },
        List(reps.length()) { i -> reps.getJSONObject(i).let {
            RepSpan(it.getInt("index"), it.getDouble("start_s"), it.getDouble("end_s"))
        } },
    )
}

internal fun SetChart.toJson() = JSONObject()
    .put("samples", JSONArray().apply { samples.forEach { put(JSONObject()
        .put("time_s", it.timeS).put("upper_arm_g", it.upperArmG.toDouble()).put("forearm_g", it.forearmG.toDouble())) } })
    .put("reps", JSONArray().apply { reps.forEach { put(JSONObject()
        .put("index", it.index).put("start_s", it.startS).put("end_s", it.endS)) } })
