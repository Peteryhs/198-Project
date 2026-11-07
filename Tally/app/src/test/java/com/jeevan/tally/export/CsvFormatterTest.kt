package com.jeevan.tally.export

import com.jeevan.tally.sensors.SensorSample
import org.junit.Assert.assertEquals
import org.junit.Test

class CsvFormatterTest {

    @Test
    fun `header row joins t_seconds with the axis names`() {
        assertEquals(
            "t_seconds,x,y,z,magnitude",
            CsvFormatter.headerRow(listOf("x", "y", "z", "magnitude")),
        )
    }

    @Test
    fun `data row lists elapsed time then each axis value`() {
        val sample = SensorSample(1.5f, floatArrayOf(0.1f, 9.8f, -0.3f))
        assertEquals("1.5,0.1,9.8,-0.3", CsvFormatter.dataRow(sample))
    }

    @Test
    fun `toCsv produces a header line followed by one line per sample`() {
        val samples = listOf(
            SensorSample(0f, floatArrayOf(1f, 2f)),
            SensorSample(0.02f, floatArrayOf(3f, 4f)),
        )
        val csv = CsvFormatter.toCsv(listOf("a", "b"), samples)
        val lines = csv.trimEnd('\n').split("\n")

        assertEquals(3, lines.size)
        assertEquals("t_seconds,a,b", lines[0])
        assertEquals("0.0,1.0,2.0", lines[1])
        assertEquals("0.02,3.0,4.0", lines[2])
    }

    @Test
    fun `safeFileStem strips anything that is not alphanumeric or underscore`() {
        assertEquals("Accelerometer", CsvFormatter.safeFileStem("Accelerometer"))
        assertEquals("Sound_meter", CsvFormatter.safeFileStem("Sound meter"))
        assertEquals("GPS_speedometer", CsvFormatter.safeFileStem("GPS/speedometer!"))
    }

    @Test fun `scalar and six axis plugs export the correct column count`() {
        assertEquals("t_seconds,temperature\n0.0,23.5\n", CsvFormatter.toCsv(listOf("temperature"), listOf(SensorSample(0f, floatArrayOf(23.5f)))))
        val csv = CsvFormatter.toCsv(List(6) { "axis_${it + 1}" }, listOf(SensorSample(1f, FloatArray(6) { it.toFloat() })))
        assertEquals(7, csv.lineSequence().first().split(',').size)
        assertEquals(7, csv.lineSequence().drop(1).first().split(',').size)
    }
    @Test fun `remote labels are escaped and formula headers neutralized`() {
        assertEquals("t_seconds,\"force, left\",\"say \"\"hi\"\"\",'=SUM(A1)",
            CsvFormatter.headerRow(listOf("force, left", "say \"hi\"", "=SUM(A1)")))
    }
}
