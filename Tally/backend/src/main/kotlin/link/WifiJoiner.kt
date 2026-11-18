package com.tally.app.backend.link

import android.content.Context
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import android.net.wifi.WifiNetworkSpecifier
import android.os.PatternMatcher
import android.os.Build
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

internal class WifiJoiner(context: Context) {
    private val connectivity = context.getSystemService(ConnectivityManager::class.java)
    private val wifi = context.getSystemService(WifiManager::class.java)
    private val location = context.getSystemService(LocationManager::class.java)
    private var callback: ConnectivityManager.NetworkCallback? = null
    private var pending: CancellableContinuation<Network>? = null
    @Volatile var currentNetwork: Network? = null
        private set

    /** Null or blank [passphrase] requests an open `Tally-*` network; otherwise a WPA2 one. */
    suspend fun join(passphrase: String?): Network {
        close()
        val credential = try { wifiPassphraseOrOpen(passphrase) }
            catch (e: IllegalArgumentException) { throw IOException(e.message, e) }
        @Suppress("DEPRECATION")
        if (!wifi.isWifiEnabled) throw IOException("Turn on Wi-Fi to connect to Tally")
        if (Build.VERSION.SDK_INT < 33 && !location.isLocationEnabled)
            throw IOException("Turn on Location to let Android find the Tally Wi-Fi network")
        val builder = WifiNetworkSpecifier.Builder()
            .setSsidPattern(PatternMatcher("Tally-", PatternMatcher.PATTERN_PREFIX))
        if (credential != null) builder.setWpa2Passphrase(credential)
        val specifier = builder.build()
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .setNetworkSpecifier(specifier)
            .build()
        return suspendCancellableCoroutine { continuation ->
            val requested = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    val waiting = synchronized(this@WifiJoiner) {
                        if (callback !== this) return
                        currentNetwork = network
                        pending.also { pending = null }
                    }
                    if (waiting?.isActive == true) waiting.resume(network)
                }
                override fun onLost(network: Network) {
                    synchronized(this@WifiJoiner) {
                        if (callback === this && currentNetwork == network) currentNetwork = null
                    }
                }
                override fun onUnavailable() {
                    val waiting = synchronized(this@WifiJoiner) {
                        if (callback !== this) return
                        pending.also { pending = null }
                    }
                    release(this)
                    if (waiting?.isActive == true) waiting.resumeWithException(IOException(unavailableReason(credential != null)))
                }
            }
            synchronized(this) { callback = requested; pending = continuation }
            continuation.invokeOnCancellation { release(requested) }
            try {
                connectivity.requestNetwork(request, requested, 30_000)
                if (continuation.isCancelled) release(requested)
            } catch (error: Exception) {
                release(requested)
                if (continuation.isActive) continuation.resumeWithException(error)
            }
        }
    }

    fun close() {
        val (current, waiting) = synchronized(this) {
            (callback to pending).also { callback = null; pending = null; currentNetwork = null }
        }
        waiting?.cancel()
        if (current != null) runCatching { connectivity.unregisterNetworkCallback(current) }
    }

    private fun release(requested: ConnectivityManager.NetworkCallback) {
        synchronized(this) {
            if (callback === requested) { callback = null; pending = null; currentNetwork = null }
        }
        runCatching { connectivity.unregisterNetworkCallback(requested) }
    }
}

/**
 * Android reports a wrong password, an open/WPA2 mismatch, a declined prompt and an absent AP all as
 * onUnavailable, so name the request that was made and the likely mismatch.
 */
internal fun unavailableReason(usedPassword: Boolean): String = if (usedPassword)
    "No WPA2 Tally Wi-Fi network accepted that password, or the network prompt was declined. " +
        "Check the password matches the device. If the device's Wi-Fi is open (no password), clear the field and try again."
else
    "No open Tally Wi-Fi network was found, or the network prompt was declined. The password field is blank, so the phone " +
        "asked for an open network; if the device's Wi-Fi uses WPA2 (current Tally firmware does), enter its password."

/**
 * Blank or null means an open network and returns null. Anything else must be a WPA2 passphrase:
 * 8..63 printable ASCII characters, the rule WifiNetworkSpecifier enforces. Checking it here turns
 * Android's exception into a message the user can act on.
 */
internal fun wifiPassphraseOrOpen(value: String?): String? {
    if (value.isNullOrBlank()) return null
    require(value.length in 8..63) {
        "A WPA2 Wi-Fi password has 8 to 63 characters; this one has ${value.length}. Leave it blank if the Tally Wi-Fi is open."
    }
    require(value.all { it in ' '..'~' }) { "The Wi-Fi password may only use plain ASCII letters, digits, spaces and symbols" }
    return value
}
