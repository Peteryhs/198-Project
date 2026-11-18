package com.tally.app.backend.score

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.tally.app.backend.BuildConfig
import com.tally.app.contract.Side
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors

internal data class ScoreOutput(val record: JSONObject, val reply: List<String>)

internal class PythonScorer(context: Context) {
    private val context = context.applicationContext
    private val dispatcher = Executors.newSingleThreadExecutor { task ->
        Thread(task, "tally-scorer")
    }.asCoroutineDispatcher()
    private var info: ScorerInfo? = null
    private lateinit var module: PyObject

    suspend fun warmUp(): ScorerInfo = withContext(dispatcher) { initialize() }

    suspend fun score(wire: String, intendedExercise: String?): ScoreOutput = withContext(dispatcher) {
        initialize()
        val result = JSONObject(module.callAttr("score_wire", wire, intendedExercise).toString())
        val replies = result.getJSONArray("reply")
        ScoreOutput(result.getJSONObject("record"), List(replies.length()) { replies.getString(it) })
    }

    private fun initialize(): ScorerInfo {
        info?.let { return it }
        synchronized(Python::class.java) {
            if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        }
        module = Python.getInstance().getModule("tally_app")
        val hashes = JSONObject(module.callAttr("init", ModelRegistry(context).install().path).toString())
        val scorerHash = module.callAttr("scorer_version").toString()
        check(scorerHash == BuildConfig.SCORER_SHA256) { "Packaged scorer hash differs from build" }
        val classes = JSONArray(module.callAttr("exercise_classes").toString())
        return ScorerInfo(Side.entries.associateWith { hashes.getString(it.name) }, scorerHash,
            List(classes.length()) { classes.getString(it) })
            .also { info = it }
    }
}
