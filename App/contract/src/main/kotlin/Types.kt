package com.tally.app.contract

import kotlinx.coroutines.flow.StateFlow

enum class Side { L, R }
@JvmInline value class SetId(val raw: UInt)
sealed interface LinkState {
    data object Disconnected : LinkState
    data object Joining : LinkState
    data object Connecting : LinkState
    data class Connected(val device: DeviceInfo) : LinkState
    data class Lost(val reason: String, val sinceMs: Long) : LinkState
}
data class DeviceInfo(val mac: String, val fwVersion: Int, val lastResetReason: String)
sealed interface SessionState {
    data object Idle : SessionState
    data class Recording(val id: SetId, val side: Side, val samples: Int, val linkStallMs: Long) : SessionState
    data class Scoring(val id: SetId) : SessionState
    data class Done(val result: SetResult) : SessionState
    data class Failed(val id: SetId, val reason: String, val partialScorable: Boolean) : SessionState
}
// Per-rep verdicts are estimates from series-level labels. A set is wrong when any rep is wrong.
data class RepResult(val index: Int, val wrong: Boolean, val pWrong: Double,
                     val exercise: String, val durationS: Double)
data class Provenance(val modelKind: String, val modelSha256: String, val scorerSha256: String,
                      val gitRev: String, val fwVersion: Int, val mac: String,
                      val calibrationId: String, val appVersion: String)
data class SetResult(val id: SetId, val side: Side, val startedAtEpochMs: Long,
                     val status: String, val wrong: Boolean?, val meanPWrong: Double?, val exercise: String?,
                     val reps: List<RepResult>, val diagnostics: List<String>,
                     val measuredRateHz: Double?, val provenance: Provenance, val chart: SetChart? = null,
                     val intendedExercise: String? = null) {
    /** `wrong` is true for these too: the scorer's class is not the exercise the user chose. */
    val wrongExercise get() = status == "scored" && intendedExercise != null && exercise != intendedExercise
}

/** Display-only acceleration magnitudes from the recorded channels, including gravity. */
data class ChartSample(val timeS: Double, val upperArmG: Float, val forearmG: Float) {
    init {
        require(timeS.isFinite() && timeS >= 0)
        require(upperArmG.isFinite() && upperArmG >= 0 && forearmG.isFinite() && forearmG >= 0)
    }
}

/** First and last recorded sample times in the scorer's repetition window. */
data class RepSpan(val index: Int, val startS: Double, val endS: Double) {
    init { require(index > 0 && startS.isFinite() && endS.isFinite() && startS >= 0 && endS > startS) }
}

data class SetChart(val samples: List<ChartSample>, val reps: List<RepSpan>) {
    init {
        require(samples.size >= 2 && samples.zipWithNext().all { (a, b) -> b.timeS > a.timeS })
        require(reps.map { it.index }.distinct().size == reps.size)
        require(reps.zipWithNext().all { (a, b) -> b.startS >= a.endS })
        require(reps.all { it.startS >= samples.first().timeS && it.endS <= samples.last().timeS })
    }
}
data class SetSummary(val id: SetId, val side: Side, val startedAtEpochMs: Long,
                      val status: String, val wrong: Boolean?, val exercise: String?, val repCount: Int,
                      val intendedExercise: String? = null)
enum class CalPose { X_POS, X_NEG, Y_POS, Y_NEG, Z_POS, Z_NEG }

/**
 * On-arm body holds for the body-hold calibration. The user never reads these names and no axis is
 * named in the UI: each value is one instructed body action.
 */
enum class BodyHold { HANG, FORWARD_PALM_UP, SIDE_PALM_FORWARD, OVERHEAD, CHECK }
data class CalibrationInfo(val id: String, val nominal: Boolean, val createdAtEpochMs: Long)
interface LiveRing {
    val capacitySamples: Int
    val version: StateFlow<Long>
    fun copyLatest(dst: FloatArray, maxSamples: Int): Int
}
