# ============================================================
# 校验 CLI — 解析 workflow-state + transition.log → 不变量诊断
# status 命令默认附带；发现违规立即提示
# 业务逻辑全在 engine/invariants.py，本文件只做 I/O 与输出
# ============================================================
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import invariants, state_machine as sm
from adapters.statectl import load_state, read_log


def _cmd_validate(args) -> int:
    state = load_state(args.state)
    if args.check_split:
        ok, reason = invariants.check_split_window(state)
        print(json.dumps({"ok": ok, "reason": reason}, ensure_ascii=False))
        return 0 if ok else 2
    log = read_log(args.log) if args.log else None
    model = sm.load_model()
    violations = invariants.check_all(model, state, log)
    if args.json:
        print(json.dumps({"ok": not violations, "violations": violations}, ensure_ascii=False))
    else:
        if violations:
            for v in violations:
                print(f"✗ {v}", file=sys.stderr)
            print(f"validate: {len(violations)} 个违规", file=sys.stderr)
        else:
            print("validate: ok")
    return 0 if not violations else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="validate", description="workflow 状态不变量校验")
    ap.add_argument("--state", required=True, help="workflow-state.yml 路径")
    ap.add_argument("--log", help="transition.log 路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--check-split", action="store_true",
                    help="仅检查 split 窗口：任一任务离开 TODO 即关闭（开发开始后不可拆里程碑）")
    args = ap.parse_args(argv)
    return _cmd_validate(args)


if __name__ == "__main__":
    raise SystemExit(main())
