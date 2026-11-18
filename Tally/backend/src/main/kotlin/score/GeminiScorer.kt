package com.tally.app.backend.score

import com.tally.app.backend.session.SampleStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.sqrt

/**
 * Last-resort scorer behind the debug toggle.
 *
 * The on-device model is the real path; this sends a decimated summary of both arms plus the per-arm
 * acceleration trace to Gemini and parses its JSON answer into the same record shape the local scorer
 * returns (`toSetResult`), so the UI cannot tell the two paths apart except through provenance.
 *
 * API surface: Gemini Interactions API, `POST /v1beta/interactions` with `x-goog-api-key`
 * (ai.google.dev/gemini-api/docs/thinking and /api-reference/interactions-api). The reply is
 * `{"steps":[{"type":"model_output","content":[{"type":"text","text":"..."}]}]}`.
 */
internal class GeminiScorer(
    private val apiKey: String,
    private val model: String = MODEL,
    private val thinkingLevel: String = THINKING_LEVEL,
    private val timeoutMs: Int = 120_000,
) {
    companion object {
        const val MODEL = "gemini-4-hydrogen"
        const val THINKING_LEVEL = "high"
        private const val ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
        /** Approximate rate of the timestamped samples selected for Gemini. */
        const val TRACE_HZ = 10.0
        /** Hard cap on trace length so one long set cannot blow the request size. */
        private const val MAX_TRACE_SECONDS = 300.0

        private val SYSTEM_PROMPT = """
            Score only the supplied Tally set. Locate every exercise attempt before grading any attempt.
            The trace contains aligned arrays at about 10 Hz. Each t_s[i] goes with the upper-arm and
            forearm xyz values at index i. Compare sustained changes against the nearby resting or
            turnaround posture. Axis signs, resting magnitudes and rep pace can vary.

            Count
            - Read the full trace in time order. One attempt has a directed change across successive
              samples, a turn or hold, and a return, reset or clear end. A partial or jerky movement
              counts when the trace still shows a distinct attempt. A reset can end at a new posture.
            - Count a hold and its return as part of one attempt. Start a new attempt only when there is
              a fresh directed movement after a reset. Skip isolated spikes, setup movements and
              shaking that alternates around a posture without an exercise-shaped excursion.
            - Review the gaps and the end of the trace for shorter or smaller attempts. Mark each
              interval with observed start and end timestamps. Keep intervals ordered and non-overlapping.

            Grade
            - Judge each interval on its own against set.intended_exercise when given. A fault needs
              evidence within that interval. Use cleaner attempts as references when available.
              Repeating the same movement does not establish good form.
            - "arm raise overhead": a broad upper-arm sweep, with the forearm following, then a
              controlled lowering. A clearly limited upper-arm sweep or forearm-led swing is a fault.
            - "elbow flexion": the forearm curls and returns with a relatively steady upper arm.
              Leading the motion with the upper arm or clearly cutting the range short is a fault.
            - "forearm squeeze": score visible squeeze-and-release motion. Grip force is unobservable.
            - Choose p_wrong from 0.1 (clear expected form), 0.3 (expected form more likely),
              0.5 (insufficient form evidence), 0.7 (fault more likely), 0.9 (clear form fault).
              Count an identifiable attempt even when its form score is uncertain.

            Output
            Return only schema-matching JSON. Number reps from 1. Set duration_s to end minus start
            and put the interval and a brief observed cue in reason. Set wrong to p_wrong >= 0.5
            and mean_p_wrong to the mean across reps. Use the exercise labels above verbatim.
            Use the intended label when identity is ambiguous. A clearly different exercise is a
            fault against the intended exercise. When motion is ambiguous, use notes for its time
            range and why it was counted or skipped. With no attempts, return reps: [], mean_p_wrong:
            0.5, and the reason in notes. If no exercise is identifiable and none was selected, use
            "arm raise overhead" as the required label and say in notes that it is a placeholder.

            Example decisions from synthetic motion summaries. Score only the separate input trace.

            A. Overhead target. 0.4–2.9 s: broad coordinated sweep and controlled return.
            3.7–4.6 s: a short upper-arm excursion and return, mostly forearm swing.
            5.2–6.8 s: back-and-forth shaking around one posture.
            {"exercise":"arm raise overhead","reps":[
              {"index":1,"exercise":"arm raise overhead","duration_s":2.5,"p_wrong":0.1,"wrong":false,"reason":"0.4–2.9 s: coordinated sweep and return."},
              {"index":2,"exercise":"arm raise overhead","duration_s":0.9,"p_wrong":0.9,"wrong":true,"reason":"3.7–4.6 s: short upper-arm sweep with forearm-led motion."}
            ],"mean_p_wrong":0.5,"notes":"5.2–6.8 s: shaking without a distinct attempt."}

            B. Elbow flexion target. A single spike, then a move to a new resting posture.
            No sustained curl or return.
            {"exercise":"elbow flexion","reps":[],"mean_p_wrong":0.5,"notes":"Transient spike and repositioning without a curl attempt."}
        """.trimIndent()

        /** Descriptions are what the model reads and writes; the codes stay inside the app. */
        const val ARM_RAISE = "arm raise overhead"
        const val ELBOW_FLEXION = "elbow flexion"
        const val FOREARM_SQUEEZE = "forearm squeeze"
        private val EXERCISE_DESCRIPTIONS = listOf(ARM_RAISE, ELBOW_FLEXION, FOREARM_SQUEEZE)
        private val CODE_BY_DESCRIPTION = mapOf(ARM_RAISE to "EAH", ELBOW_FLEXION to "EFE", FOREARM_SQUEEZE to "SQZ")

        /** Codes the fallback scorer accepts; the local scorer reports its own class list. */
        val exerciseCodes: List<String> = CODE_BY_DESCRIPTION.keys.toList()
        private val DESCRIPTION_BY_CODE = CODE_BY_DESCRIPTION.entries.associate { (k, v) -> v to k }

        /** Describes the exercise the user picked, or null when they did not pick one. */
        fun describeExercise(code: String?): String? = code?.let { DESCRIPTION_BY_CODE[it] ?: it }

        /** Maps whatever the model answered back onto the app's code, tolerating a bogus answer. */
        private fun codeOf(description: String?, fallback: String?): String? = when {
            description == null -> fallback
            CODE_BY_DESCRIPTION[description] != null -> CODE_BY_DESCRIPTION[description]
            DESCRIPTION_BY_CODE.containsKey(description) -> description
            else -> description
        }

        private fun schema(): JSONObject = JSONObject()
            .put("type", "object")
            .put("properties", JSONObject()
                .put("reps", JSONObject()
                    .put("type", "array")
                    .put("items", JSONObject()
                        .put("type", "object")
                        .put("properties", JSONObject()
                            .put("index", JSONObject().put("type", "integer"))
                            .put("wrong", JSONObject().put("type", "boolean"))
                            .put("p_wrong", JSONObject().put("type", "number"))
                            .put("exercise", JSONObject().put("type", "string")
                                .put("enum", JSONArray(EXERCISE_DESCRIPTIONS)))
                            .put("duration_s", JSONObject().put("type", "number"))
                            .put("reason", JSONObject().put("type", "string")))
                        .put("required", JSONArray(listOf("index", "wrong", "p_wrong", "exercise", "duration_s")))))
                .put("exercise", JSONObject().put("type", "string")
                    .put("enum", JSONArray(EXERCISE_DESCRIPTIONS)))
                .put("mean_p_wrong", JSONObject().put("type", "number"))
                .put("notes", JSONObject().put("type", "string")))
            .put("required", JSONArray(listOf("reps", "exercise", "mean_p_wrong")))

        /** Marks a record this path produced, so nothing downstream mistakes it for the on-device model. */
        const val PROVENANCE_KIND = "gemini-$MODEL-fallback"
    }

    /** Thrown when the call itself failed; the caller turns it into a failed set, never a scored one. */
    class GeminiError(message: String, val status: String = message) : IllegalStateException(message)

    fun score(side: String, store: SampleStore, intendedExercise: String?): JSONObject {
        val payload = buildPayload(side, store, intendedExercise)
        val body = requestBody(payload)
        val text = try {
            post(body)
        } catch (e: GeminiError) {
            GeminiCallStatus.report("Gemini failed: ${e.message?.take(120)}")
            throw e
        }
        val answer = runCatching { JSONObject(extractJson(text)) }
            .getOrElse {
                GeminiCallStatus.report("Gemini replied without usable JSON")
                throw GeminiError("Gemini answered with something that is not JSON: ${text.take(180)}")
            }
        val record = toRecord(answer, side, intendedExercise, payload)
        val reps = record.optJSONArray("repetitions")?.length() ?: 0
        GeminiCallStatus.report(if (reps > 0) "Gemini answered: $reps reps (streamed)" else "Gemini answered, no reps found")
        return record
    }

    private fun buildPayload(side: String, store: SampleStore, intendedExercise: String?): JSONObject {
        val n = store.size
        require(n >= 2) { "Nothing recorded" }
        val firstUs = store.timestampUs(0)
        val lastUs = store.timestampUs(n - 1)
        val durationS = (lastUs - firstUs) / 1_000_000.0

        // Fixed-rate trace: one row every 1/TRACE_HZ of recorded time, axes kept so direction survives.
        val t = ArrayList<Double>()
        val upX = ArrayList<Double>(); val upY = ArrayList<Double>(); val upZ = ArrayList<Double>()
        val foX = ArrayList<Double>(); val foY = ArrayList<Double>(); val foZ = ArrayList<Double>()
        val upperAll = DoubleArray(n)
        val foreAll = DoubleArray(n)
        val period = 1.0 / TRACE_HZ
        var nextAt = 0.0
        for (i in 0 until n) {
            val tS = (store.timestampUs(i) - firstUs) / 1_000_000.0
            upperAll[i] = magnitude(store, i, 0)
            foreAll[i] = magnitude(store, i, 3)
            if (tS + 1e-9 < nextAt) continue
            t.add(round(tS))
            upX.add(round(store.g(i, 0).toDouble())); upY.add(round(store.g(i, 1).toDouble())); upZ.add(round(store.g(i, 2).toDouble()))
            foX.add(round(store.g(i, 3).toDouble())); foY.add(round(store.g(i, 4).toDouble())); foZ.add(round(store.g(i, 5).toDouble()))
            nextAt += period
            if (tS >= MAX_TRACE_SECONDS) break
        }
        val rate = if (durationS > 0) (n - 1) / durationS else 0.0
        fun stats(v: DoubleArray) = JSONObject()
            .put("mean_g", round(v.average()))
            .put("min_g", round(v.min()))
            .put("max_g", round(v.max()))
            .put("sd_g", round(sd(v)))

        return JSONObject()
            .put("set", JSONObject()
                .put("side", side)
                .put("samples", n)
                .put("duration_s", round(durationS))
                .put("measured_rate_hz", round(rate))
                .put("intended_exercise", describeExercise(intendedExercise) ?: JSONObject.NULL))
            .put("arms", JSONObject().put("upper", stats(upperAll)).put("forearm", stats(foreAll)))
            .put("trace", JSONObject()
                .put("rate_hz", TRACE_HZ)
                .put("note", "t_s is seconds from the first sample; acceleration channels are in g, gravity included")
                .put("t_s", JSONArray(t))
                .put("upper_x_g", JSONArray(upX)).put("upper_y_g", JSONArray(upY)).put("upper_z_g", JSONArray(upZ))
                .put("forearm_x_g", JSONArray(foX)).put("forearm_y_g", JSONArray(foY)).put("forearm_z_g", JSONArray(foZ)))
    }

    private fun magnitude(store: SampleStore, i: Int, base: Int): Double {
        val x = store.g(i, base).toDouble()
        val y = store.g(i, base + 1).toDouble()
        val z = store.g(i, base + 2).toDouble()
        return sqrt(x * x + y * y + z * z)
    }

    private fun requestBody(payload: JSONObject): String = JSONObject()
        .put("model", model)
        .put("system_instruction", SYSTEM_PROMPT)
        .put("input", payload.toString())
        .put("stream", true)
        .put("generation_config", JSONObject().put("thinking_level", thinkingLevel))
        .put("response_format", JSONObject()
            .put("type", "text")
            .put("mime_type", "application/json")
            .put("schema", schema()))
        .toString()

    private fun post(body: String): String {
        val connection = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 20_000
            readTimeout = timeoutMs
            doOutput = true
            setRequestProperty("x-goog-api-key", apiKey)
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            if (code !in 200..299) {
                val error = connection.errorStream?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
                throw GeminiError("Gemini returned HTTP $code: ${error.take(300)}")
            }
            val reader = connection.inputStream.bufferedReader()
            val deltas = StringBuilder()
            var lastPayload: String? = null
            reader.useLines { lines ->
                for (line in lines) {
                    if (!line.startsWith("data:")) continue
                    val data = line.removePrefix("data:").trim()
                    if (data.isEmpty()) continue
                    if (data == "[DONE]") break
                    if (lastPayload == null || data.contains("\"steps\"")) lastPayload = data
                    val json = runCatching { JSONObject(data) }.getOrNull() ?: continue
                    collectDeltaText(json, deltas)
                }
            }
            // A streamed answer arrives as deltas; if the server sent only whole interactions, use that.
            if (deltas.isNotBlank()) {
                return JSONObject().put("output_text", deltas.toString()).toString()
            }
            return lastPayload ?: throw GeminiError("Gemini stream carried no content")
        } finally {
            connection.disconnect()
        }
    }

    /** Appends any `delta.content[].text` fragments a streaming event carries. */
    private fun collectDeltaText(obj: JSONObject, into: StringBuilder) {
        val delta = obj.optJSONObject("delta") ?: return
        val content = delta.optJSONArray("content") ?: delta.optJSONObject("content")?.let { JSONArray().put(it) }
        if (content == null) {
            delta.optString("text").takeIf { it.isNotEmpty() }?.let { into.append(it) }
            return
        }
        for (i in 0 until content.length()) {
            val part = content.optJSONObject(i) ?: continue
            if (part.optString("type").endsWith("text")) part.optString("text").takeIf { it.isNotEmpty() }?.let { into.append(it) }
        }
    }

    /** Pulls the model text out of the Interactions reply. */
    private fun extractJson(reply: String): String {
        val root = JSONObject(reply)
        root.optString("output_text").takeIf { it.isNotBlank() }?.let { return it }
        val steps = root.optJSONArray("steps") ?: JSONArray()
        for (i in 0 until steps.length()) {
            val step = steps.optJSONObject(i) ?: continue
            if (step.optString("type") != "model_output") continue
            val content = step.optJSONArray("content") ?: continue
            for (j in 0 until content.length()) {
                val part = content.optJSONObject(j) ?: continue
                if (part.optString("type") == "text" && part.optString("text").isNotBlank()) return part.getString("text")
            }
        }
        throw GeminiError("Gemini reply carried no model output text")
    }

    /** Same record shape [toSetResult] reads from the local scorer. */
    private fun toRecord(
        answer: JSONObject,
        side: String,
        intendedExercise: String?,
        payload: JSONObject,
    ): JSONObject {
        val reps = answer.optJSONArray("reps") ?: JSONArray()
        val exercise = codeOf(answer.optString("exercise").takeIf { it.isNotEmpty() }, null)
        val record = JSONObject()
        val repArray = JSONArray()
        var sum = 0.0
        var count = 0
        var anyWrong = false
        for (i in 0 until reps.length()) {
            val rep = reps.getJSONObject(i)
            val pWrong = rep.optDouble("p_wrong", 0.5).coerceIn(0.0, 1.0)
            val wrong = rep.optBoolean("wrong", pWrong >= 0.5) || pWrong >= 0.5
            if (wrong) anyWrong = true
            sum += pWrong
            count += 1
            repArray.put(JSONObject()
                .put("rep_index", rep.optInt("index", i + 1))
                .put("verdict", if (wrong) "wrong" else "correct")
                .put("p_wrong", round(pWrong))
                .put("exercise", codeOf(rep.optString("exercise").takeIf { it.isNotEmpty() }, exercise) ?: "unknown")
                .put("duration_s", round(rep.optDouble("duration_s", 0.0))))
        }
        val meanPWrong = if (answer.has("mean_p_wrong")) answer.optDouble("mean_p_wrong", 0.5)
            else if (count > 0) sum / count else Double.NaN
        val wrongExercise = intendedExercise != null && exercise != null && exercise != intendedExercise
        val verdict = when {
            count == 0 -> "correct".let { if (anyWrong) "wrong" else "unscored" }
            wrongExercise || anyWrong -> "wrong_exercise".takeIf { wrongExercise } ?: "wrong"
            else -> "correct"
        }
        val diagnostics = JSONArray()
            .put("scored_by=$PROVENANCE_KIND")
            .put("thinking_level=$thinkingLevel")
            .put("reps_from_model=${count}")
        answer.optString("notes").takeIf { it.isNotBlank() }?.let { diagnostics.put("model_notes=${it.take(200)}") }

        record.put("status", if (count == 0) "not_scored" else "scored")
        record.put("verdict", if (count == 0) JSONObject.NULL else verdict)
        record.put("mean_p_wrong", if (meanPWrong.isFinite()) round(meanPWrong) else JSONObject.NULL)
        record.put("exercise", exercise ?: JSONObject.NULL)
        record.put("repetitions", repArray)
        record.put("diagnostics", diagnostics)
        record.put("measured_rate_hz", payload.getJSONObject("set").optDouble("measured_rate_hz", 0.0))
        record.put("chart", chartOf(payload))
        if (intendedExercise != null) record.put("intended_exercise", intendedExercise)
        return record
    }

    /** The chart shown in the UI is the trace the model saw; rep spans are left empty on purpose. */
    private fun chartOf(payload: JSONObject): JSONObject {
        val trace = payload.getJSONObject("trace")
        val t = trace.getJSONArray("t_s")
        val ux = trace.getJSONArray("upper_x_g"); val uy = trace.getJSONArray("upper_y_g"); val uz = trace.getJSONArray("upper_z_g")
        val fx = trace.getJSONArray("forearm_x_g"); val fy = trace.getJSONArray("forearm_y_g"); val fz = trace.getJSONArray("forearm_z_g")
        val samples = JSONArray()
        for (i in 0 until t.length()) {
            val u = sqrt(ux.getDouble(i).let { it * it } + uy.getDouble(i).let { it * it } + uz.getDouble(i).let { it * it })
            val f = sqrt(fx.getDouble(i).let { it * it } + fy.getDouble(i).let { it * it } + fz.getDouble(i).let { it * it })
            samples.put(JSONObject()
                .put("time_s", t.getDouble(i))
                .put("upper_arm_g", u)
                .put("forearm_g", f))
        }
        return JSONObject().put("samples", samples).put("reps", JSONArray())
    }

    private fun sd(v: DoubleArray): Double {
        if (v.size < 2) return 0.0
        val m = v.average()
        var s = 0.0
        for (x in v) s += (x - m) * (x - m)
        return sqrt(s / v.size)
    }

    private fun round(x: Double): Double = Math.round(x * 1000.0) / 1000.0

}
