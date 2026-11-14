package com.jeevan.tally.exercise

import com.jeevan.tally.exercise.MotionFixtures.hold
import com.jeevan.tally.exercise.MotionFixtures.rep
import com.jeevan.tally.exercise.MotionFixtures.sequence
import org.junit.Assert.*
import org.junit.Test

class SetTrackerTest {
    private val tempo = Prescription(Exercise.EFE, targetCount = 5, minSeconds = 2f, targetSeconds = 2.5f, maxSeconds = 3f)

    private fun feed(tracker: SetTracker, frames: List<MotionFixtures.Frame>) =
        frames.mapNotNull { f ->
            tracker.advanceTo(f.ms / 1000f)
            tracker.onFrame(f.ms / 1000f, f.values, f.ms)
        }

    private fun status(state: BoardState, cycles: Int, seconds: Float = 0f, faults: Int = 0, assess: Boolean = false,
                       activeMs: Long = cycles * 2500L, pWrong: Float = Float.NaN) =
        BoardStatus(state, cycles, 10, activeMs, faults, seconds, seconds > 0f, TempoCue.ABSTAIN, 5, assess,
            listOf(0.1f, 0.8f, 0.1f), pWrong)

    @Test fun `app estimate logs count pace range and efficiency`() {
        val tracker = SetTracker(tempo, 0L, MotionFixtures.calibration())
        tracker.start()
        val reps = feed(tracker, sequence(
            { hold(it, 1.0, 0.0) },
            { rep(it, 2.0, 90.0) }, { hold(it, 0.5, 0.0) },   // pace = first movement only
            { rep(it, 2.0, 90.0) }, { hold(it, 0.5, 0.0) },   // ~2.5 s period: on target
            { rep(it, 1.0, 90.0) }, { hold(it, 0.1, 0.0) },   // ~1.1 s period: too fast
            { rep(it, 2.0, 54.0) }, { hold(it, 0.5, 0.0) },   // shallow
            { hold(it, 1.0, 0.0) },
        ))
        assertEquals(4, reps.size)
        val s = tracker.summary()
        assertEquals(CountSource.APP, s.source)
        assertEquals(4, s.counted)
        assertEquals(0.8f, s.completion, 1e-6f)
        assertEquals(3, s.fullReps)
        assertEquals(1, s.shallowReps)
        assertEquals(TempoCue.ON_TARGET, reps[1].cue)
        assertEquals(TempoCue.TOO_FAST, reps[2].cue)
        assertEquals(2.5f, reps[1].paceSeconds!!, 0.15f)
        // Rep 1 (paced by its own ~1.4 s movement) is too fast, rep 3 too fast, rep 4 shallow: only rep 2 is effective.
        assertEquals(1, s.effectiveReps)
        assertEquals(0.25f, s.efficiency!!, 1e-6f)
        assertEquals(0.75f, s.rangeEfficiency!!, 1e-6f)
        assertEquals(1f, s.coverage!!, 1e-6f)
        assertTrue(s.coverageFromDeviceClock)
        assertEquals(0, s.timingGaps)
        assertEquals(0, s.faults)
    }

    @Test fun `without a tempo prescription efficiency is the full-range share`() {
        val tracker = SetTracker(Prescription(Exercise.EFE, 3), 0L, MotionFixtures.calibration())
        tracker.start()
        feed(tracker, sequence({ hold(it, 1.0, 0.0) }, { rep(it, 2.0, 90.0) }, { hold(it, 0.5, 0.0) },
            { rep(it, 2.0, 54.0) }, { hold(it, 1.0, 0.0) }))
        val s = tracker.summary()
        assertNull(s.paceAdherence)
        assertEquals(0.5f, s.efficiency!!, 1e-6f)
        assertTrue(tracker.reps.all { it.cue == TempoCue.ABSTAIN })
    }

    @Test fun `missing frames lower coverage and count timing gaps`() {
        val tracker = SetTracker(tempo, 0L, MotionFixtures.calibration())
        tracker.start()
        val frames = hold(0, 10.0, 0.0).filterIndexed { i, _ -> i % 10 != 5 }  // drop 10%
        feed(tracker, frames)
        val s = tracker.summary()
        assertEquals(0.9f, s.coverage!!, 0.002f)
        assertEquals(100, s.timingGaps)
        assertEquals(false, s.meetsCoverageTarget)
    }

    @Test fun `pauses are excluded from coverage and drop the partial repetition`() {
        val tracker = SetTracker(tempo, 0L, MotionFixtures.calibration())
        tracker.start()
        val first = sequence({ hold(it, 1.0, 0.0) }, { rep(it, 2.0, 90.0) })
        feed(tracker, first.take(first.size - 50))      // pause mid-way down
        tracker.pause()
        val resumed = hold(first.last().ms + 5000, 2.0, 0.0)  // five seconds later, at rest
        tracker.start()
        feed(tracker, resumed)
        val s = tracker.summary()
        assertEquals(0, s.counted)
        assertEquals(1, s.pauseCount)
        assertEquals(1f, s.coverage!!, 1e-6f)
        assertEquals(0, s.timingGaps)
    }

    @Test fun `clipping latches a fault`() {
        val tracker = SetTracker(tempo, 0L)
        tracker.start()
        tracker.onFrame(0f, floatArrayOf(0f, -1f, 0f, 3.2f, 0f, 0f), 0)
        val s = tracker.summary()
        assertEquals(1L, s.clippedSamples)
        assertTrue(s.faultNames.any { "clipped" in it })
    }

    @Test fun `board status is authoritative and logged rep by rep`() {
        val tracker = SetTracker(tempo, 0L, MotionFixtures.calibration())
        tracker.start()
        feed(tracker, sequence({ hold(it, 1.0, 0.0) }, { rep(it, 2.0, 90.0) }, { hold(it, 1.0, 0.0) }))
        assertEquals(1, tracker.counted)   // app estimate until the board speaks

        tracker.onBoardStatus(status(BoardState.RUNNING, 0))
        assertEquals(CountSource.BOARD, tracker.source)
        assertEquals(0, tracker.counted)
        tracker.onBoardStatus(status(BoardState.RUNNING, 1, 2.6f))
        tracker.onBoardStatus(status(BoardState.RUNNING, 1, 2.6f))  // repeated frame adds nothing
        tracker.onBoardStatus(status(BoardState.RUNNING, 3, 1.5f))  // two cycles in one frame
        assertEquals(3, tracker.counted)
        assertEquals(listOf(2.6f, null, 1.5f), tracker.reps.map { it.paceSeconds })
        assertEquals(listOf(TempoCue.ON_TARGET, TempoCue.ABSTAIN, TempoCue.TOO_FAST), tracker.reps.map { it.cue })
        assertEquals(7.5f, tracker.activeSeconds, 1e-6f)

        tracker.onBoardStatus(status(BoardState.FINISHED, 3, assess = true, pWrong = 0.62f))
        val a = tracker.summary().assessment!!
        assertEquals(Exercise.EFE, a.likelyExercise)
        assertTrue(a.seriesLabelIncorrect)
    }

    @Test fun `assessment is ignored unless the board says it is available`() {
        val tracker = SetTracker(tempo, 0L)
        tracker.start()
        tracker.onBoardStatus(status(BoardState.FINISHED, 2, assess = false, pWrong = 0.9f))
        assertNull(tracker.summary().assessment)
        assertNull(tracker.summary().efficiency)  // no range or pace evidence at all
    }

    @Test fun `a board restart keeps the set cumulative`() {
        val tracker = SetTracker(tempo, 0L)
        tracker.start()
        tracker.onBoardStatus(status(BoardState.RUNNING, 4, 2.5f))
        tracker.onBoardStatus(status(BoardState.RUNNING, 1, 2.5f))
        assertEquals(5, tracker.counted)
        assertEquals(1, tracker.boardRestarts)
        assertEquals(5, tracker.reps.last().index)
    }

    @Test fun `board faults are merged with app faults`() {
        val tracker = SetTracker(tempo, 0L)
        tracker.start()
        tracker.onBoardStatus(status(BoardState.RUNNING, 1, faults = Faults.OVERFLOW))
        tracker.onDropped(3)
        val names = tracker.summary().faultNames
        assertTrue(names.contains("Buffer overflow"))
        assertTrue(names.contains("Samples dropped on the phone"))
    }

    @Test fun `counting error is measured against the observed count`() {
        val tracker = SetTracker(tempo, 0L)
        tracker.start()
        tracker.onBoardStatus(status(BoardState.RUNNING, 9))
        tracker.observedCount = 10
        val s = tracker.summary()
        assertEquals(1, s.countingError)
        assertEquals(1f, s.errorsPer10!!, 1e-6f)
        assertEquals(true, s.meetsCountingTarget)
        tracker.observedCount = 12
        assertEquals(false, tracker.summary().meetsCountingTarget)
    }

    @Test fun `prescription validation and inclusive pace range`() {
        assertThrows(IllegalArgumentException::class.java) { Prescription(Exercise.EAH, 0) }
        assertThrows(IllegalArgumentException::class.java) { Prescription(Exercise.EAH, 5, 2f, null, 3f) }
        assertThrows(IllegalArgumentException::class.java) { Prescription(Exercise.EAH, 5, 3f, 2f, 4f) }
        assertEquals(TempoCue.ON_TARGET, tempo.classify(2f))
        assertEquals(TempoCue.ON_TARGET, tempo.classify(3f))
        assertEquals(TempoCue.TOO_SLOW, tempo.classify(3.01f))
        assertEquals(TempoCue.ABSTAIN, Prescription(Exercise.EAH, 5).classify(2f))
    }
}
