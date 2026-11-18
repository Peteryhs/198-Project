package com.tally.app.backend.session

import org.junit.Assert.*
import org.junit.Test

class SampleStoreTest {
    @Test fun validatesOrderAndCapacityWithoutDroppingSamples() {
        val store = SampleStore()
        val row = floatArrayOf(0f, 1f, 2f, 3f, 4f, 5f)
        repeat(60_000) { store.append(it * 10_000L, row) }
        assertEquals(60_000, store.size)
        assertEquals(599_990_000L, store.timestampUs(59_999))
        assertEquals(5f, store.g(59_999, 5), 0f)
        assertTrue(runCatching { store.append(600_000_000, row) }.isFailure)
        store.clear()
        store.append(0, row)
        assertTrue(runCatching { store.append(0, row) }.isFailure)
        row[0] = Float.NaN
        assertTrue(runCatching { store.append(1, row) }.isFailure)
        assertEquals(1, store.size)
    }
    @Test fun ringCopiesWrappedRowsOldestFirstAndPublishesOncePerFrame() {
        val ring = LiveRing()
        val row = FloatArray(6)
        repeat(1010) { i -> row.fill(i.toFloat()); ring.append(row) }
        assertEquals(0L, ring.version.value)
        ring.publishFrame()
        assertEquals(1L, ring.version.value)
        val dst = FloatArray(6000)
        assertEquals(1000, ring.copyLatest(dst, 1000))
        assertEquals(10f, dst[0], 0f)
        assertEquals(1009f, dst.last(), 0f)
        assertEquals(2, ring.copyLatest(FloatArray(12), 1000))
        ring.clear()
        assertEquals(0, ring.copyLatest(dst, 1000))
    }
}
