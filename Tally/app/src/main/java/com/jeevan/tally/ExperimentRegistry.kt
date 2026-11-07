package com.jeevan.tally

import android.content.Context
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import com.jeevan.tally.sensors.*

data class ExperimentEntry(val spec: PlugSpec) {
    val id get() = spec.id
    val icon: ImageVector get() = when (spec.icon) {
        "motion" -> Icons.Filled.Speed
        "rotation" -> Icons.Filled.Vibration
        "temperature" -> Icons.Filled.Thermostat
        "event" -> Icons.Filled.TouchApp
        else -> Icons.Filled.Sensors
    }
    val accent get() = Color(android.graphics.Color.parseColor(spec.accentHex))
    val factory: (Context) -> SensorStream get() = { ArduinoPlugStream(spec) }
}

object ExperimentRegistry {
    val all get() = ArduinoLink.plugs.value.map(::ExperimentEntry)
    fun find(id: String) = all.find { it.id == id }
}
