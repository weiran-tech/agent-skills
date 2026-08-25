# ============================================================
# 策略解析器 — 纯函数，无状态副作用
# Policy 只做判断（resolve -> Decision），计数递增由转换层执行
# 实现 model/policy.yml 决策矩阵（顺序判断，首中即返）
# 谓词表达式用最小递归下降解析器求值，不使用 eval
# ============================================================
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import vocab

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
_DEFAULT_POLICY_PATH = MODEL_DIR / "policy.yml"

_QUOTED = re.compile(r"^'([^']*)'$")
_NUM = re.compile(r"^-?\d+$")
_TOKEN = re.compile(
    r"\s*(==|!=|>=|<=|>|<|\band\b|\bor\b|\bnot\b|\bin\b|\bhas\b|\(|\)|\[|\]|,|'[^']*'|[^\s]+)"
)

_policy_cache = None


class PolicyError(ValueError):
    pass


class UnknownEventError(PolicyError):
    pass


class NoDecisionError(PolicyError):
    pass


def load_policy(path: str | Path | None = None) -> dict:
    """加载策略模型（默认 model/policy.yml）。引擎唯一允许的 I/O：读模型。"""
    global _policy_cache
    if path is not None:
        with open(path) as fh:
            return yaml.safe_load(fh)
    if _policy_cache is None:
        with open(_DEFAULT_POLICY_PATH) as fh:
            _policy_cache = yaml.safe_load(fh)
    return _policy_cache


# ---------------- 谓词求值（安全，非 eval） ----------------

def _get(ctx: dict, path: str):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _tokenize(expr: str) -> list[str]:
    toks = _TOKEN.findall(expr)
    if not toks:
        raise PolicyError(f"空谓词: {expr!r}")
    return toks


def _scalar(tok: str):
    m = _QUOTED.match(tok)
    if m:
        return m.group(1)
    if _NUM.match(tok):
        return int(tok)
    if tok in ("true", "false"):
        return tok == "true"
    return tok  # 裸符号 → 字符串


def _parse_value(toks: list[str], i: int, ctx: dict):
    """解析值（字符串/数字/布尔/列表字面量/路径引用）。返回 (新下标, 值)。"""
    tok = toks[i]
    if tok == "[":
        vals = []
        i += 1
        while toks[i] != "]":
            i, v = _parse_value(toks, i, ctx)
            vals.append(v)
            if toks[i] == ",":
                i += 1
        return i + 1, vals
    if tok in ("true", "false"):
        return i + 1, tok == "true"
    m = _QUOTED.match(tok)
    if m:
        return i + 1, m.group(1)
    if _NUM.match(tok):
        return i + 1, int(tok)
    if "." in tok:  # 路径引用（如 limits.acceptance_fix_max）
        return i + 1, _get(ctx, tok)
    return i + 1, tok  # 裸符号 → 字符串


def _parse_primary(toks: list[str], i: int, ctx: dict):
    tok = toks[i]
    if tok == "not":
        i, v = _parse_primary(toks, i + 1, ctx)
        return i, not v
    if tok == "(":
        i, v = _parse_or(toks, i + 1, ctx)
        if toks[i] != ")":
            raise PolicyError("缺右括号")
        return i + 1, v
    if tok in ("true", "false"):
        return i + 1, tok == "true"
    # path op value；路径后无操作符 → 按布尔真值处理（如 `not payload.simple_gate_valid`）
    path = tok
    if i + 1 >= len(toks) or toks[i + 1] not in ("==", "!=", ">", ">=", "<", "<=", "in", "has"):
        return i + 1, bool(_get(ctx, path))
    op = toks[i + 1]
    i += 2
    left = _get(ctx, path)
    if op == "has":
        i, right = _parse_value(toks, i, ctx)
        return i, isinstance(left, (list, tuple)) and right in left
    if op == "in":
        i, right = _parse_value(toks, i, ctx)
        return i, left in right
    i, right = _parse_value(toks, i, ctx)
    if op in ("==", "!="):
        return i, (left == right) if op == "==" else (left != right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return i, {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op]
    raise PolicyError(f"无法比较 {path} {op} {right!r}")


def _parse_and(toks: list[str], i: int, ctx: dict):
    i, v = _parse_primary(toks, i, ctx)
    while i < len(toks) and toks[i] == "and":
        i, r = _parse_primary(toks, i + 1, ctx)
        v = v and r
    return i, v


def _parse_or(toks: list[str], i: int, ctx: dict):
    i, v = _parse_and(toks, i, ctx)
    while i < len(toks) and toks[i] == "or":
        i, r = _parse_and(toks, i + 1, ctx)
        v = v or r
    return i, v


def eval_predicate(expr: str, ctx: dict) -> bool:
    toks = _tokenize(expr)
    i, v = _parse_or(toks, 0, ctx)
    if i != len(toks):
        raise PolicyError(f"谓词有多余内容: {toks[i:]!r}")
    return bool(v)


# ---------------- SIMPLE Gate 有效性（fs-2 固定安全规则） ----------------
# 文件数阈值按变更类型（风险驱动而非纯文件数驱动），唯一数据源 model/policy.yml#simple_gate.max_files
# （禁止在代码里复制模型数据）；risk_signals 仍独立把关。


def simple_gate_valid(payload: dict) -> bool:
    """SIMPLE Gate 通过条件。非 SIMPLE 任务返回 True（由首条规则走 RUN_CR，此标志不参与）。"""
    if payload.get("complexity") != vocab.Complexity.SIMPLE:
        return True
    gate = payload.get("simple_gate")
    if not isinstance(gate, dict):
        return False
    kind = gate.get("change_kind", "CODE")
    thresholds = load_policy().get("simple_gate", {}).get("max_files", {})
    # 仅显式声明 unlimited 的类型不限文件数；未知类型保守回退 CODE 阈值（schema 先拦未知枚举，防御纵深）
    max_files = thresholds.get(kind, thresholds.get("CODE", 2))
    if max_files != "unlimited":
        if not isinstance(gate.get("changed_file_count"), int) or not (1 <= gate["changed_file_count"] <= max_files):
            return False
    for key in ("scope_check", "tests", "static_checks", "diff_integrity"):
        if gate.get(key) != vocab.GateResult.PASS:
            return False
    if gate.get("risk_signals"):
        return False
    if not gate.get("evidence_path"):
        return False
    return True


# ---------------- 决策入口 ----------------

def resolve(event: str, payload: dict | None = None, limits: dict | None = None,
            quality: dict | None = None, capabilities: dict | None = None) -> str:
    """返回标准动作 Decision。纯判断，无副作用。

    参数:
      event:   事件名（model/events.schema.json）
      payload: 事件 payload
      limits:  配置 limits（如 cr_fix_max / acceptance_fix_max）
      quality: 配置 quality（cr.levels 严重度行为 cr_zero_auto_confirm / cr_minor_auto_fix、
               judge_min_confidence）
      capabilities: 各域 capabilities 显式值（advance_stage / advance_task / advance_accept /
                   advance_summary / simple_skip_cr / plan_auto_validate /
                   accept_auto_fix；无 profile 运行时概念，preset 仅为 init 模板）
    返回:
      Decision 字符串（如 RUN_CR / WAIT_USER_APPROVAL）
    """
    policy = load_policy()
    rules = policy["decisions"].get(event)
    if rules is None:
        raise UnknownEventError(f"未知事件: {event}")
    payload = dict(payload or {})
    if event == vocab.Event.TASK_DOD_PASSED:
        payload["simple_gate_valid"] = simple_gate_valid(payload)
    ctx = {"payload": payload, "limits": limits or {}}
    # 能力标志注入谓词上下文（配置显式值）
    ctx.update({k: bool(v) for k, v in (capabilities or {}).items()})
    # CR 严重度行为（cr.levels）+ judge 置信度（终态路由 advance_summary 经 capabilities 注入）
    q = quality or {}
    ctx["quality"] = {"judge_min_confidence": q.get("judge_min_confidence", 0.85)}
    ctx["cr_zero_auto_confirm"] = q.get("cr_zero_auto_confirm", True)
    ctx["cr_minor_auto_fix"] = q.get("cr_minor_auto_fix", False)
    for rule in rules:
        if eval_predicate(rule["when"], ctx):
            return rule["decision"]
    raise NoDecisionError(f"{event} 无匹配决策")
