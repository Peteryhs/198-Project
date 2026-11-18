package com.tally.app.backend.score

import android.content.Context
import com.tally.app.contract.Side
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption

internal class ModelRegistry(private val context: Context) {
    fun install(): File {
        val root = File(context.filesDir, "model")
        for (side in Side.entries) {
            for (name in listOf("realtime_model.npz", "metadata.json")) {
                val relative = "paired-synchronized-offline/${side.name}/$name"
                val bytes = context.assets.open("model/$relative").use { it.readBytes() }
                val destination = File(root, relative)
                if (!destination.isFile || !destination.readBytes().contentEquals(bytes)) {
                    check(destination.parentFile!!.isDirectory || destination.parentFile!!.mkdirs())
                    val temporary = File(destination.parentFile, "$name.tmp")
                    temporary.writeBytes(bytes)
                    Files.move(temporary.toPath(), destination.toPath(),
                        StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
                }
                check(destination.readBytes().contentEquals(bytes)) { "Model copy differs: $relative" }
            }
        }
        return root
    }
}
