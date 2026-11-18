package com.tally.app.backend.store

import com.tally.app.backend.export.CsvExport
import com.tally.app.backend.link.EndReason
import com.tally.app.backend.score.TallyWireWriter
import com.tally.app.backend.session.LiveRing
import com.tally.app.backend.session.SampleStore
import com.tally.app.contract.*
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.util.Locale
import java.util.zip.CRC32
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONObject

internal object StorageChecks {
    @JvmStatic fun main(args: Array<String>) {
        sampleChecks(); repositoryChecks(); csvChecks(); fakeChecks()
        println("Storage, CSV, wire writer and fake self-checks passed")
    }
    private fun sampleChecks() {
        val store = SampleStore()
        val row = floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)
        repeat(60_000) { store.append(it * 10_000L, row) }
        check(store.size == 60_000 && store.timestampUs(59_999) == 599_990_000L)
        check(store.g(59_999, 5) == 5f)
        fails { store.append(600_000_000, row) }
        store.clear(); store.append(10_999, row)
        fails { store.append(10_999, row) }
        row[0] = Float.NaN
        fails { store.append(11_000, row) }
        check(store.size == 1)
        val locale = Locale.getDefault()
        val wire = try {
            Locale.setDefault(Locale.GERMANY)
            buildString { TallyWireWriter.write(Side.R, store, EndReason.DONE, this) }
        } finally { Locale.setDefault(locale) }
        check(wire.contains("side=R") && wire.contains("S 0 10 +0.00000000 +1.00000000"))
        check(wire.endsWith("E done\n"))
        val ring = LiveRing()
        row.fill(0f)
        repeat(1010) { row.fill(it.toFloat()); ring.append(row) }
        check(ring.version.value == 0L)
        ring.publishFrame(); check(ring.version.value == 1L)
        val dst = FloatArray(6000)
        check(ring.copyLatest(dst, 1000) == 1000 && dst.first() == 10f && dst.last() == 1009f)
        check((0 until 1000).all { row -> (0 until 6).all { dst[row * 6 + it] == (row + 10).toFloat() } })
        check(ring.copyLatest(FloatArray(12), 1000) == 2)
        ring.clear(); check(ring.copyLatest(dst, 1000) == 0)
    }
    private fun repositoryChecks() {
        val root = Files.createTempDirectory("tally-store-check-").toFile()
        try {
            val id = SetId(UInt.MAX_VALUE)
            val repo = SetRepository(root)
            val meta = JSONObject().put("side", "R").put("started_at_epoch_ms", 123L)
                .put("provenance", JSONObject().put("model_sha256", JSONObject().put("L", "left").put("R", "old")))
            repo.create(id, meta)
            fails { repo.create(id, meta) }
            repo.appendFrame(id, byteArrayOf(1, 2, 3))
            check(repo.frames(id).contentEquals(byteArrayOf(1, 2, 3)))
            repo.finishFrames(id)
            repo.updateMeta(id, meta.put("end_reason", "DONE"))
            check(repo.meta(id)?.getString("end_reason") == "DONE")
            fails { repo.appendFrame(id, byteArrayOf(4)) }
            val result = SetResult(id, Side.R, 123, "scored", false, 0.25, "EFE",
                listOf(RepResult(1, false, 0.25, "EFE", 2.0)), listOf("fixture"), 100.0,
                Provenance("paired-synchronized-offline", "right-new", "scorer", "git", 12, "00:00:00:00:00:01", "nominal", "1.0"))
            repo.saveResult(result)
            repo.saveResult(result) // Rescoring must atomically replace an existing result too.
            check(repo.result(id) == result)
            val persisted = JSONObject(root.resolve("${id.raw}/result.json").readText())
            val hashes = persisted.getJSONObject("provenance").getJSONObject("model_sha256")
            check(hashes.getString("L") == "left" && hashes.getString("R") == "right-new")
            val reopened = SetRepository(root)
            check(reopened.result(id) == result && reopened.history.value.single().repCount == 1)
            val second = SetId(8u)
            repo.create(second, JSONObject().put("side", "L").put("started_at_epoch_ms", 10L))
            repo.finishFrames(second)
            check(repo.history.value.map { it.id } == listOf(id, second))
            repo.updateMeta(second, JSONObject().put("side", "L").put("started_at_epoch_ms", 300L))
            check(repo.history.value.map { it.id } == listOf(second, id))
            repo.saveResult(result.copy(reps = emptyList()))
            check(repo.history.value.map { it.repCount } == listOf(0, 0))
            check(repo.history.value == SetRepository(root).history.value)
            check(root.walkTopDown().none { it.extension == "tmp" })
            val bad = root.resolve("7").apply { mkdir() }
            bad.resolve("meta.json").writeText("broken")
            check(SetRepository(root).history.value.size == 2 && bad.exists())
        } finally { root.deleteRecursively() }
    }
    private fun csvChecks() {
        val start = frame(2, ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN).putInt(9).put('L'.code.toByte()).array())
        val raw = start + samples(0)
        val csv = buildString { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(raw), this) }
        check(csv.lines()[1] == "9,L,0,0,1000,1001,1002,1003,1004,1005")
        check(csv.lines()[2] == "9,L,1,10000,1010,1011,1012,1013,1014,1015")
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(raw.copyOf(raw.size - 1)), StringBuilder()) }
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(start + samples(2)), StringBuilder()) }
        fails { CsvExport.writeSamples(SetId(8u), "L", ByteBuffer.wrap(raw), StringBuilder()) }
        val end = frame(4, ByteBuffer.allocate(9).order(ByteOrder.LITTLE_ENDIAN).putInt(9).put(0).putInt(2).array())
        check(buildString { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(raw + end), this) } == csv)
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(samples(0)), StringBuilder()) }
        fails { CsvExport.writeSamples(SetId(9u), "R", ByteBuffer.wrap(raw), StringBuilder()) }
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(start + raw), StringBuilder()) }
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(raw + end + samples(2)), StringBuilder()) }
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(start + end), StringBuilder()) }
        val truncatedTail = raw + samples(2).copyOf(20)
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(truncatedTail), StringBuilder()) }
        check(buildString { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(truncatedTail), this, allowIncomplete = true) } == csv)
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(start.copyOf(5)), StringBuilder(), allowIncomplete = true) }
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(raw + end + samples(2).copyOf(5)), StringBuilder(), allowIncomplete = true) }
        val corrupt = raw.copyOf().apply { this[start.size + 19] = 1 }
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(corrupt), StringBuilder()) }
        fails { CsvExport.writeSamples(SetId(9u), "L", ByteBuffer.wrap(corrupt), StringBuilder(), allowIncomplete = true) }
    }
    private fun fakeChecks() = runBlocking {
        val fake = FakeTallyBackend()
        check(fake.startSet(Side.L).isFailure)
        fake.connect().getOrThrow()
        val id = fake.startSet(Side.R).getOrThrow()
        check(fake.startSet(Side.L).isFailure)
        val done = withTimeout(5000) { fake.session.first { it is SessionState.Done } } as SessionState.Done
        check(done.result.side == Side.R && done.result.id == id && fake.result(id) == done.result)
        val live = FloatArray(6000)
        check(fake.live.copyLatest(live, 1000) == 1000 && live.any { it != 0f })
        check(fake.history().first().single().id == id)
        check(fake.saveCalibration().isFailure)
        CalPose.entries.forEach { fake.captureCalibrationPose(it).getOrThrow() }
        check(!fake.saveCalibration().getOrThrow().nominal)
        fake.startSet(Side.L).getOrThrow(); fake.abortSet(); delay(400)
        check(fake.session.value is SessionState.Failed)
        fake.disconnect(); check(fake.link.value == LinkState.Disconnected)
    }
    private fun samples(first: Int): ByteArray {
        val payload = ByteBuffer.allocate(9 + 32).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(9).putInt(first).put(2)
        repeat(2) { sample ->
            payload.putInt(sample * 10_000)
            repeat(6) { ch -> payload.putShort((1000 + sample * 10 + ch).toShort()) }
        }
        return frame(3, payload.array())
    }
    private fun frame(type: Int, payload: ByteArray): ByteArray {
        val raw = ByteArray(payload.size + 10)
        ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN).apply {
            put(0x54).put(0x59).put(1).put(type.toByte()).putShort(payload.size.toShort()).put(payload)
            putInt(CRC32().apply { update(raw, 2, payload.size + 4) }.value.toInt())
        }
        return raw
    }
    private fun fails(block: () -> Unit) { check(runCatching(block).isFailure) }
}
