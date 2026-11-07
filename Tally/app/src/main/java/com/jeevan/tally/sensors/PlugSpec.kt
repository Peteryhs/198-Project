package com.jeevan.tally.sensors

import kotlin.math.sqrt

enum class ValueKind { VECTOR, SCALAR, BOOLEAN, EVENT }

/** Transport-neutral metadata. axisNames describes wire values; magnitude is derived locally. */
data class PlugSpec(
    val id: String,
    val displayName: String,
    val axisNames: List<String>,
    val unit: String = "raw",
    val kind: ValueKind = if (axisNames.size == 1) ValueKind.SCALAR else ValueKind.VECTOR,
    val icon: String = "sensor",
    val accentHex: String = "#995438",
    val minimum: Float? = null,
    val maximum: Float? = null,
    val magnitude: Boolean = false,
) {
    val axisCount get() = axisNames.size
    val outputAxes get() = axisNames + if (magnitude) listOf("magnitude") else emptyList()
    init {
        require(Regex("[a-z][a-z0-9_-]{0,39}").matches(id))
        require(displayName.isNotBlank() && displayName.length <= 80)
        require(axisCount in 1..16 && axisNames.all { it.isNotBlank() && it.length <= 40 })
        require(axisNames.distinct().size == axisCount)
        require(unit.length <= 40 && Regex("#[0-9a-fA-F]{6}").matches(accentHex))
        require(kind == ValueKind.VECTOR || axisCount == 1)
        require(!magnitude || kind == ValueKind.VECTOR)
        require(minimum == null || minimum.isFinite())
        require(maximum == null || maximum.isFinite())
        require(minimum == null || maximum == null || minimum < maximum)
    }
    fun interpret(values: List<Float>): FloatArray? {
        if (values.size != axisCount || values.any { !it.isFinite() }) return null
        if ((kind == ValueKind.BOOLEAN || kind == ValueKind.EVENT) && values.any { it != 0f && it != 1f }) return null
        val result = if (magnitude) values + sqrt(values.sumOf { it.toDouble() * it }).toFloat() else values
        return result.takeIf { it.all(Float::isFinite) }?.toFloatArray()
    }
    companion object {
        val accel = PlugSpec("accelerometer", "Accelerometer", listOf("x", "y", "z"), "m/s²", icon = "motion", accentHex = "#26372C", magnitude = true)
        val gyro = PlugSpec("gyroscope", "Gyroscope", listOf("x", "y", "z"), "°/s", icon = "rotation", magnitude = true)
        val legacy = listOf(accel, gyro)
        fun canonicalId(id: String) = when (id.lowercase()) { "accel", "a" -> "accelerometer"; "gyro", "g" -> "gyroscope"; else -> id.lowercase() }
        fun basic(id: String, count: Int): PlugSpec {
            val canonical = canonicalId(id)
            if (count == 3) legacy.find { it.id == canonical }?.let { return it }
            return PlugSpec(canonical, canonical.replace('_', ' ').replaceFirstChar { it.uppercase() },
                if (count == 1) listOf("value") else List(count) { "axis_${it + 1}" })
        }
    }
}
