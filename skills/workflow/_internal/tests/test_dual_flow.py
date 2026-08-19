# ============================================================
# 双仓端到端 harness — 验证 dispatch 落地的执行仓状态能被内核驱动
# 覆盖：arch-docs 里程碑 dual 路径 → dispatch 落地 → 执行仓任务事件 → report 回 arch-docs
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

from adapters.dispatchctl import main as dispatchctl_main
from adapters.statectl import load_state, main as statectl_main, write_state


def run_statectl(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = statectl_main(args)
    return code, out.getvalue(), err.getvalue()


def run_dispatchctl(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = dispatchctl_main(args)
    return code, out.getvalue(), err.getvalue()


class DualFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arch = Path(self.tmp.name) / "arch"
        self.unit = Path(self.tmp.name) / "unit-repo"
        self.unit.mkdir()
        self.req = "order/2026-08-11-x"
        self.arch_worktree = (self.arch / "docs" / "discuss" / self.req / ".task")
        self.arch_state = (self.arch_worktree / "state" / "workflow-state.yml")
        self.arch_log = (self.arch_worktree / "state" / "transition.log")
        self.cfg = (self.arch / ".claude" / "workflow" / "config.yml")
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text("version: 2\nmode: dual\n", encoding="utf-8")
        self.unit_cfg = self.unit / ".claude" / "workflow" / "config.yml"
        self.unit_worktree = (self.unit / "docs" / "discuss" / self.req / ".task")
        self.unit_state = (self.unit_worktree / "state" / "workflow-state.yml")
        self.unit_log = (self.unit_worktree / "state" / "transition.log")
        # arch-docs 初始状态（阶段 3 设计门待审，mode dual）
        write_state(self.arch_state, {"milestone": {"phase": "DESIGN_REVIEW", "lifecycle": "ACTIVE",
                                                    "pending_gate": {"type": "DESIGN", "target_task": None},
                                                    "blocker": None, "mode": "dual"}, "tasks": {}})
        self.base = ["transit", "--state", str(self.arch_state), "--config", str(self.cfg),
                     "--log", str(self.arch_log)]

    def tearDown(self):
        self.tmp.cleanup()

    def arch_transit(self, event, payload=None):
        args = self.base + ["--event", event]
        if payload is not None:
            args += ["--payload", json.dumps(payload)]
        return run_statectl(args)

    def unit_transit(self, event, payload=None, task=None):
        args = ["transit", "--state", str(self.unit_state), "--config", str(self.unit_cfg),
                "--log", str(self.unit_log), "--event", event]
        if payload is not None:
            args += ["--payload", json.dumps(payload)]
        if task is not None:
            args += ["--task", task]
        return run_statectl(args)


class TestDualEndToEnd(DualFlowTestCase):
    def test_full_dual_flow(self):
        # ① 设计通过（dual）→ DISPATCHING
        code, out, err = self.arch_transit("DESIGN_APPROVED", {"mode": "dual"})
        self.assertEqual(code, 0, err)
        self.assertEqual(load_state(self.arch_state)["milestone"]["phase"], "DISPATCHING")

        # ② dispatch 落地单元工作包
        units = [{"id": "trade", "repo": str(self.unit),
                  "tasks": [{"id": "1.1", "title": "t", "complexity": "NORMAL"}],
                  "dev_tasks": "# trade", "design_package": "## MQ\ntable"}]
        code, out, err = run_dispatchctl(["dispatch", "--arch-docs-state", str(self.arch_state),
                                          "--arch-docs-root", str(self.arch), "--config", str(self.cfg),
                                          "--units", json.dumps(units)])
        self.assertEqual(code, 0, err)
        self.assertTrue(self.unit_state.exists())
        self.assertEqual(load_state(self.arch_state)["units"]["trade"]["dispatched"], True)

        # ③ 全部下发完成 → DEVELOPING
        code, out, err = self.arch_transit("DISPATCH_COMPLETED")
        self.assertEqual(code, 0, err)
        self.assertEqual(load_state(self.arch_state)["milestone"]["phase"], "DEVELOPING")

        # ④ 执行仓内任务事件（内核驱动 dispatch 落地的状态）→ CODING
        code, out, err = self.unit_transit("TASK_STARTED", {"complexity": "NORMAL"}, task="1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(load_state(self.unit_state)["tasks"]["1.1"]["state"], "CODING")

        # ⑤ 执行仓上报契约变更 → arch-docs reports 台账
        code, out, err = run_dispatchctl(["report", "--unit-worktree", str(self.unit_worktree),
                                          "--arch-docs-root", str(self.arch), "--unit", "trade",
                                          "--content", "## 契约变更\nRPC 签名变化"])
        self.assertEqual(code, 0, err)
        report = Path(json.loads(out)["report"])
        self.assertTrue(report.exists())
        # arch-docs 收报告后走 rework → 里程碑回退 DESIGN_REVIEW（阶段 3 重审）
        code, out, err = self.arch_transit("REWORK_STARTED",
                                           {"level": "DESIGN", "affected_tasks": ["1.1"]})
        self.assertEqual(code, 0, err)
        self.assertEqual(load_state(self.arch_state)["milestone"]["phase"], "ANALYZING")


if __name__ == "__main__":
    unittest.main()
