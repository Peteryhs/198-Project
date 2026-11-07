package com.jeevan.tally.export

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import com.jeevan.tally.sensors.SensorSample
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Writes a recorded session to CSV in app-specific external storage and returns a share Intent. */
object CsvExporter {

    fun export(
        context: Context,
        experimentTitle: String,
        axisNames: List<String>,
        samples: List<SensorSample>,
    ): Intent {
        val dir = File(context.getExternalFilesDir(null), "exports").apply { mkdirs() }
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val file = File(dir, "${CsvFormatter.safeFileStem(experimentTitle)}_$stamp.csv")

        file.writeText(CsvFormatter.toCsv(axisNames, samples))

        val uri = FileProvider.getUriForFile(context, "com.jeevan.tally.fileprovider", file)

        return Intent(Intent.ACTION_SEND).apply {
            type = "text/csv"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }
}
