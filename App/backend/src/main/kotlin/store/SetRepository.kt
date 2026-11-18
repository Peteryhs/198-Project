package com.tally.app.backend.store

import android.content.Context
import com.tally.app.contract.*
import com.tally.app.backend.score.toJson
import com.tally.app.backend.score.toSetChart
import java.io.BufferedOutputStream
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject

internal class SetRepository(private val root: File) {
    constructor(context: Context) : this(File(context.filesDir, "sets"))
    private var output: BufferedOutputStream? = null
    private var activeId: SetId? = null
    private var lastFlushNs = 0L
    private val summaries = MutableStateFlow<List<SetSummary>>(emptyList())
    val history = summaries.asStateFlow()

    init {
        check(root.isDirectory || root.mkdirs())
        summaries.value = ids().mapNotNull(::readSummary).sortedByDescending { it.startedAtEpochMs }
    }
    private fun directory(id: SetId) = File(root, id.raw.toString())
    @Synchronized fun ids(): List<SetId> = root.listFiles().orEmpty().filter { it.isDirectory }
        .mapNotNull { it.name.toUIntOrNull()?.let(::SetId) }
    @Synchronized fun create(id: SetId, metadata: JSONObject) {
        check(output == null) { "Another recording is open" }
        val dir = directory(id)
        check(!dir.exists() && dir.mkdirs()) { "Set already exists or cannot be created" }
        atomicJson(File(dir, "meta.json"), metadata.put("id", id.raw.toString()))
        output = File(dir, "frames.bin").outputStream().buffered()
        activeId = id
        lastFlushNs = System.nanoTime()
        refresh(id)
    }
    @Synchronized fun appendFrame(id: SetId, bytes: ByteArray) {
        check(activeId == id) { "Recording is not open" }
        val stream = checkNotNull(output)
        stream.write(bytes)
        val now = System.nanoTime()
        if (now - lastFlushNs >= 1_000_000_000L) { stream.flush(); lastFlushNs = now }
    }
    @Synchronized fun finishFrames(id: SetId) {
        if (activeId == id) {
            try { output?.close() } finally { output = null; activeId = null }
        }
    }
    @Synchronized fun meta(id: SetId): JSONObject? = File(directory(id), "meta.json")
        .takeIf { it.isFile }?.readText()?.let(::JSONObject)
    @Synchronized fun updateMeta(id: SetId, metadata: JSONObject) {
        check(directory(id).isDirectory) { "Unknown set" }
        atomicJson(File(directory(id), "meta.json"), metadata.put("id", id.raw.toString()))
        refresh(id)
    }
    @Synchronized fun frames(id: SetId): ByteArray {
        if (activeId == id) output?.flush()
        return File(directory(id), "frames.bin").readBytes()
    }
    @Synchronized fun result(id: SetId): SetResult? = File(directory(id), "result.json")
        .takeIf { it.isFile }?.readText()?.let { decode(JSONObject(it)) }
    @Synchronized fun saveResult(result: SetResult) {
        check(directory(result.id).isDirectory) { "Unknown set" }
        val json = encode(result)
        meta(result.id)?.optJSONObject("provenance")?.optJSONObject("model_sha256")?.let {
            json.getJSONObject("provenance").put("model_sha256",
                JSONObject(it.toString()).put(result.side.name, result.provenance.modelSha256))
        }
        atomicJson(File(directory(result.id), "result.json"), json)
        publishSummary(result.id, result.toSummary())
    }
    private fun refresh(id: SetId) = publishSummary(id, readSummary(id))

    private fun publishSummary(id: SetId, summary: SetSummary?) {
        val current = summaries.value
        if (current.firstOrNull { it.id == id } == summary) return
        summaries.value = buildList {
            addAll(current.filterNot { it.id == id })
            if (summary != null) {
                val insertion = indexOfFirst { it.startedAtEpochMs < summary.startedAtEpochMs }
                add(if (insertion < 0) size else insertion, summary)
            }
        }
    }

    private fun readSummary(id: SetId): SetSummary? = try {
        result(id)?.toSummary() ?: meta(id)?.let { m -> SetSummary(id, Side.valueOf(m.getString("side")),
            m.getLong("started_at_epoch_ms"), "interrupted", null, null, 0, m.intendedExercise()) }
    } catch (_: Exception) {
        // Metadata can still identify a set whose result is unreadable.
        runCatching { meta(id)?.let { m -> SetSummary(id, Side.valueOf(m.getString("side")),
            m.getLong("started_at_epoch_ms"), "unreadable", null, null, 0) } }.getOrNull()
    }

    private fun SetResult.toSummary() =
        SetSummary(id, side, startedAtEpochMs, status, wrong, exercise, reps.size, intendedExercise)

    private fun atomicJson(file: File, json: JSONObject) {
        val temp = File(file.parentFile, file.name + ".tmp")
        temp.outputStream().use { stream ->
            stream.write(json.toString().toByteArray(Charsets.UTF_8))
            stream.fd.sync()
        }
        Files.move(temp.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
    }
    private fun encode(r: SetResult): JSONObject = JSONObject().apply {
        put("id", r.id.raw.toString()); put("side", r.side.name); put("started_at_epoch_ms", r.startedAtEpochMs)
        put("status", r.status); put("wrong", r.wrong ?: JSONObject.NULL)
        put("mean_p_wrong", r.meanPWrong ?: JSONObject.NULL); put("exercise", r.exercise ?: JSONObject.NULL)
        put("measured_rate_hz", r.measuredRateHz ?: JSONObject.NULL)
        put("intended_exercise", r.intendedExercise ?: JSONObject.NULL)
        put("diagnostics", JSONArray(r.diagnostics))
        put("chart", r.chart?.toJson() ?: JSONObject.NULL)
        put("reps", JSONArray().apply { r.reps.forEach { rep -> put(JSONObject().apply {
            put("index", rep.index); put("wrong", rep.wrong); put("p_wrong", rep.pWrong)
            put("exercise", rep.exercise); put("duration_s", rep.durationS)
        }) } })
        put("provenance", JSONObject().apply { with(r.provenance) {
            put("model_kind", modelKind); put("model_sha256", JSONObject().put(r.side.name, modelSha256))
            put("scorer_sha256", scorerSha256); put("git_rev", gitRev); put("fw_version", fwVersion)
            put("mac", mac); put("calibration_id", calibrationId); put("app_version", appVersion)
        } })
    }
    private fun decode(j: JSONObject): SetResult {
        val side = Side.valueOf(j.getString("side"))
        val p = j.getJSONObject("provenance")
        val reps = j.getJSONArray("reps")
        val diagnostics = j.getJSONArray("diagnostics")
        return SetResult(SetId(j.getString("id").toUInt()), side, j.getLong("started_at_epoch_ms"),
            j.getString("status"), if (j.isNull("wrong")) null else j.getBoolean("wrong"),
            if (j.isNull("mean_p_wrong")) null else j.getDouble("mean_p_wrong"),
            if (j.isNull("exercise")) null else j.getString("exercise"),
            List(reps.length()) { i -> reps.getJSONObject(i).let { rep -> RepResult(rep.getInt("index"),
                rep.getBoolean("wrong"), rep.getDouble("p_wrong"), rep.getString("exercise"), rep.getDouble("duration_s")) } },
            List(diagnostics.length()) { diagnostics.getString(it) },
            if (j.isNull("measured_rate_hz")) null else j.getDouble("measured_rate_hz"),
            Provenance(p.getString("model_kind"), p.getJSONObject("model_sha256").getString(side.name),
                p.getString("scorer_sha256"), p.getString("git_rev"), p.getInt("fw_version"),
                p.getString("mac"), p.getString("calibration_id"), p.getString("app_version")),
            j.optJSONObject("chart")?.toSetChart(), j.intendedExercise())
    }
}

/** Absent in sets and results stored before BRIEF6; null means the user did not choose an exercise. */
internal fun JSONObject.intendedExercise(): String? = if (isNull("intended_exercise")) null else getString("intended_exercise")
