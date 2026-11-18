package com.tally.app.backend.calib

import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.sqrt

/**
 * On-arm calibration maths, ported from
 * tally-research/08-experiments/protocol/on_arm_redesign (MATH-REVIEW.md, MOTION-NOISE-ENVIRONMENT.md).
 *
 * Nothing here touches Android: it is pure so the JVM unit tests can run it.
 * Constants are the measured exercise-proxy envelope and the predeclared tolerances, never invented.
 */
internal object OnArmMath {

    /**
     * Stillness envelope from MOTION-NOISE-ENVIRONMENT.md §1: the largest detrended SD and the largest
     * fitted drift among the quietest selected windows of the four recordings, in millivolts.
     * These are UPPER BOUNDS on noise, not a certified stillness classifier.
     */
    const val SD_MAX_MV = 16.0
    const val DRIFT_MAX_MV = 16.0

    /** mV per g when no bench gains exist. A nominal calibration never licenses a g-based verdict. */
    const val MV_PER_G_NOMINAL = 330.0

    /** MATH-REVIEW.md §"Review of the improved candidate": radius must read 1 g; never pin r = 1. */
    const val RADIUS_TOL_G = 0.10

    /** MATH-REVIEW.md §anchor gate: anchors that are nearly parallel cannot define a frame. */
    const val MIN_ANCHOR_SEPARATION_DEG = 20.0

    /** Refusal wording, verbatim from LIMITS.md. */
    const val MSG_NOT_STEADY = "The readings were not steady. Rest your arm and repeat that hold."
    const val MSG_CAL_UNAVAILABLE =
        "Calibration is unavailable. The readings did not settle; this set cannot be scored."
    const val MSG_SENSOR_UNCERTAIN =
        "Sensor response is uncertain. Calibration is unavailable; this set cannot be scored."

    data class Stillness(val sdMv: Double, val driftMv: Double, val channel: Int) {
        val still: Boolean get() = sdMv <= SD_MAX_MV && driftMv <= DRIFT_MAX_MV
    }

    /**
     * Per-component detrended SD `s` and fitted drift `D = |beta| * (n - 1)` for one hold.
     * [samplesMv] is channel-major: 6 channels, each with the same sample count.
     * A ramp cannot disappear through detrending because [Stillness.driftMv] measures it directly.
     */
    fun stillness(samplesMv: Array<DoubleArray>): Stillness? {
        require(samplesMv.size == 6) { "six channels" }
        val n = samplesMv.first().size
        if (n < 3) return null
        var worstSd = 0.0
        var worstDrift = 0.0
        var worstCh = 0
        for (ch in 0 until 6) {
            val v = samplesMv[ch]
            val mean = v.average()
            val tMean = (n - 1) / 2.0
            var num = 0.0
            var den = 0.0
            for (i in 0 until n) {
                val t = i - tMean
                num += t * (v[i] - mean)
                den += t * t
            }
            val beta = num / den
            var ss = 0.0
            for (i in 0 until n) {
                val r = v[i] - mean - beta * (i - tMean)
                ss += r * r
            }
            val sd = sqrt(ss / n)
            val drift = abs(beta) * (n - 1)
            if (sd > worstSd || drift > worstDrift) {
                if (sd >= worstSd && drift >= worstDrift) worstCh = ch
            }
            if (sd > worstSd) worstSd = sd
            if (drift > worstDrift) worstDrift = drift
        }
        return Stillness(worstSd, worstDrift, worstCh)
    }

    data class Sphere(val center: DoubleArray, val radiusG: Double) {
        val radiusOk: Boolean get() = abs(radiusG - 1.0) <= RADIUS_TOL_G
    }

    /**
     * Free-radius sphere fit over corrected hold centres `d = S^-1 (v - a)`.
     *
     * MATH-REVIEW.md §sphere fit: linear least squares on rows `[2d_x, 2d_y, 2d_z, 1]` against `|d|^2`,
     * four affinely non-coplanar holds (rank 4) are the algebraic minimum, and the fitted radius is a
     * nuisance parameter that must then be checked against 1 g. Never re-fit with `r = 1` pinned.
     *
     * Returns null when the design is rank-deficient (coplanar or duplicated holds).
     */
    fun sphereFit(points: List<DoubleArray>): Sphere? {
        if (points.size < 4) return null
        val a = Array(4) { DoubleArray(4) }
        val b = DoubleArray(4)
        for (p in points) {
            require(p.size == 3)
            val row = doubleArrayOf(2 * p[0], 2 * p[1], 2 * p[2], 1.0)
            val rhs = p[0] * p[0] + p[1] * p[1] + p[2] * p[2]
            for (i in 0 until 4) {
                b[i] += row[i] * rhs
                for (j in 0 until 4) a[i][j] += row[i] * row[j]
            }
        }
        val solved = solve(a, b) ?: return null
        val c = doubleArrayOf(solved[0], solved[1], solved[2])
        val k = solved[3]
        val rSq = k + c[0] * c[0] + c[1] * c[1] + c[2] * c[2]
        if (!rSq.isFinite() || rSq <= 0.0) return null
        return Sphere(c, sqrt(rSq))
    }

    /** Rank-revealing Gaussian elimination with partial pivoting; null when singular. */
    fun solve(a0: Array<DoubleArray>, b0: DoubleArray): DoubleArray? {
        val n = b0.size
        val a = Array(n) { a0[it].copyOf() }
        val b = b0.copyOf()
        var scale = 0.0
        for (row in a) for (x in row) scale += abs(x)
        if (scale <= 0.0) return null
        val eps = 1e-12 * scale
        for (col in 0 until n) {
            var piv = col
            for (r in col until n) if (abs(a[r][col]) > abs(a[piv][col])) piv = r
            if (abs(a[piv][col]) <= eps) return null
            if (piv != col) {
                val t = a[piv]; a[piv] = a[col]; a[col] = t
                val tb = b[piv]; b[piv] = b[col]; b[col] = tb
            }
            for (r in col + 1 until n) {
                val f = a[r][col] / a[col][col]
                if (f == 0.0) continue
                for (cc in col until n) a[r][cc] -= f * a[col][cc]
                b[r] -= f * b[col]
            }
        }
        val x = DoubleArray(n)
        for (row in n - 1 downTo 0) {
            var s = b[row]
            for (col in row + 1 until n) s -= a[row][col] * x[col]
            x[row] = s / a[row][row]
        }
        return x
    }

    /**
     * Functional frame from two anchor holds (MATH-REVIEW.md §functional anchors):
     * `z = hang`, `x = forward orthogonalised against z`, `y = z x x`.
     * Invariant to the arbitrary board rotation, so the mounting angle drops out.
     * Returns null when the anchors are closer than [MIN_ANCHOR_SEPARATION_DEG] or degenerate.
     */
    fun functionalFrame(hang: DoubleArray, forward: DoubleArray): Array<DoubleArray>? {
        val z = unit(hang) ?: return null
        val f = unit(forward) ?: return null
        val dot = z[0] * f[0] + z[1] * f[1] + z[2] * f[2]
        val sepDeg = Math.toDegrees(acos(dot.coerceIn(-1.0, 1.0)))
        if (sepDeg < MIN_ANCHOR_SEPARATION_DEG || sepDeg > 180.0 - MIN_ANCHOR_SEPARATION_DEG) return null
        var x = doubleArrayOf(f[0] - dot * z[0], f[1] - dot * z[1], f[2] - dot * z[2])
        x = unit(x) ?: return null
        val y = doubleArrayOf(
            z[1] * x[2] - z[2] * x[1],
            z[2] * x[0] - z[0] * x[2],
            z[0] * x[1] - z[1] * x[0],
        )
        return arrayOf(x, y, z)
    }

    /** Gravity unit vector of a corrected hold in the sensor's own axes. */
    fun unit(v: DoubleArray): DoubleArray? {
        val n = sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
        if (!n.isFinite() || n <= 1e-9) return null
        return doubleArrayOf(v[0] / n, v[1] / n, v[2] / n)
    }

    /** `R^T g` for a frame built by [functionalFrame]; nine values, row-major. */
    fun toFrame(frame: Array<DoubleArray>, g: DoubleArray): DoubleArray =
        doubleArrayOf(
            frame[0][0] * g[0] + frame[0][1] * g[1] + frame[0][2] * g[2],
            frame[1][0] * g[0] + frame[1][1] * g[1] + frame[1][2] * g[2],
            frame[2][0] * g[0] + frame[2][1] * g[1] + frame[2][2] * g[2],
        )

    fun flatten(frame: Array<DoubleArray>): FloatArray =
        FloatArray(9) { i -> frame[i / 3][i % 3].toFloat() }

    fun unflatten(flat: FloatArray): Array<DoubleArray> =
        Array(3) { r -> DoubleArray(3) { c -> flat[r * 3 + c].toDouble() } }
}
