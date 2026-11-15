package com.jeevan.tally.sensors

import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import java.net.ServerSocket
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first

class ArduinoLinkTest {
    @Test fun `firmware stream reaches the exercise bus without a plug advertisement`() = runBlocking {
        ServerSocket(0).use { server ->
            server.soTimeout = 3000
            ArduinoLink.connect("127.0.0.1", server.localPort)
            server.accept().use { client ->
                awaitStatus(ArduinoLink.Status.CONNECTED)
                val reading = async(start = CoroutineStart.UNDISPATCHED) {
                    withTimeout(3000) { ArduinoLink.samples("arm_pair").first() }
                }
                client.getOutputStream().write(
                    "#TALLY2 fs=100 unit=g range=3 side=L\nS 42 420 1 2 3 0.1 0.2 0.3\n".toByteArray()
                )
                client.getOutputStream().flush()
                val sample = reading.await()
                assertEquals(420L, sample.deviceMillis)
                assertArrayEquals(floatArrayOf(1f, 2f, 3f, 0.1f, 0.2f, 0.3f), sample.values, 0f)
            }
        }
    }

    @After fun disconnect() { ArduinoLink.disconnect() }
    private fun awaitStatus(status: ArduinoLink.Status) {
        val deadline = System.nanoTime() + 3_000_000_000L
        while (ArduinoLink.status.value != status && System.nanoTime() < deadline) Thread.sleep(10)
        assertEquals(status, ArduinoLink.status.value)
    }
    @Test fun `cancelled connection cannot overwrite disconnected status`() {
        ServerSocket(0).use { server ->
            ArduinoLink.connect("127.0.0.1", server.localPort)
            server.soTimeout = 3000
            server.accept().use {
                awaitStatus(ArduinoLink.Status.CONNECTED)
                ArduinoLink.disconnect()
                Thread.sleep(100)
                assertEquals(ArduinoLink.Status.DISCONNECTED, ArduinoLink.status.value)
                assertNull(ArduinoLink.errorMessage.value)
            }
        }
    }
    @Test fun `replacing a connection does not let old worker close new socket`() {
        ServerSocket(0).use { first -> ServerSocket(0).use { second ->
            first.soTimeout = 3000; second.soTimeout = 3000
            ArduinoLink.connect("127.0.0.1", first.localPort)
            first.accept().use {
                awaitStatus(ArduinoLink.Status.CONNECTED)
                ArduinoLink.connect("127.0.0.1", second.localPort)
                second.accept().use { current ->
                    awaitStatus(ArduinoLink.Status.CONNECTED)
                    Thread.sleep(100)
                    assertEquals(ArduinoLink.Status.CONNECTED, ArduinoLink.status.value)
                    current.getOutputStream().write("A,1,2,3\n".toByteArray())
                    current.getOutputStream().flush()
                    Thread.sleep(30)
                    assertEquals(ArduinoLink.Status.CONNECTED, ArduinoLink.status.value)
                }
            }
        } }
    }

    @Test fun `advertised scalar routes by id and reconnect restores legacy catalog`() = runBlocking {
        ServerSocket(0).use { server ->
            server.soTimeout = 3000
            ArduinoLink.connect("127.0.0.1", server.localPort)
            server.accept().use { client ->
                awaitStatus(ArduinoLink.Status.CONNECTED)
                client.getOutputStream().write("PLUGS,temp:1:scalar:degC:Temperature\n".toByteArray())
                client.getOutputStream().flush()
                withTimeout(3000) { ArduinoLink.plugs.first { it.singleOrNull()?.id == "temp" } }
                val reading = async(start = CoroutineStart.UNDISPATCHED) { withTimeout(3000) { ArduinoLink.samples("temp").first() } }
                client.getOutputStream().write("D,temp,23.5\n".toByteArray())
                client.getOutputStream().flush()
                assertArrayEquals(floatArrayOf(23.5f), reading.await().values, 0f)
                ArduinoLink.disconnect()
            }
            ArduinoLink.connect("127.0.0.1", server.localPort)
            server.accept().use {
                awaitStatus(ArduinoLink.Status.CONNECTED)
                assertEquals(PlugSpec.legacy, ArduinoLink.plugs.value)
            }
        }
    }
}
