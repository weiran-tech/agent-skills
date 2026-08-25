# ============================================================
# 配置适配器 — 读/校验/初始化 .claude/workflow/config.yml
# Schema 唯一来源 model/config.schema.json；init 模板来源 model/presets.yml
# 命令：init（按 preset 生成显式配置）/ read（读取并校验）
# 配置全显式：无 profile 运行时概念，preset 仅为 init 模板
# ============================================================
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

# 使 adapters 可导入（脚本可能在 skill 根或子目录被调用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters._schema import validate_config, SchemaError

DEFAULT_CONFIG_FILENAME = ".claude/workflow/config.yml"

# skills 缺省映射：未配置时的内置默认（与历史硬编码引用一致）
SKILL_DEFAULTS = {"discuss": "devops-discuss", "arch_rules": "arch-rules", "arch_analyzer": "arch-analyzer"}


def _load_presets() -> dict:
    """加载 init 模板 model/presets.yml（presets + docs；仅 init 用；运行时 policy 不读）。"""
    path = Path(__file__).resolve().parent.parent / "model" / "presets.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _domain_capabilities(cfg: dict) -> dict:
    """各域 capabilities → 扁平能力 dict（配置显式值，默认 False 保守）。"""
    automation = cfg.get("automation", {})
    return {
        "advance_stage": automation.get("advance_stage", False),
        "advance_task": automation.get("advance_task", False),
        "advance_accept": automation.get("advance_accept", False),
        "advance_summary": automation.get("advance_summary", False),
        "simple_skip_cr": cfg.get("cr", {}).get("capabilities", {}).get("simple_skip_cr", False),
        # hotfix 域：SIMPLE Gate 通过（含非空转回归测试证据）时跳过 hotfix 单维度 CR（默认 true）
        "hotfix_simple_skip_cr": cfg.get("hotfix", {}).get("capabilities", {}).get("simple_skip_cr", True),
        # recheck（默认 true）→ 扁平为反相 skip_recheck（默认 false，符合"默认保守 False"约定；true = 跳过二次审核）
        "skip_recheck": not cfg.get("cr", {}).get("capabilities", {}).get("recheck", True),
        # minor_fix_auto_confirm（默认 true）：纯 MINOR+IMPLEMENT_FIX 修复且带质量门证据 → 跳二次审核直接确认
        "minor_fix_auto_confirm": cfg.get("cr", {}).get("capabilities", {}).get("minor_fix_auto_confirm", True),
        "plan_auto_validate": cfg.get("plan", {}).get("capabilities", {}).get("auto_validate", False),
        "accept_auto_fix": cfg.get("accept", {}).get("capabilities", {}).get("auto_fix", False),
    }


def read_config(path: str | Path) -> dict:
    """读取并校验配置，返回扁平 policy 输入 + cr 编排视图。

    返回 {mode, limits, quality, capabilities, cr}：
    - mode 为仓库拓扑（single|dual，默认 single）
    - limits/quality/capabilities 为扁平谓词输入（全显式，无 profile 解析）
    - cr.levels 为编排视图（主 Agent 读重审派发 recheck 列表）
    - cr.review.dimensions 为项目审核维度池（首审风险候选 ∩ 池，重审 recheck ∩ 池）
    校验失败抛 SchemaError。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"配置不存在: {p}")
    with open(p) as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise SchemaError("配置不是对象")
    validate_config(cfg)
    cr = cfg.get("cr", {})
    plan = cfg.get("plan", {})
    accept = cfg.get("accept", {})
    rework = cfg.get("rework", {})
    # cr.levels 应用默认：主 Agent 始终拿到完整严重度阶梯（含重审派发默认值）
    levels = {
        "zero": {"auto_confirm": cr.get("levels", {}).get("zero", {}).get("auto_confirm", True)},
        "minor": {"auto_fix": cr.get("levels", {}).get("minor", {}).get("auto_fix", False),
                  "recheck": cr.get("levels", {}).get("minor", {}).get("recheck", [])},
        "major": {"recheck": cr.get("levels", {}).get("major", {}).get("recheck",
                                                              ["design", "security", "performance"])},
    }
    # 项目审核维度池：首审风险候选 ∩ 池、重审 recheck ∩ 池；默认全开（当前行为）
    review = {"dimensions": cr.get("review", {}).get(
        "dimensions", ["implementation", "design", "security", "performance"])}
    return {"limits": {"acceptance_fix_max": accept.get("limits", {}).get("fix_max", 2),
                       "cr_fix_max": cr.get("limits", {}).get("fix_max", 3),
                       "plan_retry_max": plan.get("limits", {}).get("retry_max", 2),
                       "design_rework_max": rework.get("limits", {}).get("design_max", 2)},
            "quality": {"judge_min_confidence": cr.get("quality", {}).get("judge", {}).get("min_confidence", 0.85),
                        "cr_zero_auto_confirm": levels["zero"]["auto_confirm"],
                        "cr_minor_auto_fix": levels["minor"]["auto_fix"]},
            "capabilities": _domain_capabilities(cfg),
            "mode": cfg.get("mode", "single"),
            "skills": {**SKILL_DEFAULTS, **cfg.get("skills", {})},
            "cr": {"levels": levels, "review": review}}


def _cmd_read(args) -> int:
    try:
        ctx = read_config(args.config)
    except (FileNotFoundError, SchemaError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"skills": ctx["skills"],
                      "acceptance_fix_max": ctx["limits"].get("acceptance_fix_max"),
                      "cr_fix_max": ctx["limits"].get("cr_fix_max")}))
    return 0


def _fmt_yaml(val) -> str:
    """标量/列表渲染（列表用 flow 风格；bool 小写）。"""
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def _render_config(cfg: dict, docs: dict) -> str:
    """按 cfg 结构通用渲染 YAML，逐路径从 presets.yml 的 docs 注入注释（无骨架硬编码）。

    cfg 的形状来自 model/presets.yml 的预设值；docs 的键 = 点路径（如 cr.limits.fix_max）。
    改字段/注释只改 presets.yml，本函数无需维护。
    """
    lines = ["# workflow 配置 v2（字段注释见 model/presets.yml docs）",
             f"version: {cfg['version']}"]
    _walk_yaml(lines, cfg, "", docs, top=True)
    return "\n".join(lines) + "\n"


def _walk_yaml(lines: list, node: dict, path: str, docs: dict, top: bool = False,
               indent: int = 0) -> None:
    pad = "  " * indent
    for key, val in node.items():
        if key == "version":
            continue
        p = f"{path}.{key}" if path else key
        if top:
            lines.append("")
        comment = docs.get(p)
        if comment:
            lines.append(f"{pad}# {comment}")
        if isinstance(val, dict):
            lines.append(f"{pad}{key}:")
            _walk_yaml(lines, val, p, docs, indent=indent + 1)
        else:
            lines.append(f"{pad}{key}: {_fmt_yaml(val)}")


def _preset_config(data: dict, preset: str, fix_max: int) -> dict:
    """从 model/presets.yml 取 preset 完整模板，应用 --fix-max 覆盖。"""
    values = {k: v for k, v in data["presets"][preset].items() if k != "description"}
    cfg = {"version": 2, **copy.deepcopy(values)}
    cfg["accept"]["limits"]["fix_max"] = fix_max
    return cfg


def _cmd_init(args) -> int:
    preset = args.preset
    fix_max = args.fix_max
    data = _load_presets()
    if preset not in data["presets"]:
        print(f"error: preset 非法: {preset!r}（{', '.join(data['presets'])}）", file=sys.stderr)
        return 1
    if not isinstance(fix_max, int) or not (0 <= fix_max <= 10):
        print(f"error: fix_max 非法: {fix_max!r}（0-10 整数）", file=sys.stderr)
        return 1
    cfg = _preset_config(data, preset, fix_max)
    try:
        validate_config(cfg)
    except SchemaError as e:
        print(f"error: 生成的配置非法: {e}", file=sys.stderr)
        return 1
    rendered = _render_config(cfg, data.get("docs", {}))
    # 防御：渲染文本必须解析回同一配置，防止注释模板与 cfg 漂移
    if yaml.safe_load(rendered) != cfg:
        print("error: 渲染配置与校验配置不一致", file=sys.stderr)
        return 1
    p = Path(args.config)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(rendered)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print(json.dumps({"ok": True, "config": str(p), "preset": preset, "acceptance_fix_max": fix_max}))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="configctl", description="workflow 配置读写")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read", help="读取并校验配置")
    r.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径")
    r.set_defaults(handler=_cmd_read)

    i = sub.add_parser("init", help="按 preset 生成显式配置（原子写入）")
    i.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径")
    i.add_argument("--preset", default="guarded", help="内置预设模板（manual|guarded|autonomous）")
    i.add_argument("--fix-max", type=int, default=2, help="accept.limits.fix_max 验收自动修复轮次（0-10）")
    i.set_defaults(handler=_cmd_init)

    args = ap.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
