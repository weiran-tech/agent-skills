# ============================================================
# adapters/progress_render.py 测试 — workflow-state → progress.md 派生视图
# ============================================================
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from adapters.progress_render import main


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def milestone(phase="DISCUSSING"):
    return {"phase": phase, "lifecycle": "ACTIVE", "pending_gate": None, "blocker": None, "fix_attempts": 0}


class TestProgressRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_state(self, state):
        p = self.root / "workflow-state.yml"
        p.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return p

    def test_render_creates_progress_md(self):
        state = {"milestone": milestone("DEVELOPING"),
                 "tasks": {"1.1": {"state": "CODING", "title": "订单查询", "cr_path": None}}, "meta": {}}
        s = self.write_state(state)
        out_file = self.root / "progress.md"
        code, _, _ = run(["--state", str(s), "--out", str(out_file),
                          "--meta", '{"name":"订单优化","id":"order/2026-08-07-订单优化"}'])
        self.assertEqual(code, 0)
        text = out_file.read_text(encoding="utf-8")
        self.assertIn("GENERATED", text)
        self.assertIn("订单优化", text)
        self.assertIn("DEVELOPING", text)
        self.assertIn("1.1", text)
        self.assertIn("CODING", text)

    def test_render_missing_state_uses_empty(self):
        s = self.root / "nope" / "workflow-state.yml"
        out_file = self.root / "progress.md"
        code, _, _ = run(["--state", str(s), "--out", str(out_file)])
        self.assertEqual(code, 0)
        self.assertIn("DISCUSSING", out_file.read_text(encoding="utf-8"))

    def test_render_pending_gate_shown(self):
        ms = milestone("DEVELOPING")
        ms["pending_gate"] = {"type": "CR", "target_task": "1.1", "since": "t1"}
        state = {"milestone": ms, "tasks": {"1.1": {"state": "CR_PLANNED", "title": "t"}}, "meta": {}}
        s = self.write_state(state)
        out_file = self.root / "progress.md"
        code, _, _ = run(["--state", str(s), "--out", str(out_file)])
        self.assertEqual(code, 0)
        text = out_file.read_text(encoding="utf-8")
        self.assertIn("CR", text)
        self.assertIn("target: 1.1", text)


if __name__ == "__main__":
    unittest.main()
