# calc-engine — 計算サービス（Java 21）

鳴潮ドメインの決定的な計算を担当します。**LLM はここで計算した値だけを回答に使います**（ADR-0001）。

## M1 の範囲

| パッケージ | 内容 |
|---|---|
| `domain` | `record` と `sealed interface` によるモデル（詞条・声骸・ステータス）。精度方針は `Precision` に集約（`BigDecimal`・DECIMAL64） |
| `damage` | 期待ダメージ。乗区ごとの値を明細として返す（回答の数値トレースに使う） |
| `echo` | 声骸サブ詞条の重み付きスコア。`switch` による sealed 型の網羅 |
| `gacha` | 天井モデル。厳密解（マルコフ連鎖）とモンテカルロ法（逐次・parallel stream・仮想スレッド） |
| `golden` | ゴールデンケース（`domains/wuwa/golden/*.yaml`）の読み込み |

**Spring と MCP の公開は M2 で追加します**（ADR-0004）。M1 は依存の少ない純粋なライブラリとして作り、計算の正しさを先に固めます。

## テスト

| 種類 | 内容 |
|---|---|
| 単体テスト（JUnit 5） | 境界値・入力検証 |
| 性質テスト（jqwik） | 確率が [0, 1]・回数に対して単調・ハード天井で必ず最高レア・攻撃力に対して単調 など |
| 契約テスト | `domains/wuwa/golden/*.yaml` を全件照合。同じファイルを Python の参照実装でも照合している |
| アーキテクチャ（ArchUnit） | `domain` が計算パッケージに依存しない・循環依存がない |
| 一致性 | モンテカルロ法の 3 方式が同じ seed で完全一致・厳密解と誤差内で一致 |

品質ゲート: Spotless（google-java-format）、Error Prone（警告はエラー扱い）、JaCoCo（行カバレッジ 90% 未満で失敗）。

## 実行

ホストに JDK を入れずに Docker で実行できます。

```bash
cd services/calc-engine
docker run --rm -u "$(id -u):$(id -g)" -e GRADLE_USER_HOME=/cache \
  -v "$HOME/.gradle-echolab:/cache" -v "$(cd ../.. && pwd):/w" -w /w/services/calc-engine \
  gradle:8-jdk21 ./gradlew check        # テスト・整形・静的解析・カバレッジ
# ベンチマーク（3 方式の速度比較）
#   ... gradle:8-jdk21 ./gradlew jmh
```

JDK 21 が手元にあれば `./gradlew check` だけで動きます。

## 既知の制約

- `domains/wuwa/data/v2.x` の数値は**未確認のサンプル**です（`verified: false`）。計算式は汎用モデルで、実際のゲームの式・定数は確認してから与えてください。
- 防御・耐性の乗区は汎用モデルです。ゲームによって式が異なる場合は、乗区の関数を差し替えます（各乗区を独立した関数にしてあるのはこのためです）。
