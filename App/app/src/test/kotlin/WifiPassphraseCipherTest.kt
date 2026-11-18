package com.tally.app

import javax.crypto.AEADBadTagException
import javax.crypto.KeyGenerator
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Test

class WifiPassphraseCipherTest {
    private val cipher = WifiPassphraseCipher(KeyGenerator.getInstance("AES").generateKey())

    @Test fun spacesRoundTripAndEachSaveUsesFreshCiphertext() {
        val passphrase = "  pass with spaces  "
        val encrypted = cipher.encrypt(passphrase)

        assertEquals(passphrase, cipher.decrypt(encrypted))
        assertFalse(encrypted.contentEquals(cipher.encrypt(passphrase)))
    }

    @Test fun tamperedOrTruncatedDataCannotBeDecoded() {
        val encrypted = cipher.encrypt("local-test")
        encrypted[encrypted.lastIndex] = (encrypted.last().toInt() xor 1).toByte()

        assertThrows(AEADBadTagException::class.java) { cipher.decrypt(encrypted) }
        assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(encrypted.copyOf(8)) }
    }
}
