package com.jeevan.tally.recording

import androidx.compose.runtime.*
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jeevan.tally.sensors.ArduinoLink
import com.jeevan.tally.sensors.SensorSample
import com.jeevan.tally.sensors.SensorStream
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.StateFlow

/** One navigation-scoped session. Survives rotation; acquisition is paused in the background. */
class ExperimentSession(
    private val nowMillis: () -> Long = { System.nanoTime() / 1_000_000 },
    private val connectionStatus: StateFlow<ArduinoLink.Status> = ArduinoLink.status,
) : ViewModel() {
    var recordingSpec: com.jeevan.tally.sensors.PlugSpec? = null
    val samples = mutableStateListOf<SensorSample>()
    var running by mutableStateOf(false); private set
    var countdown by mutableStateOf(0); private set
    var elapsed by mutableStateOf(0f); private set
    var duration by mutableStateOf(0)
    var startDelay by mutableStateOf(0)
    var message by mutableStateOf<String?>(null)
    var dirty by mutableStateOf(false); private set
    var busy by mutableStateOf(false); private set
    var savedName by mutableStateOf<String?>(null); private set
    var loadedId: String? = null; private set
    var loadAttempted = false; private set
    var droppedSamples by mutableStateOf(0L); private set
    var lastReceived by mutableStateOf(0f); private set
    private var acquisition: Job? = null
    private var clock: Job? = null
    private var segment = 0
    private var offset = 0f
    private var started = 0L
    val active get() = running || countdown > 0

    init {
        viewModelScope.launch {
            connectionStatus.collect { status ->
                if (status != ArduinoLink.Status.CONNECTED && active) {
                    pause()
                    message = "Connection lost. Measurements captured so far are preserved."
                }
            }
        }
    }
    fun start(stream: SensorStream) {
        if (active || busy || connectionStatus.value != ArduinoLink.Status.CONNECTED) return
        if (!stream.isCompatible()) { message = "This board does not advertise a matching plug definition. Open its current channel from Experiments."; return }
        if (samples.size >= SAMPLE_LIMIT) { message = "Sample limit reached. Save this recording before starting a new one."; return }
        message = null
        clock = viewModelScope.launch {
            countdown = startDelay
            while (countdown > 0) { delay(1000); countdown-- }
            if (connectionStatus.value != ArduinoLink.Status.CONNECTED) return@launch
            offset = elapsed
            started = nowMillis()
            segment++
            lastReceived = elapsed
            running = true
            acquisition = launch {
                stream.sampleBatches().collect { batch ->
                    if (!stream.isCompatible()) {
                        pause()
                        message = "Plug definition changed. Recording paused to preserve its units and axes."
                        return@collect
                    }
                    if (batch.dropped > 0) {
                        droppedSamples += batch.dropped
                        message = "Input buffer overflow: $droppedSamples samples omitted from this session."
                    }
                    val available = SAMPLE_LIMIT - samples.size
                    var previous = samples.lastOrNull()?.t ?: offset
                    val accepted = batch.samples.asSequence().filter {
                        it.values.size == stream.axisNames.size && it.values.all(Float::isFinite)
                    }.take(available).map { sample ->
                        // Keep arrival timing independent of delayed UI delivery. Device timestamps
                        // are not available in the legacy Arduino protocol.
                        val receivedMillis = sample.receivedAtNanos?.div(1_000_000.0)
                        val time = (receivedMillis?.let { offset + ((it - started) / 1000).toFloat() }
                            ?: currentTime()).coerceAtLeast(previous)
                        previous = time
                        SensorSample(time, sample.values.copyOf(), segment)
                    }.toList()
                    if (accepted.isNotEmpty()) {
                        samples.addAll(accepted)
                        lastReceived = accepted.last().t
                        elapsed = maxOf(currentTime(), lastReceived)
                        dirty = true
                    }
                    if (samples.size >= SAMPLE_LIMIT) {
                        pause()
                        message = "20,000 samples captured. Save or export before clearing."
                    }
                }
            }

            while (running) {
                if (!stream.isCompatible()) {
                    pause()
                    message = "Plug definition changed. Recording paused to preserve its units and axes."
                    break
                }
                elapsed = currentTime()
                if (duration > 0 && elapsed - offset >= duration) {
                    pause()
                    message = "Timed run complete."
                    break
                }
                delay(100)
            }
        }
    }
    private fun currentTime() = offset + (nowMillis() - started) / 1000f
    fun pause() {
        if (running) elapsed = currentTime()
        running = false; countdown = 0
        acquisition?.cancel(); clock?.cancel()
    }
    fun clear() {
        pause(); samples.clear(); elapsed = 0f; lastReceived = 0f
        droppedSamples = 0L
        dirty = false; savedName = null; loadedId = null; message = null
    }
    fun save(store: RecordingStore, experimentId: String, name: String, onSaved: () -> Unit = {}) {
        if (active || busy || samples.isEmpty()) return
        val snapshot = samples.toList()
        val time = elapsed
        busy = true
        viewModelScope.launch {
            try {
                val info = withContext(Dispatchers.IO) { store.save(experimentId, name, time, snapshot, recordingSpec) }
                dirty = false; savedName = info.name; loadedId = info.id
                message = "Saved to Recordings."
                onSaved()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                message = "Could not save. Your measurements are still here. ${e.localizedMessage.orEmpty()}"
            } finally { busy = false }
        }
    }
    fun load(store: RecordingStore, id: String, experimentId: String) {
        if (loadAttempted) return
        loadAttempted = true; busy = true
        viewModelScope.launch {
            try {
                val recording = withContext(Dispatchers.IO) { store.load(id) }
                require(recording.info.experimentId == experimentId) { "Experiment does not match this recording" }
                recordingSpec = recording.info.spec
                samples.clear(); samples.addAll(recording.samples)
                elapsed = recording.info.elapsed; segment = samples.maxOf { it.segment }
                savedName = recording.info.name; loadedId = id; dirty = false
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                message = "Could not open this recording. ${e.localizedMessage.orEmpty()}"
            } finally { busy = false }
        }
    }
}
