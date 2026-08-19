# ============================================================
# 词表一致性检查 — 手写 md 的工作流词汇必须与 model 一致
# 背景：SKILL.md / README / references / prompts 手写文档会引用事件/决策/状态/门/能力键。
#       加流程后这些文档若漏改会静默漂移；本模块机器校验，让漂移当场可见。
# 覆盖：带下划线的 UPPER_SNAKE token（事件/决策/多词状态/能力键/门事件/枚举值）与
#       lowercase chain_case token（config/payload 字段名，如 fix_max / min_confidence），
#       不在 model 词表即报错。单词语（如 COMPLETED/DONE 之外的英文、SQL 关键字）不受检，
#       因为无法与普通英文区分（文档化局限）。
# 词表来源：model/state-machine.yml + model/policy.yml + model/events.schema.json（唯一权威）
# ============================================================
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from . import ROOT, _MODEL_DIR
from engine import state_machine as sm  # noqa: E402  (transitions 需与引擎一致地扁平化)

# 非工作流但合法的带下划线词；增补需附理由，保持最小
_ALLOW_UNDERSCORE = {
    "AUTO_INCREMENT",  # summary change-manifest DDL 模板
    # statectl next 输出动作契约（stage-4.0 消费；非 model 状态机词，属 adapter 输出协议）
    "START_NEXT_TASK", "ASK_NEXT_TASK", "ADVANCE_TO_ACCEPT", "ASK_ADVANCE_TO_ACCEPT",
    "WAIT_GATE", "CONTINUE",
}

_TOK = re.compile(r"\b[A-Z][A-Z0-9_]{4,}\b")

# lowercase chain_case：config/payload 字段名（如 fix_max / min_confidence / stage_advance）。
# ≥5 字符且必须含 _，避免与普通英文词混淆；词表见 _load_lower_vocab（model 派生）。
_TOK_LOWER = re.compile(r"\b[a-z][a-z0-9_]{4,}\b")

# 非 config/payload 但合法的 lowercase 下划线词；增补需附理由，保持最小
_ALLOW_LOWER = {
    "pending_gate", "target_task", "task_state",      # workflow-state.yml / statectl get 输出字段
    "agent_id", "subagent_type",                      # Agent 工具/协议字段（Claude Code harness，不在 model）
    "job_name", "queue_name",                         # summary 模板业务字段（DDL/Job·MQ 交付物）
    "idx_name",                                       # summary 模板 DDL 索引标识符
    "doc_lint", "generate_docs", "progress_render", "state_machine",  # 工具/引擎文件名（维护参考）
    "check_zero_autonomous_blocked",                  # engine/invariants.py 函数名（stage-5 引用）
    "design_rework_exit",                             # invariants.py 不变量名（stage-4.2/rework 引用；不变量不再声明于 model）
    "baseline_align",                                 # 修复契约 baseline_align 段字段名（stage-4.2/executor 引用；非 payload 键，位于 fix-contract.md）
    "fail_modes",                                     # stage 文档 frontmatter 语义类别（v2 定稿 §9）
    "max_files",                                      # model/policy.yml#simple_gate.max_files 数据段键（lower 词表只收集 when 谓词，数据段键手动登记）
    "hotfix_simple_skip_cr",                          # configctl 扁平能力名（schema 嵌套 hotfix.capabilities.simple_skip_cr 的扁平化产物）
}


def _load_vocab() -> set:
    """从 model 构建合法工作流词表（事件/状态/阶段/门/决策/能力键/profile/枚举）。"""
    model = sm.load_model()
    policy = yaml.safe_load((_MODEL_DIR / "policy.yml").read_text(encoding="utf-8"))
    events = json.loads((_MODEL_DIR / "events.schema.json").read_text(encoding="utf-8"))

    vocab = set(model["events"].keys())
    vocab |= set(model["task_states"].keys())
    vocab |= set(model["milestone"]["phase_values"].keys())
    vocab |= set(model["milestone"]["lifecycle_values"].keys())
    vocab |= set(model["milestone"]["gate_types"])
    vocab |= set(model["milestone"].get("gate_events", {}).keys())
    vocab |= set(model["milestone"].get("gate_events", {}).values())
    for rules in policy.get("decisions", {}).values():
        vocab |= {r["decision"] for r in rules}
    vocab |= set(policy.get("implicit_decisions", {}).values())
    vocab |= {t.get("decision") for t in model["transitions"] if t.get("decision")}

    def collect(node):
        nonlocal vocab
        if isinstance(node, dict):
            if "enum" in node:
                vocab |= set(node["enum"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)

    collect(events)
    # Judge 裁决协议额外值（stage-4.2 语义；design_rework 处置与低置信度裁决，非 payload 枚举）
    vocab |= {"UNCERTAIN", "DESIGN_REWORK"}
    return vocab


def _collect_keys(node, vocab: set) -> None:
    """递归收集 dict 的所有带下划线键（config/payload/agent 契约字段名）。"""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and "_" in k:
                vocab.add(k)
            _collect_keys(v, vocab)
    elif isinstance(node, list):
        for v in node:
            _collect_keys(v, vocab)


def _load_lower_vocab() -> set:
    """构建 lowercase 标识符词表：config/payload 字段名 + agent 契约键 + 谓词 token + 状态机结构键。

    来源（唯一权威）：model/config.schema.json（配置键）、model/events.schema.json（payload 字段）、
    model/agent-contracts.yml（契约键）、model/presets.yml#docs（注释键末段）、
    model/policy.yml#decisions.when（扁平能力/限额名）、model/state-machine.yml（gate_events 键）。
    非模型标识符的合法例外见 _ALLOW_LOWER。
    """
    cfg = json.loads((_MODEL_DIR / "config.schema.json").read_text(encoding="utf-8"))
    events = json.loads((_MODEL_DIR / "events.schema.json").read_text(encoding="utf-8"))
    agents = yaml.safe_load((_MODEL_DIR / "agent-contracts.yml").read_text(encoding="utf-8"))
    presets = yaml.safe_load((_MODEL_DIR / "presets.yml").read_text(encoding="utf-8"))
    policy = yaml.safe_load((_MODEL_DIR / "policy.yml").read_text(encoding="utf-8"))
    model = sm.load_model()

    vocab: set = set()
    for doc in (cfg, events, agents):
        _collect_keys(doc, vocab)
    for key in presets.get("docs", {}):  # docs 键为点路径，取末段（如 cr.limits.fix_max → fix_max）
        vocab.add(key.rsplit(".", 1)[-1])
    for rules in policy.get("decisions", {}).values():  # 谓词 token（plan_auto_validate / acceptance_fix_max 等扁平名）
        for r in rules:
            vocab.update(re.findall(r"[a-z][a-z0-9_]+", r["when"]))
    vocab.add("gate_events")  # 状态机结构键（MD 引用 model 定位锚）
    vocab.update(model.get("milestone", {}).get("gate_events", {}).keys())
    # 不变量键不再从 model 派生：唯一来源 engine/invariants.py；文档引用的不变量名见 _ALLOW_LOWER
    return vocab


def _scan(path: Path, vocab: set, lower_vocab: set) -> list[str]:
    violations = []
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path  # ROOT 外（测试临时文件）回退绝对路径
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for tok in _TOK.findall(line):
            if "_" not in tok:
                continue  # 单词语与普通英文无法区分，不受检
            if tok in vocab or tok in _ALLOW_UNDERSCORE:
                continue
            violations.append(f"{rel}:{i}: 未知工作流词 {tok!r}（不在 model 词表）")
        for tok in _TOK_LOWER.findall(line):
            if "_" not in tok:
                continue
            if tok in lower_vocab or tok in _ALLOW_LOWER:
                continue
            violations.append(f"{rel}:{i}: 未知配置/payload 字段 {tok!r}（不在 config/events 模型词表）")
    return violations


def _targets() -> list[Path]:
    out = [ROOT / "SKILL.md", ROOT / "README.md"]
    out += sorted((ROOT / "references").rglob("*.md"))
    out += sorted((ROOT / "prompts").rglob("*.md"))
    return [p for p in out if p.exists()]


def scan_all() -> list[str]:
    """扫描所有手写 md 目标，返回全部词表违规。"""
    vocab = _load_vocab()
    lower_vocab = _load_lower_vocab()
    out = []
    for p in _targets():
        out += _scan(p, vocab, lower_vocab)
    return out
