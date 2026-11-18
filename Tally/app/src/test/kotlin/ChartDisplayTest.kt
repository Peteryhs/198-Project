package com.tally.app

import com.tally.app.contract.ChartSample
import com.tally.app.contract.RepSpan
import com.tally.app.ui.chartAxisMaximum
import com.tally.app.ui.chartX
import com.tally.app.ui.liveRevealFrontier
import com.tally.app.ui.liveScrollOffset
import com.tally.app.ui.scrollFraction
import com.tally.app.ui.selectedRepIndexAt
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ChartDisplayTest {
    @Test fun liveScrollUsesClampedDisplayTimeWithoutChangingSamples() {
        assertEquals(0f, scrollFraction(900, 1_000, 100), 0f)
        assertEquals(0.5f, scrollFraction(1_050, 1_000, 100), 0f)
        assertEquals(1f, scrollFraction(1_200, 1_000, 100), 0f)
        assertEquals(0f, scrollFraction(1_050, 1_000, 0), 0f)
        assertEquals(-10f, liveScrollOffset(0f, true, -10f), 0f)
        assertEquals(-5f, liveScrollOffset(0.5f, true, -10f), 0f)
        assertEquals(0f, liveScrollOffset(1f, true, -10f), 0f)
        assertEquals(0f, liveScrollOffset(1f, true, -15f), 0f) // Late packets still reveal the latest point.
    }

    @Test fun incomingSamplesRevealFractionallyWithoutMovingTheStoredPoints() {
        assertEquals(9f, liveRevealFrontier(20, 10, 0f), 0f)
        assertEquals(14f, liveRevealFrontier(20, 10, 0.5f), 0f)
        assertEquals(19f, liveRevealFrontier(20, 10, 1f), 0f)
    }

    @Test fun timeAndRepSelectionUseRecordedSpanBoundaries() {
        assertEquals(0f, chartX(2.0, 2.0, 12.0, 100f), 0f)
        assertEquals(50f, chartX(7.0, 2.0, 12.0, 100f), 0f)
        assertEquals(100f, chartX(12.0, 2.0, 12.0, 100f), 0f)

        val spans = listOf(RepSpan(1, 3.0, 4.0), RepSpan(2, 7.0, 8.5))
        assertEquals(1, selectedRepIndexAt(0.1f, 2.0, 12.0, spans) ?: -1)
        assertNull(selectedRepIndexAt(0.4f, 2.0, 12.0, spans))
        assertEquals(2, selectedRepIndexAt(0.6f, 2.0, 12.0, spans) ?: -1)
    }

    @Test fun magnitudeAxisContainsExtremaAndUsesHalfGSteps() {
        assertEquals(2f, chartAxisMaximum(listOf(
            ChartSample(0.0, 1.5f, 0.4f), ChartSample(0.01, 1.2f, 1.5001f),
        )), 0f)
        assertEquals(0.5f, chartAxisMaximum(listOf(ChartSample(0.0, 0f, 0f))), 0f)
    }
}
