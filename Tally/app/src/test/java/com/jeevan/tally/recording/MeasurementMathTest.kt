package com.jeevan.tally.recording

import com.jeevan.tally.sensors.SensorSample
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.sqrt

class MeasurementMathTest {
    @Test fun `statistics distinguish mean rms and population deviation`() {
        val samples = listOf(-2f, 0f, 2f).mapIndexed { i, value -> SensorSample(i.toFloat(), floatArrayOf(value)) }
        val result = axisStatistics(samples, 0)!!
        assertEquals(-2.0, result.min, 0.0); assertEquals(2.0, result.max, 0.0)
        assertEquals(0.0, result.mean, 0.0)
        assertEquals(sqrt(8.0 / 3), result.rms, 1e-10)
        assertEquals(result.rms, result.deviation, 1e-10)
    }
    @Test fun `plot window preserves duplicate timestamps at both boundaries`() {
        val samples = listOf(0f, 2f, 2f, 3f, 4f, 4f, 6f).mapIndexed { i, time ->
            SensorSample(time, floatArrayOf(i.toFloat()))
        }
        assertEquals(samples.subList(1, 6), samplesInWindow(samples, 2f, 4f))
        assertEquals(samples.subList(4, 6), samplesInWindow(samples, 4f, 4f))
        assertEquals(samples, samplesInWindow(samples, -1f, 7f))
        assertTrue(samplesInWindow(samples, 4.5f, 5f).isEmpty())
        assertTrue(samplesInWindow(samples, 7f, 8f).isEmpty())
        assertTrue(samplesInWindow(emptyList(), 0f, 1f).isEmpty())
    }
    @Test fun `statistics ignore missing readings and retain small variation at large offsets`() {
        val samples = listOf(floatArrayOf(), floatArrayOf(Float.NaN), floatArrayOf(1_000_000f),
            floatArrayOf(1_000_001f), floatArrayOf(1_000_002f)).mapIndexed { index, values ->
            SensorSample(index.toFloat(), values)
        }
        val result = axisStatistics(samples, 0)!!
        assertEquals(1_000_001.0, result.mean, 0.0)
        assertEquals(sqrt(2.0 / 3.0), result.deviation, 1e-10)
        assertEquals(PlotBounds(999_999.8f, 1_000_002.2f), plotBounds(samples, setOf(0)))
    }
    @Test fun `constant signal has zero deviation and nonzero range on plot`() {
        val samples = listOf(SensorSample(0f, floatArrayOf(9.8f)), SensorSample(1f, floatArrayOf(9.8f)))
        assertEquals(0.0, axisStatistics(samples, 0)!!.deviation, 0.0)
        val bounds = plotBounds(samples, setOf(0))
        assertTrue(bounds.min < 9.8f && bounds.max > 9.8f)
    }
    @Test fun `hidden axes cannot dominate vertical scale`() {
        val samples = listOf(SensorSample(0f, floatArrayOf(-1f, 1000f)), SensorSample(1f, floatArrayOf(1f, 2000f)))
        val bounds = plotBounds(samples, setOf(0))
        assertTrue(bounds.max < 2f && bounds.min > -2f)
    }
    @Test fun `inspection returns closest actual sample`() {
        val samples = listOf(SensorSample(1f, floatArrayOf(1f)), SensorSample(4f, floatArrayOf(2f)))
        assertSame(samples.last(), nearestSample(samples, 3.8f))
        assertSame(samples.first(), nearestSample(samples, -10f))
    }
    @Test fun `empty measurement set is handled without invented statistics`() {
        assertNull(axisStatistics(emptyList(), 0))
        assertNull(nearestSample(emptyList(), 0f))
        assertEquals(PlotBounds(-1f, 1f), plotBounds(emptyList(), setOf(0)))
    }
}
