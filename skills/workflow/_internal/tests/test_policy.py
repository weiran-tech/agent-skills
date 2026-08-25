# ============================================================
# engine/policy.py 测试 — 事件决策矩阵 + 计数边界 + 固定安全规则
# Policy 纯判断；配置全显式（capabilities 来自 config，无 profile）
# ============================================================
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine import policy

VALID_GATE = {"change_kind": "CODE", "changed_file_count": 1, "scope_check": "PASS", "tests": "PASS",
              "static_checks": "PASS", "diff_integrity": "PASS",
              "risk_signals": [], "evidence_path": "x"}

LIMITS = {"acceptance_fix_max": 2, "cr_fix_max": 3, "plan_retry_max": 2, "design_rework_max": 2}


class TestStageCompleted(unittest.TestCase):
    def test_no_stage_advance_wait(self):
        self.assertEqual(policy.resolve("STAGE_COMPLETED", {}), "WAIT_NEXT_COMMAND")

    def test_stage_advance(self):
        self.assertEqual(policy.resolve("STAGE_COMPLETED", {}, capabilities={"advance_stage": True}),
                         "ADVANCE_WORKFLOW")


class TestTaskDodPassed(unittest.TestCase):
    def test_simple_valid_skip(self):
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": VALID_GATE},
                                        capabilities={"simple_skip_cr": True}), "SKIP_CR")

    def test_simple_valid_without_skip_capability_run(self):
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": VALID_GATE}), "RUN_CR")

    def test_simple_invalid_gate_run(self):
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": {}},
                                        capabilities={"simple_skip_cr": True}), "RUN_CR")

    def test_simple_risk_signal_run(self):
        gate = dict(VALID_GATE, risk_signals=["权限变更"])
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "RUN_CR")

    def test_simple_three_files_run(self):
        # CODE（含生产代码）>2 文件 → RUN_CR（文件数门保持 2）
        gate = dict(VALID_GATE, changed_file_count=3)
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "RUN_CR")

    def test_simple_docs_only_multifile_skip(self):
        # DOCS_ONLY（纯文档）不限文件数 → SKIP_CR（test/doc 类型不按文件数一刀切）
        gate = dict(VALID_GATE, change_kind="DOCS_ONLY", changed_file_count=4)
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "SKIP_CR")

    def test_simple_tests_only_multifile_skip(self):
        gate = dict(VALID_GATE, change_kind="TESTS_ONLY", changed_file_count=6)
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "SKIP_CR")

    def test_simple_docs_only_many_skip(self):
        # DOCS_ONLY 不限文件数：7 文件仍 SKIP_CR（test/doc 类型文件数门取消）
        gate = dict(VALID_GATE, change_kind="DOCS_ONLY", changed_file_count=7)
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "SKIP_CR")

    def test_simple_tests_docs_mixed_skip(self):
        # TESTS_DOCS（仅测试+文档、无生产代码）不限文件数 → SKIP_CR
        gate = dict(VALID_GATE, change_kind="TESTS_DOCS", changed_file_count=12)
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "SKIP_CR")

    def test_simple_unknown_kind_run(self):
        # 未知 change_kind → 保守按 CODE 阈值处理（schema 先拦未知枚举，防御纵深）
        gate = dict(VALID_GATE, change_kind="OTHER", changed_file_count=3)
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "RUN_CR")

    def test_simple_docs_only_risk_signal_run(self):
        # 放宽文件数但不放宽 risk_signals：文档标契约变化仍走完整 CR
        gate = dict(VALID_GATE, change_kind="DOCS_ONLY", changed_file_count=4, risk_signals=["CONTRACT"])
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        capabilities={"simple_skip_cr": True}), "RUN_CR")

    def test_normal_run(self):
        self.assertEqual(policy.resolve("TASK_DOD_PASSED", {"complexity": "NORMAL"}), "RUN_CR")


class TestCrJudged(unittest.TestCase):
    """CR_JUDGED 决策矩阵：低置信度/uncertain 进人工门，设计返工，cr.levels 严重度行为（配置显式）。"""
    BASE = {"accepted_count": 0, "rejected_count": 0, "uncertain_count": 0,
            "min_confidence": 0.9, "has_design_rework": False}
    Q = {"judge_min_confidence": 0.85, "cr_zero_auto_confirm": True, "cr_minor_auto_fix": False}

    def test_low_confidence_wait_approval(self):
        # 有已采纳问题 + 置信度保守但问题真实 → 进 CR 人工门（可恢复），不再 AUTONOMOUS_BLOCK
        p = dict(self.BASE, accepted_count=2, min_confidence=0.5)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "WAIT_USER_APPROVAL")

    def test_low_confidence_all_rejected_confirms(self):
        # 全部 REJECTED（accepted_count=0）→ 无"最低置信度"可评估，跳过置信度门 → 零问题自动确认
        p = dict(self.BASE, min_confidence=0.5)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "CONFIRM_CR")

    def test_uncertain_wait_approval(self):
        # Judge 拿不准（uncertain_count>0）→ 始终人工确认，与 accepted_count 无关
        p = dict(self.BASE, uncertain_count=1)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "WAIT_USER_APPROVAL")

    def test_uncertain_with_accepted_wait_approval(self):
        # 有已采纳问题且存在 uncertain → 仍人工门
        p = dict(self.BASE, accepted_count=2, uncertain_count=1)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "WAIT_USER_APPROVAL")

    def test_design_rework(self):
        p = dict(self.BASE, has_design_rework=True)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "REQUEST_DESIGN_REWORK")

    def test_zero_auto_confirm(self):
        self.assertEqual(policy.resolve("CR_JUDGED", dict(self.BASE), LIMITS, self.Q), "CONFIRM_CR")

    def test_zero_auto_confirm_disabled_wait(self):
        q = dict(self.Q, cr_zero_auto_confirm=False)
        self.assertEqual(policy.resolve("CR_JUDGED", dict(self.BASE), LIMITS, q), "WAIT_USER_APPROVAL")

    def test_issues_wait_without_auto_fix(self):
        p = dict(self.BASE, accepted_count=2)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "WAIT_USER_APPROVAL")

    def test_issues_auto_fix_from_config(self):
        p = dict(self.BASE, accepted_count=2)
        q = dict(self.Q, cr_minor_auto_fix=True)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, q), "FIX_CR_ISSUES")

    def test_baseline_align_not_design_rework(self):
        # 处置三档：has_baseline_align=true 不触发 rework（仅 has_design_rework 触发），走修复/人工门
        p = dict(self.BASE, accepted_count=2, has_baseline_align=True)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "WAIT_USER_APPROVAL")

    def test_baseline_align_auto_fix(self):
        p = dict(self.BASE, accepted_count=2, has_baseline_align=True)
        q = dict(self.Q, cr_minor_auto_fix=True)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, q), "FIX_CR_ISSUES")

    def test_baseline_align_never_zero_confirm(self):
        # fs-8：has_baseline_align=true 但 accepted_count=0 的矛盾态不得零问题确认，交人工门
        p = dict(self.BASE, accepted_count=0, has_baseline_align=True)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "WAIT_USER_APPROVAL")

    def test_baseline_align_with_design_rework_prioritizes_rework(self):
        # fs-8 互斥：has_design_rework=true 时仍优先 REQUEST_DESIGN_REWORK
        p = dict(self.BASE, accepted_count=2, has_baseline_align=True, has_design_rework=True)
        self.assertEqual(policy.resolve("CR_JUDGED", p, LIMITS, self.Q), "REQUEST_DESIGN_REWORK")


class TestCrZeroAutoConfirm(unittest.TestCase):
    """cr.levels.zero.auto_confirm：配置显式值，默认 true。"""
    BASE = {"accepted_count": 0, "rejected_count": 0, "uncertain_count": 0,
            "min_confidence": 0.9, "has_design_rework": False}

    def test_default_true_no_quality(self):
        self.assertEqual(policy.resolve("CR_JUDGED", dict(self.BASE), LIMITS, None), "CONFIRM_CR")

    def test_disabled_wait(self):
        q = {"cr_zero_auto_confirm": False}
        self.assertEqual(policy.resolve("CR_JUDGED", dict(self.BASE), LIMITS, q), "WAIT_USER_APPROVAL")


class TestCapabilitiesExplicit(unittest.TestCase):
    """capabilities 为配置显式值（无 profile 默认）：传入才生效，默认 False。"""
    BASE = {"accepted_count": 2, "rejected_count": 0, "uncertain_count": 0,
            "min_confidence": 0.9, "has_design_rework": False}

    def test_cr_minor_auto_fix_from_quality(self):
        q = {"cr_minor_auto_fix": True}
        self.assertEqual(policy.resolve("CR_JUDGED", dict(self.BASE), LIMITS, q), "FIX_CR_ISSUES")
        q2 = {"cr_minor_auto_fix": False}
        self.assertEqual(policy.resolve("CR_JUDGED", dict(self.BASE), LIMITS, q2), "WAIT_USER_APPROVAL")

    def test_accept_auto_fix_from_capabilities(self):
        p = {"report_complete": True, "major_count": 0, "minor_count": 1,
             "root_causes": ["IMPLEMENTATION"], "fix_attempts": 1}
        self.assertEqual(policy.resolve("ACCEPTANCE_FAILED", p, LIMITS, None, {"accept_auto_fix": True}),
                         "FIX_ACCEPTANCE_ISSUES")
        self.assertEqual(policy.resolve("ACCEPTANCE_FAILED", p, LIMITS, None, {"accept_auto_fix": False}),
                         "WAIT_USER_APPROVAL")

    def test_simple_skip_cr_from_capabilities(self):
        gate = VALID_GATE
        self.assertEqual(policy.resolve("TASK_DOD_PASSED",
                                        {"complexity": "SIMPLE", "simple_gate": gate},
                                        LIMITS, None, {"simple_skip_cr": False}),
                         "RUN_CR")


class TestCrRechecked(unittest.TestCase):
    """CR_RECHECKED：劣化→阻塞、仍有问题→下一轮、达上限→熔断、干净→确认。"""

    def test_regression_block(self):
        p = {"cr_round": 1, "resolved_count": 0, "new_issue_count": 0, "regression_detected": True}
        self.assertEqual(policy.resolve("CR_RECHECKED", p, LIMITS), "AUTONOMOUS_BLOCK")

    def test_iterate_next_round(self):
        p = {"cr_round": 1, "resolved_count": 1, "new_issue_count": 1, "regression_detected": False}
        self.assertEqual(policy.resolve("CR_RECHECKED", p, LIMITS), "FIX_CR_ISSUES")

    def test_exhausted_block(self):
        p = {"cr_round": 3, "resolved_count": 1, "new_issue_count": 1, "regression_detected": False}
        self.assertEqual(policy.resolve("CR_RECHECKED", p, LIMITS), "AUTONOMOUS_BLOCK")

    def test_clean_confirm(self):
        p = {"cr_round": 1, "resolved_count": 1, "new_issue_count": 0, "regression_detected": False}
        self.assertEqual(policy.resolve("CR_RECHECKED", p, LIMITS), "CONFIRM_CR")


class TestVerifyFailed(unittest.TestCase):
    """VERIFY_FAILED：fix 相关且未超限→CR_RECHECK；否则→AUTONOMOUS_BLOCK；skip_recheck 时一律阻塞。"""

    def test_fix_related_recheck(self):
        p = {"evidence": "x", "is_fix_related": True, "cr_round": 1}
        self.assertEqual(policy.resolve("VERIFY_FAILED", p, LIMITS), "CR_RECHECK")

    def test_unrelated_block(self):
        p = {"evidence": "x", "is_fix_related": False, "cr_round": 1}
        self.assertEqual(policy.resolve("VERIFY_FAILED", p, LIMITS), "AUTONOMOUS_BLOCK")

    def test_over_limit_block(self):
        p = {"evidence": "x", "is_fix_related": True, "cr_round": 3}
        self.assertEqual(policy.resolve("VERIFY_FAILED", p, LIMITS), "AUTONOMOUS_BLOCK")

    def test_recheck_disabled_blocks_fix_related(self):
        # skip_recheck=true（cr.capabilities.recheck=false）：无重审路径可回，fix 相关复验失败也保守阻塞
        p = {"evidence": "x", "is_fix_related": True, "cr_round": 1}
        self.assertEqual(policy.resolve("VERIFY_FAILED", p, LIMITS, None, {"skip_recheck": True}),
                         "AUTONOMOUS_BLOCK")

    def test_recheck_enabled_recheck_path_unchanged(self):
        p = {"evidence": "x", "is_fix_related": True, "cr_round": 1}
        self.assertEqual(policy.resolve("VERIFY_FAILED", p, LIMITS, None, {"skip_recheck": False}),
                         "CR_RECHECK")


class TestRewriteCompleted(unittest.TestCase):
    """REWRITE_COMPLETED：skip_recheck（cr.capabilities.recheck 扁平，默认 false）决定修复后走二次审核还是只审一次。"""

    def test_recheck_default_enabled_enters_rechecking(self):
        # 默认：不传 skip_recheck → 保守默认 false → 开启二次审核（向后兼容）
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", {}), "CR_RECHECK")

    def test_recheck_enabled_enters_rechecking(self):
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", {},
                                        capabilities={"skip_recheck": False}), "CR_RECHECK")

    def test_recheck_disabled_confirms(self):
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", {},
                                        capabilities={"skip_recheck": True}), "CONFIRM_CR")


class TestRewriteCompletedSeverity(unittest.TestCase):
    """REWRITE_COMPLETED 按严重度缩放：MAJOR/BASELINE_ALIGN 强制重审；纯 MINOR+IMPLEMENT_FIX 修复且带质量门证据自动确认（跳重审）。"""
    CAPS = {"skip_recheck": False, "minor_fix_auto_confirm": True}

    def test_minor_only_with_evidence_confirms(self):
        p = {"fixed_has_major": False, "fixed_has_baseline_align": False, "quality_gate_evidence": "ev.md"}
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", p, capabilities=self.CAPS), "CONFIRM_CR")

    def test_minor_only_without_evidence_rechecks(self):
        # minor 自动确认但缺质量门证据 → 保守重审（不得无证据放行）
        p = {"fixed_has_major": False, "fixed_has_baseline_align": False}
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", p, capabilities=self.CAPS), "CR_RECHECK")

    def test_major_force_recheck(self):
        p = {"fixed_has_major": True, "fixed_has_baseline_align": False, "quality_gate_evidence": "ev.md"}
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", p, capabilities=self.CAPS), "CR_RECHECK")

    def test_baseline_align_force_recheck(self):
        p = {"fixed_has_major": False, "fixed_has_baseline_align": True, "quality_gate_evidence": "ev.md"}
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", p, capabilities=self.CAPS), "CR_RECHECK")

    def test_auto_confirm_disabled_rechecks(self):
        caps = {"skip_recheck": False, "minor_fix_auto_confirm": False}
        p = {"fixed_has_major": False, "fixed_has_baseline_align": False, "quality_gate_evidence": "ev.md"}
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", p, capabilities=caps), "CR_RECHECK")

    def test_skip_recheck_global_wins(self):
        # 全局只审一次（recheck=false）优先于严重度强制重审
        caps = {"skip_recheck": True, "minor_fix_auto_confirm": True}
        p = {"fixed_has_major": True, "quality_gate_evidence": "ev.md"}
        self.assertEqual(policy.resolve("REWRITE_COMPLETED", p, capabilities=caps), "CONFIRM_CR")


class TestAcceptanceFailed(unittest.TestCase):
    BASE = {"report_complete": True, "major_count": 0, "minor_count": 1, "root_causes": ["IMPLEMENTATION"]}
    LIMITS = {"acceptance_fix_max": 2}

    def test_design_root_rework(self):
        p = dict(self.BASE, root_causes=["DESIGN"])
        self.assertEqual(policy.resolve("ACCEPTANCE_FAILED", p, self.LIMITS), "REQUEST_DESIGN_REWORK")

    def test_requirement_root_rework(self):
        p = dict(self.BASE, root_causes=["REQUIREMENT"])
        self.assertEqual(policy.resolve("ACCEPTANCE_FAILED", p, self.LIMITS), "REQUEST_DESIGN_REWORK")

    def test_fix_attempts_at_limit_wait(self):
        p = dict(self.BASE, fix_attempts=2)
        self.assertEqual(policy.resolve("ACCEPTANCE_FAILED", p, self.LIMITS), "WAIT_USER_APPROVAL")

    def test_fix_attempts_below_limit_fix(self):
        p = dict(self.BASE, fix_attempts=1)
        self.assertEqual(policy.resolve("ACCEPTANCE_FAILED", p, self.LIMITS, None, {"accept_auto_fix": True}),
                         "FIX_ACCEPTANCE_ISSUES")

    def test_no_auto_fix_wait(self):
        p = dict(self.BASE, fix_attempts=0)
        self.assertEqual(policy.resolve("ACCEPTANCE_FAILED", p, self.LIMITS), "WAIT_USER_APPROVAL")


class TestAcceptanceCompleted(unittest.TestCase):
    """ACCEPTANCE_COMPLETED：advance_summary=true → GENERATE_SUMMARY，否则 FINISH_ACCEPTANCE。"""

    def test_generate_summary(self):
        self.assertEqual(policy.resolve("ACCEPTANCE_COMPLETED", {},
                                        capabilities={"advance_summary": True}), "GENERATE_SUMMARY")

    def test_no_summary_finish(self):
        self.assertEqual(policy.resolve("ACCEPTANCE_COMPLETED", {}), "FINISH_ACCEPTANCE")
        self.assertEqual(policy.resolve("ACCEPTANCE_COMPLETED", {},
                                        capabilities={"advance_summary": False}), "FINISH_ACCEPTANCE")


class TestPredicateParser(unittest.TestCase):
    """谓词解析器边界：裸路径真值、路径引用、列表 in、has。"""

    def test_bare_path_truthy(self):
        ctx = {"payload": {"simple_gate_valid": False}, "limits": {}}
        self.assertTrue(policy.eval_predicate("not payload.simple_gate_valid", ctx))

    def test_path_reference_rhs(self):
        ctx = {"payload": {"fix_attempts": 2}, "limits": {"acceptance_fix_max": 2}}
        self.assertTrue(policy.eval_predicate("payload.fix_attempts >= limits.acceptance_fix_max", ctx))

    def test_list_in(self):
        ctx = {"payload": {}, "limits": {}, "flow": "guarded"}
        self.assertTrue(policy.eval_predicate("flow in ['guarded', 'autonomous']", ctx))

    def test_has(self):
        ctx = {"payload": {"root_causes": ["IMPLEMENTATION", "DESIGN"]}, "limits": {}}
        self.assertTrue(policy.eval_predicate("payload.root_causes has DESIGN", ctx))

    def test_or_short_circuit(self):
        ctx = {"payload": {"has_design_issue": True, "major_count": 0}, "limits": {}}
        self.assertTrue(policy.eval_predicate("payload.has_design_issue or payload.major_count > 0", ctx))


class TestModelConsistency(unittest.TestCase):
    """implicit_decisions 单一来源一致性。"""

    def test_implicit_decisions_disjoint_from_matrix(self):
        pol = policy.load_policy()
        matrix = set(pol["decisions"].keys())
        implicit = set(pol.get("implicit_decisions", {}).keys())
        self.assertEqual(matrix & implicit, set(),
                         f"事件同时出现在 decisions 与 implicit_decisions: {matrix & implicit}")

    def test_implicit_decisions_are_real_events(self):
        from engine import state_machine as sm
        pol, model = policy.load_policy(), sm.load_model()
        events = set(model["events"].keys())
        for ev in pol.get("implicit_decisions", {}):
            self.assertIn(ev, events, f"implicit_decisions 含未知事件 {ev}")

    def test_decision_predicates_reference_no_profile(self):
        pol = policy.load_policy()
        for rules in pol["decisions"].values():
            for r in rules:
                self.assertNotIn("profile", r["when"], f"决策矩阵不得引用 profile: {r['when']}")


if __name__ == "__main__":
    unittest.main()
