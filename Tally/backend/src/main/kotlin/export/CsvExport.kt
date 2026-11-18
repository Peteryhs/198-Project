package com.tally.app.backend.export

import android.content.Context
import android.net.Uri
import com.tally.app.backend.link.Frame
import com.tally.app.backend.link.FrameCodec
import com.tally.app.backend.store.SetRepository
import com.tally.app.contract.SetId
import java.io.File
import java.nio.ByteBuffer

internal class CsvExport(private val context: Context, private val repository: SetRepository) {
    fun export(id: SetId): String {
        val metadata = checkNotNull(repository.meta(id)) { "Unknown set" }
        val frames = ByteBuffer.wrap(repository.frames(id))
        val directory = File(context.cacheDir, "exports").apply { check(isDirectory || mkdirs()) }
        val file = File(directory, "${id.raw}.csv")
        val temporary = File.createTempFile("${id.raw}-", ".csv.tmp", directory)
        try {
            temporary.bufferedWriter().use { out ->
                out.append("# meta=").append(metadata.toString()).append('\n')
                val resultFile = File(context.filesDir, "sets/${id.raw}/result.json")
                if (resultFile.isFile) out.append("# result=").append(resultFile.readText()).append('\n')
                writeSamples(id, metadata.getString("side"), frames, out, metadata.optBoolean("partial", false))
            }
            check(temporary.renameTo(file)) { "Cannot write CSV" }
        } finally { temporary.delete() }
        return Uri.Builder().scheme("content").authority(context.packageName + ".exports")
            .appendPath(file.name).build().toString()
    }
    companion object {
        internal fun writeSamples(id: SetId, side: String, frames: ByteBuffer, out: Appendable, allowIncomplete: Boolean = false) {
            require(side == "L" || side == "R")
            out.append("set_id,side,seq,t_us,upper_x_mv,upper_y_mv,upper_z_mv,forearm_x_mv,forearm_y_mv,forearm_z_mv\n")
            var nextSeq = 0u
            var lastTime = -1L
            var started = false
            var ended = false
            while (frames.hasRemaining()) {
                check(!ended) { "Saved frame after SET_END" }
                val frame = FrameCodec.decode(frames)
                if (frame == null) {
                    check(allowIncomplete && started) { "Truncated saved frame" }
                    break
                }
                when (frame) {
                    is Frame.SetStarted -> {
                        check(!started && frame.id == id && frame.side.name == side) { "Saved SET_STARTED mismatch" }
                        started = true
                    }
                    is Frame.SetEnd -> {
                        check(started && frame.id == id && frame.sampleCount == nextSeq) { "Saved SET_END mismatch" }
                        ended = true
                    }
                    is Frame.Samples -> {
                        check(started && frame.id == id && frame.firstSeq == nextSeq) { "Saved sample sequence gap" }
                        repeat(frame.count) { sample ->
                            val tUs = frame.timeUs(sample)
                            check(tUs > lastTime) { "Saved timestamp is not increasing" }
                            lastTime = tUs
                            out.append(id.raw.toString()).append(',').append(side)
                                .append(',').append(nextSeq.toString()).append(',').append(tUs.toString())
                            repeat(6) { channel -> out.append(',').append(frame.millivolts(sample, channel).toString()) }
                            out.append('\n')
                            nextSeq++
                        }
                    }
                    else -> error("Unexpected saved set frame")
                }
            }
        }
    }
}
