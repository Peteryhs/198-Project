package com.tally.app.contract

import org.junit.Assert.*
import org.junit.Test

class SetChartTest {
    @Test fun refusesInvalidSamplesAndRepPositions() {
        val samples = listOf(ChartSample(0.0, 1f, 2f), ChartSample(1.0, 2f, 1f))
        assertEquals(1, SetChart(samples, listOf(RepSpan(1, 0.0, 1.0))).reps.size)
        assertThrows(IllegalArgumentException::class.java) { ChartSample(Double.NaN, 1f, 1f) }
        assertThrows(IllegalArgumentException::class.java) { ChartSample(0.0, -1f, 1f) }
        assertThrows(IllegalArgumentException::class.java) { SetChart(samples.reversed(), emptyList()) }
        assertThrows(IllegalArgumentException::class.java) { SetChart(samples, listOf(RepSpan(1, 0.0, 2.0))) }
        assertThrows(IllegalArgumentException::class.java) {
            SetChart(samples, listOf(RepSpan(1, 0.0, 0.8), RepSpan(2, 0.5, 1.0)))
        }
    }
}
