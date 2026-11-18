package com.tally.app.backend.session

import org.junit.Assert.*
import org.junit.Test

class SampleProgressTest {
    @Test fun responsiveLinkWithoutSamplesStillStallsAndNewSamplesRecoverIt() {
        val progress = SampleProgress(0)
        assertFalse(progress.stalled(0, 1_000_000_000))
        assertFalse(progress.stalled(0, 2_000_000_000))
        assertTrue(progress.stalled(0, 3_000_000_000))
        assertEquals(0L, progress.lastProgressNs)
        assertFalse(progress.stalled(10, 3_500_000_000))
        assertFalse(progress.stalled(10, 6_499_999_999))
        assertTrue(progress.stalled(10, 6_500_000_000))
        assertFalse(progress.stalled(20, 7_000_000_000))
    }
}
