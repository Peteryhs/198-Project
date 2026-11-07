package com.jeevan.tally.recording

import com.jeevan.tally.sensors.SensorSample
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class RecordingStoreTest {
    @get:Rule val temp = TemporaryFolder()
    private fun samples() = listOf(SensorSample(0f, floatArrayOf(1f, 2f, 3f, 4f), 1), SensorSample(2f, floatArrayOf(-1f, -2f, -3f, 4f), 2))
    @Test fun `saved recording survives reopening store with samples and pause segments intact`() {
        val dir = temp.newFolder()
        val info = RecordingStore(dir).save("accelerometer", "Pendulum", 2.5f, samples())
        val reopened = RecordingStore(dir)
        assertEquals(info, reopened.list().single())
        val recording = reopened.load(info.id)
        assertEquals(info, recording.info)
        assertEquals(2, recording.samples.last().segment)
        assertEquals(2f, recording.samples.last().t, 0f)
        assertArrayEquals(samples().last().values, recording.samples.last().values, 0f)
    }
    @Test fun `interrupted writes never appear as saved recordings`() {
        val dir = temp.newFolder()
        File(dir, "interrupted.tmp").writeText("incomplete")
        assertTrue(RecordingStore(dir).list().isEmpty())
    }
    @Test fun `corrupt files do not hide valid recordings`() {
        val dir = temp.newFolder()
        File(dir, "00000000-0000-0000-0000-000000000000.tally").writeText("corrupt")
        val store = RecordingStore(dir)
        val info = store.save("gyroscope", "Turn", 2f, samples())
        assertEquals(listOf(info), store.list())
    }
    @Test(expected = IllegalArgumentException::class) fun `refuses path traversal`() { RecordingStore(temp.newFolder()).load("../../private") }
    @Test(expected = IllegalArgumentException::class) fun `refuses nonfinite measurements`() {
        RecordingStore(temp.newFolder()).save("accelerometer", "Invalid", 1f, listOf(SensorSample(0f, floatArrayOf(Float.NaN, 0f, 0f, 0f))))
    }
    @Test(expected = IllegalArgumentException::class) fun `refuses out of order timestamps`() {
        RecordingStore(temp.newFolder()).save("accelerometer", "Invalid", 2f, samples().reversed())
    }

    @Test fun `custom scalar metadata survives saving and reopening offline`() {
        val store = RecordingStore(temp.newFolder())
        val spec = com.jeevan.tally.sensors.PlugSpec("temp", "Temperature", listOf("temperature"), "°C")
        val info = store.save("temp", "Room", 1f, listOf(SensorSample(0f, floatArrayOf(21.5f))), spec)
        val recording = store.load(info.id)
        assertEquals(spec, recording.info.spec)
        assertEquals(1, recording.samples.single().values.size)
        assertEquals(21.5f, recording.samples.single().values[0], 0f)
    }
    @Test fun `legacy version one recordings still reopen`() {
        val dir = temp.newFolder()
        val id = "00000000-0000-0000-0000-000000000001"
        java.io.DataOutputStream(File(dir, "$id.tally").outputStream()).use {
            it.writeUTF("TALLY-1"); it.writeUTF("accelerometer"); it.writeUTF("Old session")
            it.writeLong(0); it.writeFloat(1f); it.writeInt(1)
            it.writeFloat(0f); it.writeInt(1)
            repeat(4) { axis -> it.writeFloat(axis.toFloat()) }
        }
        val recording = RecordingStore(dir).load(id)
        assertEquals(com.jeevan.tally.sensors.PlugSpec.accel, recording.info.spec)
        assertArrayEquals(floatArrayOf(0f, 1f, 2f, 3f), recording.samples.single().values, 0f)
    }
}
