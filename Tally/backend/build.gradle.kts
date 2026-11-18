import java.security.MessageDigest

plugins {
    id("com.android.library")
    id("com.chaquo.python")
}

val scripts = listOf("stdlib_runtime.py", "tally_stdlib.py")
val copyPython by tasks.registering(Sync::class) {
    from(rootProject.file("reference/scripts")) { include(scripts) }
    into(layout.buildDirectory.dir("generated/python"))
}
val copyModels by tasks.registering(Sync::class) {
    from(rootProject.file("reference/model"))
    into(layout.buildDirectory.dir("generated/assets/model"))
}
val scorerHash = MessageDigest.getInstance("SHA-256").run {
    scripts.forEach { update(rootProject.file("reference/scripts/$it").readBytes()) }
    digest().joinToString("") { "%02x".format(it) }
}
copyPython {
    doLast {
        layout.buildDirectory.file("generated/python/_scorer_build.py").get().asFile
            .writeText("SHA256 = '$scorerHash'\n")
    }
}
val gitRev = providers.exec {
    commandLine("git", "rev-parse", "HEAD")
}.standardOutput.asText.get().trim()

android {
    namespace = "com.tally.app.backend"
    compileSdk = 37
    defaultConfig {
        minSdk = 29
        ndk { abiFilters += "arm64-v8a" }
        buildConfigField("String", "SCORER_SHA256", "\"$scorerHash\"")
        buildConfigField("String", "GIT_REV", "\"$gitRev\"")
        buildConfigField("String", "APP_VERSION", "\"1.0\"")
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
    sourceSets.getByName("main").assets.srcDir(file("build/generated/assets"))  // static path: AGP 9 rejects Providers here
}
chaquopy {
    defaultConfig { version = "3.14" }
    sourceSets.getByName("main").srcDir(layout.buildDirectory.dir("generated/python"))
}
tasks.configureEach {
    if (name == "preBuild") dependsOn(copyPython, copyModels)
    if ((name.startsWith("generate") || name.startsWith("merge")) && name.contains("Python")) dependsOn(copyPython)
    if (name.startsWith("merge") && name.endsWith("Assets")) dependsOn(copyModels)
}
dependencies {
    implementation(project(":contract"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    testImplementation("junit:junit:4.13.2")
    // org.json is part of Android, so JVM unit tests see a stub that throws. The real implementation
    // makes the JSON round-trip tests run on the JVM instead of being silently unmocked.
    testImplementation("org.json:json:20240303")
}
