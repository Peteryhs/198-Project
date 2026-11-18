package com.tally.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import java.io.File
import java.io.FileNotFoundException
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Application-owned store. Only the authenticated ciphertext is written to disk. */
internal class WifiPassphraseStore(context: Context) {
    private val file = AtomicFile(File(context.noBackupFilesDir, "wifi-passphrase"))

    @Synchronized
    fun load(): String = try {
        val encrypted = file.readFully()
        val key = keyStore().getKey(KEY_ALIAS, null) as? SecretKey
        key?.let { WifiPassphraseCipher(it).decrypt(encrypted) }.orEmpty()
    } catch (_: Exception) {
        // The user can re-enter the password if the key or ciphertext is unavailable.
        ""
    }

    @Synchronized
    fun save(passphrase: String): Boolean {
        if (passphrase.isEmpty()) return clear()
        return try {
            val key = keyStore().getKey(KEY_ALIAS, null) as? SecretKey ?: createKey()
            val encrypted = WifiPassphraseCipher(key).encrypt(passphrase)
            val stream = file.startWrite()
            try {
                stream.write(encrypted)
            } catch (failure: Exception) {
                file.failWrite(stream)
                throw failure
            }
            file.finishWrite(stream)
            file.readFully().contentEquals(encrypted)
        } catch (_: Exception) {
            false
        }
    }

    @Synchronized
    fun clear(): Boolean = try {
        file.delete()
        file.openRead().use { false }
    } catch (_: FileNotFoundException) {
        true
    } catch (_: Exception) {
        false
    }

    private fun keyStore() = KeyStore.getInstance(KEY_STORE).apply { load(null) }

    private fun createKey(): SecretKey = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEY_STORE).run {
        init(
            KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        generateKey()
    }

    private companion object {
        const val KEY_STORE = "AndroidKeyStore"
        const val KEY_ALIAS = "tally.wifi.passphrase"
    }
}

internal class WifiPassphraseCipher(private val key: SecretKey) {
    fun encrypt(passphrase: String): ByteArray {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key)
        val iv = cipher.iv
        check(iv.size == IV_BYTES)
        return iv + cipher.doFinal(passphrase.toByteArray(Charsets.UTF_8))
    }

    fun decrypt(encrypted: ByteArray): String {
        require(encrypted.size >= IV_BYTES + TAG_BITS / Byte.SIZE_BITS)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(TAG_BITS, encrypted, 0, IV_BYTES))
        return cipher.doFinal(encrypted, IV_BYTES, encrypted.size - IV_BYTES).toString(Charsets.UTF_8)
    }

    private companion object {
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_BYTES = 12
        const val TAG_BITS = 128
    }
}
