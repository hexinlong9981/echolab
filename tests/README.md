# tests/ — リポジトリ横断のテスト（Python）

| ファイル | 内容 |
|---|---|
| `test_golden_schema.py` | ゴールデンケースとドメインデータの形式を JSON Schema で検査。`verified: false` の値には出典が TODO であることを要求。各ツールに `derivation` が `reference` 以外（手計算・閉形式）のケースが最低 1 件あることを要求。`verified: true` の出典規則（ADR-0006）が効くことを、違反例と正常例で確認 |
| `test_golden_reference.py` | ゴールデンケースの期待値を Python の参照実装（`reference/calc_reference.py`）で再計算。Java の契約テストと合わせて、YAML・Java・Python の 3 者一致を保証 |
| `test_domain_manifest.py` | ドメインパックのマニフェスト（`domains/*/domain.yaml`）を `schemas/domain.schema.json` で検査。`name` とディレクトリ名の一致、`data_dir`・`golden_dir`・`prompts_dir` の存在、ゴールデンケースのツールがすべて `tools` に宣言されていること、ツール名の重複がないことを確認 |

今後（M2〜）、拒否の回帰テスト・一貫性チェック・「コアの差分ゼロ」チェックをここに足します。
