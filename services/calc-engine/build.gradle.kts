import net.ltgt.gradle.errorprone.errorprone

plugins {
    java
    jacoco
    id("com.diffplug.spotless") version "7.0.4"
    id("net.ltgt.errorprone") version "4.1.0"
    id("me.champeau.jmh") version "0.7.3"
    // MCP サーバ層（dev.echolab.app）の実行用 jar を作る。依存の版は下の BOM で揃える（ADR-0004・ADR-0008）
    id("org.springframework.boot") version "4.1.1"
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

// Spring AI 2.0.1 は Spring Boot 4.1.1 を前提にしている（spring-ai-starter-mcp-server 2.0.1 の POM）
val springBootVersion = "4.1.1"
val springAiVersion = "2.0.1"

dependencies {
    implementation("com.fasterxml.jackson.dataformat:jackson-dataformat-yaml:2.18.3")

    // MCP サーバ層（dev.echolab.app）だけが使う。計算パッケージ（dev.echolab.calc）からの依存は ArchUnit で禁止している
    implementation(platform("org.springframework.boot:spring-boot-dependencies:$springBootVersion"))
    implementation(platform("org.springframework.ai:spring-ai-bom:$springAiVersion"))
    implementation("org.springframework.ai:spring-ai-starter-mcp-server")

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
val domainDir = layout.projectDirectory.dir("../../domains/wuwa")
val goldenDir = domainDir.dir("golden")

tasks.test {
    useJUnitPlatform {
        includeEngines("junit-jupiter", "jqwik", "archunit")
    }
    systemProperty("golden.dir", goldenDir.asFile.absolutePath)
    inputs.dir(goldenDir).withPropertyName("goldenCases").withPathSensitivity(PathSensitivity.RELATIVE)
    // MCP 層のテストは domain.yaml とデータ（banner・profile の参照先）も読む
    inputs.file(domainDir.file("domain.yaml")).withPropertyName("domainManifest").withPathSensitivity(PathSensitivity.RELATIVE)
    inputs.dir(domainDir.dir("data")).withPropertyName("domainData").withPathSensitivity(PathSensitivity.RELATIVE)
    finalizedBy(tasks.jacocoTestReport)
}

// Spring Boot の起動クラス（main で SpringApplication.run を呼ぶだけ）はカバレッジの対象外にする。
// 実行すると標準入出力を MCP の通信に使うサーバが立ち上がるため単体テストでは起動せず、
// jar を stdio で起動する端から端までの試験（Python の mcp SDK）で確かめる。
val coverageExcludes = listOf("dev/echolab/app/McpServerApplication.class")

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    classDirectories.setFrom(sourceSets.main.get().output.asFileTree.matching { exclude(coverageExcludes) })
    reports {
        xml.required = true
        html.required = true
    }
}

tasks.jacocoTestCoverageVerification {
    classDirectories.setFrom(sourceSets.main.get().output.asFileTree.matching { exclude(coverageExcludes) })
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

// MCP サーバとして起動する jar。名前は config/services.yaml から参照している
tasks.bootJar {
    archiveFileName = "calc-engine-mcp.jar"
}

// ライブラリとしての jar（Spring Boot の依存を含まない通常の jar）も残す。
// Spring Boot プラグインは既定で "-plain" を付けるので、通常の名前に戻す
tasks.jar {
    archiveClassifier = ""
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
