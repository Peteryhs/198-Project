package com.tally.app.backend.calib

import android.content.Context
import android.util.AtomicFile
import com.tally.app.contract.CalibrationInfo
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileNotFoundException

internal class CalibrationStore(context: Context) {
    private val file = AtomicFile(File(context.filesDir, "calibration.json"))

    fun load(): Calibration = try {
        fromJson(JSONObject(file.openRead().bufferedReader().use { it.readText() }))
    } catch (_: FileNotFoundException) { Calibration.nominal() }

    fun save(calibration: Calibration) {
        val stream = file.startWrite()
        try {
            stream.write(toJson(calibration).toString().toByteArray(Charsets.UTF_8))
            file.finishWrite(stream)
        } catch (e: Exception) {
            file.failWrite(stream)
            throw e
        }
    }

    companion object {
        fun toJson(calibration: Calibration): JSONObject = JSONObject()
            .put("id", calibration.info.id).put("nominal", calibration.info.nominal)
            .put("created_at_epoch_ms", calibration.info.createdAtEpochMs)
            .put("offset_mv", JSONArray(calibration.offsetMv.toList()))
            .put("mv_per_g", JSONArray(calibration.mvPerG.toList()))
            .put("gain_source", calibration.gainSource)
            .put("status", if (calibration.info.nominal) "nominal" else if (calibration.usable) "usable" else "marginal")
            .put("reasons", JSONArray(calibration.reasons))
            .apply {
                calibration.frames?.let { frames ->
                    put("frames", JSONArray().apply { frames.forEach { f -> put(JSONArray(f.toList())) } })
                }
            }

        fun fromJson(json: JSONObject) = Calibration(
            CalibrationInfo(json.getString("id"), json.getBoolean("nominal"), json.getLong("created_at_epoch_ms")),
            FloatArray(6) { json.getJSONArray("offset_mv").getDouble(it).toFloat() },
            FloatArray(6) { json.getJSONArray("mv_per_g").getDouble(it).toFloat() },
            json.optJSONArray("frames")?.let { arr ->
                List(arr.length()) { i ->
                    val inner = arr.getJSONArray(i)
                    FloatArray(9) { j -> inner.getDouble(j).toFloat() }
                }
            },
            json.optString("gain_source", "nominal"),
            json.optJSONArray("reasons")?.let { arr -> List(arr.length()) { arr.getString(it) } } ?: emptyList(),
        )
    }
}
