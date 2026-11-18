package com.tally.app.contract

import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.sin

class FakeTallyBackendTest {
    @Test fun replaysFullRecordingAndCannedResult() = runBlocking {
        val fake = FakeTallyBackend(frameDelayMs = 0, scoringDelayMs = 0)
        assertTrue(fake.startSet(Side.L).isFailure)
        fake.connect().getOrThrow()
        val id = fake.startSet(Side.R).getOrThrow()
        val done = withTimeout(5000) { fake.session.first { it is SessionState.Done } } as SessionState.Done
        assertEquals(id, done.result.id)
        assertEquals(Side.R, done.result.side)
        assertEquals("fake_canned_fixture", done.result.diagnostics.single())
        assertNull(done.result.measuredRateHz)
        assertEquals(4, done.result.reps.size)
        val chart = checkNotNull(done.result.chart)
        assertEquals(1000, chart.samples.size)
        assertEquals(done.result.reps.map { it.index }, chart.reps.map { it.index })
        assertEquals(9.99, chart.samples.last().timeS, 0.00001)
        assertEquals(chart.samples.last().timeS, chart.reps.last().endS, 0.00001)
        val data = FloatArray(6000)
        assertEquals(1000, fake.live.copyLatest(data, 1000))
        assertEquals(sin(0.0).toFloat(), data[0], 0.000001f)
        assertEquals(sin(999 * 0.04).toFloat(), data[(999 * 6)], 0.000001f)
        assertEquals(done.result, fake.result(id))
        assertEquals(id, fake.history().first().single().id)
    }

    @Test fun cannedResultsVaryAcrossRepeatedSets() = runBlocking {
        val fake = FakeTallyBackend(frameDelayMs = 0, scoringDelayMs = 0)
        fake.connect()
        val firstId = fake.startSet(Side.L).getOrThrow()
        val first = withTimeout(5000) {
            fake.session.first { it is SessionState.Done && it.result.id == firstId }
        } as SessionState.Done
        val secondId = fake.startSet(Side.R).getOrThrow()
        val second = withTimeout(5000) {
            fake.session.first { it is SessionState.Done && it.result.id == secondId }
        } as SessionState.Done

        assertFalse(first.result.wrong!!)
        assertTrue(second.result.wrong!!)
        assertTrue(first.result.meanPWrong!! < 0.5)
        assertTrue(second.result.meanPWrong!! >= 0.5)
        assertEquals(second.result.reps.map { it.pWrong }.average(), second.result.meanPWrong, 0.000001)
        assertEquals("EFE", first.result.exercise)
        assertEquals("SQZ", second.result.exercise)
        assertTrue(first.result.reps.map { it.exercise }.toSet().size > 1)
        assertTrue(second.result.reps.any { !it.wrong } && second.result.reps.any { it.wrong })
        assertNull(first.result.measuredRateHz)
        assertNull(second.result.measuredRateHz)
        assertEquals(2, fake.history().first().size)
    }

    @Test fun stopScoresAndAbortDoesNot() = runBlocking {
        val stopped = FakeTallyBackend(frameDelayMs = 1000, scoringDelayMs = 0)
        stopped.connect()
        val stoppedId = stopped.startSet(Side.L).getOrThrow()
        assertTrue(stopped.startSet(Side.R).isFailure)
        stopped.stopSet().getOrThrow()
        assertEquals(stoppedId, (stopped.session.value as SessionState.Done).result.id)

        val aborted = FakeTallyBackend(frameDelayMs = 20, scoringDelayMs = 0)
        aborted.connect()
        val abortedId = aborted.startSet(Side.R).getOrThrow()
        aborted.abortSet().getOrThrow()
        delay(50)
        assertEquals(abortedId, (aborted.session.value as SessionState.Failed).id)
        assertNull(aborted.result(abortedId))
    }

    @Test fun fakeLiveRingCopiesChronologicallyAfterWrap() {
        val ring = FakeLiveRing()
        repeat(101) { frame -> ring.appendFrame(frame * 10) }
        val data = FloatArray(6000)
        assertEquals(1000, ring.copyLatest(data, 1000))
        assertEquals(sin(10 * 0.04).toFloat(), data[0], 0.000001f)
        assertEquals(sin(1009 * 0.04).toFloat(), data[(999 * 6)], 0.000001f)
    }

    @Test fun calibrationRequiresConnectionResetsAfterSaveAndCleansUpCancellation() = runBlocking {
        val fake = FakeTallyBackend(frameDelayMs = 20, scoringDelayMs = 0)
        assertTrue(fake.captureCalibrationPose(CalPose.X_POS).isFailure)
        assertTrue(fake.saveCalibration().isFailure)
        fake.connect()

        val capture = async(start = CoroutineStart.UNDISPATCHED) { fake.captureCalibrationPose(CalPose.X_POS) }
        assertTrue(fake.startSet(Side.L).isFailure)
        capture.cancelAndJoin()
        val id = fake.startSet(Side.L).getOrThrow()
        fake.abortSet()
        assertEquals(id, (fake.session.value as SessionState.Failed).id)

        CalPose.entries.forEach { fake.captureCalibrationPose(it).getOrThrow() }
        assertFalse(fake.saveCalibration().getOrThrow().nominal)
        assertTrue(fake.saveCalibration().isFailure)
    }

    @Test fun intendedExerciseTravelsWithTheSetAndAMismatchIsWrong() = runBlocking {
        val fake = FakeTallyBackend(frameDelayMs = 0, scoringDelayMs = 0)
        fake.connect()
        suspend fun run(intended: String?) = fake.startSet(Side.L, intended).getOrThrow().let { id ->
            (withTimeout(5000) { fake.session.first { it is SessionState.Done && it.result.id == id } } as SessionState.Done).result
        }
        val unspecified = run(null) // id 1: the canned correct EFE set
        assertEquals(false, unspecified.wrong)
        assertNull(unspecified.intendedExercise)
        assertFalse(unspecified.wrongExercise)
        val match = run("SQZ") // id 2: canned SQZ, 3 of 4 reps wrong
        assertTrue(!match.wrongExercise && match.wrong == true)
        val mismatch = run("SQZ") // id 3: canned EFE, every rep correct
        assertTrue(mismatch.reps.none { it.wrong })
        assertTrue(mismatch.wrongExercise && mismatch.wrong == true)
        assertEquals("SQZ", fake.history().first().last().intendedExercise)
    }
}
