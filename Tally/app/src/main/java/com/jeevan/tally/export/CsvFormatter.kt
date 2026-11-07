package com.jeevan.tally.export

import com.jeevan.tally.sensors.SensorSample

/** Pure CSV text building, split out from CsvExporter so it's a plain JVM unit test target. */
object CsvFormatter {

    fun headerRow(axisNames: List<String>): String =
        "t_seconds," + axisNames.joinToString(",") { csvCell(it) }

    private fun csvCell(value: String): String {
        val safe = if (value.firstOrNull() in listOf('=', '+', '-', '@')) "'" + value else value
        return if (safe.any { it == ',' || it == '"' || it == '\n' || it == '\r' })
            "\"" + safe.replace("\"", "\"\"") + "\"" else safe
    }

    fun dataRow(sample: SensorSample): String = buildString {
        append(sample.t)
        for (v in sample.values) {
            append(',')
            append(v)
        }
    }

    fun toCsv(axisNames: List<String>, samples: List<SensorSample>): String = buildString {
        appendLine(headerRow(axisNames))
        for (s in samples) {
            appendLine(dataRow(s))
        }
    }

    /** A filesystem-safe basename: letters, digits and underscores only, no leading/trailing underscore. */
    fun safeFileStem(title: String): String =
        title.replace(Regex("[^A-Za-z0-9_]+"), "_").trim('_')
}
