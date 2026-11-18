package com.tally.app.backend.session

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

internal class LiveRing : com.tally.app.contract.LiveRing {
    override val capacitySamples = 1000 // Documented: docs/PLAN.md §4.
    private val data = FloatArray(capacitySamples * 6)
    private var next = 0
    private var size = 0
    private val updates = MutableStateFlow(0L)
    override val version = updates.asStateFlow()

    /** One calibrated sample, six channels in g. */
    @Synchronized fun append(g: FloatArray) {
        require(g.size >= 6)
        g.copyInto(data, next * 6, 0, 6)
        next = (next + 1) % capacitySamples
        size = minOf(size + 1, capacitySamples)
    }
    fun publishFrame() { updates.value++ }
    @Synchronized fun clear() { next = 0; size = 0; updates.value++ }
    @Synchronized override fun copyLatest(dst: FloatArray, maxSamples: Int): Int {
        require(maxSamples >= 0)
        val count = minOf(size, maxSamples, dst.size / 6)
        val start = (next - count + capacitySamples) % capacitySamples
        val first = minOf(count, capacitySamples - start)
        data.copyInto(dst, 0, start * 6, (start + first) * 6)
        if (first < count) {
            data.copyInto(dst, first * 6, 0, (count - first) * 6)
        }
        return count
    }
}
