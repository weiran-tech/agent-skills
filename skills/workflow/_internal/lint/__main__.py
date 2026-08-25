# ============================================================
# 一致性检查 CLI — python3 -m _internal.lint [--json] [--check {all,docs,model}]
# exit 0 通过 / 2 有违规；--json 机器输出
# ============================================================
from __future__ import annotations

import argparse
import json
import sys

from .vocab import scan_all
from .model_meta import check_model_meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lint", description="workflow 一致性检查（手写 md 词表 + model 元数据）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--check", choices=("all", "docs", "model"), default="all",
                    help="docs=词表；model=模型元数据；all=两者（默认）")
    args = ap.parse_args(argv)

    violations: list[str] = []
    if args.check in ("all", "docs"):
        violations += scan_all()
    if args.check in ("all", "model"):
        violations += check_model_meta()

    if args.json:
        print(json.dumps({"ok": not violations, "violations": violations}, ensure_ascii=False))
    else:
        for v in violations:
            print(f"✗ {v}", file=sys.stderr)
        label = {"all": "全部", "docs": "词表", "model": "模型元数据"}[args.check]
        print(f"lint: {'通过' if not violations else f'{label} {len(violations)} 个违规'}")
    return 0 if not violations else 2


if __name__ == "__main__":
    raise SystemExit(main())
