package com.jeevan.tally.sensors

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SampleBufferTest {
    private fun sample(i: Int) = SensorSample(i.toFloat(), floatArrayOf(i.toFloat(), 0f, 0f, 0f), receivedAtNanos = i * 1_000_000L)

    @Test fun `wraparound retains newest samples in order and counts every eviction`() {
        val buffer = SampleBuffer(3)
        repeat(10) { buffer.offer(sample(it)) }
        val batch = buffer.drain()
        assertEquals(listOf(7f, 8f, 9f), batch.samples.map { it.t })
        assertEquals(7L, batch.dropped)
        assertTrue(buffer.drain().samples.isEmpty())
        buffer.offer(sample(10))
        assertEquals(0L, buffer.drain().dropped)
    }

    @Test fun `buffer owns sample arrays and preserves acquisition timestamps`() {
        val buffer = SampleBuffer(2)
        val original = sample(1)
        buffer.offer(original)
        original.values[0] = 99f
        val received = buffer.drain().samples.single()
        assertEquals(1f, received.values[0], 0f)
        assertEquals(original.receivedAtNanos, received.receivedAtNanos)
    }

    @Test fun `burst is batched without replay and cancellation releases subscribers`() = runTest {
        val bus = BufferedSampleBus(4096, 16)
        bus.publish(sample(-1))
        val batches = mutableListOf<SampleBatch>()
        val job = launch { bus.batches().collect { batches.add(it) } }
        runCurrent()
        repeat(3000) { bus.publish(sample(it)) }
        runCurrent(); advanceTimeBy(16); runCurrent()
        assertEquals(1, batches.size)
        assertEquals((0 until 3000).map { it.toFloat() }, batches.single().samples.map { it.t })
        assertEquals(0L, batches.single().dropped)
        job.cancel(); runCurrent()
        assertEquals(0, bus.subscriberCount)
    }

    @Test fun `slow subscriber reports its own overflow without blocking fast subscriber`() = runTest {
        val bus = BufferedSampleBus(4, 1)
        val fast = mutableListOf<SampleBatch>()
        val slow = mutableListOf<SampleBatch>()
        val a = launch { bus.batches().collect { fast.add(it) } }
        val b = launch { bus.batches().collect { slow.add(it); delay(100) } }
        runCurrent()
        repeat(20) { bus.publish(sample(it)); advanceTimeBy(2); runCurrent() }
        advanceTimeBy(100); runCurrent()
        assertEquals(20, fast.sumOf { it.samples.size })
        assertEquals(0L, fast.sumOf { it.dropped })
        assertEquals(20L, slow.sumOf { it.samples.size.toLong() + it.dropped })
        assertTrue(slow.sumOf { it.dropped } > 0)
        a.cancel(); b.cancel(); runCurrent()
        assertEquals(0, bus.subscriberCount)
    }
}
