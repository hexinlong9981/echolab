"""端から端までの試験：実物の calc-engine（MCP サーバの jar）を
``config/services.yaml`` のとおりに起動する。

- ゴールデンケースを MCP 経由で全件照合する
  （Java の単体試験・Python の参照実装に続く 3 つ目の照合）。
- データ参照（バナー・重みのプロファイル）は未確認データとして伝わり、回答に注記が付く（ADR-0006）。
- 台本の LLM で、Agent の往復を実物の計算サービスの上で通す。

jar（``./gradlew bootJar``）と ``java`` が無ければ飛ばす。``pytest -m e2e`` で実行する。
"""

from __future__ import annotations

import asyncio
import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.agent import Agent, load_system_prompt
from core.agent.llm import ScriptedLLM
from core.contracts import UNVERIFIED_NOTE, to_wire_name
from core.gateway import Budget, Gateway
from core.gateway.mcp_backend import resolve_executable
from core.verifier import verify

ROOT = Path(__file__).resolve().parents[2]
JAR = ROOT / "services/calc-engine/build/libs/calc-engine-mcp.jar"

#: CI では jar を作ってから実行するので、無ければ飛ばさずに失敗させる（見逃さないため）。
REQUIRED = os.environ.get("ECHOLAB_E2E_REQUIRED") == "1"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not REQUIRED and not JAR.is_file(), reason=f"jar がありません: {JAR}"),
    # 起動時と同じ規則（PATH、無ければ JAVA_HOME）で java を探す
    pytest.mark.skipif(
        not REQUIRED and shutil.which(resolve_executable("java", os.environ)) is None,
        reason="java が見つかりません（PATH か JAVA_HOME を設定してください）",
    ),
]


#: 1 回の往復（JVM の起動後）にかけてよい時間（秒）。
CALL_TIMEOUT_S = 60


def golden_cases() -> list[tuple[str, dict]]:
    cases = []
    for path in sorted((ROOT / "domains/wuwa/golden").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases += [(doc["tool"], case) for case in doc["cases"]]
    return cases


def make_budget(tmp_path: Path) -> Budget:
    return Budget(tmp_path / "costs.jsonl", Decimal("1"), Decimal("10"))


async def open_real_gateway(tmp_path: Path) -> Gateway:
    return await Gateway.open(ROOT, "wuwa", budget=make_budget(tmp_path))


async def test_golden_cases_through_mcp(tmp_path: Path) -> None:
    cases = golden_cases()
    assert len(cases) >= 10
    async with await open_real_gateway(tmp_path) as gw:
        names = {t.name for t in gw.tool_specs()}
        assert {"damage_expected", "echo_score", "gacha_probability_within"} <= names
        for tool, case in cases:
            outcome = await gw.call(to_wire_name(tool), case["input"])
            assert outcome.error is None, (case["id"], outcome.error)
            assert outcome.tool == tool
            actual = {s.source_id.split(".", 1)[1]: s for s in outcome.sources}
            for field, expected in case["expected"].items():
                assert float(actual[field].value) == pytest.approx(
                    expected, abs=case["tolerance"]
                ), (case["id"], field)
                # ゴールデンケースの入力は明示した値だけなので、未確認データは使わない
                assert actual[field].unverified_inputs == (), case["id"]


async def test_parallel_calls_right_after_start(tmp_path: Path) -> None:
    """起動直後に並列で呼んでも、両方の結果が返る（Agent は tool_use を並列に実行する）。"""
    _, case_a = golden_cases()[0]
    _, case_b = golden_cases()[1]
    async with await open_real_gateway(tmp_path) as gw:
        outcomes = await asyncio.wait_for(
            asyncio.gather(
                gw.call("damage_expected", case_a["input"]),
                gw.call("damage_expected", case_b["input"]),
            ),
            CALL_TIMEOUT_S,
        )
    assert [o.error for o in outcomes] == [None, None]
    assert [o.call_id for o in outcomes] == ["c1", "c2"]


async def test_invalid_input_is_an_error_result(tmp_path: Path) -> None:
    async with await open_real_gateway(tmp_path) as gw:
        outcome = await gw.call("damage_expected", {"atk": 2000})
        assert outcome.error is not None and outcome.sources == ()


async def test_data_references_are_marked_unverified_and_noted(tmp_path: Path) -> None:
    async with await open_real_gateway(tmp_path) as gw:
        gacha = await gw.call(
            "gacha_probability_within",
            {"banner": "featured-character", "start_pity": 0, "guaranteed": False, "pulls": 80},
        )
        assert gacha.error is None, gacha.error
        [prob] = gacha.sources
        assert prob.unverified_inputs and any(
            "featured-character" in u for u in prob.unverified_inputs
        )
        # 同じ規則を直接与えたゴールデンケース（gacha-004）と同じ値
        assert float(prob.value) == pytest.approx(0.6058637851964593, abs=1e-9)

        echo = await gw.call(
            "echo_score",
            {
                "echo": {
                    "name": "sample-echo-a",
                    "cost": 4,
                    "main": {"stat": "CRIT_RATE", "value": 0.22},
                    "subs": [
                        {"stat": "CRIT_RATE", "value": 0.08},
                        {"stat": "CRIT_DMG", "value": 0.16},
                    ],
                },
                "profile": "sample-crit-attacker",
            },
        )
        assert echo.error is None, echo.error
        assert all(s.unverified_inputs for s in echo.sources)

        question = "80 回以内に限定キャラクターを獲得できる確率は？"
        verdict = verify(f"確率は [[{prob.source_id}|%1]] です。", question, gw.sources)
        assert verdict.ok, verdict.problems
        assert verdict.rendered is not None
        assert verdict.rendered.startswith("確率は 60.6% です。")
        assert UNVERIFIED_NOTE in verdict.rendered


async def test_scripted_agent_over_real_service(tmp_path: Path) -> None:
    llm = ScriptedLLM.from_file(ROOT / "core/agent/examples/compare_builds.yaml")
    question = (
        "ビルド A（攻撃力 2000、スキル倍率 2.5、ダメージバフ 0.3、会心率 0.6、会心ダメージ 2.2、"
        "敵の防御 1000、耐性ダウンなし）とビルド B（攻撃力 1800、スキル倍率 3.0、ダメージバフ 0.2、"
        "会心率 0.5、会心ダメージ 2.5、敵の防御 1200、耐性ダウン 0.3）では、どちらがどれだけ強い？"
        "どちらも防御定数 1600、防御無視 0、敵の耐性 0.1。"
    )
    async with await open_real_gateway(tmp_path) as gw:
        agent = Agent(
            gateway=gw,
            llm=llm,
            system_prompt=load_system_prompt(ROOT, "wuwa"),
            trace_dir=tmp_path / "traces",
            domain="wuwa",
        )
        # 計算サービスが応答しないときに CI を止めないよう、上限の時間を置く
        result = await asyncio.wait_for(agent.ask(question), CALL_TIMEOUT_S)
    assert result.status == "answered", result.problems
    assert result.drafts_rejected == 1
    assert llm.remaining == 0
    assert "ビルド A の期待ダメージ: 6,192" in result.answer
    assert "ビルド B の期待ダメージ: 7,128" in result.answer
    assert "差: 936（A に比べて 15.1% 増加）" in result.answer
    assert UNVERIFIED_NOTE not in result.answer
    assert [s.tool for s in result.cited] == [
        "damage.expected",
        "damage.expected",
        "compare.diff",
        "compare.ratio",
    ]
