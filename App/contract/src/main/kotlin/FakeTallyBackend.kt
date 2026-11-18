package com.tally.app.contract

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.math.sin
import kotlin.math.sqrt

/** Canned fixture only: no model inference and no live rep count. */
class FakeTallyBackend(
    private val frameDelayMs: Long = 10L,
    private val scoringDelayMs: Long = 10L,
) : TallyBackend {
    init {
        require(frameDelayMs in 0..(Long.MAX_VALUE / 10))
        require(scoringDelayMs >= 0)
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val lock = Any()
    private val mutableLink = MutableStateFlow<LinkState>(LinkState.Disconnected)
    private val mutableSession = MutableStateFlow<SessionState>(SessionState.Idle)
    private val mutableCalibration = MutableStateFlow<CalibrationInfo?>(CalibrationInfo("nominal", true, 0))
    private val summaries = MutableStateFlow<List<SetSummary>>(emptyList())
    private val results = mutableMapOf<SetId, SetResult>()
    private val poses = mutableSetOf<CalPose>()
    private val bodyHolds = mutableSetOf<BodyHold>()
    private var captureInProgress = false
    private var nextId = 1u
    private var replay: Job? = null
    private var startedAt = 0L
    private var intended: String? = null
    override val link = mutableLink.asStateFlow()
    override val session = mutableSession.asStateFlow()
    override val calibration = mutableCalibration.asStateFlow()
    private val fixtureRing = FakeLiveRing()
    override val live: LiveRing = fixtureRing

    override suspend fun connect(): Result<DeviceInfo> {
        val device = DeviceInfo("00:00:00:00:00:00", 0, "fake_fixture")
        mutableLink.value = LinkState.Connected(device)
        return Result.success(device)
    }

    override suspend fun disconnect() {
        abortSet()
        mutableLink.value = LinkState.Disconnected
    }

    override suspend fun startSet(side: Side, intendedExercise: String?): Result<SetId> {
        if (link.value !is LinkState.Connected) return Result.failure(IllegalStateException("Connect first"))
        val id: SetId
        synchronized(lock) {
            if (captureInProgress) return Result.failure(IllegalStateException("Calibration capture in progress"))
            if (session.value is SessionState.Recording || session.value is SessionState.Scoring)
                return Result.failure(IllegalStateException("Set already active"))
            id = SetId(nextId++)
            fixtureRing.clear()
            startedAt = System.currentTimeMillis()
            intended = intendedExercise
            mutableSession.value = SessionState.Recording(id, side, 0, 0)
            replay = scope.launch {
                repeat(100) { frame ->
                    delay(frameDelayMs)
                    fixtureRing.appendFrame(frame * 10)
                    mutableSession.value = SessionState.Recording(id, side, (frame + 1) * 10, 0)
                }
                finish(id, side)
            }
        }
        return Result.success(id)
    }

    private suspend fun finish(id: SetId, side: Side) {
        mutableSession.value = SessionState.Scoring(id)
        delay(scoringDelayMs)
        val wrong = id.raw % 2u == 0u
        val exercises = if (wrong) listOf("SQZ", "EAH", "EFE", "SQZ") else listOf("EFE", "EAH", "SQZ", "EFE")
        val captured = FloatArray(fixtureRing.capacitySamples * 6)
        val count = fixtureRing.copyLatest(captured, fixtureRing.capacitySamples)
        val reps = exercises.mapIndexed { index, exercise ->
            val repWrong = wrong && index > 0
            RepResult(index + 1, repWrong, if (repWrong) 0.82 else 0.08, exercise,
                if (count > 0) count / 100.0 / exercises.size else 1.0)
        }
        val chart = if (count < exercises.size * 2) null else SetChart(
            List(count) { i ->
                fun magnitude(offset: Int): Float {
                    var sum = 0f
                    repeat(3) { sum += captured[i * 6 + offset + it] * captured[i * 6 + offset + it] }
                    return sqrt(sum)
                }
                ChartSample(i / 100.0, magnitude(0), magnitude(3))
            },
            reps.mapIndexed { i, rep -> RepSpan(rep.index, (i * count / reps.size) / 100.0,
                ((i + 1) * count / reps.size - 1) / 100.0) },
        )
        val exercise = if (wrong) "SQZ" else "EFE"
        // Same rule as tally_app._decide: any wrong rep, or a class that is not the intended exercise.
        val result = SetResult(
            id, side, startedAt, "scored", reps.any { it.wrong } || (intended != null && intended != exercise),
            if (wrong) 0.635 else 0.08, exercise, reps, listOf("fake_canned_fixture"), null,
            Provenance("fake", "fake", "fake", "fake", 0, "00:00:00:00:00:00",
                calibration.value?.id ?: "nominal", "fake"), chart, intended,
        )
        synchronized(results) { results[id] = result }
        summaries.value = summaries.value + SetSummary(id, side, startedAt, result.status, result.wrong, result.exercise,
            result.reps.size, result.intendedExercise)
        mutableSession.value = SessionState.Done(result)
    }

    override suspend fun stopSet(): Result<Unit> {
        val active = session.value as? SessionState.Recording
            ?: return Result.failure(IllegalStateException("No recording"))
        replay?.cancelAndJoin()
        finish(active.id, active.side)
        return Result.success(Unit)
    }

    override suspend fun abortSet(): Result<Unit> {
        replay?.cancelAndJoin()
        val id = when (val active = session.value) {
            is SessionState.Recording -> active.id
            is SessionState.Scoring -> active.id
            else -> null
        }
        if (id != null) mutableSession.value = SessionState.Failed(id, "aborted", false)
        return Result.success(Unit)
    }

    override suspend fun scorePartial(id: SetId): Result<SetResult> = Result.failure(IllegalStateException("No partial fixture"))

    override suspend fun captureCalibrationPose(pose: CalPose): Result<Unit> {
        if (link.value !is LinkState.Connected) return Result.failure(IllegalStateException("Connect first"))
        synchronized(lock) {
            if (session.value is SessionState.Recording || session.value is SessionState.Scoring)
                return Result.failure(IllegalStateException("Set already active"))
            if (captureInProgress) return Result.failure(IllegalStateException("Calibration capture in progress"))
            captureInProgress = true
        }
        return try {
            delay(frameDelayMs * 10)
            synchronized(lock) { poses += pose }
            Result.success(Unit)
        } finally {
            synchronized(lock) { captureInProgress = false }
        }
    }

    override suspend fun captureBodyHold(hold: BodyHold): Result<Unit> {
        if (link.value !is LinkState.Connected) return Result.failure(IllegalStateException("Connect first"))
        synchronized(lock) {
            if (session.value is SessionState.Recording || session.value is SessionState.Scoring)
                return Result.failure(IllegalStateException("Set already active"))
            if (captureInProgress) return Result.failure(IllegalStateException("Calibration capture in progress"))
            captureInProgress = true
            bodyHolds.add(hold)
            captureInProgress = false
        }
        return Result.success(Unit)
    }

    override suspend fun saveBodyCalibration(): Result<CalibrationInfo> {
        if (link.value !is LinkState.Connected) return Result.failure(IllegalStateException("Connect first"))
        synchronized(lock) {
            if (bodyHolds.size != BodyHold.entries.size)
                return Result.failure(IllegalStateException("Capture every hold first"))
            val info = CalibrationInfo("fake-body-calibration", false, System.currentTimeMillis())
            mutableCalibration.value = info
            bodyHolds.clear()
            return Result.success(info)
        }
    }

    override suspend fun saveCalibration(): Result<CalibrationInfo> {
        if (link.value !is LinkState.Connected) return Result.failure(IllegalStateException("Connect first"))
        synchronized(lock) {
            if (session.value is SessionState.Recording || session.value is SessionState.Scoring)
                return Result.failure(IllegalStateException("Set already active"))
            if (captureInProgress) return Result.failure(IllegalStateException("Calibration capture in progress"))
            if (poses.size != CalPose.entries.size) return Result.failure(IllegalStateException("Capture all six poses"))
            val info = CalibrationInfo("fake-calibration", false, System.currentTimeMillis())
            mutableCalibration.value = info
            poses.clear()
            return Result.success(info)
        }
    }

    override fun history() = summaries.asStateFlow()
    override suspend fun result(id: SetId): SetResult? = synchronized(results) { results[id] }
    override suspend fun rescore(id: SetId): Result<SetResult> = result(id)?.let { Result.success(it) }
        ?: Result.failure(IllegalArgumentException("Unknown set"))
    override suspend fun exportCsv(id: SetId): Result<String> = Result.failure(UnsupportedOperationException("Fake has no content provider"))
}

internal class FakeLiveRing : LiveRing {
    override val capacitySamples = 1000
    private val updates = MutableStateFlow(0L)
    override val version = updates.asStateFlow()
    private val samples = FloatArray(capacitySamples * 6)
    private var size = 0
    private var writeIndex = 0

    @Synchronized fun clear() {
        size = 0
        writeIndex = 0
        updates.value++
    }

    @Synchronized fun appendFrame(first: Int) {
        repeat(10) { row ->
            val sample = first + row
            repeat(6) { channel -> samples[writeIndex * 6 + channel] = sin(sample * 0.04 + channel).toFloat() }
            writeIndex = (writeIndex + 1) % capacitySamples
            size = minOf(size + 1, capacitySamples)
        }
        updates.value++
    }

    @Synchronized override fun copyLatest(dst: FloatArray, maxSamples: Int): Int {
        require(maxSamples >= 0)
        val count = minOf(size, maxSamples, dst.size / 6)
        val start = (writeIndex - count + capacitySamples) % capacitySamples
        repeat(count) { row ->
            val source = ((start + row) % capacitySamples) * 6
            samples.copyInto(dst, row * 6, source, source + 6)
        }
        return count
    }
}
