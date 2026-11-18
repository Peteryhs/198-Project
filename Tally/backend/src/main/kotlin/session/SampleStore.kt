package com.tally.app.backend.session

/** One set's samples after calibration: timestamps in µs (ESP32 clock), six channels in g. */
internal class SampleStore {
    val capacitySamples = 60_000 // Documented: docs/PLAN.md §5.
    private val timestamps = LongArray(capacitySamples)
    private val samplesG = FloatArray(capacitySamples * 6)
    var size: Int = 0
        private set

    fun append(tUs: Long, g: FloatArray) {
        require(size < capacitySamples) { "Sample capacity exceeded" }
        require(g.size >= 6) { "Invalid channels" }
        for (channel in 0..5) require(g[channel].isFinite()) { "Non-finite channel" }
        require(tUs >= 0 && (size == 0 || tUs > timestamps[size - 1])) { "Non-increasing timestamp" }
        timestamps[size] = tUs
        g.copyInto(samplesG, size * 6, 0, 6)
        size++
    }
    fun timestampUs(index: Int): Long { require(index in 0 until size); return timestamps[index] }
    fun g(index: Int, channel: Int): Float {
        require(index in 0 until size && channel in 0..5)
        return samplesG[index * 6 + channel]
    }
    fun clear() { size = 0 }
}
