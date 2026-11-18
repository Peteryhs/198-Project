package com.tally.app.backend.score

import com.tally.app.backend.link.EndReason
import com.tally.app.backend.session.SampleStore
import com.tally.app.contract.Side
import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.Locale

class TallyWireWriterTest {
    @Test fun usesDeviceMillisecondsAndRootLocale() {
        val previous = Locale.getDefault()
        try {
            Locale.setDefault(Locale.GERMANY)
            val store = SampleStore()
            store.append(10_999, floatArrayOf(1f, -1f, 0f, .5f, -.5f, 2f))
            val wire = StringBuilder()
            TallyWireWriter.write(Side.R, store, EndReason.DONE, wire)
            assertEquals("#TALLY2 fs=100 unit=g range=3 side=R\n" +
                "S 0 10 +1.00000000 -1.00000000 +0.00000000 +0.50000000 -0.50000000 +2.00000000\n" +
                "E done\n", wire.toString())
        } finally {
            Locale.setDefault(previous)
        }
    }
}
