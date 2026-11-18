package com.tally.app

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

class SeamTest {
    @Test fun appImportsOnlyTheBackendFactory() {
        val forbidden = File("src/main").walkTopDown().filter { it.extension == "kt" }.flatMap { file ->
            file.readLines().asSequence().filter {
                it.trim().startsWith("import com.tally.app.backend.") &&
                    it.trim() != "import com.tally.app.backend.TallyBackendFactory"
            }
        }.toList()
        assertTrue("Forbidden backend imports: $forbidden", forbidden.isEmpty())
    }
}
