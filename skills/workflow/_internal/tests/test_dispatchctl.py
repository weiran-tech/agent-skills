# ============================================================
# adapters/dispatchctl.py 测试 — 双仓下发确定性部分
# 覆盖：工作包落地（state/dev-tasks/design-package/config/arch-docs-path）+ arch-docs 台账回写
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

from adapters.dispatchctl import main
from adapters.statectl import load_state, write_state


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class DispatchctlTestCase(unittest.TestCase):
    """公共 setUp：arch-docs 临时仓 + 一个执行仓临时目录。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arch = Path(self.tmp.name) / "arch"
        self.unit = Path(self.tmp.name) / "unit-repo"
        self.unit.mkdir()
        self.req = "order/2026-08-11-x"
        self.state = (self.arch / "docs" / "discuss" / self.req / ".task" / "state" / "workflow-state.yml")
        write_state(self.state, {"milestone": {"phase": "DISPATCHING", "lifecycle": "ACTIVE",
                                               "pending_gate": None, "blocker": None, "mode": "dual"},
                                 "tasks": {}})
        cfg = (self.arch / ".claude" / "workflow" / "config.yml")
        cfg.parent.mkdir(parents=True)
        cfg.write_text("version: 2\nmode: dual\n")
        self.cfg = cfg
        self.units = [{"id": "trade", "repo": str(self.unit),
                       "tasks": [{"id": "1.1", "title": "t", "complexity": "NORMAL"}],
                       "dev_tasks": "# trade tasks", "design_package": "## MQ\ntable"}]

    def tearDown(self):
        self.tmp.cleanup()

    def dispatch(self, units=None):
        return run(["dispatch", "--arch-docs-state", str(self.state),
                    "--arch-docs-root", str(self.arch), "--config", str(self.cfg),
                    "--units", json.dumps(units if units is not None else self.units)])


class TestDispatch(DispatchctlTestCase):
    def test_dispatch_creates_work_package(self):
        code, out, err = self.dispatch()
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["requirement"], self.req)
        self.assertEqual(result["mode"], "dual")
        self.assertEqual(result["units_dispatched"], 1)
        wt = self.unit / "docs" / "discuss" / self.req / ".task"
        # 五件套：state / dev-tasks / design-package / config / arch-docs-path
        self.assertTrue((wt / "state" / "workflow-state.yml").exists())
        self.assertEqual((wt / "dev-tasks.md").read_text(), "# trade tasks")
        self.assertEqual((wt / "design-package.md").read_text(), "## MQ\ntable")
        self.assertEqual((self.unit / ".claude" / "workflow" / "config.yml").read_text(),
                         "version: 2\nmode: dual\n")
        self.assertEqual((wt / "arch-docs-path").read_text(), str(self.arch.resolve()))
        # 执行仓状态：冻结 DEVELOPING + 任务 TODO
        unit_state = load_state(wt / "state" / "workflow-state.yml")
        self.assertEqual(unit_state["milestone"]["phase"], "DEVELOPING")
        self.assertEqual(unit_state["milestone"]["mode"], "dual")
        self.assertEqual(unit_state["tasks"]["1.1"]["state"], "TODO")
        self.assertEqual(unit_state["tasks"]["1.1"]["complexity"], "NORMAL")

    def test_dispatch_updates_arch_docs_ledger(self):
        code, _, err = self.dispatch()
        self.assertEqual(code, 0, err)
        state = load_state(self.state)
        self.assertEqual(state["units"]["trade"], {"repo": str(self.unit), "dispatched": True})
        self.assertEqual(state["milestone"]["phase"], "DISPATCHING")  # 里程碑由主 Agent 后续 DISPATCH_COMPLETED 推进

    def test_dispatch_missing_repo_rejected(self):
        units = [{"id": "web", "repo": "/nonexistent-repo", "tasks": []}]
        code, _, err = self.dispatch(units)
        self.assertEqual(code, 1)
        self.assertIn("执行仓不存在", err)

    def test_dispatch_empty_units_rejected(self):
        code, _, err = self.dispatch([])
        self.assertEqual(code, 1)
        self.assertIn("--units", err)


class TestReport(DispatchctlTestCase):
    def test_report_writes_to_arch_docs(self):
        # 先 dispatch 出单元工作包，再 report 契约变更到 arch-docs
        self.dispatch()
        wt = self.unit / "docs" / "discuss" / self.req / ".task"
        code, out, err = run(["report", "--unit-worktree", str(wt),
                              "--arch-docs-root", str(self.arch), "--unit", "trade",
                              "--content", "## 契约变更\nXxxRpcService.method 签名变化，影响下游 consumer"])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        report = Path(result["report"])
        self.assertTrue(report.exists())
        self.assertIn("契约变更", report.read_text())
        self.assertIn(self.req, str(report))

    def test_report_derives_requirement_from_worktree(self):
        # 从单元工作包路径反推 {域}/{需求名}，写入 arch-docs 对应目录
        self.dispatch()
        wt = self.unit / "docs" / "discuss" / self.req / ".task"
        code, out, _ = run(["report", "--unit-worktree", str(wt),
                            "--arch-docs-root", str(self.arch), "--unit", "trade",
                            "--content", "x"])
        self.assertEqual(code, 0)
        self.assertIn(self.req, json.loads(out)["requirement"])


if __name__ == "__main__":
    unittest.main()
