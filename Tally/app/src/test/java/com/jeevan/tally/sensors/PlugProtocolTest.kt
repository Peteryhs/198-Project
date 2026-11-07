package com.jeevan.tally.sensors

import org.junit.Assert.*
import org.junit.Test
import java.io.StringReader

class PlugProtocolTest {
    @Test fun `short handshake supports legacy aliases and an unknown scalar`() {
        val m = LineProtocol.parseMessage("PLUGS,accel:3,gyro:3,temp:1\r\n") as LineProtocol.Message.Plugs
        assertEquals(listOf("accelerometer", "gyroscope", "temp"), m.specs.map { it.id })
        assertEquals(listOf("value"), m.specs.last().outputAxes)
        assertEquals("raw", m.specs.last().unit)
        assertEquals(4, m.specs.first().outputAxes.size)
    }
    @Test fun `metadata provides labels units range kind and icon without Android`() {
        val m = LineProtocol.parseMessage("PLUGS,temp:1:scalar:°C:Temperature:temperature:-40:125:temperature") as LineProtocol.Message.Plugs
        val spec = m.specs.single()
        assertEquals("Temperature", spec.displayName)
        assertEquals("°C", spec.unit)
        assertEquals(-40f, spec.minimum!!, 0f)
        assertEquals("temperature", spec.icon)
    }
    @Test fun `invalid catalogs are rejected atomically`() {
        listOf("PLUGS", "PLUGS,a:3,accel:3", "PLUGS,temp:0", "PLUGS,temp:17", "PLUGS,temp:1:boolean::T:a|b",
            "PLUGS,temp:1:unknown", "PLUGS,../temp:1", "PLUGS,temp:1:scalar:::value:NaN:1",
            "PLUGS,temp:1:scalar:::value:5:1").forEach { assertNull(it, LineProtocol.parseMessage(it)) }
    }
    @Test fun `generic values retain arbitrary dimensions and reject nonfinite payloads`() {
        val m = LineProtocol.parseMessage("D,force,1,2,3,4,5,6") as LineProtocol.Message.Values
        assertEquals(6, m.values.size)
        assertEquals("force", m.id)
        assertNull(LineProtocol.parseMessage("D,temp,NaN"))
        assertNull(LineProtocol.parseMessage("D,temp,Infinity"))
        assertNull(LineProtocol.parseMessage("D,temp"))
    }
    @Test fun `interpretation checks dimensions boolean values and derived magnitude`() {
        assertArrayEquals(floatArrayOf(3f, 4f, 0f, 5f), PlugSpec.accel.interpret(listOf(3f, 4f, 0f)), 0f)
        assertNull(PlugSpec.accel.interpret(listOf(1f)))
        val flag = PlugSpec("contact", "Contact", listOf("state"), kind = ValueKind.BOOLEAN)
        assertArrayEquals(floatArrayOf(1f), flag.interpret(listOf(1f)), 0f)
        assertNull(flag.interpret(listOf(2f)))
    }
    @Test fun `legacy reading remains compatible with trailing fields`() {
        val m = LineProtocol.parseMessage("A,1,2,3,checksum") as LineProtocol.Message.Values
        assertEquals("accelerometer", m.id)
        assertEquals(listOf(1f, 2f, 3f), m.values)
    }
    @Test fun `line reader bounds memory accepts crlf and handles eof`() {
        val reader = StringReader("D,t,1\r\nD,t,2")
        assertEquals("D,t,1", readBoundedLine(reader))
        assertEquals("D,t,2", readBoundedLine(reader))
        assertNull(readBoundedLine(reader))
        assertThrows(java.io.IOException::class.java) { readBoundedLine(StringReader("123456"), 5) }
    }
}
