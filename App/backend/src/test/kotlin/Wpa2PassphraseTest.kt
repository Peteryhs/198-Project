package com.tally.app.backend

import com.tally.app.backend.link.unavailableReason
import com.tally.app.backend.link.wifiPassphraseOrOpen
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class Wpa2PassphraseTest {
    @Test fun blankMeansOpenNetwork() {
        assertNull(wifiPassphraseOrOpen(null))
        assertNull(wifiPassphraseOrOpen(""))
        assertNull(wifiPassphraseOrOpen("   "))
    }

    @Test fun wpa2PassphraseMustBe8To63PrintableAscii() {
        assertEquals("pass with spaces", wifiPassphraseOrOpen("pass with spaces"))
        assertEquals("12345678", wifiPassphraseOrOpen("12345678"))
        assertEquals("x".repeat(63), wifiPassphraseOrOpen("x".repeat(63)))
        val short = assertThrows(IllegalArgumentException::class.java) { wifiPassphraseOrOpen("short") }
        assertTrue(short.message!!.contains("8 to 63") && short.message!!.contains("blank"))
        assertThrows(IllegalArgumentException::class.java) { wifiPassphraseOrOpen("x".repeat(64)) }
        assertThrows(IllegalArgumentException::class.java) { wifiPassphraseOrOpen("pässwörter") }
        assertThrows(IllegalArgumentException::class.java) { wifiPassphraseOrOpen("tab\tinside!") }
    }

    @Test fun unavailableNamesTheRequestThatWasMade() {
        assertTrue(unavailableReason(usedPassword = false).let { it.contains("open") && it.contains("blank") && it.contains("WPA2") })
        assertTrue(unavailableReason(usedPassword = true).let { it.contains("password") && it.contains("open") })
    }
}
