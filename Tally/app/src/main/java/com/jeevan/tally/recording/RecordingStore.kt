package com.jeevan.tally.recording

import com.jeevan.tally.sensors.SensorSample
import com.jeevan.tally.sensors.PlugSpec
import com.jeevan.tally.sensors.ValueKind
import java.io.*
import java.util.UUID

const val SAMPLE_LIMIT = 20_000

data class RecordingInfo(
    val id: String,
    val experimentId: String,
    val name: String,
    val savedAt: Long,
    val elapsed: Float,
    val count: Int,
    val spec: PlugSpec? = null,
)
data class Recording(val info: RecordingInfo, val samples: List<SensorSample>)

/** Private, versioned files; a completed recording is published by an atomic rename. */
class RecordingStore(private val directory: File) {
    fun save(experimentId: String, name: String, elapsed: Float, samples: List<SensorSample>, spec: PlugSpec? = null): RecordingInfo {
        require(samples.isNotEmpty() && samples.size <= SAMPLE_LIMIT)
        require(elapsed.isFinite() && elapsed >= 0f)
        require(name.isNotBlank() && name.length <= 80)
        val resolved = spec ?: PlugSpec.legacy.find { it.id == experimentId && it.outputAxes.size == samples.first().values.size }
            ?: PlugSpec.basic(experimentId, samples.first().values.size)
        require(resolved.id == experimentId)
        require(samples.all { it.t.isFinite() && it.t >= 0 && it.values.size == resolved.outputAxes.size && it.values.all(Float::isFinite) })
        require(samples.zipWithNext().all { (a, b) -> a.t <= b.t })
        check(directory.isDirectory || directory.mkdirs()) { "Cannot create recordings folder" }
        val info = RecordingInfo(UUID.randomUUID().toString(), experimentId, name.trim(), System.currentTimeMillis(), elapsed, samples.size, resolved)
        val temp = File(directory, "${info.id}.tmp")
        try {
            DataOutputStream(temp.outputStream().buffered()).use { out ->
                out.writeUTF("TALLY-2")
                out.writeUTF(info.experimentId); out.writeUTF(info.name)
                out.writeLong(info.savedAt); out.writeFloat(info.elapsed); out.writeInt(info.count)
                writeSpec(out, resolved)
                samples.forEach { sample ->
                    out.writeFloat(sample.t); out.writeInt(sample.segment)
                    sample.values.forEach(out::writeFloat)
                }
            }
            check(temp.renameTo(file(info.id))) { "Could not finish saving recording" }
        } finally { temp.delete() }
        return info
    }
    fun list(): List<RecordingInfo> = directory.listFiles { file -> file.extension == "tally" }
        ?.mapNotNull { file -> runCatching { readInfo(file.nameWithoutExtension) }.getOrNull() }
        ?.sortedByDescending { it.savedAt } ?: emptyList()

    private fun file(id: String): File {
        require(Regex("[a-f0-9-]{36}").matches(id)) { "Invalid recording ID" }
        return File(directory, "$id.tally")
    }
    private fun header(input: DataInputStream, id: String): RecordingInfo {
        val version = input.readUTF()
        require(version == "TALLY-1" || version == "TALLY-2") { "Unsupported recording version" }
        val info = RecordingInfo(id, input.readUTF(), input.readUTF(), input.readLong(), input.readFloat(), input.readInt())
        require(info.count in 1..SAMPLE_LIMIT && info.elapsed.isFinite() && info.elapsed >= 0)
        val spec = if (version == "TALLY-2") readSpec(input) else
            PlugSpec.legacy.find { it.id == info.experimentId } ?: PlugSpec.basic(info.experimentId, 4)
        require(spec.id == info.experimentId)
        return info.copy(spec = spec)
    }
    fun readInfo(id: String): RecordingInfo = DataInputStream(file(id).inputStream().buffered()).use { header(it, id) }
    private fun writeSpec(out: DataOutputStream, spec: PlugSpec) {
        out.writeUTF(spec.id); out.writeUTF(spec.displayName); out.writeUTF(spec.unit)
        out.writeUTF(spec.kind.name); out.writeUTF(spec.icon); out.writeUTF(spec.accentHex)
        out.writeBoolean(spec.magnitude); out.writeInt(spec.axisCount)
        spec.axisNames.forEach(out::writeUTF)
        out.writeBoolean(spec.minimum != null); spec.minimum?.let(out::writeFloat)
        out.writeBoolean(spec.maximum != null); spec.maximum?.let(out::writeFloat)
    }
    private fun readSpec(input: DataInputStream): PlugSpec {
        val id = input.readUTF(); val name = input.readUTF(); val unit = input.readUTF()
        val kind = ValueKind.valueOf(input.readUTF()); val icon = input.readUTF(); val accent = input.readUTF()
        val magnitude = input.readBoolean(); val count = input.readInt()
        require(count in 1..16)
        val axes = List(count) { input.readUTF() }
        val min = if (input.readBoolean()) input.readFloat() else null
        val max = if (input.readBoolean()) input.readFloat() else null
        return PlugSpec(id, name, axes, unit, kind, icon, accent, min, max, magnitude)
    }
    fun load(id: String): Recording = DataInputStream(file(id).inputStream().buffered()).use { input ->
        val info = header(input, id)
        val samples = List(info.count) {
            val time = input.readFloat()
            val segment = input.readInt()
            val values = FloatArray(checkNotNull(info.spec).outputAxes.size) { input.readFloat() }
            require(time.isFinite() && time >= 0 && values.all(Float::isFinite)) { "Invalid measurement in file" }
            SensorSample(time, values, segment)
        }
        require(samples.zipWithNext().all { (a, b) -> a.t <= b.t })
        Recording(info, samples)
    }
}
