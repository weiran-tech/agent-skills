# ============================================================
# adapters/configctl.py 测试 — init（preset 模板）/ read + v2 全显式 Schema
# ============================================================
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from adapters.configctl import main, read_config


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def base_cfg():
    """v2 全显式配置（guarded 风格完整值）。"""
    return {"version": 2,
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
            "hotfix": {"capabilities": {"simple_skip_cr": True}}}


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / ".claude" / "workflow" / "config.yml"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, cfg):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


class TestInit(ConfigTestCase):
    def test_init_creates_valid_v2_config(self):
        code, out, _ = run(["init", "--config", str(self.path), "--preset", "guarded"])
        self.assertEqual(code, 0)
        self.assertTrue(self.path.exists())
        self.assertEqual(yaml.safe_load(self.path.read_text())["version"], 2)
        ctx = read_config(self.path)
        self.assertEqual(ctx["limits"]["acceptance_fix_max"], 2)

    def test_init_writes_atomically_no_partial_file(self):
        code, _, _ = run(["init", "--config", str(self.path), "--preset", "autonomous", "--fix-max", "5"])
        self.assertEqual(code, 0)
        self.assertTrue(self.path.exists())
        # 无残留 .tmp
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_init_renders_full_domain_config_with_comments(self):
        code, _, _ = run(["init", "--config", str(self.path), "--preset", "guarded"])
        self.assertEqual(code, 0)
        text = self.path.read_text(encoding="utf-8")
        # 各域块生成且带注释
        self.assertIn("# automation 自动化控制", text)
        self.assertIn("# cr 代码审查域", text)
        self.assertIn("# accept 收尾验收域", text)
        self.assertIn("advance_stage:", text)
        self.assertIn("advance_task:", text)
        self.assertIn("# 项目审核维度池", text)
        # 渲染可解析回同一配置（防漂移）
        loaded = yaml.safe_load(text)
        self.assertEqual(loaded["version"], 2)
        self.assertNotIn("profile", loaded)
        self.assertEqual(loaded["cr"]["levels"]["major"]["recheck"],
                         ["design", "security", "performance"])
        self.assertEqual(loaded["cr"]["review"]["dimensions"],
                         ["implementation", "design", "security", "performance"])
        self.assertTrue(loaded["automation"]["advance_stage"])
        self.assertTrue(loaded["automation"]["advance_task"])
        self.assertFalse(loaded["automation"]["advance_accept"])
        self.assertFalse(loaded["automation"]["advance_summary"])

    def test_init_manual_preset_conservative(self):
        code, _, _ = run(["init", "--config", str(self.path), "--preset", "manual"])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        # manual preset 烘焙保守值：capabilities 全关 + cr 零问题不等
        self.assertFalse(ctx["capabilities"]["advance_stage"])
        self.assertFalse(ctx["capabilities"]["advance_task"])
        self.assertFalse(ctx["capabilities"]["advance_accept"])
        self.assertFalse(ctx["capabilities"]["advance_summary"])
        self.assertFalse(ctx["capabilities"]["accept_auto_fix"])
        self.assertFalse(ctx["quality"]["cr_zero_auto_confirm"])

    def test_init_autonomous_preset_auto_fix_and_summary(self):
        code, _, _ = run(["init", "--config", str(self.path), "--preset", "autonomous"])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertTrue(ctx["quality"]["cr_minor_auto_fix"])
        self.assertTrue(ctx["capabilities"]["advance_summary"])

    def test_init_bakes_skills_defaults(self):
        # preset 烘焙外部 skill 缺省映射（与历史硬编码引用一致）
        code, _, _ = run(["init", "--config", str(self.path), "--preset", "guarded"])
        self.assertEqual(code, 0)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("# 外部 skill 调用映射", text)
        self.assertIn("discuss: devops-discuss", text)
        self.assertIn("arch_rules: arch-rules", text)
        self.assertIn("arch_analyzer: arch-analyzer", text)
        ctx = read_config(self.path)
        self.assertEqual(ctx["skills"]["discuss"], "devops-discuss")

    def test_init_invalid_preset_rejected(self):
        code, _, err = run(["init", "--config", str(self.path), "--preset", "bogus"])
        self.assertEqual(code, 1)
        self.assertIn("preset", err)
        self.assertFalse(self.path.exists())

    def test_init_invalid_fix_max_rejected(self):
        code, _, err = run(["init", "--config", str(self.path), "--fix-max", "99"])
        self.assertEqual(code, 1)
        self.assertIn("fix_max", err)
        self.assertFalse(self.path.exists())


class TestRead(ConfigTestCase):
    def test_read_missing_file_fails(self):
        code, _, err = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 1)
        self.assertIn("error", err)

    def test_read_rejects_wrong_version(self):
        self.write(dict(base_cfg(), version=3))
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 1)

    def test_read_rejects_unknown_field(self):
        cfg = base_cfg()
        cfg["bogus"] = True
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 1)

    def test_read_returns_explicit_values(self):
        self.write(base_cfg())
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertTrue(ctx["capabilities"]["advance_stage"])
        self.assertTrue(ctx["capabilities"]["advance_task"])
        self.assertFalse(ctx["capabilities"]["advance_accept"])
        self.assertFalse(ctx["capabilities"]["advance_summary"])
        self.assertTrue(ctx["capabilities"]["simple_skip_cr"])
        self.assertTrue(ctx["capabilities"]["hotfix_simple_skip_cr"])
        self.assertTrue(ctx["capabilities"]["accept_auto_fix"])
        self.assertTrue(ctx["quality"]["cr_zero_auto_confirm"])

    def test_read_applies_defaults_and_exposes_cr_levels(self):
        # 最小配置（仅 version）：域块默认兜底 + cr.levels 编排视图暴露
        self.write({"version": 2})
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertEqual(ctx["limits"]["cr_fix_max"], 3)
        self.assertEqual(ctx["limits"]["acceptance_fix_max"], 2)
        self.assertEqual(ctx["quality"]["judge_min_confidence"], 0.85)
        self.assertTrue(ctx["quality"]["cr_zero_auto_confirm"])
        self.assertFalse(ctx["quality"]["cr_minor_auto_fix"])
        self.assertFalse(ctx["capabilities"]["advance_stage"])  # 默认保守 False
        self.assertEqual(ctx["cr"]["levels"]["major"]["recheck"],
                         ["design", "security", "performance"])

    def test_read_returns_normalized_limits(self):
        self.write(base_cfg())
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertEqual(ctx["limits"]["acceptance_fix_max"], 2)
        self.assertEqual(ctx["limits"]["cr_fix_max"], 3)

    def test_read_dimensions_defaults_to_full_pool(self):
        # 无 review 块 → 默认全开（当前行为零变化）
        self.write({"version": 2})
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertEqual(ctx["cr"]["review"]["dimensions"],
                         ["implementation", "design", "security", "performance"])

    def test_read_dimensions_explicit(self):
        cfg = base_cfg()
        cfg["cr"]["review"] = {"dimensions": ["implementation", "design"]}
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertEqual(ctx["cr"]["review"]["dimensions"], ["implementation", "design"])

    def test_read_rejects_invalid_dimension_name(self):
        cfg = base_cfg()
        cfg["cr"]["review"] = {"dimensions": ["implementation", "bogus"]}
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 1)

    def test_read_recheck_default_enabled(self):
        # 默认 recheck=true → 扁平 skip_recheck=false（保守默认约定，不跳过二次审核）
        self.write({"version": 2})
        ctx = read_config(self.path)
        self.assertFalse(ctx["capabilities"]["skip_recheck"])

    def test_read_recheck_disabled(self):
        cfg = base_cfg()
        cfg["cr"]["capabilities"]["recheck"] = False
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertTrue(ctx["capabilities"]["skip_recheck"])

    def test_read_minor_fix_auto_confirm_default_true(self):
        # 默认 minor_fix_auto_confirm=true（纯 MINOR 修复带证据自动确认，省一次重审）
        self.write({"version": 2})
        ctx = read_config(self.path)
        self.assertTrue(ctx["capabilities"]["minor_fix_auto_confirm"])

    def test_read_minor_fix_auto_confirm_disabled(self):
        cfg = base_cfg()
        cfg["cr"]["capabilities"]["minor_fix_auto_confirm"] = False
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertFalse(ctx["capabilities"]["minor_fix_auto_confirm"])

    def test_read_hotfix_simple_skip_cr_default_true(self):
        # 默认 hotfix_simple_skip_cr=true（SIMPLE Gate 通过即跳过 hotfix 单维度 CR，用户选定默认开）
        self.write({"version": 2})
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertTrue(ctx["capabilities"]["hotfix_simple_skip_cr"])

    def test_read_hotfix_simple_skip_cr_disabled(self):
        cfg = base_cfg()
        cfg["hotfix"]["capabilities"]["simple_skip_cr"] = False
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertFalse(ctx["capabilities"]["hotfix_simple_skip_cr"])

    def test_read_mode_default_single(self):
        # 默认 mode=single（向后兼容：无 mode 字段的既有配置按单仓处理）
        self.write({"version": 2})
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertEqual(ctx["mode"], "single")

    def test_read_mode_explicit_dual(self):
        cfg = base_cfg()
        cfg["mode"] = "dual"
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertEqual(ctx["mode"], "dual")

    def test_read_rejects_invalid_mode(self):
        cfg = base_cfg()
        cfg["mode"] = "tri"
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 1)

    def test_read_skills_default_when_absent(self):
        # 无 skills 块 → 内置默认（向后兼容：既有配置行为零变化）
        self.write({"version": 2})
        ctx = read_config(self.path)
        self.assertEqual(ctx["skills"], {"discuss": "devops-discuss",
                                         "arch_rules": "arch-rules",
                                         "arch_analyzer": "arch-analyzer"})

    def test_read_skills_explicit(self):
        cfg = base_cfg()
        cfg["skills"] = {"discuss": "my-discuss", "arch_analyzer": "my-arch-analyzer"}
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 0)
        ctx = read_config(self.path)
        self.assertEqual(ctx["skills"]["discuss"], "my-discuss")
        self.assertEqual(ctx["skills"]["arch_analyzer"], "my-arch-analyzer")
        # 未覆盖的 key 保持内置默认
        self.assertEqual(ctx["skills"]["arch_rules"], "arch-rules")

    def test_read_rejects_unknown_skill_key(self):
        cfg = base_cfg()
        cfg["skills"] = {"bogus": "x"}
        self.write(cfg)
        code, _, _ = run(["read", "--config", str(self.path)])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
