package com.tally.app

import com.tally.app.ui.failureText
import com.tally.app.ui.scoringPathWords
import org.junit.Assert.*
import org.junit.Test

class ScoringFeedbackTest {
    @Test fun nullAndBlankExceptionMessagesStayVisible() {
        assertEquals("IllegalStateException", failureText(IllegalStateException()))
        assertEquals("IllegalStateException", failureText(IllegalStateException("  ")))
        assertEquals("HTTP 403", failureText(IllegalStateException("HTTP 403")))
    }
    @Test fun pathCopyUsesStoredProvenance() {
        assertEquals("Scored by: Gemini (gemini-test-fallback)", scoringPathWords("gemini-test-fallback"))
        assertTrue(scoringPathWords("paired-synchronized-offline").contains("codex-side model"))
    }
}
