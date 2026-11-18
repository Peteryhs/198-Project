package com.tally.app.backend.session

import com.tally.app.backend.calib.Calibration
import com.tally.app.backend.calib.CalibrationStore
import com.tally.app.backend.link.Command
import com.tally.app.backend.link.DeviceLink
import com.tally.app.backend.link.EndReason
import com.tally.app.backend.link.Frame
import com.tally.app.backend.link.FrameCodec
import com.tally.app.backend.score.TallyWireWriter
import com.tally.app.backend.score.toSetResult
import com.tally.app.backend.store.SetRepository
import com.tally.app.contract.CalPose
import com.tally.app.contract.Provenance
import com.tally.app.contract.SetId
import com.tally.app.contract.SetResult
import com.tally.app.contract.Side
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import java.util.zip.CRC32
import javax.net.SocketFactory
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/** Offline integration check. The only stand-in is a synthetic ESP32 TCP sender. */
internal object PipelineChecks {
    private const val FW_VERSION = 42
    private const val MAC = "02:00:00:00:00:42"
    private const val SAMPLE_COUNT = 60_000
    private const val SAMPLES_PER_FRAME = 10
    private const val FRAMES_PER_SET = SAMPLE_COUNT / SAMPLES_PER_FRAME

    @JvmStatic fun main(args: Array<String>) {
        require(args.size == 2) { "usage: PipelineChecks capture|verify <artifact-directory>" }
        val mode = args[0]
        val directory = File(args[1]).absoluteFile
        val manifest = JSONObject(File(directory, "manifest.json").readText())
        when (mode) {
            "capture" -> capture(directory, manifest)
            "verify" -> verify(directory, manifest)
            else -> error("Unknown mode $mode")
        }
    }

    private fun capture(directory: File, manifest: JSONObject) {
        check(directory.isDirectory)
        val models = manifest.getJSONObject("model_sha256")
        val modelHashes = JSONObject().put("L", models.getString("L")).put("R", models.getString("R"))
        val scorerHash = manifest.getString("scorer_sha256")
        val gitRev = manifest.getString("git_rev")
        val appVersion = manifest.getString("app_version")
        checkSha256(scorerHash, "scorer_sha256")
        Side.entries.forEach { checkSha256(models.getString(it.name), "model_sha256.${it.name}") }

        val sets = File(directory, "sets")
        check(!sets.exists() || sets.list().isNullOrEmpty()) { "Capture requires an empty sets directory" }
        val repository = SetRepository(sets)
        val calibration = sixPoseCalibration()
        for (side in Side.entries) {
            val id = SetId(100u + side.ordinal.toUInt())
            val metadata = JSONObject()
                .put("id", id.raw.toString())
                .put("side", side.name)
                .put("started_at_epoch_ms", System.currentTimeMillis() + side.ordinal)
                .put("calibration", CalibrationStore.toJson(calibration))
                .put("provenance", JSONObject()
                    .put("model_kind", "paired-synchronized-offline")
                    .put("model_sha256", JSONObject(modelHashes.toString()))
                    .put("scorer_sha256", scorerHash)
                    .put("git_rev", gitRev)
                    .put("fw_version", FW_VERSION)
                    .put("mac", MAC)
                    .put("reset_reason", 1)
                    .put("calibration_id", calibration.info.id)
                    .put("app_version", appVersion))
            val recorder = SetRecorder(id, side, calibration, metadata, repository, null)
            captureSet(side, id, recorder)
            check(recorder.ended && recorder.store.size == SAMPLE_COUNT)
            File(directory, "${side.name}.wire").bufferedWriter(Charsets.US_ASCII).use { out ->
                TallyWireWriter.write(side, recorder.store, EndReason.DONE, out)
            }
            println("host-only synthetic TCP capture: side=${side.name}, derived samples=${recorder.store.size}, archive=${File(sets, id.raw.toString()).relativeTo(directory)}")
        }
    }

    private fun captureSet(side: Side, id: SetId, recorder: SetRecorder) = runBlocking {
        val server = ServerSocket(0, 1, InetAddress.getLoopbackAddress()).apply { soTimeout = 30_000 }
        val endpoint = InetSocketAddress(InetAddress.getLoopbackAddress(), server.localPort)
        val ended = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>()
        val closing = AtomicBoolean(false)
        val sender = Thread({
            try {
                server.accept().use { socket ->
                    socket.soTimeout = 10_000
                    val output = socket.getOutputStream()
                    val input = socket.getInputStream()
                    val hello = helloFrame()
                    output.write(hello, 0, 3)
                    output.flush()
                    output.write(hello, 3, hello.size - 3)
                    output.flush()

                    val startBytes = input.readNBytes(15)
                    check(startBytes.size == 15) { "Phone did not send a complete START" }
                    val command = (FrameCodec.decode(ByteBuffer.wrap(startBytes)) as? Frame.CommandFrame)?.command
                    check(command == Command.Start(id, side)) { "Unexpected START command: $command" }

                    output.write(concatenate(startedFrame(id, side), samplesFrame(id, 0), samplesFrame(id, 1)))
                    output.flush()
                    var index = 2
                    while (index < FRAMES_PER_SET) {
                        val frame = samplesFrame(id, index)
                        if (index == 17) {
                            output.write(frame, 0, 7)
                            output.flush()
                            output.write(frame, 7, frame.size - 7)
                            output.flush()
                            index++
                        } else {
                            val batch = ByteArrayOutputStream()
                            batch.write(frame)
                            index++
                            if (index < FRAMES_PER_SET && index != 17) {
                                batch.write(samplesFrame(id, index))
                                index++
                            }
                            output.write(batch.toByteArray())
                            output.flush()
                        }
                    }
                    output.write(endFrame(id, SAMPLE_COUNT))
                    output.flush()
                    while (input.read() >= 0) { }
                }
            } catch (error: Throwable) {
                if (!closing.get()) failure.compareAndSet(null, error)
                ended.countDown()
            } finally {
                runCatching { server.close() }
            }
        }, "pipeline-synthetic-esp32-${side.name}").apply { isDaemon = true; start() }

        val link = DeviceLink(SocketFactory.getDefault(), { frame ->
            if (frame !is Frame.Hello) try {
                recorder.accept(frame)
                if (frame is Frame.SetEnd) ended.countDown()
            } catch (error: Throwable) {
                failure.compareAndSet(null, error)
                ended.countDown()
                throw error
            }
        }, { reason ->
            if (!closing.get()) {
                failure.compareAndSet(null, IllegalStateException("DeviceLink lost: $reason"))
                ended.countDown()
            }
        }, endpoint)

        try {
            val hello = link.connect()
            check(hello.device.fwVersion == FW_VERSION && hello.device.mac == MAC)
            link.send(Command.Start(id, side))
            check(ended.await(60, TimeUnit.SECONDS)) { "Timed out waiting for SET_END" }
            failure.get()?.let { throw IllegalStateException("Synthetic pipeline failed", it) }
            check(recorder.ended) { "No SET_END received" }
        } finally {
            closing.set(true)
            link.close()
            runCatching { server.close() }
            if (!recorder.ended) runCatching { recorder.closeIncomplete("pipeline capture failed") }
            sender.join(5_000)
            check(!sender.isAlive) { "Synthetic ESP32 sender did not stop" }
            failure.get()?.let { throw IllegalStateException("Synthetic sender failed", it) }
        }
    }

    private fun verify(directory: File, manifest: JSONObject) {
        val repository = SetRepository(File(directory, "sets"))
        val hashes = manifest.getJSONObject("model_sha256")
        val expectedSides = Side.entries.toSet()
        val idsBySide = repository.ids().mapNotNull { id ->
            repository.meta(id)?.let { id to Side.valueOf(it.getString("side")) }
        }.groupBy({ it.second }, { it.first })
        check(idsBySide.keys == expectedSides && idsBySide.values.all { it.size == 1 }) {
            "Expected one persisted set for each side"
        }

        for (side in Side.entries) {
            val id = idsBySide.getValue(side).single()
            val metadata = requireNotNull(repository.meta(id))
            check(metadata.getString("end_reason") == EndReason.DONE.name)
            val calibration = CalibrationStore.fromJson(metadata.getJSONObject("calibration"))
            val provenanceJson = metadata.getJSONObject("provenance")
            check(provenanceJson.getInt("fw_version") == FW_VERSION && provenanceJson.getString("mac") == MAC)
            check(provenanceJson.getString("scorer_sha256") == manifest.getString("scorer_sha256"))
            check(provenanceJson.getString("git_rev") == manifest.getString("git_rev"))
            check(provenanceJson.getString("app_version") == manifest.getString("app_version"))
            check(provenanceJson.getString("calibration_id") == calibration.info.id)
            val archivedHashes = provenanceJson.getJSONObject("model_sha256")
            Side.entries.forEach { check(archivedHashes.getString(it.name) == hashes.getString(it.name)) }

            val recorder = SetRecorder(id, side, calibration, metadata, null, null)
            recorder.replay(repository.frames(id))
            check(recorder.ended && recorder.store.size == SAMPLE_COUNT)
            val first = recorder.store.timestampUs(0)
            val last = recorder.store.timestampUs(recorder.store.size - 1)
            val rateHz = (recorder.store.size - 1) * 1_000_000.0 / (last - first)
            check(rateHz in 95.0..105.0 && kotlin.math.abs(rateHz - 100.0) < 0.01) { "Unexpected timestamp rate $rateHz Hz" }

            val scoredFile = File(directory, "${side.name}.score.json")
            val full = JSONObject(scoredFile.readText())
            val record = full.optJSONObject("record") ?: full
            val reps = record.getJSONArray("repetitions")
            check(record.getString("verdict") in setOf("correct", "wrong"))
            repeat(reps.length()) { i ->
                val rep = reps.getJSONObject(i)
                val repP = rep.getDouble("p_wrong")
                check(rep.getString("verdict") in setOf("correct", "wrong"))
                check(repP in 0.0..1.0 && (rep.getString("verdict") == "wrong") == (repP >= 0.5))
            }
            val p = Provenance(
                provenanceJson.getString("model_kind"), hashes.getString(side.name),
                manifest.getString("scorer_sha256"), manifest.getString("git_rev"), FW_VERSION, MAC,
                calibration.info.id, manifest.getString("app_version"),
            )
            val result = record.toSetResult(id, side, metadata.getLong("started_at_epoch_ms"), p)
            assertScoredResult(result)
            check(kotlin.math.abs(checkNotNull(result.measuredRateHz) - rateHz) < 0.01) {
                "Scorer rate disagrees with archived timestamps"
            }
            repository.saveResult(result)
            val persisted = repository.result(id)
            check(persisted == result) { "Persisted result differs for side $side" }
            val summary = repository.history.value.single { it.id == id }
            check(summary.side == side && summary.repCount == result.reps.size && summary.status == result.status)
            val verdict = if (result.wrong == true) "wrong" else "correct"
            println("host-only verification: side=${side.name}, derived samples=${recorder.store.size}, derived rate=${"%.2f".format(java.util.Locale.ROOT, rateHz)} Hz, scorer verdict=$verdict, reps=${result.reps.size}")
        }
    }

    private fun assertScoredResult(result: SetResult) {
        val chart = checkNotNull(result.chart) { "New results must retain the recorded chart" }
        check(chart.samples.size <= 1200)
        check(chart.reps.map { it.index } == result.reps.map { it.index })
        check(result.status == "scored") { "Expected scored result, got ${result.status}: ${result.diagnostics}" }
        val wrong = checkNotNull(result.wrong)
        val meanPWrong = checkNotNull(result.meanPWrong)
        val exercise = checkNotNull(result.exercise)
        check(exercise in setOf("EAH", "EFE", "SQZ"))
        check(meanPWrong in 0.0..1.0)
        check(result.intendedExercise == null)
        check(wrong == result.reps.any { it.wrong }) { "Set verdict disagrees with the any-wrong-rep rule" }
        check(checkNotNull(result.measuredRateHz) in 95.0..105.0)
        check(result.reps.isNotEmpty())
        check(result.reps.all { it.exercise in setOf("EAH", "EFE", "SQZ") && it.pWrong in 0.0..1.0 })
        check(result.diagnostics.none { it.contains("fake", ignoreCase = true) })
    }

    private fun sixPoseCalibration(): Calibration {
        val poses = CalPose.entries.associateWith { pose ->
            FloatArray(6) { channel ->
                1500f + channel + if (pose.ordinal / 2 == channel % 3)
                    (if (pose.ordinal % 2 == 0) 300f else -300f) else 0f
            }
        }
        return Calibration.fromPoses(poses, System.currentTimeMillis())
    }

    private fun samplesFrame(id: SetId, frameIndex: Int): ByteArray {
        val firstSeq = frameIndex * SAMPLES_PER_FRAME
        val payload = ByteBuffer.allocate(9 + SAMPLES_PER_FRAME * 16).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(id.raw.toInt()).putInt(firstSeq).put(SAMPLES_PER_FRAME.toByte())
        repeat(SAMPLES_PER_FRAME) { row ->
            val seq = firstSeq + row
            val phase = 2.0 * PI * 0.4 * seq / 100.0
            val g = doubleArrayOf(
                .2 * sin(phase), .1 * cos(phase), 1 + .3 * sin(phase),
                .3 * sin(phase + .2), .2 * cos(phase + .1), 1 + .6 * sin(phase),
            )
            payload.putInt(seq * 10_000)
            g.forEachIndexed { channel, value ->
                payload.putShort((1500 + channel + 300 * value).roundToInt().toShort())
            }
        }
        return frame(0x03, payload.array())
    }

    private fun helloFrame(): ByteArray {
        val payload = ByteBuffer.allocate(27).order(ByteOrder.LITTLE_ENDIAN)
            .putShort(FW_VERSION.toShort())
            .put(byteArrayOf(0x02, 0, 0, 0, 0, 0x42))
            .put(1)
            .putInt(10_000)
            .put(6).put(3)
            .putShort(60_000.toShort()).putShort(3_000.toShort())
            .putInt(0).putInt(0)
            .array()
        return frame(0x01, payload)
    }

    private fun startedFrame(id: SetId, side: Side) = frame(0x02,
        ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN).putInt(id.raw.toInt()).put(side.name.single().code.toByte()).array())

    private fun endFrame(id: SetId, count: Int) = frame(0x04,
        ByteBuffer.allocate(9).order(ByteOrder.LITTLE_ENDIAN).putInt(id.raw.toInt()).put(EndReason.DONE.ordinal.toByte()).putInt(count).array())

    private fun frame(type: Int, payload: ByteArray): ByteArray {
        val raw = ByteArray(payload.size + 10)
        val bytes = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
            .put(0x54).put(0x59).put(1).put(type.toByte()).putShort(payload.size.toShort()).put(payload)
        bytes.putInt(CRC32().apply { update(raw, 2, payload.size + 4) }.value.toInt())
        return raw
    }

    private fun concatenate(vararg frames: ByteArray): ByteArray = ByteArrayOutputStream().use { out ->
        frames.forEach { out.write(it) }
        out.toByteArray()
    }

    private fun checkSha256(value: String, field: String) {
        check(value.matches(Regex("[0-9a-fA-F]{64}"))) { "Invalid $field in manifest" }
    }
}
