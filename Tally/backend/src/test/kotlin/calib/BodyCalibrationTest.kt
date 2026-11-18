package com.tally.app.backend.calib

import com.tally.app.contract.BodyHold
import org.junit.Assert.*
import org.junit.Test

class BodyCalibrationTest {
    private fun recordedHolds(): Map<BodyHold, FloatArray> = buildMap {
        val lines = javaClass.getResource("/calibration/recorded-proxies.csv")!!.readText().lines()
        lines.filter { it.isNotBlank() && !it.startsWith("#") }.drop(1).forEach { line ->
            val columns = line.split(',')
            put(BodyHold.valueOf(columns[0]), columns.drop(3).map { it.toFloat() }.toFloatArray())
        }
    }

    @Test fun recordedExerciseProxiesExposeTheOriginalRadiusRefusal() {
        val holds = recordedHolds()
        repeat(2) { mount ->
            val ch = mount * 3
            val sphere = OnArmMath.sphereFit(Calibration.REQUIRED_HOLDS.take(4).map { h ->
                DoubleArray(3) { holds.getValue(h)[ch + it] / 330.0 }
            })!!
            println("DERIVED recorded proxy mount=$mount radius=${sphere.radiusG} offsets=${sphere.center.map { it * 330 }}")
            assertFalse(sphere.radiusOk)
        }
        val saved = Calibration.fromBodyHolds(holds, 123)
        assertEquals("body-123", saved.info.id)
        assertFalse(saved.usable)
        assertTrue(saved.reasons.any { "fitted radius" in it })
        assertTrue(saved.reasons.any { "norm" in it })
        println("DERIVED fixed proxy result: marginal; ${saved.reasons}")
    }

    private fun controlledHolds(gain: Float = 330f, offset: Float = 1500f): Map<BodyHold, FloatArray> {
        val directions = listOf(floatArrayOf(0f, 0f, 1f), floatArrayOf(1f, 0f, 0f),
            floatArrayOf(0f, 1f, 0f), floatArrayOf(0f, 0f, -1f), floatArrayOf(-1f, 0f, 0f))
        return Calibration.REQUIRED_HOLDS.zip(directions).associate { (hold, direction) ->
            hold to FloatArray(6) { offset + gain * direction[it % 3] }
        }
    }

    @Test fun unknownGainAndOffsetSaveAsMarginal() {
        // Derived controlled cases, not measured device gains or offsets.
        for (holds in listOf(controlledHolds(400f), controlledHolds(offset = 2600f))) {
            val saved = Calibration.fromBodyHolds(holds, 123)
            assertFalse(saved.usable)
            assertEquals("nominal", saved.gainSource)
            assertTrue(saved.reasons.any { "unmeasured" in it })
            println("DERIVED controlled result: ${saved.reasons}")
        }
        val offsetCase = Calibration.fromBodyHolds(controlledHolds(offset = 2600f), 123)
        assertArrayEquals(FloatArray(6) { 2600f }, offsetCase.offsetMv, 0.001f)
        assertTrue(offsetCase.reasons.any { "offset outside" in it })
    }

    @Test fun plausibleBodyHoldsDerivedFromRecordedLevelsAllowUnknownPerChannelGains() {
        // Derived scenario: measured starting levels; assumed gravity directions and unknown gains.
        val base = recordedHolds().getValue(BodyHold.HANG)
        val gains = floatArrayOf(290f, 400f, 360f, 410f, 280f, 350f)
        val holds = controlledHolds().mapValues { (_, values) ->
            FloatArray(6) { ch -> base[ch] + (values[ch] - 1500f) / 330f * gains[ch] }
        }
        val saved = Calibration.fromBodyHolds(holds, 456)
        assertEquals("body-456", saved.info.id)
        assertEquals("nominal", saved.gainSource)
        assertFalse(saved.usable)
        assertEquals(2, saved.frames!!.size)
        println("DERIVED plausible holds from recorded levels: ${saved.reasons}")
    }

    @Test fun offsetsFramesAndMarginalDiagnosticsSurviveSerializedJson() {
        val holds = controlledHolds(400f, 2600f).mapValues { (_, v) ->
            // Rotate the forearm basis so copying either mount over the other cannot pass.
            floatArrayOf(v[0], v[1], v[2], v[4], v[5], v[3])
        }
        val saved = Calibration.fromBodyHolds(holds, 123)
        assertFalse(saved.frames!![0].contentEquals(saved.frames[1]))
        val json = CalibrationStore.toJson(saved)
        assertEquals("marginal", json.getString("status"))
        val restored = CalibrationStore.fromJson(org.json.JSONObject(json.toString()))
        assertEquals(saved.info, restored.info)
        assertArrayEquals(saved.offsetMv, restored.offsetMv, 0f)
        assertArrayEquals(saved.mvPerG, restored.mvPerG, 0f)
        repeat(2) { assertArrayEquals(saved.frames!![it], restored.frames!![it], 0f) }
        assertEquals(saved.gainSource, restored.gainSource)
        assertEquals(saved.reasons, restored.reasons)
        assertFalse(restored.usable)
        // Existing JSON without diagnostics is also marginal with nominal gains.
        json.remove("reasons")
        json.remove("status")
        assertFalse(CalibrationStore.fromJson(json).usable)
    }

    @Test fun incompleteInvalidAndDegenerateHoldsStillRefuseWithBodyActions() {
        val missing = controlledHolds() - BodyHold.CHECK
        val absent = assertThrows(IllegalStateException::class.java) { Calibration.fromBodyHolds(missing, 0) }
        assertTrue(absent.message!!.contains(Calibration.bodyAction(BodyHold.CHECK)))
        for (bad in listOf(floatArrayOf(1f), FloatArray(6) { Float.NaN }, FloatArray(6) { -1f })) {
            val invalid = controlledHolds() + (BodyHold.CHECK to bad)
            val error = assertThrows(IllegalArgumentException::class.java) { Calibration.fromBodyHolds(invalid, 0) }
            assertTrue(error.message!!.contains(Calibration.bodyAction(BodyHold.CHECK)))
        }
        val repeated = Calibration.REQUIRED_HOLDS.associateWith { FloatArray(6) { 1500f } }
        val error = assertThrows(IllegalStateException::class.java) { Calibration.fromBodyHolds(repeated, 0) }
        assertTrue(error.message!!.contains(Calibration.bodyAction(BodyHold.OVERHEAD)))
        assertFalse(error.message!!.contains("axis"))
        val closeAnchors = controlledHolds().toMutableMap()
        closeAnchors[BodyHold.FORWARD_PALM_UP] = FloatArray(6) { ch ->
            1500f + 330f * when (ch % 3) { 0 -> kotlin.math.sin(0.1).toFloat(); 2 -> kotlin.math.cos(0.1).toFloat(); else -> 0f }
        }
        val anchors = assertThrows(IllegalStateException::class.java) { Calibration.fromBodyHolds(closeAnchors, 0) }
        assertTrue(anchors.message!!.contains(Calibration.bodyAction(BodyHold.FORWARD_PALM_UP)))
    }
}
