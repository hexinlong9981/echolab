package dev.echolab.app;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

/** 公開層（dev.echolab.app）の依存関係。 */
@AnalyzeClasses(packages = "dev.echolab", importOptions = ImportOption.DoNotIncludeTests.class)
class AppArchitectureTest {

  /** ツールの中身（tool・data）は Spring にも MCP の SDK にも依存しない（単体で試験できるように）。 */
  @ArchTest
  static final ArchRule toolHandlersAreFrameworkFree =
      noClasses()
          .that()
          .resideInAnyPackage("dev.echolab.app.tool..", "dev.echolab.app.data..")
          .should()
          .dependOnClassesThat()
          .resideInAnyPackage("org.springframework..", "io.modelcontextprotocol..");

  /** 公開層はゴールデンケースの読み込み（テスト基盤）を使わない。 */
  @ArchTest
  static final ArchRule appDoesNotUseGoldenLoader =
      noClasses()
          .that()
          .resideInAPackage("dev.echolab.app..")
          .should()
          .dependOnClassesThat()
          .resideInAPackage("dev.echolab.calc.golden..");

  /** dev.echolab 全体でパッケージ間に循環依存がない。 */
  @ArchTest
  static final ArchRule noCycles = slices().matching("dev.echolab.(**)").should().beFreeOfCycles();
}
