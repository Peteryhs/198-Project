package com.tally.app.backend.link

import com.tally.app.contract.DeviceInfo
import com.tally.app.contract.SetId
import com.tally.app.contract.Side
import java.net.ProtocolException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32

internal enum class EndReason { DONE, ABORTED, OVERFLOW, TIMING, RING_OVERRUN }

internal sealed interface Command {
    val id: SetId
    data class Start(override val id: SetId, val side: Side) : Command
    data class Stop(override val id: SetId) : Command
    data class Abort(override val id: SetId) : Command
    data class Resume(override val id: SetId, val nextSeq: UInt) : Command
}

internal sealed interface Frame {
    val raw: ByteArray
    data class Hello(
        val device: DeviceInfo, val resetReason: Int, val samplePeriodUs: Long,
        val nChannels: Int, val atten: Int, val setCapacity: Int, val ringCapacity: Int,
        val activeSetId: SetId, val activeNextSeq: UInt, override val raw: ByteArray,
    ) : Frame
    data class SetStarted(val id: SetId, val side: Side, override val raw: ByteArray) : Frame
    class Samples(
        val id: SetId, val firstSeq: UInt, val count: Int, override val raw: ByteArray,
    ) : Frame {
        private val bytes = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        fun timeUs(index: Int): Long {
            require(index in 0 until count)
            return bytes.getInt(15 + index * 16).toLong() and 0xffff_ffffL
        }
        fun millivolts(index: Int, channel: Int): Int {
            require(index in 0 until count && channel in 0..5)
            return bytes.getShort(19 + index * 16 + channel * 2).toInt() and 0xffff
        }
    }
    data class SetEnd(val id: SetId, val reason: EndReason, val sampleCount: UInt, override val raw: ByteArray) : Frame
    data class Heartbeat(val uptimeMs: Long, val ringFill: Int, val minFreeHeapKb: Int, override val raw: ByteArray) : Frame
    data class CommandFrame(val command: Command, override val raw: ByteArray) : Frame
}

internal object FrameCodec {
    const val MAX_FRAME_BYTES = 522

    // Incomplete input is left untouched, so callers can append the next TCP read.
    fun decode(buf: ByteBuffer): Frame? {
        if (buf.remaining() < 6) return null
        val start = buf.position()
        val header = buf.duplicate().order(ByteOrder.LITTLE_ENDIAN)
        protocol(header.get().toInt() == 0x54 && header.get().toInt() == 0x59, "Bad magic")
        protocol(header.get().toInt() == 1, "Unsupported version")
        val type = header.get().toInt() and 0xff
        val length = header.short.toInt() and 0xffff
        protocol(length <= 512, "Payload exceeds 512 bytes")
        if (buf.remaining() < length + 10) return null
        val raw = ByteArray(length + 10)
        buf.duplicate().get(raw)
        val bytes = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        val crc = CRC32().apply { update(raw, 2, length + 4) }.value
        protocol(crc == (bytes.getInt(length + 6).toLong() and 0xffff_ffffL), "CRC32 mismatch")
        bytes.position(6)
        fun exact(n: Int) = protocol(length == n, "Invalid payload length for type $type")
        fun id(): SetId = SetId(bytes.int.toUInt()).also { protocol(it.raw != 0u, "Zero set id") }
        fun side(): Side = when (bytes.get().toInt()) {
            'L'.code -> Side.L
            'R'.code -> Side.R
            else -> throw ProtocolException("Invalid side")
        }
        val frame = when (type) {
            0x01 -> {
                exact(27)
                val fw = bytes.short.toInt() and 0xffff
                val mac = (0..5).joinToString(":") { "%02X".format(bytes.get().toInt() and 0xff) }
                val reset = bytes.get().toInt() and 0xff
                val period = bytes.int.toLong() and 0xffff_ffffL
                val channels = bytes.get().toInt() and 0xff
                val atten = bytes.get().toInt() and 0xff
                val setCap = bytes.short.toInt() and 0xffff
                val ringCap = bytes.short.toInt() and 0xffff
                val activeId = SetId(bytes.int.toUInt())
                val next = bytes.int.toUInt()
                protocol(period == 10_000L && channels == 6 && setCap == 60_000 && ringCap == 3_000,
                    "HELLO does not match ESP32-WIRE-V1")
                protocol(next <= 60_000u && (activeId.raw != 0u || next == 0u), "Invalid active set in HELLO")
                Frame.Hello(DeviceInfo(mac, fw, "esp_reset_reason=$reset"), reset, period, channels,
                    atten, setCap, ringCap, activeId, next, raw)
            }
            0x02 -> { exact(5); Frame.SetStarted(id(), side(), raw) }
            0x03 -> {
                protocol(length >= 9, "Short SAMPLES payload")
                val setId = id()
                val seq = bytes.int.toUInt()
                val count = bytes.get().toInt() and 0xff
                protocol(count in 1..10 && length == 9 + 16 * count, "Invalid SAMPLES count")
                protocol(seq < 60_000u && seq.toLong() + count <= 60_000, "SAMPLES exceeds set capacity")
                Frame.Samples(setId, seq, count, raw)
            }
            0x04 -> {
                exact(9)
                val setId = id()
                val reason = bytes.get().toInt() and 0xff
                protocol(reason in EndReason.entries.indices, "Invalid SET_END reason")
                val count = bytes.int.toUInt()
                protocol(count <= 60_000u, "SET_END exceeds set capacity")
                Frame.SetEnd(setId, EndReason.entries[reason], count, raw)
            }
            0x05 -> {
                exact(8)
                val uptime = bytes.int.toLong() and 0xffff_ffffL
                val fill = bytes.short.toInt() and 0xffff
                val heap = bytes.short.toInt() and 0xffff
                protocol(fill <= 3_000, "HEARTBEAT ring exceeds capacity")
                Frame.Heartbeat(uptime, fill, heap, raw)
            }
            0x81 -> { exact(5); Frame.CommandFrame(Command.Start(id(), side()), raw) }
            0x82 -> { exact(4); Frame.CommandFrame(Command.Stop(id()), raw) }
            0x83 -> { exact(4); Frame.CommandFrame(Command.Abort(id()), raw) }
            0x84 -> {
                exact(8)
                val setId = id()
                val next = bytes.int.toUInt()
                protocol(next <= 60_000u, "RESUME exceeds set capacity")
                Frame.CommandFrame(Command.Resume(setId, next), raw)
            }
            else -> throw ProtocolException("Unknown frame type $type")
        }
        buf.position(start + raw.size)
        return frame
    }

    fun encode(c: Command): ByteArray {
        require(c.id.raw != 0u) { "Zero set id" }
        val type = when (c) { is Command.Start -> 0x81; is Command.Stop -> 0x82; is Command.Abort -> 0x83; is Command.Resume -> 0x84 }
        val length = when (c) { is Command.Start -> 5; is Command.Resume -> 8; else -> 4 }
        val raw = ByteArray(length + 10)
        val bytes = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        bytes.put(0x54).put(0x59).put(1).put(type.toByte()).putShort(length.toShort()).putInt(c.id.raw.toInt())
        when (c) {
            is Command.Start -> bytes.put(c.side.name.single().code.toByte())
            is Command.Resume -> { require(c.nextSeq <= 60_000u); bytes.putInt(c.nextSeq.toInt()) }
            else -> Unit
        }
        bytes.putInt(CRC32().apply { update(raw, 2, length + 4) }.value.toInt())
        return raw
    }

    private fun protocol(valid: Boolean, reason: String) {
        if (!valid) throw ProtocolException(reason)
    }
}
