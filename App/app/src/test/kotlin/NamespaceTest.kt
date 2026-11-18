package com.tally.app

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class NamespaceTest {
    @Test fun appIdentityAndAllSourcePackagesUseTheRequestedNamespace() {
        val build = File("build.gradle.kts").readText()
        assertTrue(build.contains("namespace = \"com.tally.app\""))
        assertTrue(build.contains("applicationId = \"com.tally.app\""))
        for (module in listOf("app", "backend", "contract")) {
            val source = File("../$module/src")
            source.walkTopDown().filter { it.extension == "kt" }.forEach {
                val declaration = it.readLines().first { line -> line.startsWith("package ") }
                assertTrue("Unexpected package in $it", declaration == "package com.tally.app" ||
                    declaration.startsWith("package com.tally.app."))
            }
        }
        assertFalse(File("src/main/kotlin/com/jeevan").exists())
    }
}
