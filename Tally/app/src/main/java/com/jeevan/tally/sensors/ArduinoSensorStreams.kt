package com.jeevan.tally.sensors

/** Every advertised plug uses the same runtime adapter. Metadata contains no Android types. */
class ArduinoPlugStream(val spec: PlugSpec) : SensorStream {
    override val title = spec.displayName
    override val description = "${spec.axisCount} channel values from the Arduino · ${spec.kind.name.lowercase()}"
    override val axisNames = spec.outputAxes
    override val axisColorsHex = axisNames.indices.map { axis ->
        val palette = (listOf(spec.accentHex) + listOf("#26372C", "#995438", "#586442", "#72523D")).distinct()
        palette[axis % palette.size]
    }
    override val unit = spec.unit
    override val permissions = emptyList<String>()
    override fun isCompatible() = ArduinoLink.plugs.value.any { it == spec }
    override fun samples() = ArduinoLink.samples(spec.id)
    override fun sampleBatches() = ArduinoLink.batches(spec.id)
}
