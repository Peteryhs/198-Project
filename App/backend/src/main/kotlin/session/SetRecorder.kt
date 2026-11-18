package com.tally.app.backend.session

import com.tally.app.backend.calib.Calibration
import com.tally.app.backend.link.Frame
import com.tally.app.backend.link.FrameCodec
import com.tally.app.backend.store.SetRepository
import com.tally.app.contract.SetId
import com.tally.app.contract.Side
import org.json.JSONObject
import java.nio.ByteBuffer

/** One contiguous set. Caller serializes control and reader callbacks on its monitor. */
internal class SetRecorder(
    val id: SetId,
    val side: Side,
    val calibration: Calibration,
    val metadata: JSONObject,
    private val repository: SetRepository?,
    private val live: LiveRing?,
) {
    val store = SampleStore()
    private val sampleG = FloatArray(6)
    private var started = false
    var ended = false
        private set
    // Derived duration gate: 4 × minimum 1.2 s peak spacing × 100 Hz; Python validates cycles.
    val partialScorable: Boolean get() = store.size >= 480 && !ended && !metadata.has("end_reason") &&
        metadata.optBoolean("partial_scorable", !metadata.has("failure"))

    init { repository?.create(id, metadata) }

    fun replay(archive: ByteArray, allowIncomplete: Boolean = false) {
        val bytes = ByteBuffer.wrap(archive)
        while (bytes.hasRemaining()) {
            val frame = FrameCodec.decode(bytes) ?: if (!ended &&
                (allowIncomplete || metadata.optBoolean("partial", false))) {
                metadata.put("archive_truncated_tail", true)
                break
            } else error("Truncated archived frame")
            accept(frame)
        }
    }

    fun accept(frame: Frame) {
        check(!ended) { "Frame after SET_END" }
        when (frame) {
            is Frame.SetStarted -> {
                check(!started && frame.id == id && frame.side == side) { "SET_STARTED mismatch" }
                started = true
            }
            is Frame.Samples -> {
                check(started && frame.id == id && frame.firstSeq.toLong() == store.size.toLong()) { "Sample sequence break" }
                // Validate the whole frame before committing any of it to memory or disk.
                var previous = if (store.size == 0) -1L else store.timestampUs(store.size - 1)
                var previousMs = if (previous < 0) -1L else previous / 1000
                repeat(frame.count) { i ->
                    val time = frame.timeUs(i)
                    // TallyWireWriter truncates to milliseconds, so emitted timestamps must stay distinct too.
                    check(time > previous && time / 1000 > previousMs && time <= 610_000_000L &&
                        (previous < 0 || time - previous <= 15_000L)) {
                        "Sample timing violation"
                    }
                    repeat(6) { ch -> check(frame.millivolts(i, ch) <= 3300) { "ADC millivolts outside supply range" } }
                    previous = time
                    previousMs = time / 1000
                }
                check(store.size + frame.count <= 60_000) { "Set capacity exceeded" }
                // The mV → g boundary: nothing downstream of this line (store, live trace, model) sees mV.
                repeat(frame.count) { i ->
                    repeat(6) { ch -> sampleG[ch] = calibration.toG(frame.millivolts(i, ch), ch) }
                    store.append(frame.timeUs(i), sampleG)
                    live?.append(sampleG)
                }
                live?.publishFrame()
            }
            is Frame.SetEnd -> {
                check(started && frame.id == id && frame.sampleCount.toLong() == store.size.toLong()) { "SET_END count mismatch" }
                ended = true
            }
            else -> error("Unexpected set frame")
        }
        repository?.appendFrame(id, frame.raw)
        if (ended) {
            metadata.put("end_reason", (frame as Frame.SetEnd).reason.name)
            repository?.finishFrames(id)
            repository?.updateMeta(id, metadata)
        }
    }

    fun closeIncomplete(reason: String) {
        ended = true
        metadata.put("failure", reason)
        repository?.finishFrames(id)
        repository?.updateMeta(id, metadata)
    }
}
