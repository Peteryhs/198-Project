package com.tally.app.backend.score

import com.tally.app.backend.link.EndReason
import com.tally.app.backend.session.SampleStore
import com.tally.app.contract.Side
import java.util.Locale

/** Writes the scorer's `#TALLY2 unit=g` input from a [SampleStore] that already holds g. */
internal object TallyWireWriter {
    fun write(side: Side, store: SampleStore, end: EndReason, out: Appendable) {
        out.append("#TALLY2 fs=100 unit=g range=3 side=${side.name}\n")
        for (i in 0 until store.size) {
            out.append(String.format(Locale.ROOT,
                "S %d %d %+.8f %+.8f %+.8f %+.8f %+.8f %+.8f\n",
                i, store.timestampUs(i) / 1000,
                store.g(i, 0), store.g(i, 1), store.g(i, 2),
                store.g(i, 3), store.g(i, 4), store.g(i, 5)))
        }
        out.append("E ${end.name.lowercase(Locale.ROOT)}\n")
    }
}
