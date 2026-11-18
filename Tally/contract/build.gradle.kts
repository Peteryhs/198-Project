plugins {
    `java-library`
    id("org.jetbrains.kotlin.jvm")
}
kotlin { jvmToolchain(21) }
dependencies {
    api("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    testImplementation("junit:junit:4.13.2")
}
