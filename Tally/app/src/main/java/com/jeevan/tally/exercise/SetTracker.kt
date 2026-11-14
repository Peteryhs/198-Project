package com.jeevan.tally.exercise

import kotlin.math.abs

/** Nominal acquisition rate from the model input contract (100 Hz, 10 ms per sample). */
const val NOMINAL_HZ = 100
/** tally_push accepts 8–12 ms between samples; anything longer is a timing gap. */
const val MAX_SAMPLE_GAP_MS = 12L

/** Project design targets from the 198-Project README. Requirements, not results. */
object DesignTargets {
    const val MAX_ERRORS_PER_10_REPS = 1f
    const val MIN_COVERAGE = 0.95f
    const val CONTINUOUS_RUN_SECONDS = 60 * 60f
}

/**
 * Everything one set logs. Pure and serialisable: the UI layer feeds it frames, board status and
 * clock ticks; [summary] derives every displayed metric so the same numbers are shown, saved and
 * exported.
 */
class SetTracker(
    val prescription: Prescription,
    val startedAtMillis: Long,
    calibration: Calibration? = null,
    private val counterConfig: CounterConfig = CounterConfig(),
) {
    var calibration: Calibration? = calibration
        private set
    private var counter: RepCounter? = calibration?.let { RepCounter(it, counterConfig) }

    var source = CountSource.APP; private set
    private val _reps = mutableListOf<Rep>()
    val reps: List<Rep> get() = _reps

    var running = false; private set
    var finished = false; private set
    var activeSeconds = 0f; private set
    var pauseCount = 0; private set
    var appFaults = 0; private set

    // Data quality, counted only while running.
    var samplesReceived = 0L; private set
    var clippedSamples = 0L; private set
    var droppedSamples = 0L; private set
    var timingGaps = 0; private set
    private var deviceExpected = 0L
    private var deviceTimed = 0L
    private var lastDeviceMillis: Long? = null
    private var firstDeviceMillis: Long? = null
    private var lastRepEnd: Float? = null

    // Board mirror.
    var lastBoardStatus: BoardStatus? = null; private set
    private var boardCycleOffset = 0
    var boardRestarts = 0; private set
    var assessment: ModelAssessment? = null; private set
    var calibrationEvents = 0; private set

    /** Count the person or instructor observed, entered after the set to measure counting error. */
    var observedCount: Int? = null
        set(value) { require(value == null || value in 0..9999); field = value }

    val counted: Int
        get() = if (source == CountSource.BOARD) boardCycleOffset + (lastBoardStatus?.cycles ?: 0) else _reps.size

    val canCountInApp get() = counter != null

    /** Live position between the calibrated rest (0) and end (1) poses, for the range meter. */
    val progress: Float get() = counter?.progress ?: 0f

    fun setCalibration(value: Calibration) {
        calibration = value
        counter = RepCounter(value, counterConfig)
        calibrationEvents++
    }

    fun onBoardCalibration() { calibrationEvents++ }

    fun start() {
        if (finished) return
        running = true
        lastDeviceMillis = null
        firstDeviceMillis = null
        lastRepEnd = null
        counter?.reset()
    }

    fun pause() {
        if (!running) return
        closeDeviceSegment()
        running = false
        pauseCount++
        counter?.reset()
    }

    fun finish() {
        if (finished) return
        if (running) closeDeviceSegment()
        running = false
        finished = true
        counter?.reset()
    }

    /** Wall-clock active time from the UI layer; ignored once the board reports its own. */
    fun advanceTo(seconds: Float) {
        if (running && seconds.isFinite() && seconds >= activeSeconds && source == CountSource.APP) activeSeconds = seconds
    }

    fun markConnectionLost() {
        appFaults = appFaults or Faults.CONNECTION_LOST
        pause()
    }

    fun onDropped(count: Long) {
        if (count <= 0) return
        droppedSamples += count
        appFaults = appFaults or Faults.APP_DROPPED
    }

    /**
     * One synchronized six-channel frame. [t] is the counter time base in seconds (device clock
     * when the board sends it, arrival clock otherwise). Returns a repetition when one completes.
     */
    fun onFrame(t: Float, values: FloatArray, deviceMillis: Long? = null): Rep? {
        if (!running || values.size != 6) return null
        if (!values.all(Float::isFinite)) {
            appFaults = appFaults or Faults.BAD_SAMPLE
            return null
        }
        samplesReceived++
        if (values.any { abs(it) >= 3f }) {
            clippedSamples++
            appFaults = appFaults or Faults.CLIPPED
        }
        if (deviceMillis != null) {
            deviceTimed++
            val previous = lastDeviceMillis
            if (previous != null && deviceMillis - previous > MAX_SAMPLE_GAP_MS) timingGaps++
            if (previous == null || deviceMillis >= previous) lastDeviceMillis = deviceMillis
            if (firstDeviceMillis == null) firstDeviceMillis = deviceMillis
        }
        if (source != CountSource.APP) return null
        val detected = counter?.push(t, values) ?: return null
        val pace = lastRepEnd?.let { detected.endT - it } ?: detected.movementSeconds
        lastRepEnd = detected.endT
        val rep = Rep(
            index = _reps.size + 1,
            t = activeSeconds,
            paceSeconds = pace,
            movementSeconds = detected.movementSeconds,
            peakRangeFraction = detected.peakFraction,
            full = detected.full,
            cue = prescription.classify(pace),
        )
        _reps += rep
        return rep
    }

    /** Mirrors one TALLY status frame. Returns the repetitions it newly reported. */
    fun onBoardStatus(status: BoardStatus): List<Rep> {
        if (finished) return emptyList()
        val previous = lastBoardStatus
        if (source != CountSource.BOARD) {
            source = CountSource.BOARD
            _reps.clear()  // the board's count is authoritative; drop the app estimate
        }
        if (previous != null && status.cycles < previous.cycles) {
            // tally_start after tally_finish resets the board's counters; keep this set cumulative.
            boardRestarts++
            boardCycleOffset += previous.cycles
        }
        val before = previous?.takeIf { status.cycles >= it.cycles }?.cycles ?: 0
        lastBoardStatus = status
        activeSeconds = maxOf(activeSeconds, status.activeMs / 1000f)
        if (status.state == BoardState.FINISHED && status.assessmentAvailable &&
            status.exerciseProbability.size == 3 && status.pIncorrect.isFinite()
        ) assessment = ModelAssessment(status.exerciseProbability, status.pIncorrect)

        val added = mutableListOf<Rep>()
        for (cycle in before + 1..status.cycles) {
            // Only the newest cycle has a reported duration; earlier ones in a burst are unknown.
            val pace = if (cycle == status.cycles && status.durationAvailable && status.cycleSeconds.isFinite() && status.cycleSeconds > 0f)
                status.cycleSeconds else null
            val cue = if (cycle == status.cycles && status.cue != TempoCue.ABSTAIN) status.cue else prescription.classify(pace)
            val rep = Rep(index = boardCycleOffset + cycle, t = activeSeconds, paceSeconds = pace, cue = cue)
            _reps += rep
            added += rep
        }
        return added
    }

    private fun closeDeviceSegment() {
        val first = firstDeviceMillis
        val last = lastDeviceMillis
        if (first != null && last != null && last >= first) deviceExpected += (last - first) / (1000 / NOMINAL_HZ) + 1
        firstDeviceMillis = null
        lastDeviceMillis = null
    }

    fun summary(): SetSummary {
        val openSegment = run {
            val first = firstDeviceMillis
            val last = lastDeviceMillis
            if (first != null && last != null && last >= first) (last - first) / (1000 / NOMINAL_HZ) + 1 else 0L
        }
        val deviceBasis = deviceTimed > 0 && deviceTimed == samplesReceived
        val expected = if (deviceBasis) (deviceExpected + openSegment).toDouble() else activeSeconds.toDouble() * NOMINAL_HZ
        val coverage = if (expected >= 1.0 && samplesReceived > 0) (samplesReceived / expected).coerceAtMost(1.0).toFloat() else null
        return SetTotals(
            source = source, startedAtMillis = startedAtMillis, finished = finished, counted = counted,
            activeSeconds = activeSeconds, pauseCount = pauseCount, samplesReceived = samplesReceived,
            expectedSamples = expected.toLong(), coverage = coverage, coverageFromDeviceClock = deviceBasis,
            timingGaps = timingGaps, clippedSamples = clippedSamples, droppedSamples = droppedSamples,
            faults = appFaults or (lastBoardStatus?.faults ?: 0), boardRestarts = boardRestarts,
            calibrationSignal = calibration?.signal, calibrationRangeDegrees = calibration?.rangeDegrees,
            calibrationEvents = calibrationEvents, assessment = assessment, observedCount = observedCount,
        ).summarize(prescription, _reps)
    }
}

/** The stored, non-derived facts about a set. [summarize] derives every ratio from these plus the reps. */
data class SetTotals(
    val source: CountSource,
    val startedAtMillis: Long,
    val finished: Boolean,
    val counted: Int,
    val activeSeconds: Float,
    val pauseCount: Int,
    val samplesReceived: Long,
    val expectedSamples: Long,
    val coverage: Float?,
    val coverageFromDeviceClock: Boolean,
    val timingGaps: Int,
    val clippedSamples: Long,
    val droppedSamples: Long,
    val faults: Int,
    val boardRestarts: Int,
    val calibrationSignal: AngleSignal?,
    val calibrationRangeDegrees: Float?,
    val calibrationEvents: Int,
    val assessment: ModelAssessment?,
    val observedCount: Int?,
) {
    fun summarize(prescription: Prescription, reps: List<Rep>): SetSummary {
        val paces = reps.mapNotNull { it.paceSeconds }.filter { it.isFinite() && it > 0f }
        val rangeKnown = reps.filter { it.full != null }
        val tempoKnown = reps.filter { it.cue != TempoCue.ABSTAIN }
        val effective = reps.filter { it.full != false && it.cue != TempoCue.TOO_FAST && it.cue != TempoCue.TOO_SLOW }
        val observed = observedCount
        val countError = observed?.let { abs(counted - it) }
        return SetSummary(
            prescription = prescription,
            source = source,
            startedAtMillis = startedAtMillis,
            finished = finished,
            counted = counted,
            loggedReps = reps.size,
            completion = counted.toFloat() / prescription.targetCount,
            fullReps = rangeKnown.count { it.full == true },
            shallowReps = rangeKnown.count { it.full == false },
            rangeEfficiency = if (rangeKnown.isEmpty()) null else rangeKnown.count { it.full == true }.toFloat() / rangeKnown.size,
            onTarget = tempoKnown.count { it.cue == TempoCue.ON_TARGET },
            tooFast = tempoKnown.count { it.cue == TempoCue.TOO_FAST },
            tooSlow = tempoKnown.count { it.cue == TempoCue.TOO_SLOW },
            paceAdherence = if (tempoKnown.isEmpty()) null else tempoKnown.count { it.cue == TempoCue.ON_TARGET }.toFloat() / tempoKnown.size,
            efficiency = if (reps.isEmpty() || (rangeKnown.isEmpty() && tempoKnown.isEmpty())) null else effective.size.toFloat() / reps.size,
            effectiveReps = effective.size,
            lastPace = paces.lastOrNull(),
            meanPace = paces.takeIf { it.isNotEmpty() }?.average()?.toFloat(),
            fastestPace = paces.minOrNull(),
            slowestPace = paces.maxOrNull(),
            repsPerMinute = if (activeSeconds >= 1f && counted > 0) counted * 60f / activeSeconds else null,
            activeSeconds = activeSeconds,
            pauseCount = pauseCount,
            samplesReceived = samplesReceived,
            expectedSamples = expectedSamples,
            coverage = coverage,
            coverageFromDeviceClock = coverageFromDeviceClock,
            timingGaps = timingGaps,
            clippedSamples = clippedSamples,
            droppedSamples = droppedSamples,
            faults = faults,
            boardRestarts = boardRestarts,
            calibrated = calibrationSignal != null,
            calibrationSignal = calibrationSignal,
            calibrationRangeDegrees = calibrationRangeDegrees,
            calibrationEvents = calibrationEvents,
            assessment = assessment,
            observedCount = observed,
            countingError = countError,
            errorsPer10 = if (observed != null && observed > 0) countError!! * 10f / observed else null,
        )
    }
}

/** Every metric a finished (or in-progress) set reports. Ratios are 0..1; null means "not measurable". */
data class SetSummary(
    val prescription: Prescription,
    val source: CountSource,
    val startedAtMillis: Long,
    val finished: Boolean,
    val counted: Int,
    val loggedReps: Int,
    val completion: Float,
    val fullReps: Int,
    val shallowReps: Int,
    val rangeEfficiency: Float?,
    val onTarget: Int,
    val tooFast: Int,
    val tooSlow: Int,
    val paceAdherence: Float?,
    /** Share of logged repetitions that were not shallow and not off-pace. */
    val efficiency: Float?,
    val effectiveReps: Int,
    val lastPace: Float?,
    val meanPace: Float?,
    val fastestPace: Float?,
    val slowestPace: Float?,
    val repsPerMinute: Float?,
    val activeSeconds: Float,
    val pauseCount: Int,
    val samplesReceived: Long,
    val expectedSamples: Long,
    val coverage: Float?,
    val coverageFromDeviceClock: Boolean,
    val timingGaps: Int,
    val clippedSamples: Long,
    val droppedSamples: Long,
    val faults: Int,
    val boardRestarts: Int,
    val calibrated: Boolean,
    val calibrationSignal: AngleSignal?,
    val calibrationRangeDegrees: Float?,
    val calibrationEvents: Int,
    val assessment: ModelAssessment?,
    val observedCount: Int?,
    val countingError: Int?,
    val errorsPer10: Float?,
) {
    val meetsCountingTarget get() = errorsPer10?.let { it <= DesignTargets.MAX_ERRORS_PER_10_REPS }
    val meetsCoverageTarget get() = coverage?.let { it >= DesignTargets.MIN_COVERAGE }
    val continuousRunFraction get() = activeSeconds / DesignTargets.CONTINUOUS_RUN_SECONDS
    val faultNames get() = Faults.describe(faults)
}
