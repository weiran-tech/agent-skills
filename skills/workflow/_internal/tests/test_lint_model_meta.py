# ============================================================
# _internal/lint/model_meta.py 测试 — state-machine.yml v2 元数据一致性
# 覆盖：semantic_doc 放置 / action∈grammar / agent_role 单一来源 / skill.command
# ============================================================
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from _internal.lint.model_meta import (_gate_threshold_mismatch, _unlimited_enum_coverage,
                                       check_gate_threshold, check_model_meta)


class TestModelMeta(unittest.TestCase):
    def _model(self, **overrides):
        m = {
            "task_states": {"CODING": {"description": "x",
                                       "semantic_doc": "references/stages/stage-4.0-dev.md"}},
            "milestone": {"phase_values": {"DISCUSSING": {"description": "x",
                                                          "semantic_doc": "references/stages/stage-1-discuss.md"}}},
            "action_grammar": {"ENTER_CODING": {"agent_role": "main"}},
            "transitions": [
                {"id": "t1", "scope": "task", "from": "CODING", "event": "X",
                 "action": "ENTER_CODING"},
            ],
        }
        for k, v in overrides.items():
            m[k] = v
        return m

    def test_current_model_meta_passes(self):
        # 当前 model/ 真实文件必须通过元数据校验（含 skill.command 一致性）
        self.assertEqual(check_model_meta(), [])

    def test_valid_minimal_model_passes(self):
        self.assertEqual(check_model_meta(self._model()), [])

    def test_transition_missing_action_detected(self):
        m = self._model()
        m["transitions"][0] = {"id": "t1", "scope": "task", "from": "CODING", "event": "X"}
        v = check_model_meta(m)
        self.assertTrue(any("缺 action" in x for x in v))

    def test_action_not_in_grammar_detected(self):
        m = self._model()
        m["transitions"][0]["action"] = "NOPE"
        v = check_model_meta(m)
        self.assertTrue(any("不在 action_grammar" in x for x in v))

    def test_state_missing_semantic_doc_detected(self):
        m = self._model()
        m["task_states"]["CODING"] = "旧字符串"
        v = check_model_meta(m)
        self.assertTrue(any("缺 semantic_doc" in x for x in v))

    def test_transition_with_semantic_doc_detected(self):
        m = self._model()
        m["transitions"][0]["semantic_doc"] = "references/stages/stage-4.0-dev.md"
        v = check_model_meta(m)
        self.assertTrue(any("挂了 semantic_doc" in x for x in v))

    def test_grammar_agent_role_not_in_valid_set_detected(self):
        # agent_role 单一来源在 action_grammar：非法角色必须被拦
        m = self._model()
        m["action_grammar"]["ENTER_CODING"]["agent_role"] = "ghost-agent"
        v = check_model_meta(m)
        self.assertTrue(any("不在" in x and "agent_role" in x for x in v))

    def test_transition_repeating_agent_role_detected(self):
        # transition 不重复 agent_role（单一来源在 grammar），挂了必须被拦
        m = self._model()
        m["transitions"][0]["agent_role"] = "main"
        v = check_model_meta(m)
        self.assertTrue(any("挂了 agent_role" in x for x in v))

    def test_invariants_section_reappearance_detected(self):
        # 不变量唯一来源 engine/invariants.py；state-machine.yml 重现 invariants 段必须被拦（防双重来源漂移回归）
        m = self._model()
        m["invariants"] = {"single_pending_gate": {"description": "x"}}
        v = check_model_meta(m)
        self.assertTrue(any("invariants" in x for x in v))

    def test_agent_roles_section_reappearance_detected(self):
        # agent 角色唯一来源 agent-contracts.yml#agents.id；重现 agent_roles 段必须被拦
        m = self._model()
        m["agent_roles"] = {"main": "x"}
        v = check_model_meta(m)
        self.assertTrue(any("agent_roles" in x for x in v))


class TestGateThreshold(unittest.TestCase):
    """SIMPLE Gate 文件数阈值一致性：schema 硬上限必须 ≥ policy（单一数据源）最大值。"""

    def test_schema_equal_policy_passes(self):
        self.assertIsNone(_gate_threshold_mismatch({"CODE": 2, "DOCS_ONLY": 6, "TESTS_ONLY": 6}, 6))

    def test_schema_above_policy_passes(self):
        # schema 是宽松结构上限，高于 policy 阈值是合法状态
        self.assertIsNone(_gate_threshold_mismatch({"DOCS_ONLY": 6}, 20))

    def test_schema_below_policy_detected(self):
        # 改 policy 到 8 但忘同步 schema=6 → 必须被 lint 拦下（防静默打架）
        msg = _gate_threshold_mismatch({"CODE": 2, "DOCS_ONLY": 8, "TESTS_ONLY": 6}, 6)
        self.assertIsNotNone(msg)
        self.assertIn("SIMPLE Gate 文件数阈值失配", msg)

    def test_schema_missing_maximum_detected(self):
        self.assertIsNotNone(_gate_threshold_mismatch({"CODE": 2, "DOCS_ONLY": 6}, None))

    def test_empty_max_files_passes(self):
        self.assertIsNone(_gate_threshold_mismatch({}, 6))

    def test_unlimited_ignored_in_threshold_compare(self):
        # unlimited 类型不限文件数，不参与 schema 上限比较；仅有限阈值（CODE=2）校验
        self.assertIsNone(_gate_threshold_mismatch(
            {"CODE": 2, "DOCS_ONLY": "unlimited", "TESTS_ONLY": "unlimited", "TESTS_DOCS": "unlimited"}, 200))
        # 有限阈值超 schema 上限仍必须拦下（CODE=250 > 200）
        msg = _gate_threshold_mismatch({"CODE": 250, "DOCS_ONLY": "unlimited"}, 200)
        self.assertIsNotNone(msg)
        self.assertIn("SIMPLE Gate 文件数阈值失配", msg)

    def test_unlimited_kind_missing_from_enum_detected(self):
        # max_files 标 unlimited 的类型必须同步进 schema change_kind 枚举
        msg = _unlimited_enum_coverage({"CODE": 2, "DOCS_ONLY": "unlimited", "FANCY": "unlimited"}, ["CODE", "DOCS_ONLY"])
        self.assertIsNotNone(msg)
        self.assertIn("FANCY", msg)

    def test_enum_kind_missing_threshold_detected(self):
        # 枚举类型必须在 max_files 登记阈值（防新增类型漏配阈值导致静默无限）
        msg = _unlimited_enum_coverage({"CODE": 2, "DOCS_ONLY": "unlimited"}, ["CODE", "DOCS_ONLY", "TESTS_DOCS"])
        self.assertIsNotNone(msg)
        self.assertIn("TESTS_DOCS", msg)

    def test_unlimited_coverage_consistent(self):
        self.assertIsNone(_unlimited_enum_coverage(
            {"CODE": 2, "DOCS_ONLY": "unlimited", "TESTS_ONLY": "unlimited", "TESTS_DOCS": "unlimited"},
            ["CODE", "DOCS_ONLY", "TESTS_ONLY", "TESTS_DOCS"]))

    def test_current_model_consistent(self):
        # 当前真实 model 必须通过阈值一致性校验（有限阈值 ≤ schema 上限，unlimited 类型入枚举）
        self.assertEqual(check_gate_threshold(), [])


if __name__ == "__main__":
    unittest.main()
