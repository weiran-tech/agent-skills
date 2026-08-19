# ============================================================
# engine/vocab.py 测试 — 词汇枚举从 model 派生 + str 兼容
# 覆盖：事件/状态/阶段/门/决策/profile 完整覆盖 model；成员 == 字符串；
#       .value 是纯字符串（存储边界用，避免 yaml 序列化枚举对象）
# ============================================================
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine import policy, state_machine as sm, vocab


class TestVocabDerived(unittest.TestCase):
    def test_event_covers_model_events(self):
        model = sm.load_model()
        names = {e.value for e in vocab.Event}
        self.assertEqual(names, set(model["events"].keys()))

    def test_state_covers_model_states(self):
        model = sm.load_model()
        names = {s.value for s in vocab.State}
        self.assertEqual(names, set(model["task_states"].keys()))

    def test_phase_and_lifecycle(self):
        model = sm.load_model()
        self.assertEqual({p.value for p in vocab.Phase}, set(model["milestone"]["phase_values"].keys()))
        self.assertEqual({l.value for l in vocab.Lifecycle}, set(model["milestone"]["lifecycle_values"].keys()))
        self.assertEqual({g.value for g in vocab.Gate}, set(model["milestone"]["gate_types"]))

    def test_decision_covers_matrix_implicit_transitions(self):
        pol = policy.load_policy()
        expected = set()
        for rules in pol["decisions"].values():
            expected |= {r["decision"] for r in rules}
        expected |= set(pol.get("implicit_decisions", {}).values())
        model = sm.load_model()
        for t in model["transitions"]:
            if t.get("decision"):
                expected.add(t["decision"])
        self.assertEqual({d.value for d in vocab.Decision}, expected)


class TestVocabStrCompat(unittest.TestCase):
    def test_member_equals_str(self):
        self.assertEqual(vocab.Event.TASK_STARTED, "TASK_STARTED")
        self.assertEqual(vocab.State.CR_JUDGED, "CR_JUDGED")
        self.assertEqual(vocab.Decision.FIX_CR_ISSUES, "FIX_CR_ISSUES")
        self.assertEqual(vocab.Phase.DEVELOPING, "DEVELOPING")
        self.assertEqual(vocab.Complexity.COMPLEX, "COMPLEX")
        self.assertEqual(vocab.GateResult.PASS, "PASS")

    def test_disposition_three_tiers(self):
        self.assertEqual(vocab.Disposition.IMPLEMENT_FIX, "IMPLEMENT_FIX")
        self.assertEqual(vocab.Disposition.BASELINE_ALIGN, "BASELINE_ALIGN")
        self.assertEqual(vocab.Disposition.DESIGN_REWORK, "DESIGN_REWORK")

    def test_value_is_plain_str_for_storage(self):
        # 存储边界用 .value，避免 yaml.safe_dump 无法表示枚举对象
        for member in (vocab.Event.TASK_STARTED, vocab.Phase.DISCUSSING,
                       vocab.Lifecycle.ACTIVE, vocab.State.PLAN_CONFIRMED):
            self.assertIsInstance(member.value, str)
            self.assertEqual(member.value, str(member.value))  # 与 str 一致（纯值）

    def test_lookup_by_name(self):
        self.assertEqual(vocab.Event["CR_JUDGED"], "CR_JUDGED")
        self.assertEqual(vocab.State["DONE"], "DONE")


if __name__ == "__main__":
    unittest.main()
