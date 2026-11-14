package com.jeevan.tally.recording

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jeevan.tally.exercise.*
import com.jeevan.tally.sensors.ArduinoLink
import com.jeevan.tally.sensors.SensorSample
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * One exercise set on screen. All counting and metrics live in the pure [SetTracker]; this class
 * only routes connection feeds into it, keeps a clock, and mirrors the board's physical
 * Start/Pause/Finish buttons when the firmware reports TALLY status frames.
 */
class ExerciseSetSession(
    private val nowMillis: () -> Long = { System.nanoTime() / 1_000_000 },
    private val wallMillis: () -> Long = System::currentTimeMillis,
) : ViewModel() {
    enum class Phase { SETUP, RUNNING, PAUSED, FINISHED }
    enum class CalibrationStep { IDLE, REST_GET_READY, REST_HOLD, END_GET_READY, END_HOLD }

    var phase by mutableStateOf(Phase.SETUP); private set
    var summary by mutableStateOf<SetSummary?>(null); private set
    val reps = mutableStateListOf<Rep>()
    var progress by mutableStateOf(0f); private set
    val progressTrace = mutableStateListOf<Float>()
    var lastRepAt by mutableStateOf(0L); private set
    var message by mutableStateOf<String?>(null)
    var busy by mutableStateOf(false); private set
    var savedName by mutableStateOf<String?>(null); private set

    var calibration by mutableStateOf<Calibration?>(null); private set
    var calibrationStep by mutableStateOf(CalibrationStep.IDLE); private set
    var calibrationCountdown by mutableStateOf(0); private set
    var calibrationError by mutableStateOf<String?>(null); private set
    var lastFrameMillis by mutableStateOf<Long?>(null); private set

    private var tracker: SetTracker? = null
    private var restPose: Pose? = null
    private val captured = mutableListOf<FloatArray>()
    private var capturing = false
    private var calibrationJob: Job? = null
    private var clockJob: Job? = null
    private var runStartedAt = 0L
    private var activeBefore = 0f
    private var timeBase: Long? = null
    private var timeBaseIsDevice = false

    val prescription get() = tracker?.prescription

    init {
        viewModelScope.launch {
            ArduinoLink.batches(ArduinoLink.ARM_PAIR_ID).collect { batch ->
                if (batch.dropped > 0 && phase == Phase.RUNNING) tracker?.onDropped(batch.dropped)
                batch.samples.forEach(::onSample)
                refresh()
            }
        }
        viewModelScope.launch {
            ArduinoLink.boardStatus.collect { status -> if (status != null) onBoardStatus(status) }
        }
        viewModelScope.launch {
            ArduinoLink.boardCalibration.collect { event ->
                if (event == null) return@collect
                tracker?.onBoardCalibration()
                message = if (event.ok) "Board calibrated." else "Board calibration failed. ${event.detail}".trim()
                refresh()
            }
        }
        viewModelScope.launch {
            ArduinoLink.status.collect { status ->
                if (status != ArduinoLink.Status.CONNECTED && phase == Phase.RUNNING) {
                    tracker?.markConnectionLost()
                    stopClock()
                    phase = Phase.PAUSED
                    message = "Connection lost. The set is paused and everything counted so far is kept."
                    refresh()
                }
            }
        }
    }

    // ---- Set lifecycle ------------------------------------------------------------------

    fun start(prescription: Prescription) {
        if (phase != Phase.SETUP) return
        tracker = SetTracker(prescription, wallMillis(), calibration)
        reps.clear(); progressTrace.clear()
        savedName = null; message = null
        activeBefore = 0f
        timeBase = null
        resume()
        if (calibration == null && ArduinoLink.boardStatus.value == null) {
            message = "Not calibrated: the app cannot estimate repetitions until you calibrate, unless the board counts them."
        }
    }

    fun pause() {
        if (phase != Phase.RUNNING) return
        activeBefore += (nowMillis() - runStartedAt) / 1000f
        tracker?.advanceTo(activeBefore)
        tracker?.pause()
        stopClock()
        phase = Phase.PAUSED
        refresh()
    }

    fun resume() {
        val t = tracker ?: return
        if (phase == Phase.RUNNING || phase == Phase.FINISHED) return
        runStartedAt = nowMillis()
        t.start()
        phase = Phase.RUNNING
        clockJob = viewModelScope.launch {
            while (true) {
                tracker?.advanceTo(activeBefore + (nowMillis() - runStartedAt) / 1000f)
                refresh()
                // A rolling five-second view of range progress, four points per second.
                progressTrace += progress
                while (progressTrace.size > 20) progressTrace.removeAt(0)
                delay(250)
            }
        }
    }

    fun finish() {
        val t = tracker ?: return
        if (phase == Phase.RUNNING) {
            activeBefore += (nowMillis() - runStartedAt) / 1000f
            t.advanceTo(activeBefore)
        }
        stopClock()
        t.finish()
        phase = Phase.FINISHED
        refresh()
    }

    /** Discards the set (the Reset button). */
    fun reset() {
        stopClock()
        tracker = null
        reps.clear(); progressTrace.clear()
        summary = null; savedName = null; message = null
        progress = 0f
        phase = Phase.SETUP
    }

    fun setObservedCount(value: Int?) {
        tracker?.observedCount = value?.coerceIn(0, 9999)
        refresh()
    }

    fun save(store: SetStore, name: String, onSaved: () -> Unit = {}) {
        val t = tracker ?: return
        if (busy || phase != Phase.FINISHED) return
        busy = true
        viewModelScope.launch {
            try {
                val saved = withContext(Dispatchers.IO) { store.save(name, t) }
                savedName = saved.name
                message = "Saved to Exercise history."
                onSaved()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                message = "Could not save. ${e.localizedMessage.orEmpty()}"
            } finally { busy = false }
        }
    }

    /** A detached copy for sharing before (or without) saving. */
    fun snapshot(name: String): SavedSet? {
        val t = tracker ?: return null
        return SetCodec.decode(SetCodec.encode("00000000-0000-0000-0000-000000000000", name, wallMillis(), t.summary(), t.reps))
    }

    // ---- Calibration ---------------------------------------------------------------------

    fun startCalibration() {
        if (phase == Phase.RUNNING) return
        calibrationJob?.cancel()
        calibrationError = null
        restPose = null
        calibrationJob = viewModelScope.launch {
            val rest = capturePose(CalibrationStep.REST_GET_READY, CalibrationStep.REST_HOLD) ?: return@launch
            restPose = rest
            val end = capturePose(CalibrationStep.END_GET_READY, CalibrationStep.END_HOLD) ?: return@launch
            when (val result = AngleMath.calibrate(rest, end)) {
                is CalibrationResult.Ok -> {
                    calibration = result.calibration
                    tracker?.setCalibration(result.calibration)
                    message = "Calibrated on ${result.calibration.signal.label.lowercase()}, ${result.calibration.rangeDegrees.toInt()}° range."
                }
                is CalibrationResult.Failed -> calibrationError = result.reason
            }
            calibrationStep = CalibrationStep.IDLE
            refresh()
        }
    }

    fun cancelCalibration() {
        calibrationJob?.cancel()
        capturing = false
        calibrationStep = CalibrationStep.IDLE
    }

    private suspend fun capturePose(ready: CalibrationStep, hold: CalibrationStep): Pose? {
        calibrationStep = ready
        for (s in 3 downTo 1) { calibrationCountdown = s; delay(1000) }
        calibrationStep = hold
        captured.clear()
        capturing = true
        for (s in 2 downTo 1) { calibrationCountdown = s; delay(1000) }
        capturing = false
        return when (val result = AngleMath.pose(captured.toList())) {
            is PoseResult.Ok -> result.pose
            is PoseResult.Failed -> {
                calibrationError = if (captured.isEmpty()) "No arm-pair data arrived. Check that the board is sending synchronized rows." else result.reason
                calibrationStep = CalibrationStep.IDLE
                null
            }
        }
    }

    // ---- Feeds ---------------------------------------------------------------------------

    private fun onSample(sample: SensorSample) {
        if (sample.values.size != 6) return
        lastFrameMillis = nowMillis()
        if (capturing) captured += sample.values.copyOf()
        val t = tracker ?: return
        if (phase != Phase.RUNNING) return
        val device = sample.deviceMillis
        val stamp = device ?: sample.receivedAtNanos?.div(1_000_000) ?: nowMillis()
        val base = timeBase ?: stamp.also { timeBase = it; timeBaseIsDevice = device != null }
        if (timeBaseIsDevice != (device != null)) return  // never mix clocks within a set
        val rep = t.onFrame((stamp - base) / 1000f, sample.values, device)
        progress = t.progress
        if (rep != null) lastRepAt = nowMillis()
    }

    private fun onBoardStatus(status: BoardStatus) {
        when (status.state) {
            BoardState.RUNNING -> when (phase) {
                Phase.SETUP -> ArduinoLink.boardConfig.value?.let(::start) ?: run {
                    message = "The board started a set. Choose the prescription here and press Start to log it."
                }
                Phase.PAUSED -> resume()
                else -> Unit
            }
            BoardState.PAUSED -> if (phase == Phase.RUNNING) pause()
            else -> Unit
        }
        val t = tracker ?: return
        if (phase == Phase.SETUP || phase == Phase.FINISHED) return
        if (t.onBoardStatus(status).isNotEmpty()) lastRepAt = nowMillis()
        if (status.state == BoardState.FINISHED) finish() else refresh()
    }

    private fun refresh() {
        val t = tracker
        if (t == null) { summary = null; return }
        summary = t.summary()
        if (reps.size != t.reps.size || reps.lastOrNull() != t.reps.lastOrNull()) {
            reps.clear(); reps.addAll(t.reps)
        }
    }

    private fun stopClock() { clockJob?.cancel(); clockJob = null }
}
