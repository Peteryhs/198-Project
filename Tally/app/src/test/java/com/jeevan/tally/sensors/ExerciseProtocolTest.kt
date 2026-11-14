package com.jeevan.tally.sensors

import com.jeevan.tally.exercise.BoardState
import com.jeevan.tally.exercise.Exercise
import com.jeevan.tally.exercise.TempoCue
import org.junit.Assert.*
import org.junit.Test

class ExerciseProtocolTest {
    @Test fun `documented CSV row becomes a synchronized pair frame`() {
        val m = LineProtocol.parseMessage("12340,0.01,-0.98,0.12,0.5,-0.85,0.02\r") as LineProtocol.Message.PairFrame
        assertEquals(12340L, m.deviceMillis)
        assertArrayEquals(floatArrayOf(0.01f, -0.98f, 0.12f, 0.5f, -0.85f, 0.02f), m.values, 0f)
    }

    @Test fun `malformed pair rows are rejected whole`() {
        assertNull(LineProtocol.parseMessage("12340,0.01,-0.98,0.12,0.5,-0.85"))          // six fields
        assertNull(LineProtocol.parseMessage("12340,0.01,-0.98,0.12,0.5,-0.85,nan"))      // nonfinite
        assertNull(LineProtocol.parseMessage("-5,0.01,-0.98,0.12,0.5,-0.85,0.02"))        // signed time
        assertNull(LineProtocol.parseMessage("99999999999,0,0,0,0,0,0"))                  // beyond uint32
        assertNull(LineProtocol.parseMessage("time_ms,upper_ax_g,upper_ay_g,upper_az_g,forearm_ax_g,forearm_ay_g,forearm_az_g"))
    }

    @Test fun `TALLY frame mirrors TallyOutput`() {
        val m = LineProtocol.parseMessage("TALLY,2,7,10,15320,0,2.14,1,0,5,0,nan,nan,nan,nan") as LineProtocol.Message.Status
        val s = m.status
        assertEquals(BoardState.RUNNING, s.state)
        assertEquals(7, s.cycles)
        assertEquals(10, s.targetCount)
        assertEquals(15320L, s.activeMs)
        assertEquals(2.14f, s.cycleSeconds, 1e-6f)
        assertTrue(s.durationAvailable)
        assertEquals(TempoCue.ABSTAIN, s.cue)
        assertEquals(5, s.timingReason)
        assertFalse(s.assessmentAvailable)
    }

    @Test fun `finished TALLY frame carries the model assessment`() {
        val m = LineProtocol.parseMessage("TALLY,4,30,10,45750,0,0,0,0,5,1,0.12,0.08,0.80,0.621927") as LineProtocol.Message.Status
        assertEquals(BoardState.FINISHED, m.status.state)
        assertTrue(m.status.assessmentAvailable)
        assertEquals(0.621927f, m.status.pIncorrect, 1e-6f)
    }

    @Test fun `TALLY frames with impossible values are dropped`() {
        assertNull(LineProtocol.parseMessage("TALLY,9,7,10,15320,0,2.14,1,0,5,0,0,0,0,0"))       // state
        assertNull(LineProtocol.parseMessage("TALLY,2,7,10,15320,0,2.14,1,7,5,0,0,0,0,0"))       // cue
        assertNull(LineProtocol.parseMessage("TALLY,4,7,10,15320,0,0,0,0,5,1,nan,0,0,0.5"))      // assessed but nan
        assertNull(LineProtocol.parseMessage("TALLY,4,7,10,15320,0,0,0,0,5,1,0.2,0.2,0.6,1.5"))  // probability > 1
        assertNull(LineProtocol.parseMessage("TALLY,2,7,10,15320,0,nan,1,0,5,0,0,0,0,0"))        // duration claimed, nan
        assertNull(LineProtocol.parseMessage("TALLY,2,7,10"))
    }

    @Test fun `TALLYCFG echoes the board prescription`() {
        val m = LineProtocol.parseMessage("TALLYCFG,2,10,1.8,2,2.2,1,RX-0042") as LineProtocol.Message.BoardConfig
        assertEquals(Exercise.EFE, m.prescription.exercise)
        assertEquals(10, m.prescription.targetCount)
        assertEquals(2.2f, m.prescription.maxSeconds!!, 0f)
        assertEquals("RX-0042", m.prescription.prescriptionId)
        assertTrue(m.prescribed)
        assertNull(LineProtocol.parseMessage("TALLYCFG,2,10,2.2,2,1.8,1"))  // inverted range
    }

    @Test fun `calibration events`() {
        assertTrue((LineProtocol.parseMessage("CAL,1") as LineProtocol.Message.Calibration).ok)
        val failed = LineProtocol.parseMessage("CAL,0,arm moved") as LineProtocol.Message.Calibration
        assertFalse(failed.ok)
        assertEquals("arm moved", failed.detail)
        assertNull(LineProtocol.parseMessage("CAL,yes"))
    }

    @Test fun `legacy and generic frames are unaffected`() {
        assertTrue(LineProtocol.parseMessage("A,1,2,3") is LineProtocol.Message.Values)
        assertTrue(LineProtocol.parseMessage("D,arm_pair,1,2,3,4,5,6") is LineProtocol.Message.Values)
        assertTrue(LineProtocol.parseMessage("PLUGS,accel:3") is LineProtocol.Message.Plugs)
    }
}
