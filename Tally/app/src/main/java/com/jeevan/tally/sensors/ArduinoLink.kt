package com.jeevan.tally.sensors

import com.jeevan.tally.exercise.BoardStatus
import com.jeevan.tally.exercise.Prescription
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.transform
import java.net.InetSocketAddress
import java.net.Socket
import kotlin.concurrent.thread

/** A shared Arduino TCP connection. Each connection owns its socket and generation. */
object ArduinoLink {
    enum class Status { DISCONNECTED, CONNECTING, CONNECTED, ERROR }
    private val _status = MutableStateFlow(Status.DISCONNECTED)
    val status: StateFlow<Status> = _status
    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage
    private val _plugs = MutableStateFlow(PlugSpec.legacy)
    val plugs: StateFlow<List<PlugSpec>> = _plugs

    /** Bus id for synchronized upper-arm + forearm frames, from either the CSV row or `D,arm_pair,…`. */
    const val ARM_PAIR_ID = "arm_pair"
    private val _boardStatus = MutableStateFlow<BoardStatus?>(null)
    /** Latest TALLY frame on this connection; null until the board's application layer reports. */
    val boardStatus: StateFlow<BoardStatus?> = _boardStatus
    private val _boardConfig = MutableStateFlow<Prescription?>(null)
    val boardConfig: StateFlow<Prescription?> = _boardConfig
    data class CalibrationEvent(val sequence: Int, val ok: Boolean, val detail: String)
    private val _boardCalibration = MutableStateFlow<CalibrationEvent?>(null)
    val boardCalibration: StateFlow<CalibrationEvent?> = _boardCalibration

    private val buses = mutableMapOf<String, BufferedSampleBus>()
    fun batches(id: String) = synchronized(lock) { buses.getOrPut(id) { BufferedSampleBus() } }.batches()
    fun samples(id: String) = batches(id).transform { batch -> batch.samples.forEach { emit(it) } }
    private val lock = Any()
    @Volatile private var generation = 0L
    private var socket: Socket? = null

    fun connect(host: String, port: Int) {
        if (host.isBlank() || port !in 1..65535) {
            synchronized(lock) {
                disconnect()
                _errorMessage.value = "Enter a host and a port between 1 and 65535."
                _status.value = Status.ERROR
            }
            return
        }
        val connection = Socket()
        val token = synchronized(lock) {
            generation++
            _plugs.value = PlugSpec.legacy
            _boardStatus.value = null
            _boardConfig.value = null
            buses.keys.retainAll(PlugSpec.legacy.map { it.id }.toSet() + ARM_PAIR_ID)
            runCatching { socket?.close() }
            socket = connection
            _errorMessage.value = null
            _status.value = Status.CONNECTING
            generation
        }
        thread(name = "arduino-link", isDaemon = true) {
            try {
                connection.connect(InetSocketAddress(host.trim(), port), 5000)
                val started = System.nanoTime()
                synchronized(lock) {
                    if (generation != token) return@thread
                    _status.value = Status.CONNECTED
                }
                val reader = connection.getInputStream().bufferedReader()
                var advertised = false
                while (generation == token) {
                    val line = readBoundedLine(reader) ?: break
                    val received = System.nanoTime()
                    val message = LineProtocol.parseMessage(line) ?: continue
                    synchronized(lock) {
                        if (generation != token) return@synchronized
                        when (message) {
                            is LineProtocol.Message.Plugs -> if (!advertised) {
                                _plugs.value = message.specs
                                // The exercise bus is not a catalog plug; keep its subscribers attached.
                                buses.keys.retainAll(message.specs.map { it.id }.toSet() + ARM_PAIR_ID)
                                advertised = true
                            }
                            is LineProtocol.Message.Values -> {
                                val spec = _plugs.value.find { it.id == message.id } ?: return@synchronized
                                val values = spec.interpret(message.values) ?: return@synchronized
                                val sample = SensorSample((received - started) / 1_000_000_000f,
                                    values, receivedAtNanos = received)
                                buses.getOrPut(spec.id) { BufferedSampleBus() }.publish(sample)
                            }
                            is LineProtocol.Message.PairFrame -> {
                                val sample = SensorSample((received - started) / 1_000_000_000f, message.values,
                                    receivedAtNanos = received, deviceMillis = message.deviceMillis)
                                buses.getOrPut(ARM_PAIR_ID) { BufferedSampleBus() }.publish(sample)
                            }
                            is LineProtocol.Message.Status -> _boardStatus.value = message.status
                            is LineProtocol.Message.BoardConfig -> _boardConfig.value = message.prescription
                            is LineProtocol.Message.Calibration -> _boardCalibration.value =
                                CalibrationEvent((_boardCalibration.value?.sequence ?: 0) + 1, message.ok, message.detail)
                        }
                    }
                }
                synchronized(lock) {
                    if (generation == token) {
                        _errorMessage.value = "The board closed the connection. Check Wi-Fi and reconnect."
                        _status.value = Status.ERROR
                    }
                }
            } catch (e: Exception) {
                synchronized(lock) {
                    if (generation == token) {
                        _errorMessage.value = e.message ?: "Unable to connect to the board."
                        _status.value = Status.ERROR
                    }
                }
            } finally {
                runCatching { connection.close() }
                synchronized(lock) { if (generation == token) socket = null }
            }
        }
    }
    fun disconnect() {
        synchronized(lock) {
            generation++
            runCatching { socket?.close() }
            socket = null
            _status.value = Status.DISCONNECTED
            _errorMessage.value = null
        }
    }
}

/** Refuse oversized frames before allocating an unbounded line. CRLF and LF are accepted. */
internal fun readBoundedLine(reader: java.io.Reader, limit: Int = 8192): String? {
    val result = StringBuilder()
    while (true) {
        val c = reader.read()
        if (c == -1) return if (result.isEmpty()) null else result.toString().removeSuffix("\r")
        if (c == 10) return result.toString().removeSuffix("\r")
        if (result.length >= limit) throw java.io.IOException("Board sent a frame longer than $limit characters")
        result.append(c.toChar())
    }
}
