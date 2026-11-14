package com.jeevan.tally.sensors

import com.jeevan.tally.exercise.BoardState
import com.jeevan.tally.exercise.BoardStatus
import com.jeevan.tally.exercise.Exercise
import com.jeevan.tally.exercise.Prescription
import com.jeevan.tally.exercise.TempoCue

/**
 * Pure parser for the Arduino wire protocol — kept free of any Android/IO dependency so it's
 * a plain JVM unit test target (see app/src/test). One reading per line:
 *
 *   A,<x>,<y>,<z>   accelerometer reading
 *   G,<x>,<y>,<z>   gyroscope reading
 */
object LineProtocol {

    enum class Channel { ACCEL, GYRO }

    data class Reading(val channel: Channel, val x: Float, val y: Float, val z: Float)

    fun parse(rawLine: String): Reading? {
        val line = rawLine.trim()
        if (line.isEmpty()) return null

        val parts = line.split(",")
        if (parts.size < 4) return null

        val channel = when (parts[0].trim().uppercase()) {
            "A" -> Channel.ACCEL
            "G" -> Channel.GYRO
            else -> return null
        }

        val x = parts[1].trim().toFloatOrNull() ?: return null
        val y = parts[2].trim().toFloatOrNull() ?: return null
        val z = parts[3].trim().toFloatOrNull() ?: return null

        if (!x.isFinite() || !y.isFinite() || !z.isFinite()) return null
        return Reading(channel, x, y, z)
    }

    sealed interface Message {
        data class Plugs(val specs: List<PlugSpec>) : Message
        data class Values(val id: String, val values: List<Float>) : Message
        /** One synchronized upper-arm + forearm frame in g, from the board's documented CSV row. */
        class PairFrame(val deviceMillis: Long, val values: FloatArray) : Message
        /** One TallyOutput snapshot from the board's application layer. */
        data class Status(val status: BoardStatus) : Message
        /** The prescription the board was configured with (echo of its `C` command). */
        data class BoardConfig(val prescription: Prescription, val prescribed: Boolean) : Message
        /** The board's calibrate button finished, successfully or not. */
        data class Calibration(val ok: Boolean, val detail: String) : Message
    }

    private val numericRow = Regex("[0-9]{1,10}")

    /** `time_ms,upper_ax_g,upper_ay_g,upper_az_g,forearm_ax_g,forearm_ay_g,forearm_az_g`, no header. */
    private fun pairFrame(fields: List<String>): Message.PairFrame? {
        if (fields.size != 7 || !numericRow.matches(fields[0])) return null
        val time = fields[0].toLong()
        require(time <= 0xFFFF_FFFFL)
        val values = FloatArray(6) { fields[it + 1].toFloat().also { v -> require(v.isFinite()) } }
        return Message.PairFrame(time, values)
    }

    private fun boardStatus(f: List<String>): Message.Status {
        require(f.size == 15)
        fun int(i: Int, range: IntRange) = f[i].toInt().also { require(it in range) }
        val assessment = int(10, 0..1) == 1
        val probabilities = (11..14).map { f[it].toFloatOrNull() ?: Float.NaN }
        if (assessment) require(probabilities.all { it.isFinite() && it in 0f..1f })
        val cycleSeconds = f[6].toFloatOrNull() ?: Float.NaN
        val durationAvailable = int(7, 0..1) == 1
        if (durationAvailable) require(cycleSeconds.isFinite() && cycleSeconds >= 0f)
        return Message.Status(BoardStatus(
            state = BoardState.fromCode(int(1, 0..4))!!,
            cycles = int(2, 0..1_000_000),
            targetCount = int(3, 0..9999),
            activeMs = f[4].toLong().also { require(it in 0..0xFFFF_FFFFL) },
            faults = int(5, 0..255),
            cycleSeconds = cycleSeconds,
            durationAvailable = durationAvailable,
            cue = TempoCue.fromCode(int(8, 0..3))!!,
            timingReason = int(9, 0..6),
            assessmentAvailable = assessment,
            exerciseProbability = probabilities.take(3),
            pIncorrect = probabilities[3],
        ))
    }

    private fun boardConfig(f: List<String>): Message.BoardConfig {
        require(f.size in 7..8)
        val exercise = Exercise.fromCode(f[1].toInt())!!
        return Message.BoardConfig(
            Prescription(exercise, f[2].toInt(), f[3].toFloat(), f[4].toFloat(), f[5].toFloat(), f.getOrNull(7).orEmpty()),
            prescribed = f[6] == "1",
        )
    }

    /** PLUGS is an atomic catalog replacement; any malformed descriptor rejects the line. */
    fun parseMessage(raw: String): Message? = runCatching {
        if (raw.length > 8192) return null
        val fields = raw.trim().split(',').map(String::trim)
        pairFrame(fields)?.let { return it }
        when (fields.firstOrNull()?.uppercase()) {
            "TALLY" -> boardStatus(fields)
            "TALLYCFG" -> boardConfig(fields)
            "CAL" -> {
                require(fields.size >= 2 && fields[1] in setOf("0", "1"))
                Message.Calibration(fields[1] == "1", fields.drop(2).joinToString(", ").take(120))
            }
            "PLUGS" -> {
                if (fields.size !in 2..33) return null
                val specs = fields.drop(1).map { descriptor ->
                    val p = descriptor.split(':')
                    require(p.size in 2..9)
                    val count = p[1].toInt()
                    require(count in 1..16)
                    var spec = PlugSpec.basic(p[0], count)
                    fun field(i: Int) = p.getOrNull(i)?.takeIf(String::isNotBlank)
                    spec = spec.copy(
                        kind = field(2)?.let { ValueKind.valueOf(it.uppercase()) } ?: spec.kind,
                        unit = field(3) ?: spec.unit,
                        displayName = field(4) ?: spec.displayName,
                        axisNames = field(5)?.split('|') ?: spec.axisNames,
                        minimum = field(6)?.toFloat(), maximum = field(7)?.toFloat(),
                        icon = field(8) ?: spec.icon,
                        magnitude = spec.magnitude && (field(2) == null || field(2).equals("vector", true)),
                    )
                    require(spec.axisCount == count)
                    spec
                }
                require(specs.map { it.id }.distinct().size == specs.size)
                Message.Plugs(specs)
            }
            "D" -> {
                if (fields.size !in 3..18) return null
                val id = PlugSpec.canonicalId(fields[1])
                require(Regex("[a-z][a-z0-9_-]{0,39}").matches(id))
                val values = fields.drop(2).map { it.toFloat().also { value -> require(value.isFinite()) } }
                Message.Values(id, values)
            }
            else -> parse(raw)?.let { Message.Values(if (it.channel == Channel.ACCEL) "accelerometer" else "gyroscope", listOf(it.x, it.y, it.z)) }
        }
    }.getOrNull()
}
