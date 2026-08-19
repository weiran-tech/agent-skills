# ============================================================
# 状态机 — 纯函数
# 正交维度 / 单门不变量 / 转换表数据驱动
# 只依赖 model/state-machine.yml，无状态副作用；状态写入由 adapters/statectl 执行
# ============================================================
from __future__ import annotations

from pathlib import Path

import yaml

from . import vocab

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
_DEFAULT_MODEL_PATH = MODEL_DIR / "state-machine.yml"

_model_cache = None


class TransitionError(ValueError):
    pass


def _flatten_transitions(model: dict) -> dict:
    """把 transitions.{flow}: [...] 分组的书写糖扁平化回 model["transitions"] 列表。

    唯一格式：transitions 必须是 {flow: [transitions]} 分组 dict（milestone/task/plan/cr/accept）。
    engine 遍历仍用扁平列表，因此 find_transition 逻辑零改动。非 dict 输入直接报错（无兼容路径）。
    """
    flat = []
    for entries in model["transitions"].values():
        flat.extend(entries)
    model["transitions"] = flat
    return model


def load_model(path: str | Path | None = None) -> dict:
    global _model_cache
    if path is not None:
        with open(path) as fh:
            return _flatten_transitions(yaml.safe_load(fh))
    if _model_cache is None:
        with open(_DEFAULT_MODEL_PATH) as fh:
            _model_cache = _flatten_transitions(yaml.safe_load(fh))
    return _model_cache


def _payload_get(payload: dict, path: str):
    cur = payload
    for part in path.split("."):
        if part == "payload":
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _guard_ok(when, payload: dict) -> bool:
    if not when:
        return True
    for cond in when:
        val = _payload_get(payload, cond["path"])
        op = cond["op"]
        expected = cond["value"]
        if op == "==" and val != expected:
            return False
        if op == "!=" and val == expected:
            return False
        if op == "in" and val not in expected:
            return False
        if op == "has" and (expected not in val if isinstance(val, (list, tuple, str)) else True):
            return False
    return True


def find_transition(model: dict, scope: str, from_state: str, event: str,
                    decision: str | None = None, payload: dict | None = None) -> dict | None:
    """按 from+event+decision 匹配 + when 守卫过滤，返回唯一转换或 None。"""
    matches = []
    for t in model["transitions"]:
        if t.get("scope") != scope:
            continue
        if t["from"] != "*" and t["from"] != from_state:
            continue
        if t["event"] != event:
            continue
        if t.get("decision") is not None and t["decision"] != decision:
            continue
        if not _guard_ok(t.get("when"), payload or {}):
            continue
        matches.append(t)
    if len(matches) > 1:
        raise TransitionError(f"多条匹配转换: {[m['id'] for m in matches]}")
    return matches[0] if matches else None


# ---------------- 副作用 ----------------

def _resolve_effect_value(val, context: dict):
    if isinstance(val, str):
        return {"$task": context.get("task_id"),
                "$reason": context.get("reason"),
                "$resume_event": context.get("resume_event")}.get(val, val)
    if isinstance(val, dict):
        return {k: _resolve_effect_value(v, context) for k, v in val.items()}
    return val


def apply_effects(ms: dict, effects: dict | None, context: dict) -> dict:
    """把转换副作用应用到里程碑状态。返回新 ms。"""
    new_ms = dict(ms)
    if not effects:
        return new_ms
    if effects.get("clear_pending_gate"):
        new_ms["pending_gate"] = None
    if "set_lifecycle" in effects:
        new_ms["lifecycle"] = effects["set_lifecycle"]
    if "set_pending_gate" in effects:
        pg = _resolve_effect_value(effects["set_pending_gate"], context)
        new_ms["pending_gate"] = {"type": pg["type"], "target_task": pg.get("target_task"),
                                  "since": context.get("since")}
    if effects.get("set_blocker"):
        blk = _resolve_effect_value(effects["set_blocker"], context)
        new_ms["lifecycle"] = vocab.Lifecycle.BLOCKED.value
        new_ms["blocker"] = blk
    if effects.get("clear_blocker"):
        new_ms["lifecycle"] = vocab.Lifecycle.ACTIVE.value
        new_ms["blocker"] = None
    return new_ms


# ---------------- 转换应用 ----------------

def apply_task(model: dict, state: str, event: str, payload: dict | None = None,
               decision: str | None = None) -> tuple[str, dict | None, TransitionError | None]:
    """任务级转换。返回 (新状态, 需上抛到里程碑的 effects, error)。"""
    t = find_transition(model, "task", state, event, decision=decision, payload=payload)
    if t is None:
        return state, None, TransitionError(f"任务无合法转换: state={state} event={event} decision={decision}")
    return t["to"], t.get("effects"), None


def apply_milestone(model: dict, ms: dict, event: str, payload: dict | None = None,
                    decision: str | None = None, context: dict | None = None) -> tuple[dict, TransitionError | None]:
    """里程碑级转换 + 副作用应用。ms: {phase, lifecycle, pending_gate, blocker}。"""
    context = context or {}
    phase = ms["phase"]
    t = find_transition(model, "milestone", phase, event, decision=decision, payload=payload)
    if t is None:
        return ms, TransitionError(f"里程碑无合法转换: phase={phase} event={event} decision={decision}")

    # 单门不变量：产生新门时当前不得已有未决门
    effects = t.get("effects") or {}
    if "set_pending_gate" in effects and ms.get("pending_gate") is not None:
        return ms, TransitionError("单门不变量：已有未决人工门，须先解决")
    # 人工门批准事件：必须匹配当前 pending_gate（gate_events 唯一来源 model/state-machine.yml）
    gate_events = model.get("milestone", {}).get("gate_events", {})
    if event in gate_events:
        gt = gate_events[event]
        if ms.get("pending_gate") is None or ms["pending_gate"].get("type") != gt:
            return ms, TransitionError(f"人工门不匹配: 事件 {event} 要求 gate={gt}，当前 pending_gate={ms.get('pending_gate')}")
        if gt in ("PLAN", "CR"):
            target = ms["pending_gate"].get("target_task")
            if context.get("task_id") and target and context["task_id"] != target:
                return ms, TransitionError(f"approve 定位错误: 当前门 target={target}，提交任务={context.get('task_id')}")

    new_ms = dict(ms)
    if not t.get("to_same"):
        new_ms["phase"] = t["to"]
    return apply_effects(new_ms, effects, context), None
