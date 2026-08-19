# ============================================================
# engine/state_machine.py 测试 — 合法/非法流转 + 单门不变量 + approve 定位
# ============================================================
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine import state_machine as sm


def fresh_ms():
    return {"phase": "ANALYZING", "lifecycle": "ACTIVE", "pending_gate": None, "blocker": None}


class TestTaskFlow(unittest.TestCase):
    def setUp(self):
        self.m = sm.load_model()

    def test_normal_chain(self):
        # 干净通过链：CODING → CR_PLANNED → CR_SCANNED → CR_PASSED → VERIFYING → DONE
        st, _, err = sm.apply_task(self.m, "TODO", "TASK_STARTED", {"complexity": "NORMAL"})
        self.assertEqual((st, err), ("CODING", None))
        st, _, _ = sm.apply_task(self.m, st, "TASK_DOD_PASSED", decision="RUN_CR")
        self.assertEqual(st, "CR_PLANNED")
        st, _, _ = sm.apply_task(self.m, st, "CR_SCANNED", {"report_complete": True})
        self.assertEqual(st, "CR_SCANNED")
        st, _, _ = sm.apply_task(self.m, st, "CR_JUDGED", {"quality_gate_evidence": "gate.json"},
                                 decision="CONFIRM_CR")
        self.assertEqual(st, "CR_PASSED")
        st, _, _ = sm.apply_task(self.m, st, "TASK_CR_PASSED")
        self.assertEqual(st, "VERIFYING")
        st, _, err = sm.apply_task(self.m, st, "VERIFY_PASSED")
        self.assertEqual((st, err), ("DONE", None))

    def test_cr_fix_loop_full(self):
        # 修复循环：JUDGED(FIX)→FIXING→RECHECKING→RECHECKED(FIX)→JUDGED→FIXING→…→RECHECKED(CONFIRM)→PASSED
        st, _, _ = sm.apply_task(self.m, "CR_SCANNED", "CR_JUDGED", {"fix_contract_path": "c.md"},
                                 decision="FIX_CR_ISSUES")
        self.assertEqual(st, "CR_FIXING")
        st, _, _ = sm.apply_task(self.m, st, "REWRITE_COMPLETED", decision="CR_RECHECK")
        self.assertEqual(st, "CR_RECHECKING")
        st, _, _ = sm.apply_task(self.m, st, "CR_RECHECKED", decision="FIX_CR_ISSUES")
        self.assertEqual(st, "CR_JUDGED")  # 下一轮
        st, _, _ = sm.apply_task(self.m, st, "CR_JUDGED", {"fix_contract_path": "c2.md"},
                                 decision="FIX_CR_ISSUES")
        self.assertEqual(st, "CR_FIXING")
        st, _, _ = sm.apply_task(self.m, st, "REWRITE_COMPLETED", decision="CR_RECHECK")
        st, _, _ = sm.apply_task(self.m, st, "CR_RECHECKED", {"quality_gate_evidence": "gate.json"},
                                 decision="CONFIRM_CR")
        self.assertEqual(st, "CR_PASSED")

    def test_cr_pass_requires_quality_gate(self):
        # 缺口 B：CONFIRM_CR → CR_PASSED 必须有 quality_gate_evidence
        _, _, err = sm.apply_task(self.m, "CR_SCANNED", "CR_JUDGED", decision="CONFIRM_CR")
        self.assertIsNotNone(err)

    def test_fix_requires_contract(self):
        # 缺口 C：FIX_CR_ISSUES → CR_FIXING 必须有 fix_contract_path
        _, _, err = sm.apply_task(self.m, "CR_SCANNED", "CR_JUDGED", decision="FIX_CR_ISSUES")
        self.assertIsNotNone(err)

    def test_cr_low_confidence_wait_approval(self):
        # 低置信度/uncertain → CR 人工门（CR_JUDGED + WAIT_USER_APPROVAL → 停在 CR_JUDGED），可恢复
        st, _, err = sm.apply_task(self.m, "CR_SCANNED", "CR_JUDGED", decision="WAIT_USER_APPROVAL")
        self.assertEqual((st, err), ("CR_JUDGED", None))

    def test_cr_design_rework_path(self):
        # 设计返工：CR_JUDGED + REQUEST_DESIGN_REWORK → CR_JUDGED，随后 REWORK_STARTED 回 TODO
        st, _, _ = sm.apply_task(self.m, "CR_SCANNED", "CR_JUDGED", decision="REQUEST_DESIGN_REWORK")
        self.assertEqual(st, "CR_JUDGED")
        st, _, err = sm.apply_task(self.m, st, "REWORK_STARTED")
        self.assertEqual((st, err), ("TODO", None))

    def test_cr_approved_routing(self):
        # 人工门：CR_JUDGED + CR_APPROVED 按 has_implement_fix 分流
        st, _, _ = sm.apply_task(self.m, "CR_JUDGED", "CR_APPROVED",
                                 {"has_implement_fix": True, "has_design_rework": False,
                                  "fix_contract_path": "c.md"},
                                 decision="WAIT_USER_APPROVAL")
        self.assertEqual(st, "CR_FIXING")
        st, _, _ = sm.apply_task(self.m, "CR_JUDGED", "CR_APPROVED",
                                 {"has_implement_fix": False, "has_design_rework": False,
                                  "quality_gate_evidence": "gate.json"},
                                 decision="WAIT_USER_APPROVAL")
        self.assertEqual(st, "CR_PASSED")

    def test_design_rework_exit_no_fixing(self):
        # design_rework_exit：has_design_rework=true 时 CR_APPROVED 不得进 CR_FIXING（无匹配转换）
        _, _, err = sm.apply_task(self.m, "CR_JUDGED", "CR_APPROVED",
                                  {"has_implement_fix": True, "has_design_rework": True},
                                  decision="WAIT_USER_APPROVAL")
        self.assertIsNotNone(err)

    def test_baseline_align_routing(self):
        # 基线对齐：has_baseline_align=true 且 has_implement_fix=false → baseline_align 转换进 CR_FIXING
        st, _, err = sm.apply_task(self.m, "CR_JUDGED", "CR_APPROVED",
                                   {"has_implement_fix": False, "has_design_rework": False,
                                    "has_baseline_align": True, "fix_contract_path": "c.md"},
                                   decision="WAIT_USER_APPROVAL")
        self.assertEqual((st, err), ("CR_FIXING", None))

    def test_baseline_align_with_fix_uses_has_fix(self):
        # 含实现修复的基线对齐（双旗标）走 has_fix 转换，不歧义
        st, _, _ = sm.apply_task(self.m, "CR_JUDGED", "CR_APPROVED",
                                 {"has_implement_fix": True, "has_design_rework": False,
                                  "has_baseline_align": True, "fix_contract_path": "c.md"},
                                 decision="WAIT_USER_APPROVAL")
        self.assertEqual(st, "CR_FIXING")

    def test_baseline_align_exclusive_with_design_rework(self):
        # fs-8：has_baseline_align=true 与 has_design_rework=true 互斥，CR_APPROVED 无匹配转换
        _, _, err = sm.apply_task(self.m, "CR_JUDGED", "CR_APPROVED",
                                  {"has_implement_fix": False, "has_design_rework": True,
                                   "has_baseline_align": True, "fix_contract_path": "c.md"},
                                  decision="WAIT_USER_APPROVAL")
        self.assertIsNotNone(err)

    def test_complex_requires_plan(self):
        st, _, err = sm.apply_task(self.m, "TODO", "TASK_STARTED", {"complexity": "COMPLEX"})
        self.assertEqual((st, err), ("PLANNING", None))
        st, _, _ = sm.apply_task(self.m, st, "PLAN_READY")
        self.assertEqual(st, "PLAN_AWAITING_DECISION")
        st, _, _ = sm.apply_task(self.m, st, "PLAN_VALIDATED", {"result": "PASS"}, decision="VALIDATE_PLAN")
        self.assertEqual(st, "PLAN_CONFIRMED")
        st, _, err = sm.apply_task(self.m, st, "TASK_STARTED")
        self.assertEqual((st, err), ("CODING", None))

    def test_simple_skip(self):
        st, _, err = sm.apply_task(self.m, "CODING", "TASK_DOD_PASSED", decision="SKIP_CR")
        self.assertEqual((st, err), ("VERIFYING", None))

    def test_illegal_transition(self):
        # CR_SCANNED 仅从 CR_PLANNED 合法；从 CODING 提交 → 报错
        _, _, err = sm.apply_task(self.m, "CODING", "CR_SCANNED", {"report_complete": True})
        self.assertIsNotNone(err)

    def test_done_only_via_verify(self):
        # 复验失败（fix 相关）→ 回 CR_RECHECKING，而非 DONE
        st, _, _ = sm.apply_task(self.m, "VERIFYING", "VERIFY_FAILED",
                                 {"evidence": "x", "is_fix_related": True, "cr_round": 0},
                                 decision="CR_RECHECK")
        self.assertEqual(st, "CR_RECHECKING")

    def test_verify_fail_never_done(self):
        # VERIFY_FAILED 两条分支：fix 相关 → CR_RECHECKING；无关 → AUTONOMOUS_BLOCKED
        _, _, err = sm.apply_task(self.m, "VERIFYING", "VERIFY_FAILED",
                                  {"evidence": "x", "is_fix_related": True, "cr_round": 0},
                                  decision="CR_RECHECK")
        self.assertIsNone(err)
        st, _, _ = sm.apply_task(self.m, "VERIFYING", "VERIFY_FAILED",
                                 {"evidence": "x", "is_fix_related": False, "cr_round": 0},
                                 decision="AUTONOMOUS_BLOCK")
        self.assertEqual(st, "AUTONOMOUS_BLOCKED")
        # DONE 只能由 VERIFY_PASSED 到达
        st, _, _ = sm.apply_task(self.m, "VERIFYING", "VERIFY_PASSED")
        self.assertEqual(st, "DONE")


class TestMilestoneAndGates(unittest.TestCase):
    def setUp(self):
        self.m = sm.load_model()

    def test_stage_flow(self):
        ms = fresh_ms()
        ms, err = sm.apply_milestone(self.m, ms, "STAGE_COMPLETED")
        self.assertEqual((ms["phase"], err), ("DESIGN_REVIEW", None))
        self.assertEqual(ms["pending_gate"]["type"], "DESIGN")
        ms, err = sm.apply_milestone(self.m, ms, "DESIGN_APPROVED")
        self.assertEqual((ms["phase"], ms["pending_gate"], err), ("DEVELOPING", None, None))

    def test_single_gate_invariant(self):
        # 已挂 DESIGN 门，直接 STAGE_COMPLETED 无转换（安全）；再设任务门应被拒
        ms = fresh_ms()
        ms, _ = sm.apply_milestone(self.m, ms, "STAGE_COMPLETED")  # -> DESIGN_REVIEW + gate
        # 同一转换重复触发（从 DESIGN_REVIEW 无 STAGE_COMPLETED 转换）→ 报错
        _, err = sm.apply_milestone(self.m, ms, "STAGE_COMPLETED")
        self.assertIsNotNone(err)

    def test_approve_target_mismatch(self):
        # 任务级门：approve 必须匹配 target_task
        ms = fresh_ms()
        ms, _ = sm.apply_milestone(self.m, ms, "STAGE_COMPLETED")  # DESIGN gate
        # DESIGN 门无 target_task，CR_APPROVED 是错误门类型
        _, err = sm.apply_milestone(self.m, ms, "CR_APPROVED", context={"task_id": "1.1"})
        self.assertIsNotNone(err)

    def test_design_gate_mismatch(self):
        ms = fresh_ms()
        ms, _ = sm.apply_milestone(self.m, ms, "STAGE_COMPLETED")  # DESIGN gate pending
        ms, err = sm.apply_milestone(self.m, ms, "DESIGN_REJECTED")
        self.assertIsNone(err)  # 正确门事件放行
        self.assertEqual(ms["phase"], "ANALYZING")


class TestTransitionIdConvention(unittest.TestCase):
    """转换 ID 自描述命名约定：{flow}.{from}.{event}.{区分}，小写点分；flow = transitions 分组（milestone/task/plan/cr）。"""

    def setUp(self):
        self.m = sm.load_model()

    def test_ids_follow_convention(self):
        import re
        for t in self.m["transitions"]:
            tid = t["id"]
            self.assertRegex(tid, r"^[a-z0-9_]+\.[a-z0-9_]+(\.[a-z0-9_]+)+$",
                             f"ID {tid!r} 不符合约定（flow.from.event）")

    def test_ids_unique(self):
        ids = [t["id"] for t in self.m["transitions"]]
        self.assertEqual(len(ids), len(set(ids)), "存在重复转换 ID")


class TestGateEventsConsistency(unittest.TestCase):
    """批 1：gate_events 与模型事件/门类型的一致性（approve 分发可路由所有门）。"""

    def setUp(self):
        self.m = sm.load_model()

    def test_gate_events_are_real_events(self):
        gate_events = self.m["milestone"]["gate_events"]
        events = set(self.m["events"].keys())
        for ev in gate_events:
            self.assertIn(ev, events, f"gate_events 含未知事件 {ev}")

    def test_gate_event_values_are_valid_types(self):
        gate_events = self.m["milestone"]["gate_events"]
        types = set(self.m["milestone"]["gate_types"])
        for ev, gt in gate_events.items():
            self.assertIn(gt, types, f"gate_events[{ev}] 门类型 {gt} 不在 gate_types")

    def test_gate_events_cover_all_gate_types(self):
        # 每类门至少一个批准事件；新增门类型时必须补对应 gate_events
        gate_events = self.m["milestone"]["gate_events"]
        self.assertEqual(set(gate_events.values()), set(self.m["milestone"]["gate_types"]))


if __name__ == "__main__":
    unittest.main()
