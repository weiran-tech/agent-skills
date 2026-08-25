# ============================================================
# progress 派生视图渲染器
# progress.md 由 workflow-state 派生，人工只读不手改
# 业务逻辑全在 engine/render/progress.py，本文件只做 I/O
# ============================================================
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import render
from adapters.statectl import load_state


def _cmd_render(args) -> int:
    state = load_state(args.state)
    meta = json.loads(args.meta) if args.meta else {}
    text = render.render_progress(state, meta)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"progress 视图已写入: {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="progress_render", description="workflow-state → progress.md 派生视图")
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", default="{}", help="JSON：name/id/milestone_mode")
    args = ap.parse_args(argv)
    return _cmd_render(args)


if __name__ == "__main__":
    raise SystemExit(main())
