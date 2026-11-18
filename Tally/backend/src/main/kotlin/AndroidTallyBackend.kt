package com.tally.app.backend

import android.content.Context
import android.net.Network
import com.tally.app.backend.calib.Calibration
import com.tally.app.backend.calib.CalibrationStore
import com.tally.app.backend.calib.OnArmMath
import com.tally.app.backend.log.TallyLog
import com.tally.app.backend.export.CsvExport
import com.tally.app.backend.link.*
import com.tally.app.backend.score.*
import com.tally.app.backend.service.RecordingService
import com.tally.app.backend.session.SetRecorder
import com.tally.app.backend.session.SampleProgress
import com.tally.app.backend.store.SetRepository
import com.tally.app.backend.store.intendedExercise
import com.tally.app.contract.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject
import java.security.SecureRandom

internal class AndroidTallyBackend(private val context: Context, passphrase: String?) : TallyBackend {
    /** null = the device's AP is open. */
    @Volatile private var passphrase: String? = wifiPassphraseOrOpen(passphrase)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val control = Mutex()
    private val guard = Any()
    private val repository = SetRepository(context)
    private val calibrationStore = CalibrationStore(context)
    private val loadedCalibration = runCatching { calibrationStore.load() }
    private var calibrationLoadError = loadedCalibration.exceptionOrNull()
    private var currentCalibration = loadedCalibration.getOrElse { Calibration.nominal() }
    private val mutableCalibration = MutableStateFlow<CalibrationInfo?>(loadedCalibration.getOrNull()?.info)
    private val mutableLink = MutableStateFlow<LinkState>(LinkState.Disconnected)
    private val mutableSession = MutableStateFlow<SessionState>(SessionState.Idle)
    override val calibration = mutableCalibration.asStateFlow()
    override val link = mutableLink.asStateFlow()
    override val session = mutableSession.asStateFlow()
    override val live = com.tally.app.backend.session.LiveRing()
    private val scorer = PythonScorer(context)
    private val wifi = WifiJoiner(context)
    private val random = SecureRandom()
    private val poses = mutableMapOf<CalPose, FloatArray>()
    private val bodyHolds = mutableMapOf<BodyHold, FloatArray>()
    /** Raw per-channel millivolts of the hold that just ended, kept for the stillness gate. */
    private var lastHoldSamples: Array<DoubleArray>? = null
    private var deviceLink: DeviceLink? = null
    private var hello: Frame.Hello? = null
    private var active: SetRecorder? = null
    private var capture: CompletableDeferred<FloatArray>? = null
    private var captureStopSent = false
    private var lastFrameNs = 0L
    private var lostAt = 0L
    private var lostAtNs = 0L

    init {
        scope.launch {
            attempt { scorer.warmUp() }.onFailure { TallyLog.w("On-device scorer warmup failed", it) }
        }
        // Recover interrupted sets from durable frames; never manufacture a normal end marker.
        scope.launch {
            synchronized(guard) {
                val id = repository.ids().filter { runCatching { repository.result(it) == null }.getOrDefault(true) }
                    .maxByOrNull { runCatching { repository.meta(it)?.optLong("started_at_epoch_ms") ?: 0L }.getOrDefault(0L) }
                if (id != null && mutableSession.value == SessionState.Idle) {
                    val restored = runCatching { restore(id, true) }
                    mutableSession.value = SessionState.Failed(id,
                        restored.exceptionOrNull()?.message ?: "Archived set available for rescore or explicit partial scoring",
                        restored.getOrNull()?.partialScorable == true)
                }
            }
        }
    }

    suspend fun configurePassphrase(value: String) {
        val checked = wifiPassphraseOrOpen(value)
        control.withLock {
            synchronized(guard) {
                check(active == null && capture == null && mutableSession.value !is SessionState.Scoring) {
                    "Cannot change the Wi-Fi passphrase while a set or calibration capture is active"
                }
                passphrase = checked
            }
        }
    }

    override suspend fun connect(): Result<DeviceInfo> = attempt {
        control.withLock {
            val credential = passphrase
            synchronized(guard) { check(active == null) { "Recording; automatic reconnect is in progress if needed" } }
            deviceLink?.close()
            mutableLink.value = LinkState.Joining
            try {
                val joined = wifi.join(credential)
                TallyLog.i("joined device network, requesting HELLO on 192.168.4.1:5198")
                openLink(joined).device
            } catch (e: Exception) {
                TallyLog.e("connect failed", e)
                mutableLink.value = LinkState.Lost(e.message ?: "Connection failed", System.currentTimeMillis())
                throw e
            }
        }
    }

    private suspend fun openLink(joined: Network): Frame.Hello {
        mutableLink.value = LinkState.Connecting
        val expectedMac = synchronized(guard) { hello?.device?.mac }
        lateinit var candidate: DeviceLink
        var failed = false
        candidate = DeviceLink(joined.socketFactory,
            { frame -> synchronized(guard) { if (deviceLink === candidate) onFrame(frame) } },
            { reason -> synchronized(guard) { if (deviceLink === candidate) { failed = true; onLost(reason) } } })
        synchronized(guard) { deviceLink = candidate }
        try {
            val connected = candidate.connect()
            synchronized(guard) {
                check(deviceLink === candidate && !failed) { "Connection closed or superseded" }
                val recording = active
                if (recording != null) {
                    check(expectedMac == connected.device.mac) { "Reconnected to a different ESP32" }
                    check(connected.activeSetId == recording.id) {
                        "ESP32 lost the active set (reset or set ended during disconnect)"
                    }
                    check(connected.activeNextSeq.toLong() >= recording.store.size.toLong()) {
                        "ESP32 active sequence is behind the phone"
                    }
                    candidate.send(Command.Resume(recording.id, recording.store.size.toUInt()))
                }
                hello = connected
                mutableLink.value = LinkState.Connected(connected.device)
                (mutableSession.value as? SessionState.Recording)?.let { mutableSession.value = it.copy(linkStallMs = 0) }
            }
            return connected
        } catch (e: Exception) { candidate.close(); throw e }
    }

    override suspend fun disconnect() {
        control.withLock {
            synchronized(guard) {
                active?.let {
                    runCatching { deviceLink?.send(Command.Abort(it.id)) }
                    failActive("disconnected by phone", allowPartial = false)
                }
                deviceLink?.close(); deviceLink = null
                hello = null
                wifi.close()
                mutableLink.value = LinkState.Disconnected
            }
        }
    }

    override suspend fun startSet(side: Side, intendedExercise: String?): Result<SetId> = attempt {
        TallyLog.i("startSet requested side=$side intended=$intendedExercise")
        val info = if (geminiKey() == null) scorer.warmUp() else null
        val exerciseClasses = info?.exerciseClasses ?: GeminiScorer.exerciseCodes
        require(intendedExercise == null || intendedExercise in exerciseClasses) { "Unknown exercise $intendedExercise" }
        control.withLock {
            abortHeldDeviceSet()
            synchronized(guard) {
                check(active == null && mutableSession.value !is SessionState.Scoring) { "A set is already active" }
                check(calibrationLoadError == null) { "Stored calibration is unreadable; capture and save all poses again" }
                check(mutableLink.value is LinkState.Connected) { "Connect first" }
                check(hello!!.activeSetId.raw == 0u) { "ESP32 has an unknown active set; abort it before starting" }
                val id = newId()
                val meta = metadata(id, side, info).put("intended_exercise", intendedExercise ?: JSONObject.NULL)
                val recorder = SetRecorder(id, side, currentCalibration, meta, repository, live)
                live.clear()
                active = recorder
                mutableSession.value = SessionState.Recording(id, side, 0, 0)
                try {
                    RecordingService.onUnexpectedStop = { synchronized(guard) { if (active === recorder) failActive("recording service stopped", true) } }
                    TallyLog.i("starting recording service, then sending START id=${id.raw}")
                    RecordingService.start(context)
                    deviceLink!!.send(Command.Start(id, side))
                    monitorRecording(recorder)
                } catch (e: Exception) { TallyLog.e("start failed", e); failActive(e.message ?: "Start failed", false); throw e }
                id
            }
        }
    }

    /**
     * A set the board still holds after a lost link or an app restart blocks START until its SET_END is
     * delivered (firmware session.c), so abort it and wait for SET_END aborted before starting fresh.
     */
    private suspend fun abortHeldDeviceSet() {
        val held = synchronized(guard) {
            if (active != null || mutableLink.value !is LinkState.Connected) return
            hello?.activeSetId?.takeIf { it.raw != 0u }?.also { deviceLink!!.send(Command.Abort(it)) }
        } ?: return
        TallyLog.w("device still holds set ${held.raw}; sent ABORT and waiting for SET_END")
        withTimeoutOrNull(3_000) { while (synchronized(guard) { hello?.activeSetId == held }) delay(20) }
            ?: error("ESP32 did not end its unfinished set ${held.raw} after ABORT; reconnect and try again".also { TallyLog.e(it) })
    }

    override suspend fun stopSet(): Result<Unit> = sendForActive { Command.Stop(it) }
    override suspend fun abortSet(): Result<Unit> = attempt {
        control.withLock { synchronized(guard) {
            check(capture == null) { "Calibration capture in progress" }
            check(mutableLink.value is LinkState.Connected) { "Connect first" }
            val id = active?.id ?: hello?.activeSetId?.takeIf { it.raw != 0u }
            deviceLink!!.send(Command.Abort(checkNotNull(id) { "No active device set" }))
        } }
    }
    private suspend fun sendForActive(command: (SetId) -> Command): Result<Unit> = attempt {
        control.withLock { synchronized(guard) {
            check(capture == null) { "Calibration capture in progress" }
            val recording = checkNotNull(active) { "No recording" }
            check(mutableLink.value is LinkState.Connected) { "Link lost; reconnect before sending" }
            deviceLink!!.send(command(recording.id))
        } }
    }

    private fun onFrame(frame: Frame) {
        lastFrameNs = System.nanoTime()
        if (frame is Frame.Hello) {
            if (active == null) hello = frame
            return
        }
        if (frame !is Frame.SetStarted && frame !is Frame.Samples && frame !is Frame.SetEnd) return
        synchronized(guard) {
            val recording = active
            if (recording == null) {
                val id = when (frame) { is Frame.SetStarted -> frame.id; is Frame.Samples -> frame.id; is Frame.SetEnd -> frame.id; else -> error("Unexpected frame") }
                check(id == hello?.activeSetId) { "Unexpected set frame with no recording" }
                if (frame is Frame.SetEnd) hello = hello?.copy(activeSetId = SetId(0u), activeNextSeq = 0u)
                return // An unknown/interrupted device set must be explicitly aborted before a new Start.
            }
            try {
                recording.accept(frame)
                if (frame is Frame.SetStarted || frame is Frame.Samples)
                    hello = hello?.copy(activeSetId = recording.id, activeNextSeq = recording.store.size.toUInt())
                if (capture != null && frame is Frame.Samples && recording.store.size >= 100 && !captureStopSent) {
                    captureStopSent = true
                    deviceLink!!.send(Command.Stop(recording.id))
                }
                if (frame is Frame.SetEnd) {
                    active = null
                    stopService()
                    hello = hello?.copy(activeSetId = SetId(0u), activeNextSeq = 0u)
                    val calibrationCapture = capture
                    if (calibrationCapture != null) {
                        capture = null
                        if (frame.reason != EndReason.DONE || recording.store.size < 100)
                            calibrationCapture.completeExceptionally(IllegalStateException("Calibration capture ended ${frame.reason}"))
                        else {
                            // Pose capture needs mV: undo the recorder's g conversion with the same calibration.
                            val holdMv = Array(6) { ch ->
                                DoubleArray(100) { i ->
                                    (recording.store.g(i, ch) * recording.calibration.mvPerG[ch] +
                                        recording.calibration.offsetMv[ch]).toDouble()
                                }
                            }
                            lastHoldSamples = holdMv
                            calibrationCapture.complete(FloatArray(6) { ch -> (holdMv[ch].average()).toFloat() })
                        }
                        mutableSession.value = SessionState.Idle
                    } else {
                        mutableSession.value = SessionState.Scoring(recording.id)
                        scope.launch { scoreRecording(recording, frame.reason, false) }
                    }
                } else mutableSession.value = SessionState.Recording(recording.id, recording.side, recording.store.size, 0)
            } catch (e: Exception) {
                failActive(e.message ?: "Invalid set", false)
                throw e
            }
        }
    }

    private fun onLost(reason: String, sinceNs: Long? = null) {
        synchronized(guard) {
            if (mutableLink.value is LinkState.Connected || lostAtNs == 0L || sinceNs != null) {
                lostAtNs = sinceNs ?: lastFrameNs.takeIf { it != 0L } ?: System.nanoTime()
                lostAt = System.currentTimeMillis() - (System.nanoTime() - lostAtNs) / 1_000_000
            }
            mutableLink.value = LinkState.Lost(reason, lostAt)
            if (capture != null) failActive("Calibration link lost", false)
        }
    }

    private fun monitorRecording(recording: SetRecorder) {
        val startedNs = System.nanoTime()
        val progress = SampleProgress(startedNs)
        scope.launch {
            while (isActive) {
                delay(1_000)
                control.withLock {
                    synchronized(guard) {
                        if (active !== recording) return@launch
                        val state = mutableSession.value as? SessionState.Recording ?: return@launch
                        if (mutableLink.value is LinkState.Connected && progress.stalled(state.samples, System.nanoTime())) {
                            deviceLink?.close()
                            onLost("Device connected but no sensor samples arrived for 3 s", progress.lastProgressNs)
                        }
                        if (System.nanoTime() - startedNs >= 610_000_000_000L) {
                            failActive("set_duration_exceeded", true)
                            return@launch
                        }
                        if (mutableLink.value is LinkState.Lost) {
                            mutableSession.value = state.copy(linkStallMs = System.currentTimeMillis() - lostAt)
                            if (System.nanoTime() - lostAtNs >= 30_000_000_000L) {
                                failActive("partial_device_lost", true)
                                return@launch
                            }
                        }
                    }
                    if (mutableLink.value is LinkState.Lost) {
                        try {
                            deviceLink?.close()
                            val remainingMs = ((30_000_000_000L - (System.nanoTime() - lostAtNs)) / 1_000_000)
                                .coerceAtLeast(1)
                            withTimeout(remainingMs) {
                                val joined = wifi.currentNetwork ?: wifi.join(passphrase)
                                openLink(joined)
                            }
                        } catch (e: TimeoutCancellationException) {
                            synchronized(guard) { if (active === recording) failActive("partial_device_lost", true) }
                            return@launch
                        } catch (e: CancellationException) { throw e }
                        catch (e: Exception) { mutableLink.value = LinkState.Lost(e.message ?: "Reconnect failed", lostAt) }
                    }
                }
            }
        }
    }

    private fun failActive(reason: String, allowPartial: Boolean) {
        val recording = active ?: return
        TallyLog.e("failActive reason=$reason allowPartial=$allowPartial samples=${recording.store.size}")
        runCatching { deviceLink?.send(Command.Abort(recording.id)) }
        recording.metadata.put("partial_scorable", allowPartial && recording.store.size >= PARTIAL_MIN_SAMPLES)
        var failure = reason
        try { recording.closeIncomplete(reason) }
        catch (e: Exception) { failure += "; persistence failed: ${e.message}" }
        finally {
            active = null
            capture?.completeExceptionally(IllegalStateException(reason)); capture = null
            mutableSession.value = SessionState.Failed(recording.id, failure, allowPartial && recording.store.size >= PARTIAL_MIN_SAMPLES)
            stopService()
        }
    }
    private fun stopService() {
        RecordingService.onUnexpectedStop = null
        RecordingService.stop(context)
    }

    override suspend fun captureCalibrationPose(pose: CalPose): Result<Unit> = attempt {
        control.withLock {
            abortHeldDeviceSet()
            val deferred = CompletableDeferred<FloatArray>()
            synchronized(guard) {
                check(active == null && mutableSession.value !is SessionState.Scoring) { "A set is already active" }
                check(mutableLink.value is LinkState.Connected && hello!!.activeSetId.raw == 0u) { "Connect to an idle ESP32 first" }
                val id = newId()
                active = SetRecorder(id, Side.L, currentCalibration, JSONObject(), null, null)
                capture = deferred; captureStopSent = false
                mutableSession.value = SessionState.Recording(id, Side.L, 0, 0)
                try {
                    RecordingService.onUnexpectedStop = { synchronized(guard) { failActive("recording service stopped", false) } }
                    RecordingService.start(context)
                    deviceLink!!.send(Command.Start(id, Side.L))
                } catch (e: Exception) { failActive("Calibration start failed", false); throw e }
            }
            try { poses[pose] = withTimeout(10_000) { deferred.await() } }
            finally { synchronized(guard) {
                if (capture === deferred) {
                    runCatching { deviceLink?.send(Command.Abort(active!!.id)) }
                    failActive("Calibration capture timed out or cancelled", false)
                }
            } }
        }
    }

    override suspend fun saveCalibration(): Result<CalibrationInfo> = attempt {
        control.withLock { synchronized(guard) {
            check(active == null) { "A set is active" }
            val saved = Calibration.fromPoses(poses, System.currentTimeMillis())
            calibrationStore.save(saved)
            currentCalibration = saved
            calibrationLoadError = null
            mutableCalibration.value = saved.info
            poses.clear()
            saved.info
        } }
    }


    override suspend fun captureBodyHold(hold: BodyHold): Result<Unit> = attempt {
        control.withLock {
            abortHeldDeviceSet()
            val deferred = CompletableDeferred<FloatArray>()
            synchronized(guard) {
                check(active == null && mutableSession.value !is SessionState.Scoring) { "A set is already active" }
                check(mutableLink.value is LinkState.Connected && hello!!.activeSetId.raw == 0u) { "Connect to an idle ESP32 first" }
                val id = newId()
                active = SetRecorder(id, Side.L, currentCalibration, JSONObject(), null, null)
                capture = deferred; captureStopSent = false
                mutableSession.value = SessionState.Recording(id, Side.L, 0, 0)
                try {
                    RecordingService.onUnexpectedStop = { synchronized(guard) { failActive("recording service stopped", false) } }
                    RecordingService.start(context)
                    deviceLink!!.send(Command.Start(id, Side.L))
                } catch (e: Exception) { failActive("Calibration start failed", false); throw e }
            }
            try {
                val mean = withTimeout(10_000) { deferred.await() }
                val samples = lastHoldSamples ?: throw IllegalStateException(OnArmMath.MSG_NOT_STEADY)
                val still = OnArmMath.stillness(samples) ?: throw IllegalStateException(OnArmMath.MSG_NOT_STEADY)
                if (!still.still) throw IllegalStateException(OnArmMath.MSG_NOT_STEADY)
                synchronized(guard) { bodyHolds[hold] = mean }
            } finally {
                lastHoldSamples = null
                synchronized(guard) {
                    if (capture === deferred) {
                        runCatching { deviceLink?.send(Command.Abort(active!!.id)) }
                        failActive("Calibration capture timed out or cancelled", false)
                    }
                }
            }
        }
    }

    override suspend fun saveBodyCalibration(): Result<CalibrationInfo> = attempt {
        control.withLock { synchronized(guard) {
            check(active == null) { "A set is active" }
            val saved = Calibration.fromBodyHolds(bodyHolds.toMap(), System.currentTimeMillis())
            calibrationStore.save(saved)
            currentCalibration = saved
            calibrationLoadError = null
            mutableCalibration.value = saved.info
            bodyHolds.clear()
            saved.info
        } }
    }

    override fun history() = repository.history
    override suspend fun result(id: SetId): SetResult? = withContext(Dispatchers.IO) {
        repository.result(id).also { TallyLog.i("result id=${id.raw} stored=${it?.id?.raw} path=${it?.provenance?.modelKind}") }
    }
    override suspend fun scorePartial(id: SetId): Result<SetResult> = withContext(Dispatchers.IO) { attempt {
        control.withLock {
            val recording = synchronized(guard) {
                val failed = mutableSession.value as? SessionState.Failed
                check(failed?.id == id && failed.partialScorable && active == null) { "This set cannot be scored as partial" }
                restore(id, true).also {
                    check(it.partialScorable) { "Archived set is not eligible for partial scoring" }
                    mutableSession.value = SessionState.Scoring(id)
                }
            }
            scoreRecording(recording, EndReason.DONE, true).getOrThrow()
        }
    } }
    override suspend fun rescore(id: SetId): Result<SetResult> = withContext(Dispatchers.IO) { attempt {
        TallyLog.i("rescore requested id=${id.raw}")
        control.withLock {
            val recording = synchronized(guard) {
                check(active == null && mutableSession.value !is SessionState.Scoring) { "A set is active" }
                restore(id)
            }
            val partial = recording.metadata.optBoolean("partial", false)
            val end = recording.metadata.optString("end_reason").takeIf { it.isNotEmpty() }?.let(EndReason::valueOf)
            check(end != null || partial) { "Interrupted set: use explicit partial scoring" }
            mutableSession.value = SessionState.Scoring(id)
            TallyLog.i("rescore id=${id.raw} state=Scoring samples=${recording.store.size}")
            scoreRecording(recording, if (partial) EndReason.DONE else end!!, partial).getOrThrow()
        }
    }.onFailure { TallyLog.e("rescore id=${id.raw} failed", it) } }
    override suspend fun exportCsv(id: SetId): Result<String> = attempt {
        withContext(Dispatchers.IO) { CsvExport(context, repository).export(id) }
    }

    private fun geminiKey(): String? = context.getSharedPreferences("debug", Context.MODE_PRIVATE)
        .getString("gemini_api_key", null)?.trim()?.takeIf { it.isNotEmpty() }

    private suspend fun scoreRecording(recording: SetRecorder, end: EndReason, partial: Boolean): Result<SetResult> = withContext(Dispatchers.IO) { attempt {
        try {
            val metaProvenance = recording.metadata.getJSONObject("provenance")
            val intended = recording.metadata.intendedExercise()
            val (record, localInfo) = scoreCompletedSet(geminiKey(),
                gemini = { key -> GeminiScorer(key).score(recording.side.name, recording.store, intended) },
                local = {
                    val info = scorer.warmUp()
                    val wire = buildString { TallyWireWriter.write(recording.side, recording.store, end, this) }
                    CompletedScore(scorer.score(wire, intended).record, info)
                })
            val provenance = Provenance(
                if (localInfo == null) GeminiScorer.PROVENANCE_KIND else LOCAL_MODEL_KIND,
                localInfo?.modelSha256?.getValue(recording.side) ?: "-", localInfo?.scorerSha256 ?: "-",
                BuildConfig.GIT_REV, metaProvenance.getInt("fw_version"), metaProvenance.getString("mac"),
                recording.calibration.info.id, BuildConfig.APP_VERSION,
            )
            val modelHashes = Side.entries.associate { side -> side.name to (localInfo?.modelSha256?.getValue(side) ?: "-") }
            metaProvenance.put("model_sha256", JSONObject(modelHashes)).put("scorer_sha256", provenance.scorerSha256)
            val diagnostics = record.optJSONArray("diagnostics") ?: JSONArray()
            if (partial) diagnostics.put("partial_device_lost")
            if (partial && recording.metadata.optBoolean("archive_truncated_tail", false)) diagnostics.put("partial_truncated_tail")
            if (end == EndReason.TIMING || end == EndReason.RING_OVERRUN) diagnostics.put("set_ended_${end.name.lowercase()}")
            // Preserve any diagnostics appended above before converting the scorer record.
            record.put("diagnostics", diagnostics)
            val result = record.toSetResult(recording.id, recording.side, recording.metadata.getLong("started_at_epoch_ms"),
                provenance)
            currentCoroutineContext().ensureActive()
            recording.metadata.put("partial", partial).put("provenance", metaProvenance
                .put("model_kind", provenance.modelKind)
                .put("git_rev", BuildConfig.GIT_REV).put("app_version", BuildConfig.APP_VERSION))
            repository.updateMeta(recording.id, recording.metadata)
            repository.saveResult(result)
            mutableSession.value = SessionState.Done(result)
            TallyLog.i("score id=${recording.id.raw} state=Done stored=${repository.result(recording.id)?.id?.raw} path=${provenance.modelKind}")
            result
        } catch (e: CancellationException) {
            mutableSession.value = SessionState.Failed(recording.id, "Scoring cancelled. You can score this set again.", partial)
            throw e
        } catch (e: Exception) {
            mutableSession.value = SessionState.Failed(recording.id, e.message?.takeIf { it.isNotBlank() } ?: e.javaClass.simpleName, partial)
            TallyLog.e("score id=${recording.id.raw} state=Failed", e)
            throw e
        }
    } }

    private fun restore(id: SetId, allowIncomplete: Boolean = false): SetRecorder {
        val meta = requireNotNull(repository.meta(id)) { "Unknown set" }
        val recorder = SetRecorder(id, Side.valueOf(meta.getString("side")),
            CalibrationStore.fromJson(meta.getJSONObject("calibration")), meta, null, null)
        recorder.replay(repository.frames(id), allowIncomplete || meta.optBoolean("partial", false))
        return recorder
    }

    private fun metadata(id: SetId, side: Side, info: ScorerInfo?) = JSONObject()
        .put("id", id.raw.toLong()).put("side", side.name).put("started_at_epoch_ms", System.currentTimeMillis())
        .put("calibration", CalibrationStore.toJson(currentCalibration))
        .put("provenance", JSONObject().apply {
            if (info != null) put("model_kind", LOCAL_MODEL_KIND)
                .put("model_sha256", JSONObject(info.modelSha256.mapKeys { it.key.name })).put("scorer_sha256", info.scorerSha256)
        }
            .put("git_rev", BuildConfig.GIT_REV).put("fw_version", hello!!.device.fwVersion).put("mac", hello!!.device.mac)
            .put("reset_reason", hello!!.resetReason).put("adc_attenuation_code", hello!!.atten)
            .put("calibration_id", currentCalibration.info.id).put("app_version", BuildConfig.APP_VERSION))

    private fun newId(): SetId {
        val existing = repository.ids().toSet()
        while (true) { val id = SetId(random.nextInt().toUInt()); if (id.raw != 0u && id !in existing) return id }
    }
    private suspend fun <T> attempt(block: suspend () -> T): Result<T> = try { Result.success(block()) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { Result.failure(e) }

    companion object {
        private const val LOCAL_MODEL_KIND = "paired-synchronized-offline"
        // Derived conservative duration gate: 4 × minimum 1.2 s peak spacing × 100 Hz.
        // The scorer still decides whether the prefix contains three usable cycles.
        private const val PARTIAL_MIN_SAMPLES = 480
    }
}
