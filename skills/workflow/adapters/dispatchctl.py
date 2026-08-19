# ============================================================
# dispatchctl — 双仓适配器（确定性部分）
# dispatch：主 Agent 按语言模板裁剪出每执行单元的 design-package 后，
#   落地执行仓工作包（state + dev-tasks + design-package + config + arch-docs-path）
#   + 回写 arch-docs 台账。
# report：执行仓上报对外契约变更到 arch-docs（写入 reports 台账），
#   供 arch-docs 主 Agent 走 /workflow rework（设计层重审）。
# 裁剪（LLM 判断）不在本工具；纯文件/状态 I/O，确定性、可测试。
# ============================================================
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.statectl import load_state, write_state


class DispatchError(ValueError):
    pass


def _frozen_milestone(mode: str) -> dict:
    """执行仓状态文件的里程碑骨架：冻结在 DEVELOPING，无门（任务级事件不驱动里程碑）。"""
    return {"phase": "DEVELOPING", "lifecycle": "ACTIVE", "pending_gate": None,
            "blocker": None, "mode": mode}


def _task_state(tasks: list[dict]) -> dict:
    """把任务清单初始化为 TODO 状态映射 {X.Y: {state: TODO, complexity}}。"""
    out = {}
    for t in tasks:
        out[str(t["id"])] = {"state": "TODO", "complexity": t.get("complexity", "NORMAL")}
    return out


def _requirement_rel(state_path: Path, arch_docs_root: Path) -> str:
    """从 arch-docs 状态文件反推 {域}/{需求名} 相对路径。

    arch_docs_root/docs/discuss/{域}/{需求名}/.task/state/workflow-state.yml
    → 相对 arch_docs_root 的 {域}/{需求名}。
    """
    rel = state_path.resolve().relative_to(arch_docs_root.resolve())
    # 去掉 docs/discuss/ 前缀与 /.task/state/workflow-state.yml 后缀
    parts = rel.parts
    for i, p in enumerate(parts):
        if p == "discuss":
            return "/".join(parts[i + 1:-3])
    raise DispatchError(f"状态文件不在 {arch_docs_root}/docs/discuss 下: {state_path}")


def _write_unit_work_package(unit: dict, arch_docs_root: Path, requirement_rel: str,
                             config_path: Path, mode: str) -> dict:
    """落地单个执行仓的工作包，返回写入路径摘要。"""
    repo = Path(unit["repo"]).expanduser()
    if not repo.is_dir():
        raise DispatchError(f"执行仓不存在: {repo}")
    worktree = repo / "docs" / "discuss" / requirement_rel / ".task"
    state_path = worktree / "state" / "workflow-state.yml"
    tasks = _task_state(unit.get("tasks", []))
    write_state(state_path, {"milestone": _frozen_milestone(mode), "tasks": tasks})
    (worktree / "dev-tasks.md").write_text(unit.get("dev_tasks", ""), encoding="utf-8")
    (worktree / "design-package.md").write_text(unit.get("design_package", ""), encoding="utf-8")
    # 继承 arch-docs 配置（mode: dual），写入执行仓 .claude/workflow/
    cfg_target = repo / ".claude" / "workflow" / "config.yml"
    cfg_target.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        cfg_target.write_bytes(config_path.read_bytes())
    # 回指指针（供 report 使用；git excluded，SKILL 层保证不提交）
    (worktree / "arch-docs-path").write_text(str(arch_docs_root.resolve()), encoding="utf-8")
    return {"unit": unit["id"], "repo": str(repo), "worktree": str(worktree),
            "tasks": len(tasks), "state": str(state_path)}


def _cmd_dispatch(args) -> int:
    try:
        arch_state_path = Path(args.arch_docs_state)
        arch_root = Path(args.arch_docs_root).expanduser()
        config_path = Path(args.config)
        if not arch_state_path.exists():
            raise DispatchError(f"arch-docs 状态不存在: {arch_state_path}")
        state = load_state(arch_state_path)
        mode = state.get("mode") or "dual"
        requirement_rel = _requirement_rel(arch_state_path, arch_root)
        units = json.loads(args.units)
        if not isinstance(units, list) or not units:
            raise DispatchError("--units 必须是非空 JSON 数组")
        ledger = state.setdefault("units", {})
        results = []
        for u in units:
            if not isinstance(u, dict) or not u.get("id") or not u.get("repo"):
                raise DispatchError(f"单元缺 id/repo: {u}")
            results.append(_write_unit_work_package(u, arch_root, requirement_rel, config_path, mode))
            ledger[u["id"]] = {"repo": u["repo"], "dispatched": True}
        write_state(arch_state_path, state)
        print(json.dumps({"ok": True, "requirement": requirement_rel, "mode": mode,
                          "units_dispatched": len(results), "results": results}, ensure_ascii=False))
        return 0
    except (DispatchError, json.JSONDecodeError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _requirement_rel_from_worktree(worktree: Path) -> str:
    """从执行仓工作包路径反推 {域}/{需求名}。worktree = .../docs/discuss/{域}/{需求名}/.task。"""
    parts = worktree.resolve().parts
    for i, p in enumerate(parts):
        if p == "discuss":
            return "/".join(parts[i + 1:-1])
    raise DispatchError(f"工作包路径不在 docs/discuss 下: {worktree}")


def _cmd_report(args) -> int:
    try:
        from datetime import datetime
        worktree = Path(args.unit_worktree)
        arch_root = Path(args.arch_docs_root).expanduser()
        req = _requirement_rel_from_worktree(worktree)
        reports_dir = arch_root / "docs" / "discuss" / req / ".task" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = reports_dir / f"{args.unit}-{stamp}.md"
        target.write_text(args.content, encoding="utf-8")
        print(json.dumps({"ok": True, "report": str(target), "requirement": req,
                          "arch_docs_root": str(arch_root.resolve())}, ensure_ascii=False))
        return 0
    except (DispatchError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dispatchctl", description="workflow 双仓适配器（确定性部分）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dispatch", help="按主 Agent 裁剪结果落地执行仓工作包 + 回写 arch-docs 台账")
    d.add_argument("--arch-docs-state", required=True, help="arch-docs workflow-state.yml 路径")
    d.add_argument("--arch-docs-root", required=True, help="arch-docs 仓库根（写 arch-docs-path 指针）")
    d.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径（继承到执行仓）")
    d.add_argument("--units", required=True,
                   help="JSON 数组：[{id, repo, tasks:[{id,title,complexity}], dev_tasks, design_package}, ...]")
    d.set_defaults(handler=_cmd_dispatch)
    r = sub.add_parser("report", help="执行仓上报对外契约变更到 arch-docs（供 rework 重审）")
    r.add_argument("--unit-worktree", required=True, help="执行仓工作包路径（.../docs/discuss/{域}/{需求名}/.task）")
    r.add_argument("--arch-docs-root", required=True, help="arch-docs 仓库根")
    r.add_argument("--unit", required=True, help="执行单元 id")
    r.add_argument("--content", required=True, help="报告 markdown 内容（变更的契约 + 影响）")
    r.set_defaults(handler=_cmd_report)
    args = ap.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
