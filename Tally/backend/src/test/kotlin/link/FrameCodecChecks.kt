package com.tally.app.backend.link

import com.tally.app.contract.SetId
import com.tally.app.contract.Side
import java.net.ProtocolException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32

internal object FrameCodecChecks {
    @JvmStatic fun main(args: Array<String>) { run(); println("FrameCodec self-check passed") }

    fun run() {
        val commands = listOf(Command.Start(SetId(0x1234u), Side.R), Command.Stop(SetId(1u)),
            Command.Abort(SetId(UInt.MAX_VALUE)), Command.Resume(SetId(4u), 60_000u))
        for (command in commands) {
            val encoded = FrameCodec.encode(command)
            val buffer = ByteBuffer.wrap(encoded)
            val decoded = FrameCodec.decode(buffer) as Frame.CommandFrame
            check(decoded.command == command && buffer.remaining() == 0)
            check(encoded[0] == 0x54.toByte() && encoded[1] == 0x59.toByte() && encoded[2] == 1.toByte())
            for (n in 0 until encoded.size) {
                val truncated = ByteBuffer.wrap(encoded.copyOf(n))
                check(FrameCodec.decode(truncated) == null && truncated.position() == 0)
            }
            val corrupt = encoded.copyOf().apply { this[6] = (this[6].toInt() xor 1).toByte() }
            rejects { FrameCodec.decode(ByteBuffer.wrap(corrupt)) }
        }
        val oversized = byteArrayOf(0x54, 0x59, 1, 3, 1, 2)
        rejects { FrameCodec.decode(ByteBuffer.wrap(oversized)) }
        rejects { FrameCodec.decode(ByteBuffer.wrap(byteArrayOf(0, 0, 1, 3, 0, 0))) }
        rejects { FrameCodec.decode(ByteBuffer.wrap(byteArrayOf(0x54, 0x59, 2, 3, 0, 0))) }

        val helloPayload = ByteBuffer.allocate(27).order(ByteOrder.LITTLE_ENDIAN)
            .putShort(42).put(byteArrayOf(0, 1, 2, 3, 4, 0xff.toByte())).put(9)
            .putInt(10_000).put(6).put(3).putShort(60_000.toShort()).putShort(3_000)
            .putInt(5).putInt(10).array()
        val hello = FrameCodec.decode(ByteBuffer.wrap(frame(1, helloPayload))) as Frame.Hello
        check(hello.device.mac == "00:01:02:03:04:FF" && hello.device.fwVersion == 42)
        check(hello.activeSetId == SetId(5u) && hello.activeNextSeq == 10u)

        val samplesPayload = ByteBuffer.allocate(9 + 16 * 10).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(7).putInt(59_990).put(10)
        for (i in 0 until 10) {
            samplesPayload.putInt(599_900_000 + i * 10_000)
            for (channel in 0..5) samplesPayload.putShort((1_000 + i * 6 + channel).toShort())
        }
        val samplesRaw = frame(3, samplesPayload.array())
        check(samplesRaw.size == 179)
        val samples = FrameCodec.decode(ByteBuffer.wrap(samplesRaw)) as Frame.Samples
        check(samples.id == SetId(7u) && samples.firstSeq == 59_990u && samples.count == 10)
        check(samples.timeUs(9) == 599_990_000L && samples.millivolts(9, 5) == 1_059)
        val malformed = samplesPayload.array().copyOf().apply { this[8] = 0 }
        rejects { FrameCodec.decode(ByteBuffer.wrap(frame(3, malformed))) }

        val endPayload = ByteBuffer.allocate(9).order(ByteOrder.LITTLE_ENDIAN).putInt(7).put(4).putInt(60_000).array()
        val heartbeatPayload = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putInt(-1).putShort(3_000).putShort(256).array()
        val startedPayload = ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN).putInt(7).put('L'.code.toByte()).array()
        val end = FrameCodec.decode(ByteBuffer.wrap(frame(4, endPayload))) as Frame.SetEnd
        check(end.reason == EndReason.RING_OVERRUN && end.sampleCount == 60_000u)
        val heartbeat = FrameCodec.decode(ByteBuffer.wrap(frame(5, heartbeatPayload))) as Frame.Heartbeat
        check(heartbeat.uptimeMs == 0xffff_ffffL && heartbeat.ringFill == 3_000 && heartbeat.minFreeHeapKb == 256)
        check((FrameCodec.decode(ByteBuffer.wrap(frame(2, startedPayload))) as Frame.SetStarted).side == Side.L)

        val payloads = listOf(1 to helloPayload, 2 to startedPayload, 3 to samplesPayload.array(),
            4 to endPayload, 5 to heartbeatPayload) + commands.map {
            val raw = FrameCodec.encode(it)
            (raw[3].toInt() and 0xff) to raw.copyOfRange(6, raw.size - 4)
        }
        for ((type, payload) in payloads) {
            rejects { FrameCodec.decode(ByteBuffer.wrap(frame(type, payload.copyOf(payload.size - 1)))) }
            rejects { FrameCodec.decode(ByteBuffer.wrap(frame(type, payload.copyOf(payload.size + 1)))) }
        }
        rejects { FrameCodec.decode(ByteBuffer.wrap(frame(1, helloPayload.copyOf().apply { this[13] = 5 }))) }
        rejects { FrameCodec.decode(ByteBuffer.wrap(frame(2, startedPayload.copyOf().apply { this[4] = 'X'.code.toByte() }))) }
        rejects { FrameCodec.decode(ByteBuffer.wrap(frame(4, endPayload.copyOf().apply { this[4] = 5 }))) }
        rejects { FrameCodec.decode(ByteBuffer.wrap(frame(6, byteArrayOf()))) }

        val start = FrameCodec.encode(commands[0])
        val joined = ByteBuffer.allocateDirect(start.size + samplesRaw.size).put(start).put(samplesRaw)
        joined.flip()
        check(FrameCodec.decode(joined) is Frame.CommandFrame)
        check(FrameCodec.decode(joined) is Frame.Samples && !joined.hasRemaining())
    }

    private fun frame(type: Int, payload: ByteArray): ByteArray {
        val raw = ByteArray(payload.size + 10)
        val bytes = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        bytes.put(0x54).put(0x59).put(1).put(type.toByte()).putShort(payload.size.toShort()).put(payload)
        bytes.putInt(CRC32().apply { update(raw, 2, payload.size + 4) }.value.toInt())
        return raw
    }

    private fun rejects(block: () -> Unit) {
        try { block(); error("Expected protocol rejection") } catch (_: ProtocolException) { }
    }
}
