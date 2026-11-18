package com.tally.app.backend.link

import com.tally.app.contract.SetId
import com.tally.app.contract.Side
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.nio.ByteBuffer

/**
 * Feeds the exact bytes a conforming board sends through [FrameCodec]. The fixture is the output of
 * firmware/tools/frame_encoder.py, and the firmware's frame.c prints the same bytes (tools/host_check.c),
 * so a field-order or width mistake in the Python encoder, the C encoder or this codec fails here.
 */
class Esp32FixtureTest {
    private val fixture: Map<String, ByteArray> = javaClass.getResourceAsStream("/esp32-wire-v1-fixture.txt")!!
        .bufferedReader().readLines().filter { it.isNotBlank() && !it.startsWith("#") }
        .associate { line -> line.substringBefore(' ') to line.substringAfter(' ').chunked(2).map { it.toInt(16).toByte() }.toByteArray() }
    private val id = SetId(0x1234ABCDu)

    @Test fun deviceStreamParsesFieldByField() {
        val order = listOf("HELLO", "SET_STARTED", "SAMPLES", "SET_END", "HEARTBEAT")
        assertEquals(179, fixture.getValue("SAMPLES").size)
        // One TCP stream, as DeviceLink sees it: frames back to back.
        val stream = ByteBuffer.wrap(order.map(fixture::getValue).reduce(ByteArray::plus))

        val hello = FrameCodec.decode(stream) as Frame.Hello
        assertEquals(0x0102, hello.device.fwVersion)
        assertEquals("24:6F:28:AB:CD:EF", hello.device.mac)
        assertEquals(1, hello.resetReason)
        assertEquals(10_000L, hello.samplePeriodUs)
        assertEquals(6, hello.nChannels)
        assertEquals(3, hello.atten)
        assertEquals(60_000, hello.setCapacity)
        assertEquals(3_000, hello.ringCapacity)
        assertEquals(id, hello.activeSetId)
        assertEquals(1_234u, hello.activeNextSeq)

        val started = FrameCodec.decode(stream) as Frame.SetStarted
        assertEquals(id, started.id)
        assertEquals(Side.R, started.side)

        val samples = FrameCodec.decode(stream) as Frame.Samples
        assertEquals(id, samples.id)
        assertEquals(1_230u, samples.firstSeq)
        assertEquals(10, samples.count)
        for (i in 0 until 10) {
            assertEquals(12_300_000L + 10_000L * i, samples.timeUs(i))
            for (ch in 0..5) assertEquals(1_000 + 100 * ch + i, samples.millivolts(i, ch))
        }

        val end = FrameCodec.decode(stream) as Frame.SetEnd
        assertEquals(id, end.id)
        assertEquals(EndReason.TIMING, end.reason)
        assertEquals(1_240u, end.sampleCount)

        val heartbeat = FrameCodec.decode(stream) as Frame.Heartbeat
        assertEquals(123_456_789L, heartbeat.uptimeMs)
        assertEquals(17, heartbeat.ringFill)
        assertEquals(142, heartbeat.minFreeHeapKb)

        assertEquals(0, stream.remaining())
        assertNull(FrameCodec.decode(stream))
    }

    @Test fun phoneCommandsMatchTheReferenceBytes() {
        assertArrayEquals(fixture.getValue("START"), FrameCodec.encode(Command.Start(id, Side.R)))
        assertArrayEquals(fixture.getValue("STOP"), FrameCodec.encode(Command.Stop(id)))
        assertArrayEquals(fixture.getValue("ABORT"), FrameCodec.encode(Command.Abort(id)))
        assertArrayEquals(fixture.getValue("RESUME"), FrameCodec.encode(Command.Resume(id, 1_230u)))
    }
}
