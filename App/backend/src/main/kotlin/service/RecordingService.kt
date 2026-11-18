package com.tally.app.backend.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.IBinder
import android.os.PowerManager

class RecordingService : Service() {
    private var wifiLock: WifiManager.WifiLock? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var failureCallback: (() -> Unit)? = null

    override fun onCreate() {
        super.onCreate()
        failureCallback = onUnexpectedStop
        try {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CHANNEL, "Recording", NotificationManager.IMPORTANCE_LOW))
            val notification = Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_upload).setContentTitle("Tally recording")
                .setContentText("Receiving exercise samples").setOngoing(true).build()
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
            wifiLock = applicationContext.getSystemService(WifiManager::class.java)
                .createWifiLock(WifiManager.WIFI_MODE_FULL_LOW_LATENCY, "Tally:recording").apply {
                    setReferenceCounted(false); acquire()
                }
            wakeLock = getSystemService(PowerManager::class.java)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Tally:recording").apply {
                    setReferenceCounted(false); acquire()
                }
        } catch (error: Exception) {
            com.tally.app.backend.log.TallyLog.e("recording service startForeground failed", error)
            releaseLocks()
            notifyUnexpectedStop()
            stopSelf()
        }
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        failureCallback = onUnexpectedStop
        return START_NOT_STICKY
    }
    override fun onBind(intent: Intent?): IBinder? = null
    override fun onDestroy() {
        releaseLocks()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
        notifyUnexpectedStop()
    }
    private fun notifyUnexpectedStop() {
        val callback = failureCallback
        failureCallback = null
        if (callback != null && onUnexpectedStop === callback) {
            onUnexpectedStop = null
            callback.invoke()
        }
    }
    private fun releaseLocks() {
        wakeLock?.let { if (it.isHeld) it.release() }; wakeLock = null
        wifiLock?.let { if (it.isHeld) it.release() }; wifiLock = null
    }
    companion object {
        private const val CHANNEL = "tally_recording"
        @Volatile var onUnexpectedStop: (() -> Unit)? = null
        fun start(context: Context) { context.startForegroundService(Intent(context, RecordingService::class.java)) }
        fun stop(context: Context) {
            onUnexpectedStop = null
            context.stopService(Intent(context, RecordingService::class.java))
        }
    }
}
