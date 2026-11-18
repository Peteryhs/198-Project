package com.tally.app.backend.link

import com.tally.app.contract.SetId
import com.tally.app.contract.Side
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.EOFException
import java.net.InetSocketAddress
import java.net.ProtocolException
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import java.util.zip.CRC32
import javax.net.SocketFactory
import kotlin.concurrent.thread

class DeviceLinkTest {
    @Test fun readsFragmentedHelloAndCoalescedFramesThenReportsEof() = runBlocking {
        ServerSocket(0).use { server ->
            val received = CountDownLatch(2)
            val lost = CountDownLatch(1)
            val frames = java.util.Collections.synchronizedList(mutableListOf<Frame>())
            val failure = AtomicReference<String>()
            val hello = helloFrame()
            val heartbeat = frame(5, ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN)
                .putInt(123).putShort(7).putShort(256).array())
            val peer = thread {
                server.accept().use { socket ->
                    socket.getOutputStream().apply {
                        write(hello, 0, 4)
                        flush()
                        Thread.sleep(20)
                        write(hello.copyOfRange(4, hello.size) + heartbeat)
                        flush()
                    }
                }
            }
            val link = DeviceLink(
                SocketFactory.getDefault(),
                { frames += it; received.countDown() },
                { failure.set(it); lost.countDown() },
                InetSocketAddress("127.0.0.1", server.localPort),
            )
            try {
                assertEquals("01:02:03:04:05:06", link.connect().device.mac)
                assertTrue(received.await(2, TimeUnit.SECONDS))
                assertTrue(lost.await(2, TimeUnit.SECONDS))
                assertEquals(2, frames.size)
                assertTrue(frames[0] is Frame.Hello)
                assertTrue(frames[1] is Frame.Heartbeat)
                assertEquals("TCP disconnected", failure.get())
            } finally {
                link.close()
                peer.join(2_000)
            }
        }
    }

    @Test fun rejectsNonHelloAsFirstFrame() = rejectsHandshake(frame(5, ByteArray(8)), "First frame must be HELLO")

    @Test fun rejectsBadCrcBeforeDeliveringFrame() {
        val corruptHello = helloFrame().apply { this[lastIndex] = (this[lastIndex].toInt() xor 1).toByte() }
        rejectsHandshake(corruptHello, "CRC32 mismatch")
    }

    @Test fun reportsTruncatedFrameAtEof() = runBlocking {
        ServerSocket(0).use { server ->
            val lost = CountDownLatch(1)
            val reason = AtomicReference<String>()
            val peer = thread {
                server.accept().use { socket ->
                    socket.getOutputStream().write(helloFrame(), 0, 4)
                    socket.getOutputStream().flush()
                }
            }
            val link = DeviceLink(SocketFactory.getDefault(), {}, { reason.set(it); lost.countDown() },
                InetSocketAddress("127.0.0.1", server.localPort))
            try {
                try {
                    link.connect()
                    error("Expected truncated-frame failure")
                } catch (error: EOFException) {
                    assertEquals("Truncated frame at EOF", error.message)
                }
                assertTrue(lost.await(2, TimeUnit.SECONDS))
                assertEquals("Truncated frame at EOF", reason.get())
            } finally {
                link.close()
                peer.join(2_000)
            }
        }
    }

    @Test fun rejectsRepeatedHelloAndPhoneCommandFromDevice() {
        rejectsAfterHello(helloFrame(), "Unexpected repeated HELLO")
        rejectsAfterHello(FrameCodec.encode(Command.Stop(SetId(9u))), "Device sent a phone command")
    }

    @Test fun reportsSilentLinkAfterThreeSeconds() = runBlocking {
        ServerSocket(0).use { server ->
            val lost = CountDownLatch(1)
            val reason = AtomicReference<String>()
            val peer = thread {
                server.accept().use { socket ->
                    socket.getOutputStream().write(helloFrame())
                    socket.getOutputStream().flush()
                    Thread.sleep(4_000)
                }
            }
            val link = DeviceLink(SocketFactory.getDefault(), {}, { reason.set(it); lost.countDown() },
                InetSocketAddress("127.0.0.1", server.localPort))
            try {
                link.connect()
                val started = System.nanoTime()
                assertTrue(lost.await(5, TimeUnit.SECONDS))
                val elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started)
                assertTrue("timeout fired too early: ${elapsedMs}ms", elapsedMs >= 2_500)
                assertEquals("No complete frame for 3 s", reason.get())
            } finally {
                link.close()
                peer.join(2_000)
            }
        }
    }

    @Test fun sendsExactEncodedPhoneCommands() = runBlocking {
        ServerSocket(0).use { server ->
            val commands = listOf(
                Command.Start(SetId(0x1234u), Side.R),
                Command.Stop(SetId(0x1234u)),
                Command.Abort(SetId(0x1234u)),
                Command.Resume(SetId(0x1234u), 17u),
            )
            val expected = ByteArrayOutputStream().apply { commands.forEach { write(FrameCodec.encode(it)) } }.toByteArray()
            val captured = AtomicReference<ByteArray>()
            val peer = thread {
                server.accept().use { socket ->
                    socket.getOutputStream().write(helloFrame())
                    socket.getOutputStream().flush()
                    captured.set(readExactly(socket, expected.size))
                }
            }
            val link = DeviceLink(SocketFactory.getDefault(), {}, {}, InetSocketAddress("127.0.0.1", server.localPort))
            try {
                link.connect()
                commands.forEach(link::send)
                peer.join(2_000)
                assertTrue(!peer.isAlive)
                assertArrayEquals(expected, captured.get())
            } finally {
                link.close()
                peer.join(2_000)
            }
        }
    }

    private fun rejectsHandshake(packet: ByteArray, expected: String) = runBlocking {
        ServerSocket(0).use { server ->
            val lost = CountDownLatch(1)
            val reason = AtomicReference<String>()
            val peer = thread {
                server.accept().use { socket ->
                    socket.getOutputStream().write(packet)
                    socket.getOutputStream().flush()
                }
            }
            val link = DeviceLink(SocketFactory.getDefault(), {}, { reason.set(it); lost.countDown() },
                InetSocketAddress("127.0.0.1", server.localPort))
            try {
                try {
                    link.connect()
                    error("Expected handshake rejection")
                } catch (error: ProtocolException) {
                    assertEquals(expected, error.message)
                }
                assertTrue(lost.await(2, TimeUnit.SECONDS))
                assertEquals(expected, reason.get())
            } finally {
                link.close()
                peer.join(2_000)
            }
        }
    }

    private fun rejectsAfterHello(nextFrame: ByteArray, expected: String) = runBlocking {
        ServerSocket(0).use { server ->
            val lost = CountDownLatch(1)
            val reason = AtomicReference<String>()
            val peer = thread {
                server.accept().use { socket ->
                    socket.getOutputStream().write(helloFrame() + nextFrame)
                    socket.getOutputStream().flush()
                }
            }
            val link = DeviceLink(SocketFactory.getDefault(), {}, { reason.set(it); lost.countDown() },
                InetSocketAddress("127.0.0.1", server.localPort))
            try {
                assertEquals("01:02:03:04:05:06", link.connect().device.mac)
                assertTrue(lost.await(2, TimeUnit.SECONDS))
                assertEquals(expected, reason.get())
            } finally {
                link.close()
                peer.join(2_000)
            }
        }
    }

    private fun readExactly(socket: Socket, size: Int): ByteArray {
        val result = ByteArray(size)
        var offset = 0
        while (offset < size) {
            val count = socket.getInputStream().read(result, offset, size - offset)
            check(count >= 0) { "EOF before all commands arrived" }
            offset += count
        }
        return result
    }

    private fun helloFrame(): ByteArray {
        val payload = ByteBuffer.allocate(27).order(ByteOrder.LITTLE_ENDIAN)
            .putShort(1).put(byteArrayOf(1, 2, 3, 4, 5, 6)).put(0)
            .putInt(10_000).put(6).put(3).putShort(60_000.toShort()).putShort(3_000)
            .putInt(0).putInt(0).array()
        return frame(1, payload)
    }

    private fun frame(type: Int, payload: ByteArray): ByteArray {
        val raw = ByteArray(payload.size + 10)
        ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
            .put(0x54).put(0x59).put(1).put(type.toByte()).putShort(payload.size.toShort()).put(payload)
        val crc = CRC32().apply { update(raw, 2, payload.size + 4) }.value.toInt()
        ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN).putInt(payload.size + 6, crc)
        return raw
    }
}
