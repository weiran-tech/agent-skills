# ============================================================
# 派生文档生成器
# 从 model 渲染 generated/*，带 GENERATED 标记
# --check 模式检测漂移（维护者/CI）；执行决策走 statectl，文档仅供人读
# 业务逻辑全在 engine/render/docs.py，本文件只做 I/O
# ============================================================
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import policy, render, state_machine as sm

_MODEL_DIR = Path(__file__).resolve().parent.parent / "model"


def _render_config_example() -> str:
    """渲染 guarded 预设示例配置（复用 configctl 渲染，presets.yml 变更后自动同步，无双源）。

    直接取 preset 值（不做 fix_max 覆盖），保证示例 = presets.yml 当前值。
    """
    from adapters import configctl

    data = configctl._load_presets()
    values = {k: v for k, v in data["presets"]["guarded"].items() if k != "description"}
    cfg = {"version": 2, **copy.deepcopy(values)}
    body = configctl._render_config(cfg, data.get("docs", {}))
    return "# GENERATED from model/presets.yml — 勿手改，改 presets.yml 后重新生成\n" + body


def _render_all():
    pol = policy.load_policy()
    m = sm.load_model()
    events_schema = json.loads((_MODEL_DIR / "events.schema.json").read_text(encoding="utf-8"))
    agents = yaml.safe_load((_MODEL_DIR / "agent-contracts.yml").read_text(encoding="utf-8"))
    return {
        "README.md": render.render_readme(m, pol),
        "automation.md": render.render_automation(pol),
        "templates.md": render.render_templates(m),
        "vocab.md": render.render_vocab(pol, m),
        "commands.md": (render.render_commands(m, events_schema)
                        + render.render_command_dict(agents)),
        "example-guarded.yml": _render_config_example(),
    }


def _cmd_generate(args) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in _render_all().items():
        (out_dir / name).write_text(text, encoding="utf-8")
        print(f"generated: {out_dir / name}")
    return 0


def _cmd_check(args) -> int:
    out_dir = Path(args.out)
    drift = []
    for name, text in _render_all().items():
        target = out_dir / name
        if not target.exists():
            drift.append(f"缺失: {name}")
        elif target.read_text(encoding="utf-8") != text:
            drift.append(f"漂移: {name}")
    if drift:
        print("\n".join(drift), file=sys.stderr)
        print("请运行 generate 重新生成（改 model/ 后不得手改 generated/）", file=sys.stderr)
        return 2
    print("generate --check: 一致")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="generate_docs", description="workflow 派生文档生成")
    ap.add_argument("--check", action="store_true", help="校验 generated/ 与模型一致（不写文件）")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "generated"))
    args = ap.parse_args(argv)
    return _cmd_check(args) if args.check else _cmd_generate(args)


if __name__ == "__main__":
    raise SystemExit(main())
