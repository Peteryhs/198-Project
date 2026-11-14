package com.jeevan.tally.exercise

/**
 * Pure exercise-session vocabulary. Codes mirror model/feedback/feedback.h and
 * model/application/tally_app.h so the board's TallyOutput can be logged without translation.
 */
enum class Exercise(val code: Int, val label: String) {
    EAH(1, "Arms over head"),
    EFE(2, "Elbow flexion"),
    SQZ(3, "Squeeze");

    companion object {
        fun fromCode(code: Int) = entries.firstOrNull { it.code == code }
    }
}

/** FeedbackCue codes 0..3. ABSTAIN means "not enough evidence to say". */
enum class TempoCue(val code: Int, val label: String) {
    ABSTAIN(0, "No pace verdict"),
    ON_TARGET(1, "Pace on target"),
    TOO_FAST(2, "Faster than target"),
    TOO_SLOW(3, "Slower than target");

    companion object {
        fun fromCode(code: Int) = entries.firstOrNull { it.code == code }
    }
}

/** TallyState codes 0..4. */
enum class BoardState(val label: String) {
    IDLE("Idle"), READY("Ready"), RUNNING("Running"), PAUSED("Paused"), FINISHED("Finished");

    companion object {
        fun fromCode(code: Int) = entries.getOrNull(code)
    }
}

/** TALLY_* fault bits from tally_app.h, plus app-side bits above them for faults only the phone sees. */
object Faults {
    const val BAD_SAMPLE = 1
    const val TIMING_GAP = 2
    const val CLIPPED = 4
    const val OVERFLOW = 8
    const val MODEL_ERROR = 16
    const val APP_DROPPED = 256
    const val CONNECTION_LOST = 512

    private val names = listOf(
        BAD_SAMPLE to "Bad sample",
        TIMING_GAP to "Timing gap",
        CLIPPED to "Sensor clipped (±3 g)",
        OVERFLOW to "Buffer overflow",
        MODEL_ERROR to "Model error",
        APP_DROPPED to "Samples dropped on the phone",
        CONNECTION_LOST to "Connection lost",
    )

    fun describe(mask: Int): List<String> = names.filter { (bit, _) -> mask and bit != 0 }.map { it.second }
}

/**
 * What the person was asked to do. The tempo range is optional, but when present all three
 * values must be given and ordered — there is deliberately no default therapeutic range.
 */
data class Prescription(
    val exercise: Exercise,
    val targetCount: Int,
    val minSeconds: Float? = null,
    val targetSeconds: Float? = null,
    val maxSeconds: Float? = null,
    val prescriptionId: String = "",
) {
    init {
        require(targetCount in 1..999) { "Target count must be between 1 and 999." }
        val tempo = listOf(minSeconds, targetSeconds, maxSeconds)
        require(tempo.all { it == null } || tempo.all { it != null }) { "Give all three pace values or none." }
        if (minSeconds != null && targetSeconds != null && maxSeconds != null) {
            require(tempo.all { it!!.isFinite() && it > 0f }) { "Pace values must be positive." }
            require(minSeconds <= targetSeconds && targetSeconds <= maxSeconds) { "Pace values must satisfy min ≤ target ≤ max." }
            require(maxSeconds <= 60f) { "Pace values must be 60 s or less." }
        }
        require(prescriptionId.length <= 47 && prescriptionId.none { it == ',' || it == '\n' || it == '\r' }) {
            "Prescription ID must be under 48 characters, without commas or line breaks."
        }
    }

    val hasTempo get() = minSeconds != null

    /** Inclusive range, like feedback_evaluate. Returns ABSTAIN when no range was prescribed. */
    fun classify(paceSeconds: Float?): TempoCue = when {
        !hasTempo || paceSeconds == null || !paceSeconds.isFinite() -> TempoCue.ABSTAIN
        paceSeconds < minSeconds!! -> TempoCue.TOO_FAST
        paceSeconds > maxSeconds!! -> TempoCue.TOO_SLOW
        else -> TempoCue.ON_TARGET
    }
}

/** One TALLY status frame: a field-for-field copy of TallyOutput. */
data class BoardStatus(
    val state: BoardState,
    val cycles: Int,
    val targetCount: Int,
    val activeMs: Long,
    val faults: Int,
    val cycleSeconds: Float,
    val durationAvailable: Boolean,
    val cue: TempoCue,
    val timingReason: Int,
    val assessmentAvailable: Boolean,
    /** Mean P(EAH), P(EFE), P(SQZ). Only meaningful when [assessmentAvailable]. */
    val exerciseProbability: List<Float>,
    /** Mean model probability of study class 1: incorrect. Only meaningful when [assessmentAvailable]. */
    val pIncorrect: Float,
)

/** The board's model verdict, kept only when tally_finish said it is available. */
data class ModelAssessment(val exerciseProbability: List<Float>, val pIncorrect: Float) {
    val likelyExercise: Exercise get() = Exercise.entries[exerciseProbability.indices.maxBy { exerciseProbability[it] }]
    /** The study's 0.5 decision on a series label — not a per-repetition or clinical judgment. */
    val seriesLabelIncorrect get() = pIncorrect >= 0.5f
}

enum class CountSource(val label: String) {
    BOARD("Board firmware"),
    APP("Tally app estimate"),
}

/**
 * One logged repetition. [t] is the active-time second it completed. [paceSeconds] is the
 * interval since the previous repetition (the same quantity as the board's cycle_seconds).
 * Range fields are null when the source cannot tell (board mode reports cycles, not angles).
 */
data class Rep(
    val index: Int,
    val t: Float,
    val paceSeconds: Float?,
    val movementSeconds: Float? = null,
    val peakRangeFraction: Float? = null,
    val full: Boolean? = null,
    val cue: TempoCue = TempoCue.ABSTAIN,
)
