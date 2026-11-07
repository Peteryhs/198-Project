package com.jeevan.tally.sensors

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
    }

    /** PLUGS is an atomic catalog replacement; any malformed descriptor rejects the line. */
    fun parseMessage(raw: String): Message? = runCatching {
        if (raw.length > 8192) return null
        val fields = raw.trim().split(',').map(String::trim)
        when (fields.firstOrNull()?.uppercase()) {
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
