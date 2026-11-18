package com.tally.app.ui

import com.tally.app.contract.BodyHold
import com.tally.app.contract.CalPose
import com.tally.app.contract.CalibrationInfo
import com.tally.app.contract.LinkState
import com.tally.app.contract.Side
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

// All user-facing words for backend values. Plain language, sentence case, no exclamation marks.

fun sideWords(side: Side) = when (side) { Side.L -> "Left arm"; Side.R -> "Right arm" }

fun exerciseWords(code: String) = when (code) {
    "EAH" -> "Arms raised overhead"
    "EFE" -> "Elbow bend and straighten"
    "SQZ" -> "Squeezing"
    else -> "Exercise not identified"
}

/** The set verdict in words. Statuses come from SetRepository: scored, insufficient_reps, rejected, interrupted, unreadable. */
fun verdictWords(status: String, wrong: Boolean?, wrongExercise: Boolean = false): String = when (status) {
    "scored" -> when {
        wrongExercise -> "Wrong exercise"
        wrong == false -> "Correct form"; wrong == true -> "Wrong form"; else -> "Result unavailable"
    }
    "insufficient_reps" -> "Too few reps to judge"
    "rejected" -> "Could not assess this set"
    "interrupted" -> "Not scored yet"
    "unreadable" -> "Set could not be read"
    else -> "Result unavailable"
}

fun probability(p: Double) = String.format(Locale.ROOT, "%.2f", p)

/** The set is wrong form when any rep is (tally_app._decide); the mean is shown as supporting detail only. */
fun poolingWords(wrongReps: Int, reps: Int, meanPWrong: Double) =
    "$wrongReps of $reps reps looked wrong. One wrong rep marks the set wrong. Average chance of wrong form: ${probability(meanPWrong)}."

/** Names the model's class against the exercise the user chose, or says it was not checked. */
fun exerciseCheckWords(exercise: String, intended: String?) = when (intended) {
    null -> "Exercise: ${exerciseWords(exercise)}. Unverified: no exercise was chosen before the set."
    exercise -> "Exercise: ${exerciseWords(exercise)}, as chosen."
    else -> "You chose ${exerciseWords(intended)}, but the model classed the set as ${exerciseWords(exercise)}."
}

fun intendedWords(intended: String?) =
    if (intended == null) "Not specified. The result will say the exercise class is unverified."
    else "${exerciseWords(intended)}. A different class is reported as wrong exercise."

const val unvalidatedWords = "Exercise class and form verdict are unvalidated on this hardware."
const val modelOriginWords = "The class comes from a model trained on a different sensor and an undocumented mount."

fun elapsed(ms: Long): String {
    val s = (ms / 1000).coerceAtLeast(0)
    return String.format(Locale.ROOT, "%d:%02d", s / 60, s % 60)
}

private val dateFormat = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.UK)
fun dateWords(epochMs: Long): String = dateFormat.format(Instant.ofEpochMilli(epochMs).atZone(ZoneId.systemDefault()))

fun poseWords(pose: CalPose) = when (pose) {
    CalPose.X_POS -> "X axis pointing up"
    CalPose.X_NEG -> "X axis pointing down"
    CalPose.Y_POS -> "Y axis pointing up"
    CalPose.Y_NEG -> "Y axis pointing down"
    CalPose.Z_POS -> "Z axis pointing up"
    CalPose.Z_NEG -> "Z axis pointing down"
}

internal fun bodyHoldWords(hold: BodyHold): String = when (hold) {
    BodyHold.HANG -> "Let your arm hang down by your side"
    BodyHold.FORWARD_PALM_UP -> "Arm straight forward, palm up"
    BodyHold.SIDE_PALM_FORWARD -> "Arm out to the side, palm forward"
    BodyHold.OVERHEAD -> "Arm above your head, elbow straight"
    BodyHold.CHECK -> "Forearm resting on the table, palm up"
}

fun calibrationWords(c: CalibrationInfo?): String = when {
    c == null -> "No calibration is loaded."
    c.nominal -> "Calibration nominal, starting values: documented ADXL335 values, not measurements from this device. " +
        "These constants convert live sensor millivolts to g; they do not replace sensor readings. " +
        "New sets keep using them until you save the body holds."
    c.id.startsWith("body-") -> "Calibration ${c.id} in use. Body holds saved; marginal: per-device gains and absolute scale are unmeasured (nominal gain)."
    else -> "Six-pose calibration from ${dateWords(c.createdAtEpochMs)}. Id ${c.id}."
}

const val calibrationCaptureWords = "Each hold captures about one second of live millivolt readings from both sensors on the ESP32. " +
    "Saving the body holds replaces the starting offsets for new sets. Per-device gains and absolute scale remain unmeasured."

fun linkWords(link: LinkState) = when (link) {
    LinkState.Disconnected -> "Not connected"
    LinkState.Joining -> "Joining the Tally Wi-Fi network"
    LinkState.Connecting -> "Opening a connection to the device"
    is LinkState.Connected -> "Connected"
    is LinkState.Lost -> "Connection lost"
}

internal fun failureText(error: Throwable): String =
    error.message?.takeIf { it.isNotBlank() } ?: error.javaClass.simpleName.takeIf { it.isNotBlank() } ?: "Operation failed"

internal fun scoringPathWords(kind: String): String = if (kind.startsWith("gemini-"))
    "Scored by: Gemini ($kind)" else "Scored by: codex-side model ($kind)"
