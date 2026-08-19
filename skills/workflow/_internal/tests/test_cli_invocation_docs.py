# ============================================================
# workflow CLI 调用协议文档测试 — adapter entrypoint 必须显式分隔
# 覆盖：status 的 statectl / validate 命令模板以及全局组合护栏
# ============================================================
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "SKILL.md"
COMMAND_INDEX = ROOT / "references" / "commands" / "index.md"


class TestCliInvocationDocumentation(unittest.TestCase):
    def test_skill_requires_explicit_adapter_cli_separator(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("Adapter CLI 组合（强制）", text)
        self.assertIn("显式 `&&`", text)
        self.assertIn("未分隔的文本", text)
        self.assertIn("多个独立 Bash tool call", text)

    def test_status_documents_independent_and_sequenced_calls(self):
        text = COMMAND_INDEX.read_text(encoding="utf-8")
        statectl = "python3 {skill根}/adapters/statectl.py get --state {状态文件}"
        validate = "python3 {skill根}/adapters/validate.py --state {状态文件} --log {转换日志}"
        self.assertIn(statectl, text)
        self.assertIn(validate, text)
        self.assertIn(f"{statectl} && {validate}", text)
        self.assertIn("禁止无分隔符地拼为一条 argv", text)


class TestHotfixSkipCrDocumentation(unittest.TestCase):
    def test_hotfix_documents_simple_gate_skip(self):
        text = (ROOT / "references" / "commands" / "hotfix.md").read_text(encoding="utf-8")
        self.assertIn("#regression", text)
        self.assertIn("hotfix_simple_skip_cr", text)
        self.assertIn("跳过 CR（特权", text)
        self.assertIn("必须走单维度 CR", text)


if __name__ == "__main__":
    unittest.main()
