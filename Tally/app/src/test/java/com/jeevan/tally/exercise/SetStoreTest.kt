package com.jeevan.tally.exercise

import com.jeevan.tally.exercise.MotionFixtures.hold
import com.jeevan.tally.exercise.MotionFixtures.rep
import com.jeevan.tally.exercise.MotionFixtures.sequence
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.file.Files

class SetStoreTest {
    private fun appSet(): SetTracker {
        val p = Prescription(Exercise.EFE, 4, 2f, 2.5f, 3f, "RX-1")
        val tracker = SetTracker(p, 1_700_000_000_000L, MotionFixtures.calibration())
        tracker.start()
        sequence({ hold(it, 1.0, 0.0) }, { rep(it, 2.0, 90.0) }, { hold(it, 0.5, 0.0) },
            { rep(it, 2.0, 54.0) }, { hold(it, 1.0, 0.0) }).forEach {
            tracker.advanceTo(it.ms / 1000f); tracker.onFrame(it.ms / 1000f, it.values, it.ms)
        }
        tracker.finish()
        tracker.observedCount = 2
        return tracker
    }

    @Test fun `codec round-trips every logged value`() {
        val tracker = appSet()
        val text = SetCodec.encode("00000000-0000-0000-0000-000000000001", "Monday, elbow\nflex", 42L, tracker.summary(), tracker.reps)
        val back = SetCodec.decode(text)
        assertEquals("Monday, elbow flex", back.name)
        assertEquals(tracker.reps, back.reps)
        assertEquals(tracker.summary(), back.summary)
    }

    @Test fun `codec keeps a board assessment`() {
        val tracker = SetTracker(Prescription(Exercise.EAH, 10), 0L)
        tracker.start()
        tracker.onBoardStatus(BoardStatus(BoardState.FINISHED, 30, 10, 45750, 0, 0f, false, TempoCue.ABSTAIN, 5, true,
            listOf(0.7f, 0.2f, 0.1f), 0.62f))
        val back = SetCodec.decode(SetCodec.encode("00000000-0000-0000-0000-000000000002", "x", 1L, tracker.summary(), tracker.reps))
        assertEquals(tracker.summary().assessment, back.summary.assessment)
        assertEquals(CountSource.BOARD, back.summary.source)
        assertEquals(30, back.summary.counted)
    }

    @Test fun `store saves lists loads and deletes`() {
        val dir = Files.createTempDirectory("sets").toFile()
        try {
            val store = SetStore(dir)
            val saved = store.save("First set", appSet())
            assertEquals(listOf(saved.id), store.list().map { it.id })
            assertEquals(saved.summary, store.load(saved.id).summary)
            File(dir, "junk.set").writeText("not a set")
            assertEquals(1, store.list().size)           // unreadable files are skipped, not fatal
            assertTrue(store.delete(saved.id))
            assertTrue(store.list().isEmpty())
            assertThrows(IllegalArgumentException::class.java) { store.load("../escape") }
        } finally { dir.deleteRecursively() }
    }

    @Test fun `report lists the metrics an instructor needs`() {
        val tracker = appSet()
        val saved = SetCodec.decode(SetCodec.encode("00000000-0000-0000-0000-000000000003", "=cmd", 1L, tracker.summary(), tracker.reps))
        val text = SetReport.toText(saved)
        listOf("Repetitions counted: 2 (target 4)", "Efficiency", "Shallow reps: 1", "Data coverage", "Counting error",
            "Model assessment: unavailable").forEach { assertTrue("missing '$it'", text.contains(it)) }
        val csv = SetReport.toCsv(saved)
        assertTrue(csv.startsWith("metric,value,note"))
        assertTrue(csv.contains("rep,completed_at_s,pace_s,movement_s,peak_range_pct,range,pace_check"))
        assertTrue(csv.lines().any { it.startsWith("2,") && it.contains("shallow") })
        assertTrue(csv.contains("\"Prescribed pace\"") || csv.contains("Prescribed pace,"))
    }
}
