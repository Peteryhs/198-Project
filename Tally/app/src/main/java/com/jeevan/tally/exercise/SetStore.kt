package com.jeevan.tally.exercise

import java.io.File
import java.util.UUID

data class SavedSet(
    val id: String,
    val name: String,
    val savedAt: Long,
    val summary: SetSummary,
    val reps: List<Rep>,
)

/**
 * Plain-text, versioned set files ("TALLY-SET-1"): human-readable, diff-able and small. Only the
 * non-derived [SetTotals] and the repetitions are stored; every ratio is recomputed on load by the
 * same [SetTotals.summarize] the live screen uses.
 */
object SetCodec {
    private const val HEADER = "TALLY-SET-1"

    fun encode(id: String, name: String, savedAt: Long, s: SetSummary, reps: List<Rep>): String = buildString {
        fun put(key: String, value: Any?) { append(key).append('=').append(value?.toString().orEmpty()).append('\n') }
        append(HEADER).append('\n')
        put("id", id); put("name", name.replace('\n', ' ').replace('\r', ' ')); put("savedAt", savedAt)
        val p = s.prescription
        put("exercise", p.exercise.name); put("targetCount", p.targetCount)
        put("minSeconds", p.minSeconds); put("targetSeconds", p.targetSeconds); put("maxSeconds", p.maxSeconds)
        put("prescriptionId", p.prescriptionId)
        put("source", s.source.name); put("startedAt", s.startedAtMillis); put("finished", if (s.finished) 1 else 0)
        put("counted", s.counted); put("activeSeconds", s.activeSeconds); put("pauseCount", s.pauseCount)
        put("samplesReceived", s.samplesReceived); put("expectedSamples", s.expectedSamples)
        put("coverage", s.coverage); put("coverageDevice", if (s.coverageFromDeviceClock) 1 else 0)
        put("timingGaps", s.timingGaps); put("clipped", s.clippedSamples); put("dropped", s.droppedSamples)
        put("faults", s.faults); put("boardRestarts", s.boardRestarts)
        put("calibrationSignal", s.calibrationSignal?.name); put("calibrationRange", s.calibrationRangeDegrees)
        put("calibrationEvents", s.calibrationEvents)
        put("assessment", s.assessment?.let { (it.exerciseProbability + it.pIncorrect).joinToString(";") })
        put("observedCount", s.observedCount)
        for (r in reps) {
            append("rep=").append(listOf(r.index, r.t, r.paceSeconds, r.movementSeconds, r.peakRangeFraction,
                r.full?.let { if (it) 1 else 0 }, r.cue.code).joinToString(",") { it?.toString().orEmpty() }).append('\n')
        }
    }

    fun decode(text: String): SavedSet {
        val lines = text.lines().filter { it.isNotEmpty() }
        require(lines.firstOrNull() == HEADER) { "Not a Tally set file" }
        val fields = mutableMapOf<String, String>()
        val reps = mutableListOf<Rep>()
        for (line in lines.drop(1)) {
            val split = line.indexOf('=')
            require(split > 0) { "Malformed line" }
            val key = line.substring(0, split)
            val value = line.substring(split + 1)
            if (key == "rep") reps += decodeRep(value) else fields[key] = value
        }
        fun str(k: String) = fields[k] ?: throw IllegalArgumentException("Missing $k")
        fun optional(k: String) = fields[k]?.takeIf(String::isNotEmpty)
        fun float(k: String) = optional(k)?.toFloat()
        fun int(k: String) = str(k).toInt()
        fun long(k: String) = str(k).toLong()
        val prescription = Prescription(
            Exercise.valueOf(str("exercise")), int("targetCount"),
            float("minSeconds"), float("targetSeconds"), float("maxSeconds"), fields["prescriptionId"].orEmpty(),
        )
        val assessment = optional("assessment")?.split(';')?.map(String::toFloat)?.let {
            require(it.size == 4) { "Malformed assessment" }
            ModelAssessment(it.take(3), it[3])
        }
        val totals = SetTotals(
            source = CountSource.valueOf(str("source")),
            startedAtMillis = long("startedAt"),
            finished = int("finished") == 1,
            counted = int("counted"),
            activeSeconds = float("activeSeconds") ?: 0f,
            pauseCount = int("pauseCount"),
            samplesReceived = long("samplesReceived"),
            expectedSamples = long("expectedSamples"),
            coverage = float("coverage"),
            coverageFromDeviceClock = int("coverageDevice") == 1,
            timingGaps = int("timingGaps"),
            clippedSamples = long("clipped"),
            droppedSamples = long("dropped"),
            faults = int("faults"),
            boardRestarts = int("boardRestarts"),
            calibrationSignal = optional("calibrationSignal")?.let(AngleSignal::valueOf),
            calibrationRangeDegrees = float("calibrationRange"),
            calibrationEvents = int("calibrationEvents"),
            assessment = assessment,
            observedCount = optional("observedCount")?.toInt(),
        )
        return SavedSet(str("id"), str("name"), long("savedAt"), totals.summarize(prescription, reps), reps)
    }

    private fun decodeRep(value: String): Rep {
        val p = value.split(',')
        require(p.size == 7) { "Malformed repetition" }
        fun f(i: Int) = p[i].takeIf(String::isNotEmpty)?.toFloat()
        return Rep(
            index = p[0].toInt(), t = p[1].toFloat(), paceSeconds = f(2), movementSeconds = f(3),
            peakRangeFraction = f(4), full = p[5].takeIf(String::isNotEmpty)?.let { it == "1" },
            cue = TempoCue.fromCode(p[6].toInt()) ?: TempoCue.ABSTAIN,
        )
    }
}

/** Private set files; a completed file is published by an atomic rename, like RecordingStore. */
class SetStore(private val directory: File) {
    fun save(name: String, tracker: SetTracker): SavedSet {
        require(name.isNotBlank() && name.length <= 80) { "Name must be 1–80 characters." }
        check(directory.isDirectory || directory.mkdirs()) { "Cannot create sets folder" }
        val id = UUID.randomUUID().toString()
        val text = SetCodec.encode(id, name.trim(), System.currentTimeMillis(), tracker.summary(), tracker.reps)
        val temp = File(directory, "$id.tmp")
        try {
            temp.writeText(text)
            check(temp.renameTo(File(directory, "$id.set"))) { "Could not publish set" }
        } finally {
            temp.delete()
        }
        return SetCodec.decode(text)
    }

    fun list(): List<SavedSet> = directory.listFiles { f -> f.name.endsWith(".set") }.orEmpty()
        .mapNotNull { runCatching { SetCodec.decode(it.readText()) }.getOrNull() }
        .sortedByDescending { it.savedAt }

    fun load(id: String): SavedSet = SetCodec.decode(file(id).readText())

    fun delete(id: String): Boolean = file(id).delete()

    private fun file(id: String): File {
        require(Regex("[0-9a-fA-F-]{36}").matches(id)) { "Invalid set id" }
        return File(directory, "$id.set")
    }
}
