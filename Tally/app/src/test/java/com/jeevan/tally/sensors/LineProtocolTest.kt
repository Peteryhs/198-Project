package com.jeevan.tally.sensors

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LineProtocolTest {
    @Test fun `rejects nonfinite numbers that would break plots and statistics`() {
        assertNull(LineProtocol.parse("A,NaN,1,2"))
        assertNull(LineProtocol.parse("G,1,Infinity,2"))
        assertNull(LineProtocol.parse("A,1,2,1e99"))
    }


    @Test
    fun `parses a well-formed accelerometer line`() {
        val reading = LineProtocol.parse("A,0.1,9.8,-0.3")
        assertEquals(LineProtocol.Reading(LineProtocol.Channel.ACCEL, 0.1f, 9.8f, -0.3f), reading)
    }

    @Test
    fun `parses a well-formed gyroscope line`() {
        val reading = LineProtocol.parse("G,1.0,2.0,3.0")
        assertEquals(LineProtocol.Reading(LineProtocol.Channel.GYRO, 1.0f, 2.0f, 3.0f), reading)
    }

    @Test
    fun `channel letter is case-insensitive`() {
        val reading = LineProtocol.parse("a,1,2,3")
        assertEquals(LineProtocol.Channel.ACCEL, reading?.channel)
    }

    @Test
    fun `trims whitespace around fields`() {
        val reading = LineProtocol.parse(" A , 1.5 , 2.5 , 3.5 ")
        assertEquals(LineProtocol.Reading(LineProtocol.Channel.ACCEL, 1.5f, 2.5f, 3.5f), reading)
    }

    @Test
    fun `rejects an unknown channel letter`() {
        assertNull(LineProtocol.parse("X,1,2,3"))
    }

    @Test
    fun `rejects a line with too few fields`() {
        assertNull(LineProtocol.parse("A,1,2"))
    }

    @Test
    fun `rejects non-numeric fields`() {
        assertNull(LineProtocol.parse("A,oops,2,3"))
    }

    @Test
    fun `rejects an empty or blank line`() {
        assertNull(LineProtocol.parse(""))
        assertNull(LineProtocol.parse("   "))
    }

    @Test
    fun `ignores extra trailing fields`() {
        // Real sketches sometimes append a checksum or sequence number; the app only needs x, y, z.
        val reading = LineProtocol.parse("A,1,2,3,999")
        assertEquals(LineProtocol.Reading(LineProtocol.Channel.ACCEL, 1f, 2f, 3f), reading)
    }
}
