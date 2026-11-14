package com.jeevan.tally.sensors

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * One labelled reading at a point in time: elapsed seconds since the stream started, plus one value per axis.
 * [deviceMillis] is the board's own timestamp when the frame carried one (the synchronized pair row).
 */
data class SensorSample(
    val t: Float,
    val values: FloatArray,
    val segment: Int = 0,
    val receivedAtNanos: Long? = null,
    val deviceMillis: Long? = null,
)

/**
 * A single physics "experiment": a named set of axes (e.g. x, y, z, magnitude) with a unit,
 * backed by a Flow of samples. Acquisition timestamps use System.nanoTime().
 * Arduino streams currently provide accelerometer and gyroscope channels.
 */
interface SensorStream {
    val title: String
    val description: String
    val axisNames: List<String>
    val axisColorsHex: List<String>
    val unit: String
    val permissions: List<String>

    fun isCompatible(): Boolean = true
    fun samples(): Flow<SensorSample>
    fun sampleBatches(): Flow<SampleBatch> = samples().map { SampleBatch(listOf(it)) }
}
