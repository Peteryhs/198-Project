package com.tally.app.backend.calib

import com.tally.app.contract.CalPose
import org.junit.Assert.*
import org.junit.Test

class CalibrationTest {
    @Test fun sixPosesRecoverEachSensorScaleAndOffset() {
        val poses = CalPose.entries.associateWith { pose ->
            FloatArray(6) { ch ->
                val axis = ch % 3
                1500f + ch + if (pose.ordinal / 2 == axis) (if (pose.ordinal % 2 == 0) 300f else -300f) else 0f
            }
        }
        val calibration = Calibration.fromPoses(poses, 123)
        assertTrue(Calibration.nominal().info.nominal)
        repeat(6) { assertEquals(1f, calibration.toG(1800 + it, it), 0.0001f) }
        assertEquals("six-pose-123", calibration.info.id)
        assertThrows(IllegalArgumentException::class.java) { Calibration.fromPoses(emptyMap(), 0) }
        assertThrows(IllegalArgumentException::class.java) {
            Calibration.fromPoses(CalPose.entries.associateWith { FloatArray(6) { 1500f } }, 0)
        }
        val restored = CalibrationStore.fromJson(CalibrationStore.toJson(calibration))
        assertArrayEquals(calibration.offsetMv, restored.offsetMv, 0f)
        assertArrayEquals(calibration.mvPerG, restored.mvPerG, 0f)

        val implausibleOffset = CalibrationStore.toJson(calibration)
        implausibleOffset.getJSONArray("offset_mv").put(0, 2501.0)
        assertThrows(IllegalArgumentException::class.java) { CalibrationStore.fromJson(implausibleOffset) }
        val tinyScale = CalibrationStore.toJson(calibration)
        tinyScale.getJSONArray("mv_per_g").put(0, 0.01)
        assertThrows(IllegalArgumentException::class.java) { CalibrationStore.fromJson(tinyScale) }
    }
}
