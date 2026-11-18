package com.tally.app

import com.tally.app.ui.elapsed
import com.tally.app.ui.calibrationCaptureWords
import com.tally.app.ui.calibrationWords
import com.tally.app.ui.exerciseCheckWords
import com.tally.app.ui.exerciseWords
import com.tally.app.ui.poolingWords
import com.tally.app.ui.probability
import com.tally.app.ui.verdictWords
import com.tally.app.contract.CalibrationInfo
import com.tally.app.ui.bodyHoldWords
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Test

class CopyTest {
    @Test fun verdictIsWordsForEveryKnownStatus() {
        assertEquals("Correct form", verdictWords("scored", false))
        assertEquals("Wrong form", verdictWords("scored", true))
        assertEquals("Result unavailable", verdictWords("scored", null))
        assertEquals("Too few reps to judge", verdictWords("insufficient_reps", null))
        assertEquals("Could not assess this set", verdictWords("rejected", null))
        assertEquals("Not scored yet", verdictWords("interrupted", null))
        assertEquals("Result unavailable", verdictWords("something_new", null))
    }

    @Test fun numbersAreLocaleIndependent() {
        assertEquals("0:00", elapsed(-5))
        assertEquals("10:00", elapsed(600_000))
        assertEquals("0.10", probability(0.1))
    }

    @Test fun poolingNamesTheRepCountAndTheAverage() {
        // 3 x 0.6 + 2 x 0.01 averages 0.364; the set is still wrong form because a rep is.
        assertEquals("3 of 5 reps looked wrong. One wrong rep marks the set wrong. Average chance of wrong form: 0.36.",
            poolingWords(3, 5, 0.364))
    }

    @Test fun exerciseIsCheckedAgainstTheChoiceOrMarkedUnverified() {
        assertEquals("Wrong exercise", verdictWords("scored", true, wrongExercise = true))
        assertEquals("You chose Elbow bend and straighten, but the model classed the set as Arms raised overhead.",
            exerciseCheckWords("EAH", "EFE"))
        assertTrue(exerciseCheckWords("EAH", null).contains("Unverified"))
        assertEquals("Exercise: Squeezing, as chosen.", exerciseCheckWords("SQZ", "SQZ"))
    }

    @Test fun exerciseCodesHavePlainNamesForResults() {
        assertEquals("Arms raised overhead", exerciseWords("EAH"))
        assertEquals("Elbow bend and straighten", exerciseWords("EFE"))
        assertEquals("Squeezing", exerciseWords("SQZ"))
        assertEquals("Exercise not identified", exerciseWords("new-code"))
    }

    @Test fun calibrationCopyDistinguishesFallbackFromLiveMeasurements() {
        val nominal = calibrationWords(CalibrationInfo("nominal", true, 0))
        assertTrue(nominal.contains("starting values") && nominal.contains("not measurements from this device"))
        assertTrue(nominal.contains("they do not replace sensor readings"))
        assertTrue(calibrationCaptureWords.contains("live millivolt readings from both sensors on the ESP32"))
        assertTrue(calibrationCaptureWords.contains("replaces the starting offsets"))
        val legacy = calibrationWords(CalibrationInfo("cal-123", false, 0))
        assertTrue(legacy.contains("Six-pose calibration") && legacy.contains("cal-123"))
        val saved = calibrationWords(CalibrationInfo("body-123", false, 123))
        assertTrue(saved.contains("body-123") && saved.contains("marginal") && saved.contains("unmeasured"))
        com.tally.app.contract.BodyHold.entries.forEach { hold ->
            val action = bodyHoldWords(hold)
            assertTrue(action.isNotBlank())
            assertFalse(action.contains("axis") || action.contains("channel"))
        }
    }
}
