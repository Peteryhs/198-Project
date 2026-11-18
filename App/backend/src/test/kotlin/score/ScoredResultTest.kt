package com.tally.app.backend.score

import com.tally.app.contract.Provenance
import com.tally.app.contract.SetId
import com.tally.app.contract.Side
import com.tally.app.contract.ChartSample
import com.tally.app.contract.RepSpan
import com.tally.app.contract.SetChart
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ScoredResultTest {
    @Test fun chartJsonRoundTripsExactRecordedTimesAndRepBounds() {
        val chart = SetChart(listOf(ChartSample(0.0, 1.23f, 2.45f), ChartSample(1.57, 3.21f, 1.08f)),
            listOf(RepSpan(1, 0.0, 1.57)))
        assertEquals(chart, JSONObject(chart.toJson().toString()).toSetChart())
    }

    @Test fun missingVerdictStaysUnknownInsteadOfBecomingCorrectOrZero() {
        for (status in listOf("rejected", "insufficient_reps")) {
            val record = JSONObject().put("status", status).put("verdict", "unknown")
                .put("mean_p_wrong", JSONObject.NULL).put("exercise", JSONObject.NULL)
            val provenance = Provenance("fixture", "model-hash", "scorer-hash", "revision", 42,
                "01:02:03:04:05:06", "calibration", "host-check")
            val result = record.toSetResult(SetId(1u), Side.R, 123L, provenance)
            assertEquals(status, result.status)
            assertNull(result.wrong)
            assertNull(result.meanPWrong)
            assertNull(result.exercise)
            assertNull(result.measuredRateHz)
            assertTrue(result.reps.isEmpty())
            assertEquals(provenance, result.provenance)
        }
    }
}
