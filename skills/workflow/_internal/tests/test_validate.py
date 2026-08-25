# ============================================================
# adapters/validate.py 测试 — 不变量校验 CLI（状态 + 日志联合诊断）
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

from adapters.validate import main


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def milestone(phase="DISCUSSING"):
    return {"phase": phase, "lifecycle": "ACTIVE", "pending_gate": None, "blocker": None, "fix_attempts": 0}


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_state(self, state):
        p = self.root / "workflow-state.yml"
        p.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return p

    def test_empty_state_is_valid(self):
        s = self.write_state({"milestone": milestone(), "tasks": {}, "meta": {}})
        code, out, _ = run(["--state", str(s)])
        self.assertEqual(code, 0)
        self.assertIn("ok", out)

    def test_json_mode_reports_ok(self):
        s = self.write_state({"milestone": milestone(), "tasks": {}, "meta": {}})
        code, out, _ = run(["--state", str(s), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["ok"], True)

    def test_detects_invalid_phase(self):
        ms = milestone("BOGUS")
        s = self.write_state({"milestone": ms, "tasks": {}, "meta": {}})
        code, out, _ = run(["--state", str(s), "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)["ok"], False)

    def test_detects_cr_fixing_without_contract(self):
        state = {"milestone": milestone("DEVELOPING"),
                 "tasks": {"1.1": {"state": "CR_FIXING"}}, "meta": {}}
        s = self.write_state(state)
        code, out, _ = run(["--state", str(s), "--json"])
        self.assertEqual(code, 2)
        self.assertIn("缺少修复契约", json.loads(out)["violations"][0])

    def test_check_split_allowed_before_development(self):
        s = self.write_state({"milestone": milestone("DESIGN_REVIEW"), "tasks": {}, "meta": {}})
        code, out, _ = run(["--state", str(s), "--check-split"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["ok"], True)

    def test_check_split_allowed_with_todo_tasks(self):
        # init-tasks 全量登记后任务仍为 TODO → 未开发，窗口仍开（关闭锚点 = 首个 TASK_STARTED）
        s = self.write_state({"milestone": milestone("DEVELOPING"),
                              "tasks": {"1.1": {"state": "TODO", "complexity": "NORMAL"},
                                        "1.2": {"state": "TODO", "complexity": "NORMAL"}}, "meta": {}})
        code, out, _ = run(["--state", str(s), "--check-split"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["ok"], True)

    def test_check_split_rejected_after_task_started(self):
        # 任一任务离开 TODO（开发开始）→ 窗口关闭
        s = self.write_state({"milestone": milestone("DEVELOPING"),
                              "tasks": {"1.1": {"state": "CODING", "complexity": "NORMAL"},
                                        "1.2": {"state": "TODO", "complexity": "NORMAL"}}, "meta": {}})
        code, out, _ = run(["--state", str(s), "--check-split"])
        self.assertEqual(code, 2)
        result = json.loads(out)
        self.assertEqual(result["ok"], False)
        self.assertIn("开发已开始", result["reason"])

    def test_check_split_rejected_after_accepting(self):
        # 已进验收 → 阶段不在开发窗口内，禁止 split
        s = self.write_state({"milestone": milestone("ACCEPTING"),
                              "tasks": {"1.1": {"state": "DONE"}}, "meta": {}})
        code, out, _ = run(["--state", str(s), "--check-split"])
        self.assertEqual(code, 2)
        result = json.loads(out)
        self.assertEqual(result["ok"], False)
        self.assertIn("已过开发窗口", result["reason"])

    def test_detects_done_not_via_verify(self):
        log = self.root / "transition.log"
        log.write_text(json.dumps({"event": "TASK_DOD_PASSED", "decision": "RUN_CR",
                                   "task_id": "1.1", "ts": "t1", "phase": "DEVELOPING"}) + "\n",
                       encoding="utf-8")
        state = {"milestone": milestone("DEVELOPING"),
                 "tasks": {"1.1": {"state": "DONE"}}, "meta": {}}
        s = self.write_state(state)
        code, out, _ = run(["--state", str(s), "--log", str(log), "--json"])
        self.assertEqual(code, 2)
        self.assertIn("最近事件", json.loads(out)["violations"][0])


if __name__ == "__main__":
    unittest.main()
