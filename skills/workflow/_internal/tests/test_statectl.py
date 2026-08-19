# ============================================================
# adapters/statectl.py 测试 — 唯一状态写入口
# 覆盖：schema 校验 → policy 决策 → 状态转换 → 原子写状态 + append-only 日志
# ============================================================
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from adapters.statectl import load_state, main, read_log

# 日志时间戳由 statectl 系统生成（_now_iso），测试不再注入外部时间；此常量已移除。


def write_config(path, **extra):
    """v2 全显式配置（guarded 风格：capabilities 开、cr 零问题自动确认、验收自动修）。"""
    cfg = {
        "version": 2,
        "automation": {"advance_stage": True, "advance_task": True, "advance_accept": False,
                       "advance_summary": False},
        "cr": {"limits": {"fix_max": 3}, "capabilities": {"simple_skip_cr": True},
               "levels": {"zero": {"auto_confirm": True},
                          "minor": {"auto_fix": False, "recheck": []},
                          "major": {"recheck": ["design", "security", "performance"]}},
               "quality": {"judge": {"min_confidence": 0.85}}},
        "plan": {"limits": {"retry_max": 2}, "capabilities": {"auto_validate": True}},
        "accept": {"limits": {"fix_max": 2}, "capabilities": {"auto_fix": True}},
        "rework": {"limits": {"design_max": 2}},
    }
    cfg.update(extra)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def valid_simple_gate():
    return {"change_kind": "CODE", "changed_file_count": 1, "scope_check": "PASS", "tests": "PASS",
            "static_checks": "PASS", "diff_integrity": "PASS",
            "risk_signals": [], "evidence_path": ".task/done/order-1.1.md"}


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class StatectlTestCase(unittest.TestCase):
    """公共 setUp：临时目录 + guarded 配置 + 空状态。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = self.root / ".claude" / "workflow" / "config.yml"
        self.state = self.root / "state" / "workflow-state.yml"
        self.log = self.root / "state" / "transition.log"
        write_config(self.cfg)  # 默认 guarded
        self.base = ["transit", "--state", str(self.state), "--config", str(self.cfg),
                     "--log", str(self.log)]

    def tearDown(self):
        self.tmp.cleanup()

    def transit(self, event, payload=None, task=None):
        args = self.base + ["--event", event]
        if payload is not None:
            args += ["--payload", json.dumps(payload)]
        if task is not None:
            args += ["--task", task]
        return run(args)

    def touch(self, *relpaths):
        """创建 payload 引用的产物文件（硬校验要求存在）。基准目录 = {工单根}。"""
        for p in relpaths:
            f = self.root / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("", encoding="utf-8")

    def drive_to(self, phase):
        """按里程碑推进到指定阶段（guarded 自动推进）。"""
        steps = {
            "ANALYZING": [("STAGE_COMPLETED", None)],
            "DESIGN_REVIEW": [("STAGE_COMPLETED", None), ("STAGE_COMPLETED", None)],
            "DEVELOPING": [("STAGE_COMPLETED", None), ("STAGE_COMPLETED", None), ("DESIGN_APPROVED", None)],
            "ACCEPTING": [("STAGE_COMPLETED", None), ("STAGE_COMPLETED", None), ("DESIGN_APPROVED", None),
                          ("STAGE_COMPLETED", None)],
        }
        for event, payload in steps[phase]:
            code, _, err = self.transit(event, payload)
            if code != 0:
                self.fail(f"drive_to({phase}) 在 {event} 失败: {err}")


class TestMilestoneTransit(StatectlTestCase):
    def test_stage_completed_advances_to_analyzing(self):
        code, out, _ = self.transit("STAGE_COMPLETED")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["phase"], "ANALYZING")
        self.assertEqual(result["decision"], "ADVANCE_WORKFLOW")
        self.assertEqual(load_state(self.state)["milestone"]["phase"], "ANALYZING")
        self.assertEqual(len(read_log(self.log)), 1)

    def test_no_stage_advance_returns_wait_next_command(self):
        # advance_stage 未开启（默认保守）→ 阶段照常应用，但返回 WAIT_NEXT_COMMAND
        write_config(self.cfg, automation={"advance_stage": False, "advance_task": True,
                                           "advance_accept": True, "advance_summary": False})
        code, out, _ = self.transit("STAGE_COMPLETED")
        self.assertEqual(code, 0)
        # 阶段照常应用，但返回 WAIT_NEXT_COMMAND（不自动推进）
        self.assertEqual(json.loads(out)["decision"], "WAIT_NEXT_COMMAND")
        self.assertEqual(load_state(self.state)["milestone"]["phase"], "ANALYZING")

    def test_design_gate_set_and_approved(self):
        self.drive_to("DESIGN_REVIEW")
        state = load_state(self.state)
        self.assertEqual(state["milestone"]["phase"], "DESIGN_REVIEW")
        self.assertEqual(state["milestone"]["pending_gate"]["type"], "DESIGN")
        code, _, _ = self.transit("DESIGN_APPROVED")
        self.assertEqual(code, 0)
        state = load_state(self.state)
        self.assertEqual(state["milestone"]["phase"], "DEVELOPING")
        self.assertIsNone(state["milestone"]["pending_gate"])

    def test_design_approved_without_gate_rejected(self):
        code, _, err = self.transit("DESIGN_APPROVED")
        self.assertEqual(code, 1)
        self.assertIn("无合法转换", err)
        self.assertFalse(self.state.exists())

    def test_acceptance_failed_triggers_auto_fix_and_increments(self):
        self.drive_to("ACCEPTING")
        code, out, _ = self.transit("ACCEPTANCE_FAILED",
                                    payload={"report_complete": True, "major_count": 1, "minor_count": 0,
                                             "root_causes": ["IMPLEMENTATION"], "fix_attempts": 0})
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["decision"], "FIX_ACCEPTANCE_ISSUES")
        self.assertEqual(result["fix_attempts"], 1)
        self.assertEqual(load_state(self.state)["milestone"]["fix_attempts"], 1)

    def test_acceptance_completed_finishes_milestone(self):
        self.drive_to("ACCEPTING")
        code, _, _ = self.transit("ACCEPTANCE_COMPLETED")
        self.assertEqual(code, 0)
        state = load_state(self.state)
        self.assertEqual(state["milestone"]["phase"], "COMPLETED")
        self.assertIsNone(state["milestone"]["pending_gate"])


class TestSchemaRejection(StatectlTestCase):
    def test_unknown_payload_field_rejected(self):
        code, _, err = self.transit("STAGE_COMPLETED", payload={"foo": 1})
        self.assertEqual(code, 1)
        self.assertIn("error", err)
        self.assertFalse(self.state.exists())

    def test_invalid_complexity_rejected(self):
        code, _, err = self.transit("TASK_STARTED", payload={"complexity": "BIG"}, task="1.1")
        self.assertEqual(code, 1)
        self.assertFalse(self.state.exists())

    def test_invalid_simple_gate_field_rejected(self):
        gate = valid_simple_gate()
        gate["scope_check"] = "FAIL"  # const PASS
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, _, err = self.transit("TASK_DOD_PASSED",
                                    payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("PASS", err)


class TestTaskTransit(StatectlTestCase):
    def test_task_event_requires_task_id(self):
        code, _, err = self.transit("TASK_STARTED", payload={"complexity": "NORMAL"})
        self.assertEqual(code, 1)
        self.assertIn("需要 --task", err)

    def test_task_started_normal_goes_coding(self):
        code, out, _ = self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["task_state"], "CODING")
        self.assertEqual(load_state(self.state)["tasks"]["1.1"]["complexity"], "NORMAL")

    def test_task_started_complex_goes_planning(self):
        code, out, _ = self.transit("TASK_STARTED", payload={"complexity": "COMPLEX"}, task="1.1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["task_state"], "PLANNING")

    def test_normal_dod_passed_runs_cr(self):
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        code, out, _ = self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["decision"], "RUN_CR")
        self.assertEqual(json.loads(out)["task_state"], "CR_PLANNED")

    def test_simple_valid_gate_skips_cr(self):
        self.touch(".task/done/order-1.1.md")
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, _ = self.transit("TASK_DOD_PASSED",
                                    payload={"complexity": "SIMPLE", "simple_gate": valid_simple_gate()}, task="1.1")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["decision"], "SKIP_CR")
        self.assertEqual(result["task_state"], "VERIFYING")
        self.assertEqual(load_state(self.state)["tasks"]["1.1"]["cr_path"], "SIMPLE_SKIP")

    def test_simple_risk_signal_force_runs_cr(self):
        self.touch(".task/done/order-1.1.md")
        gate = valid_simple_gate()
        gate["risk_signals"] = ["查询性能"]
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, _ = self.transit("TASK_DOD_PASSED",
                                    payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["decision"], "RUN_CR")
        self.assertEqual(result["task_state"], "CR_PLANNED")

    def test_simple_docs_only_multifile_skips_cr(self):
        # 纯文档改 4 个文件（>CODE 阈值）仍可 SKIP_CR（风险驱动放宽文件数门）
        self.touch(".task/done/order-1.1.md")
        gate = valid_simple_gate()
        gate["change_kind"] = "DOCS_ONLY"
        gate["changed_file_count"] = 4
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, _ = self.transit("TASK_DOD_PASSED",
                                    payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["decision"], "SKIP_CR")
        self.assertEqual(result["task_state"], "VERIFYING")

    def test_simple_tests_only_many_files_skips_cr(self):
        # 纯测试改 10 个文件（原 TESTS_ONLY 阈值 6）仍 SKIP_CR（test 类型不限文件数）
        self.touch(".task/done/order-1.1.md")
        gate = valid_simple_gate()
        gate["change_kind"] = "TESTS_ONLY"
        gate["changed_file_count"] = 10
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, err = self.transit("TASK_DOD_PASSED",
                                      payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["decision"], "SKIP_CR")

    def test_simple_tests_only_over_schema_old_max_skips_cr(self):
        # 文件数超过原 schema 结构上限 20 仍 SKIP_CR（test/doc 不限文件数，结构上限同步放宽）
        self.touch(".task/done/order-1.1.md")
        gate = valid_simple_gate()
        gate["change_kind"] = "TESTS_ONLY"
        gate["changed_file_count"] = 30
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, err = self.transit("TASK_DOD_PASSED",
                                      payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["decision"], "SKIP_CR")

    def test_simple_docs_only_many_files_skips_cr(self):
        # 纯文档改 10 个文件（原 DOCS_ONLY 阈值 6）仍 SKIP_CR
        self.touch(".task/done/order-1.1.md")
        gate = valid_simple_gate()
        gate["change_kind"] = "DOCS_ONLY"
        gate["changed_file_count"] = 10
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, err = self.transit("TASK_DOD_PASSED",
                                      payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["decision"], "SKIP_CR")

    def test_simple_tests_docs_mixed_skips_cr(self):
        # 仅含测试+文档、无生产代码（TESTS_DOCS）→ SKIP_CR，文件数不限
        self.touch(".task/done/order-1.1.md")
        gate = valid_simple_gate()
        gate["change_kind"] = "TESTS_DOCS"
        gate["changed_file_count"] = 12
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, err = self.transit("TASK_DOD_PASSED",
                                      payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["decision"], "SKIP_CR")
        self.assertEqual(json.loads(out)["task_state"], "VERIFYING")

    def test_simple_code_over_two_files_runs_cr(self):
        # CODE 3 文件 → RUN_CR（生产代码文件数门不放松）
        self.touch(".task/done/order-1.1.md")
        gate = valid_simple_gate()
        gate["changed_file_count"] = 3
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, _ = self.transit("TASK_DOD_PASSED",
                                    payload={"complexity": "SIMPLE", "simple_gate": gate}, task="1.1")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["decision"], "RUN_CR")
        self.assertEqual(result["task_state"], "CR_PLANNED")

    def test_simple_verify_passed_reaches_done(self):
        self.touch(".task/done/order-1.1.md")
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "SIMPLE", "simple_gate": valid_simple_gate()}, task="1.1")
        code, out, _ = self.transit("VERIFY_PASSED", task="1.1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["task_state"], "DONE")


class TestGetAndLog(StatectlTestCase):
    def test_get_returns_current_phase(self):
        self.transit("STAGE_COMPLETED")
        code, out, _ = run(["get", "--state", str(self.state)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["milestone"]["phase"], "ANALYZING")

    def test_log_is_append_only_and_ordered(self):
        self.transit("STAGE_COMPLETED")
        self.transit("STAGE_COMPLETED")
        code, out, _ = run(["log", "--log", str(self.log)])
        self.assertEqual(code, 0)
        entries = json.loads(out)
        self.assertEqual(len(entries), 2)
        # 每条日志时间戳都由系统生成（_now_iso），且是 ISO 时间（非外部占位值）
        from datetime import datetime
        for e in entries:
            self.assertIsInstance(e["ts"], str)
            parsed = datetime.fromisoformat(e["ts"])
            delta = abs((datetime.now().astimezone() - parsed.astimezone()).total_seconds())
            self.assertLess(delta, 60, f"日志 ts 应接近当前时间，got {e['ts']!r}")

    def test_log_ts_always_system_generated(self):
        # 日志时间戳一律由系统生成，外部传入不再有覆盖入口（即使伪造 since 也不影响）
        args = self.base + ["--event", "STAGE_COMPLETED"]
        code, _, err = run(args)
        self.assertEqual(code, 0, err)
        entries = read_log(self.log)
        self.assertEqual(len(entries), 1)
        from datetime import datetime
        parsed = datetime.fromisoformat(entries[0]["ts"])
        delta = abs((datetime.now().astimezone() - parsed.astimezone()).total_seconds())
        self.assertLess(delta, 60)

    def test_batch_log_ts_always_system_generated(self):
        # batch 事件时间戳同样由系统生成，不受事件内 ts / --since 影响
        args = ["batch", "--state", str(self.state), "--config", str(self.cfg),
                "--log", str(self.log),
                "--events", json.dumps([{"event": "STAGE_COMPLETED"}])]
        code, _, err = run(args)
        self.assertEqual(code, 0, err)
        entries = read_log(self.log)
        self.assertEqual(len(entries), 1)
        from datetime import datetime
        parsed = datetime.fromisoformat(entries[0]["ts"])
        delta = abs((datetime.now().astimezone() - parsed.astimezone()).total_seconds())
        self.assertLess(delta, 60)

    def test_cr_round_only_logged_on_cr_rechecked(self):
        """方案 C1：CR_RECHECKED 日志带 cr_round（重审轮次），首轮 CR_SCANNED/CR_JUDGED 不含。"""
        self.drive_to("DEVELOPING")
        self.touch("u.md", "fix.md", "ev.md", "j.md")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        # 首轮 CR
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        self.transit("CR_JUDGED",
                     payload={"accepted_count": 1, "rejected_count": 0, "uncertain_count": 0,
                              "min_confidence": 1.0, "has_design_rework": False,
                              "fix_contract_path": "fix.md", "judge_report_path": "j.md"}, task="1.1")
        # 人工门批准 → 修复 → 重审
        self.transit("CR_APPROVED",
                     payload={"adjudications": [], "has_implement_fix": True,
                              "has_design_rework": False, "fix_contract_path": "fix.md"},
                     task="1.1")
        self.transit("REWRITE_COMPLETED",
                     payload={"fixed_has_major": False, "fixed_has_baseline_align": False}, task="1.1")
        self.transit("CR_RECHECKED",
                     payload={"cr_round": 1, "resolved_count": 1, "new_issue_count": 0,
                              "regression_detected": False, "quality_gate_evidence": "ev.md",
                              "judge_report_path": "j.md"},
                     task="1.1")

        entries = read_log(self.log)
        by_event = {e["event"]: e for e in entries if e.get("task_id") == "1.1"}
        # CR_SCANNED / CR_JUDGED / CR_APPROVED / REWRITE_COMPLETED 不含 cr_round
        for ev in ("CR_SCANNED", "CR_JUDGED", "CR_APPROVED", "REWRITE_COMPLETED"):
            self.assertNotIn("cr_round", by_event[ev], f"{ev} 不应带 cr_round")
        # CR_RECHECKED 带 cr_round
        self.assertEqual(by_event["CR_RECHECKED"]["cr_round"], 1)


class TestNext(StatectlTestCase):
    """statectl next — 读 state + config 计算下一推进动作，不解析 dev-tasks 依赖图。"""

    def run_next(self, task=None):
        args = ["next", "--state", str(self.state), "--config", str(self.cfg)]
        if task is not None:
            args += ["--task", task]
        code, out, err = run(args)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_empty_state_none(self):
        self.assertEqual(self.run_next()["action"], "NONE")

    def test_wait_gate(self):
        self.drive_to("DESIGN_REVIEW")
        result = self.run_next()
        self.assertEqual(result["action"], "WAIT_GATE")
        self.assertEqual(result["gate"], "DESIGN")

    def test_continue_incomplete_task(self):
        self.drive_to("DEVELOPING")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        result = self.run_next(task="1.1")
        self.assertEqual(result["action"], "CONTINUE")

    def _finish_simple(self, task):
        self.touch(f".task/done/order-{task}.md")
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task=task)
        self.transit("TASK_DOD_PASSED", payload={"complexity": "SIMPLE", "simple_gate": valid_simple_gate()},
                     task=task)
        self.transit("VERIFY_PASSED", task=task)

    def test_advance_task_auto_starts_next(self):
        # guarded: advance_task=true,1.1 DONE 且 1.2 未开始 → 自动开下一个
        self.drive_to("DEVELOPING")
        self._finish_simple("1.1")
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.2")  # 1.2 已开始未完成
        result = self.run_next(task="1.2")
        self.assertEqual(result["action"], "CONTINUE")
        # 让 1.2 也 DONE → 全部 DONE,但 advance_accept=false(guarded) → 询问进验收
        self._finish_simple("1.2")
        result = self.run_next(task="1.2")
        self.assertEqual(result["action"], "ASK_ADVANCE_TO_ACCEPT")

    def test_advance_accept_true_auto(self):
        # autonomous: advance_accept=true → 全部任务 DONE 后自动进验收
        self.drive_to("DEVELOPING")
        write_config(self.cfg, automation={"advance_stage": True, "advance_task": True,
                                           "advance_accept": True, "advance_summary": True})
        self._finish_simple("1.1")
        self._finish_simple("1.2")
        result = self.run_next(task="1.2")
        self.assertEqual(result["action"], "ADVANCE_TO_ACCEPT")


class TestReviewDispatch(StatectlTestCase):
    """statectl review-dispatch — 读 config cr.levels + severity 计算重审派发维度（∩ 维度池）。"""

    def run_dispatch(self, severity):
        code, out, err = run(["review-dispatch", "--config", str(self.cfg), "--severity", severity])
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def _write_pool(self, dimensions):
        write_config(self.cfg, cr={
            "limits": {"fix_max": 3}, "capabilities": {"simple_skip_cr": True},
            "levels": {"zero": {"auto_confirm": True},
                       "minor": {"auto_fix": False, "recheck": []},
                       "major": {"recheck": ["design", "security", "performance"]}},
            "review": {"dimensions": dimensions},
            "quality": {"judge": {"min_confidence": 0.85}}})

    def test_major_dispatches_all_dimensions(self):
        # 默认池全开：major.recheck=[design,security,performance], IMPLEMENTATION 恒跑
        result = self.run_dispatch("MAJOR")
        self.assertEqual(result["reviewers"],
                         ["implementation", "design", "security", "performance"])

    def test_minor_only_implementation(self):
        # guarded: minor.recheck=[] → 仅 IMPLEMENTATION
        result = self.run_dispatch("MINOR")
        self.assertEqual(result["reviewers"], ["implementation"])

    def test_invalid_severity_rejected(self):
        code, out, err = run(["review-dispatch", "--config", str(self.cfg), "--severity", "BOGUS"])
        self.assertEqual(code, 0)
        self.assertIn("error", json.loads(out))

    def test_pool_narrows_major_recheck(self):
        # 池停用 security → major.recheck ∩ 池 = [design, performance]，reason 显式记录
        self._write_pool(["implementation", "design", "performance"])
        result = self.run_dispatch("MAJOR")
        self.assertEqual(result["reviewers"], ["implementation", "design", "performance"])
        self.assertIn("池停用跳过 ['security']", result["reason"])

    def test_pool_without_security_drops_security(self):
        self._write_pool(["implementation", "design"])
        result = self.run_dispatch("MAJOR")
        self.assertEqual(result["reviewers"], ["implementation", "design"])
        self.assertIn("security", result["reason"])

    def test_pool_narrows_minor(self):
        # minor.recheck=[] ∩ 池 = [] → 仅 IMPLEMENTATION
        self._write_pool(["implementation", "design"])
        result = self.run_dispatch("MINOR")
        self.assertEqual(result["reviewers"], ["implementation"])


class TestRecheckCapability(StatectlTestCase):
    """cr.capabilities.recheck：false = 只审核一次（修复后直接确认进复验）；true（默认）进重审。"""

    def _write_cr(self, recheck):
        write_config(self.cfg, cr={
            "limits": {"fix_max": 3}, "capabilities": {"simple_skip_cr": True, "recheck": recheck},
            "levels": {"zero": {"auto_confirm": True},
                       "minor": {"auto_fix": False, "recheck": []},
                       "major": {"recheck": ["design", "security", "performance"]}},
            "review": {"dimensions": ["implementation", "design", "security", "performance"]},
            "quality": {"judge": {"min_confidence": 0.85}}})

    def _to_cr_fixing(self):
        self.drive_to("DEVELOPING")
        self.touch("u.md", "fix.md", "j.md")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        self.transit("CR_JUDGED",
                     payload={"accepted_count": 1, "rejected_count": 0, "uncertain_count": 0,
                              "min_confidence": 1.0, "has_design_rework": False,
                              "fix_contract_path": "fix.md", "judge_report_path": "j.md"}, task="1.1")
        self.transit("CR_APPROVED",
                     payload={"adjudications": [], "has_implement_fix": True,
                              "has_design_rework": False, "fix_contract_path": "fix.md"},
                     task="1.1")

    def test_recheck_disabled_confirm_after_rewrite(self):
        # recheck=false → 只审核一次：修复后带质量门证据直接 CR_PASSED，不进 CR_RECHECKING
        self._write_cr(False)
        self._to_cr_fixing()
        self.touch("ev.md")
        code, out, err = self.transit("REWRITE_COMPLETED",
                                      payload={"fixed_has_major": False, "fixed_has_baseline_align": False,
                                               "quality_gate_evidence": "ev.md"}, task="1.1")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["decision"], "CONFIRM_CR")
        self.assertEqual(result["task_state"], "CR_PASSED")

    def test_recheck_disabled_missing_evidence_rejected(self):
        # 只审一次但缺质量门证据 → 无合法转换（不得无证据放行）
        self._write_cr(False)
        self._to_cr_fixing()
        code, _, err = self.transit("REWRITE_COMPLETED",
                                    payload={"fixed_has_major": False, "fixed_has_baseline_align": False},
                                    task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("无合法转换", err)

    def test_recheck_enabled_enters_rechecking(self):
        # recheck=true（默认）→ 修复后进 CR_RECHECKING 重审
        self._write_cr(True)
        self._to_cr_fixing()
        code, out, err = self.transit("REWRITE_COMPLETED",
                                      payload={"fixed_has_major": False, "fixed_has_baseline_align": False},
                                      task="1.1")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["decision"], "CR_RECHECK")
        self.assertEqual(result["task_state"], "CR_RECHECKING")

    def test_rewrite_completed_missing_fixed_fields_rejected(self):
        # C 收尾护栏：fixed_has_major / fixed_has_baseline_align 是 schema 必填，漏填被硬拒
        # （否则 policy 静默回退到恒重审，C 机制形同虚设且无迹可察）
        self._write_cr(True)
        self._to_cr_fixing()
        code, _, err = self.transit("REWRITE_COMPLETED", task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("缺必填字段", err)
        self.assertIn("fixed_has_major", err)

    def _write_cr_minor_confirm(self, minor_confirm=True):
        write_config(self.cfg, cr={
            "limits": {"fix_max": 3},
            "capabilities": {"simple_skip_cr": True, "recheck": True,
                             "minor_fix_auto_confirm": minor_confirm},
            "levels": {"zero": {"auto_confirm": True},
                       "minor": {"auto_fix": False, "recheck": []},
                       "major": {"recheck": ["design", "security", "performance"]}},
            "review": {"dimensions": ["implementation", "design", "security", "performance"]},
            "quality": {"judge": {"min_confidence": 0.85}}})

    def test_minor_fix_auto_confirm_with_evidence(self):
        # recheck=true + 纯 MINOR+IMPLEMENT_FIX 修复 + 质量门证据 → 跳重审直接 CR_PASSED
        self._write_cr_minor_confirm(True)
        self._to_cr_fixing()
        self.touch("ev.md")
        code, out, err = self.transit("REWRITE_COMPLETED",
                                      payload={"fixed_has_major": False, "fixed_has_baseline_align": False,
                                               "quality_gate_evidence": "ev.md"}, task="1.1")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["decision"], "CONFIRM_CR")
        self.assertEqual(result["task_state"], "CR_PASSED")

    def test_major_fix_force_recheck(self):
        # 修复含 MAJOR → 即使 minor_fix_auto_confirm=true 也强制重审
        self._write_cr_minor_confirm(True)
        self._to_cr_fixing()
        self.touch("ev.md")
        code, out, err = self.transit("REWRITE_COMPLETED",
                                      payload={"fixed_has_major": True, "fixed_has_baseline_align": False,
                                               "quality_gate_evidence": "ev.md"}, task="1.1")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["decision"], "CR_RECHECK")
        self.assertEqual(result["task_state"], "CR_RECHECKING")

    def test_minor_auto_confirm_disabled_rechecks(self):
        # minor_fix_auto_confirm=false → 所有修复都重审（保守）
        self._write_cr_minor_confirm(False)
        self._to_cr_fixing()
        self.touch("ev.md")
        code, out, err = self.transit("REWRITE_COMPLETED",
                                      payload={"fixed_has_major": False, "fixed_has_baseline_align": False,
                                               "quality_gate_evidence": "ev.md"}, task="1.1")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["decision"], "CR_RECHECK")
        self.assertEqual(result["task_state"], "CR_RECHECKING")


class TestDerivedEvents(StatectlTestCase):
    """批 1：事件集从 model transitions 派生（禁止硬编码）的回归防线。"""

    def test_task_events_derived_matches_transitions(self):
        from adapters.statectl import _task_events
        from engine import state_machine as sm
        derived = _task_events(sm.load_model())
        expected = {"TASK_STARTED", "TASK_DOD_PASSED", "PLAN_READY", "PLAN_VALIDATED",
                    "PLAN_APPROVED", "CR_APPROVED", "REWRITE_COMPLETED", "VERIFY_PASSED",
                    "VERIFY_FAILED", "CR_SCANNED", "CR_JUDGED", "CR_RECHECKED", "TASK_CR_PASSED"}
        self.assertEqual(derived, expected)
        self.assertNotIn("REWORK_STARTED", derived, "REWORK_STARTED 是双 scope 事件，应被显式分支接管")

    def test_rework_started_routes_to_milestone_branch(self):
        # 双 scope 事件必须走里程碑回退分支（受影响任务回 TODO + 里程碑按层级）
        self.drive_to("DEVELOPING")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        code, _, err = self.transit("REWORK_STARTED",
                                    payload={"level": "IMPLEMENTATION", "affected_tasks": ["1.1"]})
        self.assertEqual(code, 0, err)
        state = load_state(self.state)
        self.assertEqual(state["tasks"]["1.1"]["state"], "TODO")
        self.assertEqual(state["milestone"]["phase"], "DEVELOPING")  # 实现级：phase 不变

    def test_implicit_decision_plan_validated(self):
        # PLAN_VALIDATED 无决策矩阵，走 implicit_decisions → VALIDATE_PLAN
        self.drive_to("DEVELOPING")
        self.touch("p.md")
        self.transit("TASK_STARTED", payload={"complexity": "COMPLEX"}, task="1.1")
        code, _, err = self.transit("PLAN_READY", payload={"plan_path": "p.md"}, task="1.1")
        self.assertEqual(code, 0, err)
        code, out, err = self.transit("PLAN_VALIDATED", payload={"result": "PASS"}, task="1.1")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["decision"], "VALIDATE_PLAN")
        self.assertEqual(result["task_state"], "PLAN_CONFIRMED")


class TestAddTask(StatectlTestCase):
    """补充任务（rework 变体 B）：当前需求内新增子任务，可能牵动设计。"""

    def test_add_task_pure_append_starts_directly(self):
        # 纯追加：TASK_STARTED 直接开始新任务，不影响既有任务
        self.drive_to("DEVELOPING")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        code, _, err = self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.3")
        self.assertEqual(code, 0, err)
        state = load_state(self.state)
        self.assertEqual(state["tasks"]["1.3"]["state"], "CODING")
        self.assertEqual(state["tasks"]["1.1"]["state"], "CODING")  # 既有任务不受影响

    def test_add_task_design_rework_falls_back(self):
        # 牵动设计：REWORK_STARTED{level=DESIGN} → 里程碑回退 ANALYZING；STAGE_COMPLETED 后进 DESIGN_REVIEW 设门
        self.drive_to("DEVELOPING")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        code, _, err = self.transit("REWORK_STARTED",
                                    payload={"level": "DESIGN", "affected_tasks": ["1.3"]})
        self.assertEqual(code, 0, err)
        state = load_state(self.state)
        self.assertEqual(state["milestone"]["phase"], "ANALYZING")   # 设计级回退到分析
        self.assertEqual(state["tasks"]["1.3"]["state"], "TODO")     # 新任务回 TODO
        self.assertIsNone(state["milestone"]["pending_gate"])        # 回退后无门，等阶段 2 完成
        # 重做阶段 2 → STAGE_COMPLETED → DESIGN_REVIEW + DESIGN 门
        code, _, err = self.transit("STAGE_COMPLETED")
        self.assertEqual(code, 0, err)
        state = load_state(self.state)
        self.assertEqual(state["milestone"]["phase"], "DESIGN_REVIEW")
        self.assertEqual(state["milestone"]["pending_gate"]["type"], "DESIGN")

    def test_add_task_design_rework_keeps_existing_untouched(self):
        # 设计回退：affected_tasks 只列新任务时，既有任务状态保持
        self.drive_to("DEVELOPING")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        code, _, err = self.transit("REWORK_STARTED",
                                    payload={"level": "DESIGN", "affected_tasks": ["1.3"]})
        self.assertEqual(code, 0, err)
        state = load_state(self.state)
        self.assertEqual(state["tasks"]["1.1"]["state"], "CODING")  # 既有任务不受影响
        self.assertEqual(state["milestone"]["phase"], "ANALYZING")


class TestPlanConfirmedLifecycle(StatectlTestCase):
    """plan_confirmed 生命周期：PLAN_CONFIRMED 置位，REWORK 作废清除。"""

    def test_rework_clears_plan_confirmed(self):
        self.drive_to("DEVELOPING")
        self.touch("p.md")
        self.transit("TASK_STARTED", payload={"complexity": "COMPLEX"}, task="1.1")
        self.transit("PLAN_READY", payload={"plan_path": "p.md"}, task="1.1")
        code, out, _ = self.transit("PLAN_VALIDATED", payload={"result": "PASS"}, task="1.1")
        self.assertEqual(code, 0)
        self.assertTrue(load_state(self.state)["tasks"]["1.1"]["plan_confirmed"])
        # rework 实现级：受影响任务回 TODO，plan_confirmed 清除（防脏标记）
        code, _, err = self.transit("REWORK_STARTED",
                                    payload={"level": "IMPLEMENTATION", "affected_tasks": ["1.1"]})
        self.assertEqual(code, 0, err)
        state = load_state(self.state)
        self.assertEqual(state["tasks"]["1.1"]["state"], "TODO")
        self.assertNotIn("plan_confirmed", state["tasks"]["1.1"])


class TestPayloadRefValidation(StatectlTestCase):
    """statectl 硬校验：payload 引用的产物文件必须存在（防抄模板/虚报产物）。"""

    def test_missing_evidence_path_rejected(self):
        # 产物文件不存在 → 拒绝，任务停留在 CODING（不推进）
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, _, err = self.transit("TASK_DOD_PASSED",
                                    payload={"complexity": "SIMPLE", "simple_gate": valid_simple_gate()}, task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("产物文件不存在", err)
        self.assertEqual(load_state(self.state)["tasks"]["1.1"]["state"], "CODING")

    def test_existing_evidence_path_accepted(self):
        self.touch(".task/done/order-1.1.md")
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task="1.1")
        code, out, err = self.transit("TASK_DOD_PASSED",
                                      payload={"complexity": "SIMPLE", "simple_gate": valid_simple_gate()}, task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["decision"], "SKIP_CR")

    def test_missing_quality_gate_evidence_rejected(self):
        # CR_JUDGED 的 quality_gate_evidence 必须存在（防虚报质量门）
        self.drive_to("DEVELOPING")
        self.touch("u.md", "j.md")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        code, _, err = self.transit("CR_JUDGED",
                                    payload={"accepted_count": 0, "rejected_count": 0, "uncertain_count": 0,
                                             "min_confidence": 1.0, "has_design_rework": False,
                                             "quality_gate_evidence": "ev.md",
                                             "judge_report_path": "j.md"}, task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("quality_gate_evidence", err)

    def test_missing_judge_report_path_rejected(self):
        # CR_JUDGED 必须携带 judge_report_path（judge.md 存在性由 statectl 校验）
        self.drive_to("DEVELOPING")
        self.touch("u.md")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        code, _, err = self.transit("CR_JUDGED",
                                    payload={"accepted_count": 0, "rejected_count": 0, "uncertain_count": 0,
                                             "min_confidence": 1.0, "has_design_rework": False,
                                             "quality_gate_evidence": "ev.md"}, task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("judge_report_path", err)

    def test_nonexistent_judge_report_path_rejected(self):
        # judge_report_path 指向不存在的 judge.md → 拒绝（防虚报裁决产物）
        self.drive_to("DEVELOPING")
        self.touch("u.md", "ev.md")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        code, _, err = self.transit("CR_JUDGED",
                                    payload={"accepted_count": 0, "rejected_count": 0, "uncertain_count": 0,
                                             "min_confidence": 1.0, "has_design_rework": False,
                                             "quality_gate_evidence": "ev.md",
                                             "judge_report_path": "review/1.1/judge.md"}, task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("judge_report_path", err)

    def test_existing_judge_report_path_accepted(self):
        # judge_report_path 指向真实存在的 judge.md → 通过（零问题直通 CR_PASSED）
        self.drive_to("DEVELOPING")
        self.touch("u.md", "ev.md", "j.md")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        code, out, err = self.transit("CR_JUDGED",
                                      payload={"accepted_count": 0, "rejected_count": 0, "uncertain_count": 0,
                                               "min_confidence": 1.0, "has_design_rework": False,
                                               "quality_gate_evidence": "ev.md",
                                               "judge_report_path": "j.md"}, task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["task_state"], "CR_PASSED")


class TestMode(StatectlTestCase):
    """mode 管道：首次 transit 烘焙（标志 > 配置 > single），后续从状态读，标志可临时覆盖。"""

    def test_mode_default_single_baked(self):
        # 无 --mode、配置无 mode → single 烘焙进状态
        code, out, err = self.transit("STAGE_COMPLETED")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["mode"], "single")
        self.assertEqual(load_state(self.state)["mode"], "single")

    def test_mode_flag_persists_on_fresh_state(self):
        # 首次 transit 带 --mode dual → 烘焙进状态
        code, out, _ = run(self.base + ["--event", "STAGE_COMPLETED", "--mode", "dual"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mode"], "dual")
        self.assertEqual(load_state(self.state)["mode"], "dual")

    def test_mode_from_state_on_subsequent(self):
        # 烘焙 dual 后，后续命令不带 flag → 从状态读 dual
        run(self.base + ["--event", "STAGE_COMPLETED", "--mode", "dual"])
        code, out, _ = self.transit("STAGE_COMPLETED")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mode"], "dual")
        self.assertEqual(load_state(self.state)["mode"], "dual")

    def test_mode_flag_overrides_state_without_persist(self):
        # 状态已是 single，命令带 --mode dual → 本次 dual，状态仍 single（一次性覆盖不覆写）
        self.transit("STAGE_COMPLETED")
        code, out, _ = run(self.base + ["--event", "STAGE_COMPLETED", "--mode", "dual"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mode"], "dual")
        self.assertEqual(load_state(self.state)["mode"], "single")


class TestDualDispatch(StatectlTestCase):
    """mode=dual：设计通过进 DISPATCHING，下发完成进 DEVELOPING；单仓直接进 DEVELOPING。"""

    def test_single_approval_enters_developing_directly(self):
        # 无 mode（单仓默认）→ 直接 DEVELOPING（向后兼容）
        self.drive_to("DESIGN_REVIEW")
        code, _, err = self.transit("DESIGN_APPROVED")
        self.assertEqual(code, 0, err)
        self.assertEqual(load_state(self.state)["milestone"]["phase"], "DEVELOPING")

    def test_dual_approval_enters_dispatching(self):
        # DESIGN_APPROVED 带 mode: dual → 进 DISPATCHING
        self.drive_to("DESIGN_REVIEW")
        code, _, err = self.transit("DESIGN_APPROVED", payload={"mode": "dual"})
        self.assertEqual(code, 0, err)
        self.assertEqual(load_state(self.state)["milestone"]["phase"], "DISPATCHING")

    def test_dual_dispatch_completed_enters_developing(self):
        self.drive_to("DESIGN_REVIEW")
        self.transit("DESIGN_APPROVED", payload={"mode": "dual"})
        code, _, err = self.transit("DISPATCH_COMPLETED")
        self.assertEqual(code, 0, err)
        self.assertEqual(load_state(self.state)["milestone"]["phase"], "DEVELOPING")


class TestBatch(StatectlTestCase):
    """S5：statectl batch — 无分支事件链原子批量提交（状态写一次、日志逐事件）。"""

    def run_batch(self, events):
        return run(["batch", "--state", str(self.state), "--config", str(self.cfg),
                    "--log", str(self.log), "--events", json.dumps(events)])

    def test_batch_applies_design_approve_then_task_start(self):
        """跨 scope 链：里程碑门通过 + 任务开始，一次提交完成。"""
        self.drive_to("DESIGN_REVIEW")
        events = [
            {"event": "DESIGN_APPROVED"},
            {"event": "TASK_STARTED", "task": "1.1", "payload": {"complexity": "NORMAL"}},
        ]
        code, out, err = self.run_batch(events)
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["phase"], "DEVELOPING")
        self.assertEqual(result["results"][1]["task_state"], "CODING")
        state = load_state(self.state)
        self.assertEqual(state["milestone"]["phase"], "DEVELOPING")
        self.assertEqual(state["tasks"]["1.1"]["state"], "CODING")
        self.assertEqual(state["tasks"]["1.1"]["complexity"], "NORMAL")
        self.assertEqual(len(read_log(self.log)), 2 + 2)  # 2 drive_to + 2 batch

    def test_batch_task_close_chain_reaches_done(self):
        """CR 通过后的收尾链：TASK_CR_PASSED + VERIFY_PASSED 一次批量到 DONE。"""
        self.drive_to("DEVELOPING")
        self.touch("u.md", "ev.md", "j.md")
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        code, out, _ = self.transit("CR_JUDGED",
                                    payload={"accepted_count": 0, "rejected_count": 0, "uncertain_count": 0,
                                             "min_confidence": 1.0, "has_design_rework": False,
                                             "quality_gate_evidence": "ev.md",
                                             "judge_report_path": "j.md"}, task="1.1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["task_state"], "CR_PASSED")
        events = [
            {"event": "TASK_CR_PASSED", "task": "1.1"},
            {"event": "VERIFY_PASSED", "task": "1.1"},
        ]
        code, out, err = self.run_batch(events)
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["applied"], 2)
        self.assertEqual(result["results"][0]["task_state"], "VERIFYING")
        self.assertEqual(result["results"][1]["task_state"], "DONE")
        self.assertEqual(load_state(self.state)["tasks"]["1.1"]["state"], "DONE")
        # 日志逐事件记录：3 drive_to + 4 单事件 + 2 batch
        self.assertEqual(len(read_log(self.log)), 9)

    def test_batch_atomic_reject_preserves_prior_state(self):
        """任一事件失败整批不写：状态与日志保持批前值。"""
        self.drive_to("DESIGN_REVIEW")
        before = load_state(self.state)
        before_log = len(read_log(self.log))
        events = [
            {"event": "DESIGN_APPROVED"},
            {"event": "TASK_STARTED", "task": "1.1", "payload": {"complexity": "BIG"}},  # 非法复杂度
        ]
        code, _, err = self.run_batch(events)
        self.assertEqual(code, 1)
        self.assertIn("error", err)
        self.assertEqual(load_state(self.state), before)   # 状态未变
        self.assertEqual(len(read_log(self.log)), before_log)  # 日志未追加

    def test_batch_rejects_non_list_events(self):
        code, _, err = self.run_batch("not-a-list")
        self.assertEqual(code, 1)
        self.assertIn("error", err)


class TestBaselineAlign(StatectlTestCase):
    """BASELINE_ALIGN 闭环：CR_APPROVED 捕获基线指纹 → REWRITE_COMPLETED 校验基线真改（防跳步）。"""

    def _touch_baseline(self, content="design baseline v1\n"):
        (self.root / "design-baseline.md").write_text(content, encoding="utf-8")

    def _drive_baseline_fixing(self):
        """任务 1.1 经 CR_APPROVED + has_baseline_align（无实现修复）进 CR_FIXING。"""
        self.drive_to("DEVELOPING")
        self.touch("u.md", "fix.md", "j.md")
        self._touch_baseline()
        self.transit("TASK_STARTED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("TASK_DOD_PASSED", payload={"complexity": "NORMAL"}, task="1.1")
        self.transit("CR_SCANNED",
                     payload={"report_complete": True, "reviewer_count": 1, "unified_report_path": "u.md"},
                     task="1.1")
        code, _, err = self.transit("CR_JUDGED",
                                    payload={"accepted_count": 1, "rejected_count": 0, "uncertain_count": 0,
                                             "min_confidence": 1.0, "has_design_rework": False,
                                             "has_baseline_align": True,
                                             "fix_contract_path": "fix.md", "judge_report_path": "j.md"},
                                    task="1.1")
        self.assertEqual(code, 0, err)
        return self.transit("CR_APPROVED",
                            payload={"adjudications": [], "has_implement_fix": False,
                                     "has_design_rework": False, "has_baseline_align": True,
                                     "fix_contract_path": "fix.md"}, task="1.1")

    def test_baseline_align_routes_to_fixing_and_tracks(self):
        # CR_APPROVED 带 has_baseline_align → baseline_align 转换进 CR_FIXING，并捕获基线指纹
        code, out, err = self._drive_baseline_fixing()
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["task_state"], "CR_FIXING")
        t = load_state(self.state)["tasks"]["1.1"]
        self.assertTrue(t["baseline_align"])
        self.assertIn("baseline_fp_before", t)

    def test_baseline_rewrite_without_baseline_change_rejected(self):
        # 防跳步：经 BASELINE_ALIGN 修复但 design-baseline 未被实际修改 → 拒绝
        self._drive_baseline_fixing()
        code, _, err = self.transit("REWRITE_COMPLETED",
                                    payload={"fixed_has_major": False, "fixed_has_baseline_align": True},
                                    task="1.1")
        self.assertEqual(code, 1)
        self.assertIn("design-baseline.md", err)

    def test_baseline_rewrite_with_baseline_change_passes(self):
        # 基线真改 → REWRITE_COMPLETED 通过，标记 baseline_updated
        self._drive_baseline_fixing()
        self._touch_baseline("design baseline v2 (sync)\n")
        code, out, err = self.transit("REWRITE_COMPLETED",
                                      payload={"fixed_has_major": False, "fixed_has_baseline_align": True},
                                      task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["task_state"], "CR_RECHECKING")
        self.assertTrue(load_state(self.state)["tasks"]["1.1"]["baseline_updated"])


class TestInitTasks(StatectlTestCase):
    """init-tasks：阶段4入口全量登记任务（dev-tasks → state；all_done 按完整计划集判定）。"""

    TASKS9 = [{"id": f"1.{i}", "title": f"任务 {i}", "complexity": "SIMPLE"} for i in range(1, 10)]

    def init_tasks(self, tasks):
        return run(["init-tasks", "--state", str(self.state), "--config", str(self.cfg),
                    "--log", str(self.log), "--tasks", json.dumps(tasks)])

    def complete_simple(self, tid):
        self.touch(f".task/done/order-{tid}.md")
        gate = valid_simple_gate()
        gate["evidence_path"] = f".task/done/order-{tid}.md"
        self.transit("TASK_STARTED", payload={"complexity": "SIMPLE"}, task=tid)
        self.transit("TASK_DOD_PASSED", payload={"complexity": "SIMPLE", "simple_gate": gate}, task=tid)
        code, _, err = self.transit("VERIFY_PASSED", task=tid)
        if code != 0:
            self.fail(f"complete_simple({tid}) 失败: {err}")

    def test_init_tasks_registers_all_tasks(self):
        self.drive_to("DEVELOPING")
        code, out, err = self.init_tasks(self.TASKS9)
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["event"], "INIT_TASKS")
        self.assertEqual(result["task_count"], 9)
        state = load_state(self.state)
        self.assertEqual(len(state["tasks"]), 9)
        for tid in [f"1.{i}" for i in range(1, 10)]:
            self.assertEqual(state["tasks"][tid]["state"], "TODO")
            self.assertEqual(state["tasks"][tid]["complexity"], "SIMPLE")
        self.assertEqual(state["tasks"]["1.1"]["title"], "任务 1")
        # 审计日志：INIT_TASKS 记录 task_count，且事件在校验事件集内（日志一致性不违规）
        entries = read_log(self.log)
        self.assertEqual(entries[-1]["event"], "INIT_TASKS")
        self.assertEqual(entries[-1]["task_count"], 9)

    def test_init_tasks_rejected_outside_developing(self):
        # 空态（DISCUSSING）→ 拒绝，不写状态
        code, _, err = self.init_tasks(self.TASKS9)
        self.assertEqual(code, 1)
        self.assertIn("仅限阶段4开发期", err)
        self.assertEqual(load_state(self.state)["tasks"], {})

    def test_init_tasks_rejected_after_registered(self):
        self.drive_to("DEVELOPING")
        self.init_tasks(self.TASKS9)
        before = load_state(self.state)
        code, _, err = self.init_tasks([{"id": "2.1", "complexity": "NORMAL"}])
        self.assertEqual(code, 1)
        self.assertIn("任务已登记", err)
        self.assertEqual(load_state(self.state), before)  # 状态未变

    def test_init_tasks_rejects_bad_id(self):
        self.drive_to("DEVELOPING")
        code, _, err = self.init_tasks([{"id": "1", "complexity": "NORMAL"}])
        self.assertEqual(code, 1)
        self.assertIn("任务 ID 非法", err)

    def test_init_tasks_rejects_bad_complexity(self):
        self.drive_to("DEVELOPING")
        code, _, err = self.init_tasks([{"id": "1.1", "complexity": "HARD"}])
        self.assertEqual(code, 1)
        self.assertIn("complexity 非法", err)

    def test_partial_done_does_not_advance_to_accept(self):
        # 核心回归：dev-tasks 规划 1.1–1.9，只完成 1.1–1.5 → 不得判定"全部任务 DONE"进验收
        self.drive_to("DEVELOPING")
        self.init_tasks(self.TASKS9)
        for i in range(1, 6):
            self.complete_simple(f"1.{i}")
        code, out, err = run(["next", "--state", str(self.state), "--config", str(self.cfg),
                              "--task", "1.5"])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["action"], "START_NEXT_TASK")  # 还有 1.6–1.9 未启动
        self.assertNotIn(result["action"], ("ADVANCE_TO_ACCEPT", "ASK_ADVANCE_TO_ACCEPT"))

    def test_all_done_advances_to_accept(self):
        # 对照：9/9 全部 DONE 才进验收
        self.drive_to("DEVELOPING")
        self.init_tasks(self.TASKS9)
        for i in range(1, 10):
            self.complete_simple(f"1.{i}")
        code, out, err = run(["next", "--state", str(self.state), "--config", str(self.cfg),
                              "--task", "1.9"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["action"], "ASK_ADVANCE_TO_ACCEPT")


if __name__ == "__main__":
    unittest.main()
