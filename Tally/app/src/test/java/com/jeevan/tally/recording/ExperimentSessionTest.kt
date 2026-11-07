package com.jeevan.tally.recording

import androidx.lifecycle.ViewModelStore
import com.jeevan.tally.sensors.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ExperimentSessionTest {
    private val scheduler = TestCoroutineScheduler()
    private val dispatcher = StandardTestDispatcher(scheduler)
    private val connection = MutableStateFlow(ArduinoLink.Status.CONNECTED)
    private val store = ViewModelStore()
    private lateinit var session: ExperimentSession
    private val readings = MutableSharedFlow<SensorSample>(extraBufferCapacity = 10)
    private val stream = object : SensorStream {
        override val title = "Test"
        override val description = "Test stream"
        override val axisNames = listOf("x", "y", "z", "magnitude")
        override val axisColorsHex = emptyList<String>()
        override val unit = "m/s²"
        override val permissions = emptyList<String>()
        override fun samples() = readings
    }
    private fun sample() { readings.tryEmit(SensorSample(99f, floatArrayOf(1f, 2f, 3f, 4f))); scheduler.runCurrent() }
    @Before fun setup() {
        Dispatchers.setMain(dispatcher)
        session = ExperimentSession({ scheduler.currentTime }, connection)
        store.put("session", session)
        scheduler.runCurrent()
    }
    @After fun cleanup() { store.clear(); Dispatchers.resetMain() }
    @Test fun `countdown delays acquisition and timed recording stops automatically`() {
        session.startDelay = 3; session.duration = 10
        session.start(stream); scheduler.runCurrent()
        assertEquals(3, session.countdown); assertFalse(session.running)
        sample(); assertTrue(session.samples.isEmpty())
        scheduler.advanceTimeBy(3000); scheduler.runCurrent()
        assertTrue(session.running)
        sample(); assertEquals(1, session.samples.size)
        assertEquals(0f, session.samples.first().t, 0f)
        scheduler.advanceTimeBy(10_000); scheduler.runCurrent()
        assertFalse(session.running); assertEquals(10f, session.elapsed, 0.001f)
    }
    @Test fun `pause excludes downtime and resume creates separate plot segment`() {
        session.start(stream); scheduler.runCurrent()
        scheduler.advanceTimeBy(1000); sample(); session.pause()
        scheduler.advanceTimeBy(5000)
        sample(); assertEquals(1, session.samples.size)
        session.start(stream); scheduler.runCurrent()
        scheduler.advanceTimeBy(1000); sample(); session.pause()
        assertEquals(2f, session.samples.last().t, 0.001f)
        assertNotEquals(session.samples.first().segment, session.samples.last().segment)
        assertTrue(session.dirty)
    }
    @Test fun `disconnect pauses recording and preserves samples`() {
        session.start(stream); scheduler.runCurrent(); sample()
        connection.value = ArduinoLink.Status.ERROR; scheduler.runCurrent()
        assertFalse(session.active); assertEquals(1, session.samples.size)
        assertTrue(session.message!!.contains("Connection lost"))
    }
    @Test fun `cancel countdown prevents delayed recording`() {
        session.startDelay = 5; session.start(stream); scheduler.runCurrent()
        session.pause(); scheduler.advanceTimeBy(6000); scheduler.runCurrent()
        assertFalse(session.active); assertEquals(0, session.countdown)
    }
    @Test fun `clear resets data and dirty state`() {
        session.start(stream); scheduler.runCurrent(); sample(); session.pause()
        session.clear()
        assertTrue(session.samples.isEmpty()); assertFalse(session.dirty); assertEquals(0f, session.elapsed, 0f)
    }

    @Test fun `delayed batches preserve arrival spacing and expose buffer losses`() {
        val batches = MutableSharedFlow<SampleBatch>(extraBufferCapacity = 2)
        val batched = object : SensorStream by stream {
            override fun sampleBatches() = batches
        }
        session.start(batched); scheduler.runCurrent()
        scheduler.advanceTimeBy(1000)
        batches.tryEmit(SampleBatch(listOf(
            SensorSample(0f, floatArrayOf(1f, 2f, 3f, 4f), receivedAtNanos = 100_000_000L),
            SensorSample(0f, floatArrayOf(2f, 3f, 4f, 5f), receivedAtNanos = 200_000_000L)
        ), dropped = 3))
        scheduler.runCurrent()
        assertEquals(0.1f, session.samples[0].t, 0.00001f)
        assertEquals(0.2f, session.samples[1].t, 0.00001f)
        assertEquals(3L, session.droppedSamples)
        assertTrue(session.message!!.contains("overflow"))
        session.clear()
        assertEquals(0L, session.droppedSamples)
    }

    @Test fun `changed plug definition pauses before accepting incompatible values`() {
        var compatible = true
        val changing = object : SensorStream by stream {
            override fun isCompatible() = compatible
        }
        session.start(changing); scheduler.runCurrent(); sample()
        compatible = false
        sample()
        assertFalse(session.active)
        assertEquals(1, session.samples.size)
        assertTrue(session.message!!.contains("definition changed"))
        session.start(changing)
        assertFalse(session.active)
    }
}
