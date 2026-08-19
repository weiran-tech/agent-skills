# ============================================================
# engine/invariants.py 测试 — 枚举/单门/DONE 路径/日志一致性
# ============================================================
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine import invariants, state_machine as sm


class TestInvariants(unittest.TestCase):
    def setUp(self):
        self.m = sm.load_model()

    def test_valid_state_passes(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CODING"}}}
        self.assertEqual(invariants.check_all(self.m, state), [])

    def test_bad_enum(self):
        state = {"milestone": {"phase": "NOT_A_PHASE", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "BOGUS"}}}
        v = invariants.check_all(self.m, state)
        self.assertTrue(any("phase" in x for x in v))
        self.assertTrue(any("BOGUS" in x for x in v))

    def test_task_gate_requires_target(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE",
                               "pending_gate": {"type": "CR", "target_task": None}},
                 "tasks": {}}
        v = invariants.check_single_gate(state)
        self.assertTrue(any("target_task" in x for x in v))

    def test_unknown_gate_type_violation(self):
        # gate_types 从 model 派生后，未知门类型必须被拦截（派生路径回归防线）
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE",
                               "pending_gate": {"type": "BOGUS", "target_task": "1.1"}},
                 "tasks": {}}
        v = invariants.check_single_gate(state)
        self.assertTrue(any("BOGUS" in x for x in v))

    def test_done_via_verify(self):
        log = [{"task_id": "1.1", "event": "VERIFY_PASSED", "ts": "t1"}]
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "DONE"}}}
        self.assertEqual(invariants.check_done_via_verify(state, log), [])

    def test_done_not_via_verify(self):
        log = [{"task_id": "1.1", "event": "REWRITE_COMPLETED", "ts": "t1"}]
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "DONE"}}}
        v = invariants.check_done_via_verify(state, log)
        self.assertTrue(any("DONE" in x for x in v))

    def test_unknown_event_in_log(self):
        log = [{"event": "NOT_A_EVENT", "ts": "t1"}]
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None}, "tasks": {}}
        v = invariants.check_log_consistency(state, log)
        self.assertTrue(any("未知事件" in x for x in v))

    def test_design_rework_exit_violation(self):
        # G-6：CR_JUDGED 裁决 REQUEST_DESIGN_REWORK 后任务不得进 CR_FIXING
        log = [{"task_id": "1.1", "event": "CR_JUDGED", "decision": "REQUEST_DESIGN_REWORK", "ts": "t1"}]
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_FIXING"}}}
        v = invariants.check_design_rework_exit(state, log)
        self.assertTrue(any("设计返工" in x for x in v))

    def test_design_rework_exit_clean(self):
        log = [{"task_id": "1.1", "event": "CR_JUDGED", "decision": "FIX_CR_ISSUES", "ts": "t1"}]
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_FIXING"}}}
        self.assertEqual(invariants.check_design_rework_exit(state, log), [])

    def test_plan_before_code_violation(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CODING", "complexity": "COMPLEX"}}}
        v = invariants.check_plan_before_code(state)
        self.assertTrue(any("plan 确认" in x for x in v))

    def test_plan_before_code_clean(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CODING", "complexity": "COMPLEX", "plan_confirmed": True}}}
        self.assertEqual(invariants.check_plan_before_code(state), [])

    def test_fix_contract_required_violation(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_FIXING"}}}
        v = invariants.check_fix_contract_required(state)
        self.assertTrue(any("fix_contract_path" in x for x in v))

    def test_fix_contract_required_clean(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_FIXING", "fix_contract_path": "c.md"}}}
        self.assertEqual(invariants.check_fix_contract_required(state), [])

    def test_cr_pass_quality_gate_violation(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_PASSED"}}}
        v = invariants.check_cr_pass_quality_gate(state)
        self.assertTrue(any("quality_gate_evidence" in x for x in v))

    def test_cr_pass_quality_gate_clean(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_PASSED", "quality_gate_evidence": "gate.json"}}}
        self.assertEqual(invariants.check_cr_pass_quality_gate(state), [])

    def test_baseline_align_post_fix_requires_update(self):
        # baseline_align_requires_update：脱离修复态（CR_PASSED 等）必须已 baseline_updated
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_PASSED", "baseline_align": True}}}
        v = invariants.check_baseline_align_requires_update(state)
        self.assertTrue(any("baseline_updated" in x for x in v))

    def test_baseline_align_post_fix_clean(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_PASSED", "baseline_align": True, "baseline_updated": True}}}
        self.assertEqual(invariants.check_baseline_align_requires_update(state), [])

    def test_baseline_align_fixing_requires_fingerprint(self):
        # 在 CR_FIXING 时必须已捕获基线指纹（防未追踪直接修复）
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_FIXING", "baseline_align": True}}}
        v = invariants.check_baseline_align_requires_update(state)
        self.assertTrue(any("baseline_fp_before" in x for x in v))

    def test_baseline_align_fixing_clean(self):
        state = {"milestone": {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None},
                 "tasks": {"1.1": {"state": "CR_FIXING", "baseline_align": True, "baseline_fp_before": "abc"}}}
        self.assertEqual(invariants.check_baseline_align_requires_update(state), [])

    def test_zero_autonomous_blocked_violation(self):
        state = {"milestone": {"phase": "AUTONOMOUS_COMPLETED", "lifecycle": "COMPLETED", "pending_gate": None},
                 "tasks": {"1.1": {"state": "DONE"}, "1.2": {"state": "AUTONOMOUS_BLOCKED"}}}
        v = invariants.check_zero_autonomous_blocked(state)
        self.assertTrue(any("AUTONOMOUS_BLOCKED" in x for x in v))

    def test_zero_autonomous_blocked_history(self):
        log = [{"task_id": "1.2", "decision": "AUTONOMOUS_BLOCK", "event": "CR_JUDGED", "ts": "t1"}]
        state = {"milestone": {"phase": "AUTONOMOUS_COMPLETED", "lifecycle": "COMPLETED", "pending_gate": None},
                 "tasks": {"1.1": {"state": "DONE"}, "1.2": {"state": "DONE"}}}
        v = invariants.check_zero_autonomous_blocked(state, log)
        self.assertTrue(any("曾触发" in x for x in v))

    def test_zero_autonomous_blocked_clean(self):
        state = {"milestone": {"phase": "AUTONOMOUS_COMPLETED", "lifecycle": "COMPLETED", "pending_gate": None},
                 "tasks": {"1.1": {"state": "DONE"}, "1.2": {"state": "DONE"}}}
        self.assertEqual(invariants.check_zero_autonomous_blocked(state), [])


if __name__ == "__main__":
    unittest.main()
