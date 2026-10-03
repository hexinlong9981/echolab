import net.ltgt.gradle.errorprone.errorprone

plugins {
    java
    jacoco
    id("com.diffplug.spotless") version "7.0.4"
    id("net.ltgt.errorprone") version "4.1.0"
    id("me.champeau.jmh") version "0.7.3"
}

group = "dev.echolab"
version = "0.1.0-SNAPSHOT"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

repositories {
    mavenCentral()
}

val junitVersion = "5.11.4"

dependencies {
    implementation("com.fasterxml.jackson.dataformat:jackson-dataformat-yaml:2.18.3")

    errorprone("com.google.errorprone:error_prone_core:2.36.0")

    testImplementation(platform("org.junit:junit-bom:$junitVersion"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("net.jqwik:jqwik:1.9.2")
    testImplementation("com.tngtech.archunit:archunit-junit5:1.4.0")
    testImplementation("org.assertj:assertj-core:3.27.3")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.release = 21
    options.compilerArgs.addAll(listOf("-Xlint:all", "-Werror", "-parameters"))
    options.errorprone {
        // JMH が生成するコードは対象外にする
        excludedPaths = ".*/build/generated/.*"
    }
}

// ゴールデンケースはリポジトリ直下の domains/ にあり、Java と Python で共用する
val goldenDir = layout.projectDirectory.dir("../../domains/wuwa/golden")

tasks.test {
    useJUnitPlatform {
        includeEngines("junit-jupiter", "jqwik", "archunit")
    }
    systemProperty("golden.dir", goldenDir.asFile.absolutePath)
    inputs.dir(goldenDir).withPropertyName("goldenCases").withPathSensitivity(PathSensitivity.RELATIVE)
    finalizedBy(tasks.jacocoTestReport)
}

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    reports {
        xml.required = true
        html.required = true
    }
}

tasks.jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                counter = "LINE"
                minimum = "0.90".toBigDecimal()
            }
        }
    }
}

tasks.check {
    dependsOn(tasks.jacocoTestCoverageVerification)
}

spotless {
    java {
        target("src/**/*.java")
        googleJavaFormat("1.25.2")
        removeUnusedImports()
        trimTrailingWhitespace()
        endWithNewline()
    }
    kotlinGradle {
        target("*.gradle.kts")
        trimTrailingWhitespace()
        endWithNewline()
    }
}

jmh {
    warmupIterations = 1
    iterations = 2
    fork = 1
}
