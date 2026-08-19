#!/usr/bin/env bash
# ============================================================
# workflow 维护脚本：改 model/ 后一键重建 + 校验
# 背景：状态机/策略/词表以 model/ 为唯一来源，engine 派生读取、generated/* 由 renderer 生成。
#       skill 运行时只读 model/ + generated/ + references/，不需要此脚本；
#       此脚本只在维护者改完 model/ 后手动执行一次（开发侧，不进 skill 执行流）。
# 用法：
#   _internal/setup.sh            重新生成 generated/ + lint + 全量测试
#   _internal/setup.sh --check    只校验不改写（generated 漂移 + lint + 测试），CI/提交前用
# 等价于手跑：
#   python3 _internal/generate_docs.py [--check] && python3 -m _internal.lint \
#     && python3 -m unittest discover -s _internal/tests
# ============================================================
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

if [[ "${1:-}" == "--check" ]]; then
  echo "== check: generated/ 与 model 漂移 =="
  python3 _internal/generate_docs.py --check --out generated
  echo "== check: 一致性（词表 + model 元数据）=="
  python3 -m _internal.lint
else
  echo "== 重新生成 generated/ =="
  python3 _internal/generate_docs.py --out generated
  echo "== 一致性检查（词表 + model 元数据）=="
  python3 -m _internal.lint
fi

echo "== 全量测试 =="
python3 -m unittest discover -s _internal/tests

echo "OK: workflow 模型与文档一致"
