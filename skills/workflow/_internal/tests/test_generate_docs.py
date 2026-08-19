# ============================================================
# _internal/generate_docs.py 测试 — 派生文档生成 + --check 漂移检测
# ============================================================
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from _internal.generate_docs import main

FILES = ("README.md", "automation.md", "templates.md", "vocab.md", "commands.md",
         "example-guarded.yml")


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class TestGenerateDocs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_creates_three_files_with_marker(self):
        code, out, _ = run(["--out", str(self.out)])
        self.assertEqual(code, 0)
        for name in FILES:
            path = self.out / name
            self.assertTrue(path.exists(), name)
            self.assertIn("GENERATED", path.read_text(encoding="utf-8"))

    def test_check_passes_when_in_sync(self):
        run(["--out", str(self.out)])
        code, out, _ = run(["--check", "--out", str(self.out)])
        self.assertEqual(code, 0)
        self.assertIn("一致", out)

    def test_check_detects_drift(self):
        run(["--out", str(self.out)])
        (self.out / "automation.md").write_text("<!-- GENERATED --> 篡改\n", encoding="utf-8")
        code, _, err = run(["--check", "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("漂移", err)

    def test_check_detects_missing_file(self):
        run(["--out", str(self.out)])
        (self.out / "templates.md").unlink()
        code, _, err = run(["--check", "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("缺失", err)

    def test_committed_generated_is_in_sync(self):
        # 仓库内 committed generated/ 必须与 model/ 一致（防文档漂移的 CI 门禁）
        repo_gen = Path(__file__).resolve().parent.parent.parent / "generated"
        code, out, _ = run(["--check", "--out", str(repo_gen)])
        self.assertEqual(code, 0)


class TestVocabAndCommands(unittest.TestCase):
    """批 2：generated/vocab.md 与 commands.md 从 model 派生（加流程时自动跟随）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        run(["--out", str(self.out)])

    def tearDown(self):
        self.tmp.cleanup()

    def test_vocab_contains_events_decisions_gates(self):
        text = (self.out / "vocab.md").read_text(encoding="utf-8")
        self.assertIn("CR_JUDGED", text)
        self.assertIn("implicit_decisions", text)      # 决策来源列
        self.assertIn("CR_APPROVED", text)             # gate_events
        self.assertIn("WAIT_USER_APPROVAL", text)      # Decision 清单

    def test_vocab_scope_and_decision_source(self):
        text = (self.out / "vocab.md").read_text(encoding="utf-8")
        self.assertIn("REWORK_STARTED | task+milestone", text)
        self.assertIn("PLAN_VALIDATED", text)

    def test_commands_renders_task_and_milestone_templates(self):
        text = (self.out / "commands.md").read_text(encoding="utf-8")
        self.assertIn("--event TASK_STARTED --task {X.Y}", text)      # task 级带 --task
        self.assertIn("--event STAGE_COMPLETED", text)                 # milestone 级不带 --task
        self.assertNotIn("--since", text)                              # 时间戳系统生成，命令不带 --since
        self.assertNotIn("{ISO}", text)                                # ISO 占位符已移除
        self.assertIn('"complexity"', text)                            # 必填 payload 字段渲染
        self.assertIn("REWORK_STARTED", text)


if __name__ == "__main__":
    unittest.main()
