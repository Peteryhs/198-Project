package com.tally.app.backend.session

/** Heartbeats keep TCP alive; only increasing sample counts prove the sensor stream is working. */
internal class SampleProgress(startedNs: Long) {
    var lastProgressNs = startedNs
        private set
    private var samples = 0

    fun stalled(sampleCount: Int, nowNs: Long): Boolean {
        if (sampleCount > samples) {
            samples = sampleCount
            lastProgressNs = nowNs
        }
        return nowNs - lastProgressNs >= 3_000_000_000L
    }
}
