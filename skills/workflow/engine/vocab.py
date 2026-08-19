# ============================================================
# 工作流词汇常量 — 从 model/ 派生（唯一权威），代码禁止硬编码字面量
# 背景：事件/状态/阶段/门/决策/能力/枚举值是 model 定义的领域词汇。
#       手写字符串会随 model 改动静默漂移；本模块在 import 时从 model 生成
#       str 混入的 Enum（Python 3.4+），写错或删除成员在 import 时即报错（fail fast）。
# 用法：from engine import vocab; vocab.Event.TASK_STARTED
# 注意：本模块直接读 model 文件，不依赖 state_machine/policy（避免循环 import）。
# ============================================================
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import yaml

_MODEL_DIR = Path(__file__).resolve().parent.parent / "model"


def _load() -> tuple[dict, dict, dict]:
    model = yaml.safe_load((_MODEL_DIR / "state-machine.yml").read_text(encoding="utf-8"))
    policy = yaml.safe_load((_MODEL_DIR / "policy.yml").read_text(encoding="utf-8"))
    events = json.loads((_MODEL_DIR / "events.schema.json").read_text(encoding="utf-8"))
    return model, policy, events


def _enum(name: str, values) -> type[Enum]:
    """从值序列构造 str 混入枚举：成员名 == 值（Event.TASK_STARTED == "TASK_STARTED"）。"""
    mapping = {str(v): str(v) for v in values}
    return Enum(name, mapping, type=str)


model, policy, events = _load()

Event = _enum("Event", model["events"].keys())
State = _enum("State", model["task_states"].keys())
Phase = _enum("Phase", model["milestone"]["phase_values"].keys())
Lifecycle = _enum("Lifecycle", model["milestone"]["lifecycle_values"].keys())
Gate = _enum("Gate", model["milestone"]["gate_types"])

# Decision：policy 决策矩阵 + implicit_decisions + 转换表 decision 字段
_decisions: set[str] = set()
for _rules in policy.get("decisions", {}).values():
    _decisions |= {r["decision"] for r in _rules}
_decisions |= set(policy.get("implicit_decisions", {}).values())
for _flow in model["transitions"].values():  # 原始 YAML：{flow: [转换]}
    _decisions |= {t.get("decision") for t in _flow if t.get("decision")}
Decision = _enum("Decision", _decisions)

# events.schema.json 领域枚举（显式归类；schema definitions 路径不拆）
Complexity = _enum("Complexity", ["SIMPLE", "NORMAL", "COMPLEX"])
Severity = _enum("Severity", ["MAJOR", "MINOR"])
RootCause = _enum("RootCause", ["IMPLEMENTATION", "DESIGN", "REQUIREMENT"])
Verdict = _enum("Verdict", ["ACCEPTED", "REJECTED", "MODIFIED", "UNCERTAIN", "DESIGN_REWORK"])
Disposition = _enum("Disposition", ["IMPLEMENT_FIX", "BASELINE_ALIGN", "DESIGN_REWORK"])
GateResult = _enum("GateResult", ["PASS", "FAIL", "INCOMPLETE"])
