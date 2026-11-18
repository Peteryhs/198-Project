package com.tally.app.backend.log

import android.content.Context
import android.os.Build
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Append-only log kept in memory and in `filesDir/tally.log`, plus a crash file, so a failure on a phone
 * with no adb leaves evidence the owner can read and copy from inside the app.
 *
 * Every entry is one line: `MM-dd HH:mm:ss.SSS LEVEL thread: message`. A throwable follows its line as
 * indented stack frames. The file is truncated rather than rotated once it passes 256 KiB, because the
 * recent past is what matters for a crash on the start path.
 */
object TallyLog {
    private const val MAX_MEMORY_LINES = 1500
    private const val MAX_FILE_CHARS = 256 * 1024
    private const val MAX_STACK_FRAMES = 80

    private val memory = ArrayDeque<String>(MAX_MEMORY_LINES)
    private val lock = Any()
    private val stamp = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)

    @Volatile private var logFile: File? = null
    @Volatile private var crashFile: File? = null

    fun install(context: Context) {
        val dir = context.applicationContext.filesDir
        logFile = File(dir, "tally.log")
        crashFile = File(dir, "tally-crash.log")
        i("app start on ${Build.MANUFACTURER} ${Build.MODEL}, Android ${Build.VERSION.SDK_INT}, files=${dir.absolutePath}")
    }

    fun i(message: String) = write("I", message, null)
    fun w(message: String, error: Throwable? = null) = write("W", message, error)
    fun e(message: String, error: Throwable? = null) = write("E", message, error)

    /** Called from the uncaught-exception handler, so it must not throw. */
    fun crash(thread: Thread, error: Throwable) {
        val header = "FATAL ${thread.name}: ${error.javaClass.name}: ${error.message}"
        write("F", header, error)
        runCatching {
            crashFile?.appendText(buildString {
                append(stamp.format(Date())).append(' ').append(header).append('\n')
                error.stackTraceToString().lines().take(MAX_STACK_FRAMES).forEach { append("    ").append(it).append('\n') }
                append('\n')
            })
        }
    }

    /** The last lines of this session, newest last. */
    fun snapshot(): String = synchronized(lock) {
        if (memory.isEmpty()) "(no log lines yet)" else memory.joinToString("\n")
    }

    fun crashSnapshot(): String? = runCatching {
        crashFile?.takeIf { it.exists() && it.length() > 0 }?.readText()?.takeLast(MAX_FILE_CHARS)
    }.getOrNull()

    private fun write(level: String, message: String, error: Throwable?) {
        val line = "${stamp.format(Date())} $level ${Thread.currentThread().name}: $message"
        val extra = error?.stackTraceToString()?.lines()?.take(MAX_STACK_FRAMES)?.map { "    $it" } ?: emptyList()
        synchronized(lock) {
            memory.addLast(line)
            memory.addAll(extra)
            while (memory.size > MAX_MEMORY_LINES) memory.removeFirst()
            val target = logFile ?: return
            runCatching {
                if (target.length() > MAX_FILE_CHARS) target.delete()
                target.appendText((listOf(line) + extra).joinToString("\n", postfix = "\n"))
            }
        }
    }
}
