package com.jeevan.tally.exercise

import com.jeevan.tally.exercise.MotionFixtures.hold
import com.jeevan.tally.exercise.MotionFixtures.rep
import com.jeevan.tally.exercise.MotionFixtures.sequence
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.cos

class RepCounterTest {
    private fun count(frames: List<MotionFixtures.Frame>, counter: RepCounter = RepCounter(MotionFixtures.calibration())) =
        frames.mapNotNull { counter.push(it.ms / 1000f, it.values) }

    @Test fun `calibration finds the moving segment and its range`() {
        val c = MotionFixtures.calibration()
        assertNotEquals(AngleSignal.UPPER_TILT, c.signal)
        assertEquals(90f, c.rangeDegrees, 0.5f)
    }

    @Test fun `full shallow and too-small movements are told apart`() {
        val reps = count(sequence(
            { hold(it, 1.0, 0.0) },
            { rep(it, 2.0, 90.0) }, { hold(it, 0.5, 0.0) },
            { rep(it, 2.0, 90.0) }, { hold(it, 0.5, 0.0) },
            { rep(it, 2.0, 54.0) }, { hold(it, 0.5, 0.0) },   // 60% of range: counted, shallow
            { rep(it, 2.0, 27.0) }, { hold(it, 0.5, 0.0) },   // 30%: below the 40% entry, not a rep
            { rep(it, 2.0, 90.0) }, { hold(it, 1.0, 0.0) },
        ))
        assertEquals(4, reps.size)
        assertEquals(listOf(true, true, false, true), reps.map { it.full })
        assertEquals(0.6f, reps[2].peakFraction, 0.05f)
        // Movement time spans the excursion above the 20% exit band of a 2 s raise-and-return.
        reps.filter { it.full }.forEach { assertTrue("movement ${it.movementSeconds}", it.movementSeconds in 1.2f..1.9f) }
    }

    @Test fun `hysteresis keeps a wobble near the threshold to one repetition`() {
        // Rise to 45°, wobble between 30° and 50° (33%–56% of range) without returning to rest, then return.
        val wobble: (Long) -> List<MotionFixtures.Frame> = { start ->
            (0 until 300).map { i -> MotionFixtures.frameAt(start + i * 10L, 40.0 + 10 * cos(2 * PI * i / 50)) }
        }
        val reps = count(sequence({ hold(it, 1.0, 0.0) }, { rep(it, 1.0, 50.0).take(50) }, wobble,
            { rep(it, 1.0, 50.0).drop(50) }, { hold(it, 1.0, 0.0) }))
        assertEquals(1, reps.size)
    }

    @Test fun `reset drops a half-finished repetition`() {
        val counter = RepCounter(MotionFixtures.calibration())
        val frames = sequence({ hold(it, 1.0, 0.0) }, { rep(it, 2.0, 90.0) }, { hold(it, 1.0, 0.0) })
        val half = frames.size / 2
        frames.take(half).forEach { counter.push(it.ms / 1000f, it.values) }
        counter.reset()
        val after = frames.drop(half).mapNotNull { counter.push(it.ms / 1000f, it.values) }
        assertTrue(after.isEmpty())
    }

    @Test fun `starting with the arm raised does not count its first return`() {
        val reps = count(sequence({ hold(it, 1.0, 90.0) }, { hold(it, 1.0, 0.0) }, { rep(it, 2.0, 90.0) }, { hold(it, 1.0, 0.0) }))
        assertEquals(1, reps.size)
    }

    @Test fun `jitter shorter than the minimum movement is ignored`() {
        val reps = count(sequence({ hold(it, 1.0, 0.0) }, { rep(it, 0.3, 90.0) }, { hold(it, 1.0, 0.0) }),
            RepCounter(MotionFixtures.calibration(), CounterConfig(cutoffHz = 50f)))
        assertTrue(reps.isEmpty())
    }

    @Test fun `pose rejects a moving arm and calibration rejects a tiny range`() {
        val moving = rep(0, 1.0, 60.0).map { it.values }
        assertTrue(AngleMath.pose(moving) is PoseResult.Failed)
        assertTrue(AngleMath.pose(hold(0, 0.2, 0.0).map { it.values }) is PoseResult.Failed)
        val rest = (AngleMath.pose(hold(0, 1.0, 0.0).map { it.values }) as PoseResult.Ok).pose
        val nearby = (AngleMath.pose(hold(0, 1.0, 8.0).map { it.values }) as PoseResult.Ok).pose
        assertTrue(AngleMath.calibrate(rest, nearby) is CalibrationResult.Failed)
    }

    @Test fun `pose rejects a disconnected sensor`() {
        val dead = hold(0, 1.0, 0.0).map { it.values.copyOf().also { v -> v[3] = 0f; v[4] = 0f; v[5] = 0f } }
        assertTrue(AngleMath.pose(dead) is PoseResult.Failed)
    }
}
