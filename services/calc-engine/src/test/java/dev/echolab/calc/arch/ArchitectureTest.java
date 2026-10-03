package dev.echolab.calc.arch;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

/** 層の依存関係をテストで守る。 */
@AnalyzeClasses(packages = "dev.echolab.calc", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

  /** domain は他の計算パッケージに依存しない（モデルが計算方法を知らない）。 */
  @ArchTest
  static final ArchRule domainDependsOnNothingElse =
      noClasses()
          .that()
          .resideInAPackage("..calc.domain..")
          .should()
          .dependOnClassesThat()
          .resideInAnyPackage(
              "..calc.damage..", "..calc.echo..", "..calc.gacha..", "..calc.golden..");

  /** 計算ロジックはゴールデンケースの読み込み（テスト基盤）に依存しない。 */
  @ArchTest
  static final ArchRule calculatorsDoNotDependOnGolden =
      noClasses()
          .that()
          .resideInAnyPackage("..calc.damage..", "..calc.echo..", "..calc.gacha..")
          .should()
          .dependOnClassesThat()
          .resideInAPackage("..calc.golden..");

  /** 計算パッケージはフレームワークに依存しない（ADR-0004）。Spring と MCP の SDK は公開層（{@code dev.echolab.app}）だけが使う。 */
  @ArchTest
  static final ArchRule calcDoesNotDependOnFrameworks =
      noClasses()
          .that()
          .resideInAPackage("dev.echolab.calc..")
          .should()
          .dependOnClassesThat()
          .resideInAnyPackage("org.springframework..", "io.modelcontextprotocol..");

  /** 計算パッケージは公開層に依存しない（依存の向きは app → calc の一方向）。 */
  @ArchTest
  static final ArchRule calcDoesNotDependOnApp =
      noClasses()
          .that()
          .resideInAPackage("dev.echolab.calc..")
          .should()
          .dependOnClassesThat()
          .resideInAPackage("dev.echolab.app..");

  /** パッケージ間に循環依存がない。 */
  @ArchTest
  static final ArchRule noCycles =
      slices().matching("dev.echolab.calc.(*)..").should().beFreeOfCycles();
}
