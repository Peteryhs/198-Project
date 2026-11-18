package com.tally.app.backend.session

import com.tally.app.backend.calib.Calibration
import com.tally.app.backend.calib.CalibrationStore
import com.tally.app.backend.link.EndReason
import com.tally.app.backend.link.Frame
import com.tally.app.backend.link.FrameCodec
import com.tally.app.backend.score.TallyWireWriter
import com.tally.app.contract.SetId
import com.tally.app.contract.Side
import com.tally.app.contract.CalPose
import java.io.File
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import org.json.JSONObject

internal object RecorderChecks {
    private val id = SetId(7u)
    @JvmStatic fun main(args: Array<String>) {
        checkCalibration()
        checkArchives()
        val ring = LiveRing()
        val calibration = Calibration.nominal()
        val recorder = SetRecorder(id, Side.L, calibration, JSONObject(), null, ring)
        recorder.accept(start())
        repeat(6_000) { recorder.accept(samples(it * 10)) }
        recorder.accept(end(60_000))
        check(recorder.ended && recorder.store.size == 60_000)
        check(recorder.store.timestampUs(59_999) == 599_990_000L)
        check(recorder.calibration === calibration && ring.version.value == 6_000L)
        val latest = FloatArray(1_000 * 6)
        check(ring.copyLatest(latest, 1_000) == 1_000)
        check(latest[0] == recorder.store.g(59_000, 0))
        val wire = StringBuilder()
        TallyWireWriter.write(Side.L, recorder.store, EndReason.DONE, wire)
        args.firstOrNull()?.let { File(it).writeText(wire.toString()) }
        expectFailure { recorder.accept(end(60_000)) }

        val prefix = SetRecorder(id, Side.L, calibration, JSONObject(), null, null)
        expectFailure { prefix.accept(samples(0)) }
        prefix.accept(start())
        prefix.accept(samples(0))
        expectFailure { prefix.accept(samples(0)) }
        expectFailure { prefix.accept(samples(11)) }
        expectFailure { prefix.accept(samples(10, timestampOffset = 20_000)) }
        check(prefix.store.size == 10) // Failed frames never commit a partial tail.
        expectFailure { prefix.accept(end(9)) }
        prefix.accept(end(10))

        val subMillisecond = SetRecorder(id, Side.L, calibration, JSONObject(), null, null)
        subMillisecond.accept(start())
        expectFailure { subMillisecond.accept(samples(0, timestampStepUs = 500)) }
        check(subMillisecond.store.size == 0) // Distinct microseconds can collapse to duplicate TALLY2 milliseconds.
        println("RecorderChecks derived fixture: 60000 contiguous calibrated samples; malformed frames rejected")
    }

    private fun expectFailure(block: () -> Unit) {
        check(runCatching(block).isFailure)
    }
    private fun checkArchives() {
        fun recorder(meta: JSONObject = JSONObject()) =
            SetRecorder(id, Side.L, Calibration.nominal(), meta, null, null)
        val prefix = ByteArrayOutputStream().apply {
            write(start().raw)
            repeat(48) { write(samples(it * 10).raw) }
        }.toByteArray()
        val complete = prefix + end(480).raw
        val interrupted = recorder().apply { replay(prefix) }
        check(interrupted.partialScorable && interrupted.store.size == 480)
        check(!recorder(JSONObject().put("failure", "Sample timing violation"))
            .apply { replay(prefix) }.partialScorable)
        check(!recorder(JSONObject().put("partial_scorable", false))
            .apply { replay(prefix) }.partialScorable)
        check(recorder(JSONObject().put("failure", "partial_device_lost").put("partial_scorable", true))
            .apply { replay(prefix) }.partialScorable)
        for (reason in 0..4) {
            val finished = recorder().apply { replay(prefix + end(480, reason).raw) }
            check(finished.ended && !finished.partialScorable)
        }
        val truncated = prefix + samples(480).raw.copyOf(20)
        expectFailure { recorder().replay(truncated) }
        val partial = recorder().apply { replay(truncated, true) }
        check(partial.partialScorable && partial.store.size == 480)
        check(partial.metadata.getBoolean("archive_truncated_tail"))
        check(recorder(JSONObject().put("partial", true)).apply { replay(truncated) }.partialScorable)
        val corrupt = prefix.copyOf().also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }
        expectFailure { recorder().replay(corrupt, true) }
        expectFailure { recorder().replay(complete + end(480).raw, true) }
        expectFailure { recorder().replay(complete + samples(480).raw.copyOf(20), true) }
        val gap = start().raw + samples(0).raw + samples(20).raw
        expectFailure { recorder().replay(gap, true) }
    }
    private fun checkCalibration() {
        val poses = CalPose.entries.associateWith { pose ->
            FloatArray(6) { channel ->
                1500f + channel + if (pose.ordinal / 2 == channel % 3)
                    (if (pose.ordinal % 2 == 0) 300f else -300f) else 0f
            }
        }
        val calibrated = Calibration.fromPoses(poses, 123)
        check(calibrated.info.id == "six-pose-123" && !calibrated.info.nominal)
        repeat(6) { check(calibrated.toG(1800 + it, it) == 1f) }
        val restored = CalibrationStore.fromJson(CalibrationStore.toJson(calibrated))
        check(restored.info == calibrated.info)
        check(restored.offsetMv.contentEquals(calibrated.offsetMv))
        check(restored.mvPerG.contentEquals(calibrated.mvPerG))
        val implausibleOffset = CalibrationStore.toJson(calibrated)
        implausibleOffset.getJSONArray("offset_mv").put(0, 2501.0)
        expectFailure { CalibrationStore.fromJson(implausibleOffset) }
        val tinyScale = CalibrationStore.toJson(calibrated)
        tinyScale.getJSONArray("mv_per_g").put(0, 0.01)
        expectFailure { CalibrationStore.fromJson(tinyScale) }
        expectFailure { Calibration.fromPoses(emptyMap(), 0) }
        expectFailure { Calibration.fromPoses(poses - CalPose.X_POS, 0) }
        expectFailure { Calibration.fromPoses(CalPose.entries.associateWith { FloatArray(6) { 1500f } }, 0) }
        val invalid = poses.mapValues { it.value.copyOf() }
        invalid.getValue(CalPose.X_POS)[0] = Float.NaN
        expectFailure { Calibration.fromPoses(invalid, 0) }
    }
    private fun start(): Frame = frame(2, ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN)
        .putInt(id.raw.toInt()).put('L'.code.toByte()).array())
    private fun end(count: Int, reason: Int = 0): Frame = frame(4, ByteBuffer.allocate(9).order(ByteOrder.LITTLE_ENDIAN)
        .putInt(id.raw.toInt()).put(reason.toByte()).putInt(count).array())
    private fun samples(first: Int, timestampOffset: Int = 0, timestampStepUs: Int = 10_000): Frame {
        val payload = ByteBuffer.allocate(169).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(id.raw.toInt()).putInt(first).put(10)
        repeat(10) { index ->
            val seq = first + index
            val phase = 2 * Math.PI * 0.4 * seq / 100
            val values = doubleArrayOf(.2 * sin(phase), .1 * cos(phase), 1 + .3 * sin(phase),
                .3 * sin(phase + .2), .2 * cos(phase + .1), 1 + .6 * sin(phase))
            payload.putInt(seq * timestampStepUs + timestampOffset)
            values.forEach { payload.putShort((1650 + 330 * it).roundToInt().toShort()) }
        }
        return frame(3, payload.array())
    }
    private fun frame(type: Int, payload: ByteArray): Frame {
        val raw = ByteArray(payload.size + 10)
        val bytes = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
            .put(0x54).put(0x59).put(1).put(type.toByte()).putShort(payload.size.toShort()).put(payload)
        bytes.putInt(CRC32().apply { update(raw, 2, payload.size + 4) }.value.toInt())
        return checkNotNull(FrameCodec.decode(ByteBuffer.wrap(raw)))
    }
}
