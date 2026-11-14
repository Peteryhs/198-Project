package com.jeevan.tally.export

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import com.jeevan.tally.exercise.SavedSet
import com.jeevan.tally.exercise.SetReport
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Shares one set as the instructor summary: readable text in the message body, full CSV attached. */
object SetExporter {
    fun share(context: Context, set: SavedSet): Intent {
        val dir = File(context.getExternalFilesDir(null), "exports").apply { mkdirs() }
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date(set.summary.startedAtMillis))
        val stem = CsvFormatter.safeFileStem(set.name).ifEmpty { "set" }
        val file = File(dir, "tally_${stem}_$stamp.csv")
        file.writeText(SetReport.toCsv(set))
        val uri = FileProvider.getUriForFile(context, "com.jeevan.tally.fileprovider", file)
        return Intent(Intent.ACTION_SEND).apply {
            type = "text/csv"
            putExtra(Intent.EXTRA_SUBJECT, "Tally set: ${set.name}")
            putExtra(Intent.EXTRA_TEXT, SetReport.toText(set))
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }
}
