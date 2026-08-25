# ============================================================
# _internal/lint/vocab.py 测试 — 手写 md 词表与 model 一致性
# 覆盖：当前 md 全通过 / 陈旧或拼错的带下划线词汇被拦截 / 单词与 allowlist 不误报
# ============================================================
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from _internal.lint.vocab import _load_vocab, _load_lower_vocab, _scan, _targets


class TestVocabLint(unittest.TestCase):
    def test_current_handwritten_md_passes(self):
        # 当前仓库手写 md 不得含未知工作流词（改 model 后必须同步 md 或重新生成）
        vocab = _load_vocab()
        lower_vocab = _load_lower_vocab()
        violations = []
        for p in _targets():
            violations += _scan(p, vocab, lower_vocab)
        self.assertEqual(violations, [], f"手写 md 含未知词: {violations[:5]}")

    def _tmp_md(self, text: str) -> Path:
        p = Path(tempfile.mkdtemp()) / "t.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_stale_underscore_token_detected(self):
        # 拼错/陈旧的事件名必须被拦截（如 ACCEPT_APPROVE 不在词表）
        vocab = _load_vocab()
        lower_vocab = _load_lower_vocab()
        p = self._tmp_md("提交 ACCEPT_APPROVE 事件\n")
        v = _scan(p, vocab, lower_vocab)
        self.assertTrue(any("ACCEPT_APPROVE" in x for x in v))

    def test_stale_lowercase_config_key_detected(self):
        # 陈旧/拼错的 config/payload 键必须被拦截（如 stage_advance_renamed）
        vocab = _load_vocab()
        lower_vocab = _load_lower_vocab()
        p = self._tmp_md("读取 stage_advance_renamed 配置\n")
        v = _scan(p, vocab, lower_vocab)
        self.assertTrue(any("stage_advance_renamed" in x for x in v))

    def test_valid_lowercase_config_key_not_flagged(self):
        # 合法 config/payload 键与运行时字段不误报
        vocab = _load_vocab()
        lower_vocab = _load_lower_vocab()
        p = self._tmp_md("读取 advance_stage 与 fix_max 与 min_confidence 与 pending_gate\n")
        self.assertEqual(_scan(p, vocab, lower_vocab), [])

    def test_removed_vocab_is_detected(self):
        # 词表移除后残留引用必须被 lint 抓到
        vocab = _load_vocab()
        lower_vocab = _load_lower_vocab()
        vocab -= {"CR_JUDGED"}
        p = self._tmp_md("CR_JUDGED 裁决分流\n")
        v = _scan(p, vocab, lower_vocab)
        self.assertTrue(any("CR_JUDGED" in x for x in v))

    def test_single_word_and_allowlist_not_flagged(self):
        # 单词语（英文/SQL）与 allowlist（DDL 关键字）不误报
        vocab = _load_vocab()
        lower_vocab = _load_lower_vocab()
        p = self._tmp_md("AUTO_INCREMENT\nCREATE TABLE\nCOMPLETED\n")
        self.assertEqual(_scan(p, vocab, lower_vocab), [])

    def test_vocab_covers_known_events_and_decisions(self):
        vocab = _load_vocab()
        for tok in ("CR_JUDGED", "WAIT_USER_APPROVAL", "AUTONOMOUS_BLOCKED",
                    "IMPLEMENT_FIX", "UNCERTAIN", "SIMPLE"):
            self.assertIn(tok, vocab)

    def test_invariant_name_not_flagged(self):
        # 不变量名 design_rework_exit 唯一来源 invariants.py（_ALLOW_LOWER），不因不再声明于 model 而误报
        vocab = _load_vocab()
        lower_vocab = _load_lower_vocab()
        p = self._tmp_md("设计返工不变量 design_rework_exit 生效\n")
        self.assertEqual(_scan(p, vocab, lower_vocab), [])


if __name__ == "__main__":
    unittest.main()
