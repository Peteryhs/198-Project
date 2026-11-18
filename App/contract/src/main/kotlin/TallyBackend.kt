package com.tally.app.contract

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

interface TallyBackend {
    val link: StateFlow<LinkState>
    val session: StateFlow<SessionState>
    val calibration: StateFlow<CalibrationInfo?>
    val live: LiveRing
    suspend fun connect(): Result<DeviceInfo>
    suspend fun disconnect()
    /** [intendedExercise] is the class the user meant to do, or null when not specified. */
    suspend fun startSet(side: Side, intendedExercise: String? = null): Result<SetId>
    suspend fun stopSet(): Result<Unit>
    suspend fun abortSet(): Result<Unit>
    suspend fun scorePartial(id: SetId): Result<SetResult>
    suspend fun captureCalibrationPose(pose: CalPose): Result<Unit>
    suspend fun saveCalibration(): Result<CalibrationInfo>
    /** Capture one on-arm body hold; refused with a plain-words reason when the hold was not steady. */
    suspend fun captureBodyHold(hold: BodyHold): Result<Unit>
    /** Fit offsets and the functional frames from the captured holds. */
    suspend fun saveBodyCalibration(): Result<CalibrationInfo>
    fun history(): Flow<List<SetSummary>>
    suspend fun result(id: SetId): SetResult?
    suspend fun rescore(id: SetId): Result<SetResult>
    suspend fun exportCsv(id: SetId): Result<String>
}
