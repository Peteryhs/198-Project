package com.tally.app.backend.link

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.EOFException
import java.net.InetSocketAddress
import java.net.ProtocolException
import java.net.Socket
import java.net.SocketTimeoutException
import java.nio.ByteBuffer
import javax.net.SocketFactory

internal class DeviceLink(
    private val socketFactory: SocketFactory,
    private val onFrame: (Frame) -> Unit,
    private val onLost: (String) -> Unit,
    private val endpoint: InetSocketAddress = InetSocketAddress("192.168.4.1", 5198),
) {
    private val hello = CompletableDeferred<Frame.Hello>()
    private val outbox = java.util.concurrent.LinkedBlockingQueue<ByteArray>()
    @Volatile private var socket: Socket? = null
    @Volatile private var closed = false

    suspend fun connect(): Frame.Hello {
        check(socket == null && !closed) { "DeviceLink is single-use" }
        try {
            withContext(Dispatchers.IO) {
                val opened = socketFactory.createSocket()
                socket = opened
                if (closed) { opened.close(); error("Link closed") }
                opened.tcpNoDelay = true
                opened.connect(endpoint, 3_000)
                Thread({ readFrames(opened) }, "tally-link-reader").start()
                Thread({ drainWrites(opened) }, "tally-link-writer").start()
            }
            return hello.await()
        } catch (error: Exception) {
            close()
            throw error
        }
    }

    /**
     * Queue one command frame. The socket write happens on the link's writer thread because callers
     * include the main thread, where Android throws NetworkOnMainThreadException, and a failed Start
     * used to take the recording service down with it.
     */
    fun send(command: Command) {
        val raw = FrameCodec.encode(command)
        check(!closed) { "Link is closed" }
        checkNotNull(socket) { "Link is not connected" }
        outbox.offer(raw)
    }

    private fun drainWrites(connected: Socket) {
        try {
            val output = connected.getOutputStream()
            while (!closed) {
                val raw = outbox.poll(250, java.util.concurrent.TimeUnit.MILLISECONDS) ?: continue
                output.write(raw)
                output.flush()
            }
        } catch (error: java.io.IOException) {
            if (!closed) onLost(error.message ?: "Write failed")
            closed = true
            runCatching { connected.close() }
        } catch (error: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }

    fun close() {
        closed = true
        runCatching { socket?.close() }
        hello.cancel()
    }

    private fun readFrames(connected: Socket) {
        val scratch = ByteArray(FrameCodec.MAX_FRAME_BYTES)
        var buffered = 0
        var lastFrame = System.nanoTime()
        var first = true
        try {
            val input = connected.getInputStream()
            while (!closed) {
                val remainingNs = 3_000_000_000L - (System.nanoTime() - lastFrame)
                if (remainingNs <= 0) throw SocketTimeoutException("No complete frame for 3 s")
                connected.soTimeout = ((remainingNs + 999_999) / 1_000_000).toInt().coerceAtLeast(1)
                val read = try { input.read(scratch, buffered, scratch.size - buffered) }
                catch (_: SocketTimeoutException) { continue }
                if (read < 0) throw EOFException(if (buffered == 0) "TCP disconnected" else "Truncated frame at EOF")
                buffered += read
                val bytes = ByteBuffer.wrap(scratch, 0, buffered)
                while (true) {
                    val frame = FrameCodec.decode(bytes) ?: break
                    if (first && frame !is Frame.Hello) throw ProtocolException("First frame must be HELLO")
                    if (!first && frame is Frame.Hello) throw ProtocolException("Unexpected repeated HELLO")
                    if (frame is Frame.CommandFrame) throw ProtocolException("Device sent a phone command")
                    first = false
                    lastFrame = System.nanoTime()
                    onFrame(frame)
                    if (frame is Frame.Hello) hello.complete(frame)
                }
                val consumed = bytes.position()
                scratch.copyInto(scratch, 0, consumed, buffered)
                buffered -= consumed
                if (buffered == scratch.size) throw ProtocolException("Frame buffer exhausted")
            }
        } catch (error: Exception) {
            if (!closed) {
                hello.completeExceptionally(error)
                onLost(error.message ?: error.javaClass.simpleName)
            }
        } finally {
            closed = true
            runCatching { connected.close() }
        }
    }
}
