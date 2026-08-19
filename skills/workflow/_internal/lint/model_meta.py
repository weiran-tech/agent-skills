# ============================================================
# 模型元数据校验 — model/ 文件结构一致性（原 doc_lint._check_model_meta 拆出）
# 校验 model/state-machine.yml 的 v2 元数据：
#   - 每个 task_state / milestone.phase_value 有且仅有一个 semantic_doc（值 dict，文件存在）
#   - transitions 不挂 semantic_doc（应挂 state）；不挂 agent_role（单一来源在 action_grammar）
#   - 每个 transition 必须有 action；action ∈ action_grammar
#   - action_grammar 每项的 agent_role ∈ {main} ∪ agent-contracts.yml#agents.id
#   - skill.command == "/" + skill.name（命令根单源）
#   - 顶层禁止 invariants / agent_roles 段（唯一来源 engine/invariants.py / agent-contracts.yml，防回归）
# ============================================================
from __future__ import annotations

import json

import yaml

from . import ROOT, _MODEL_DIR
from engine import state_machine as sm


def check_model_meta(model: dict | None = None) -> list[str]:
    """模型元数据校验（v2 定稿 §7，agent_role 单一来源 = action_grammar）。"""
    violations: list[str] = []
    model = model or sm.load_model()
    for reserved, hint in (("invariants", "唯一来源 engine/invariants.py，此处声明会双重来源漂移"),
                           ("agent_roles", "唯一来源 model/agent-contracts.yml#agents.id")):
        if reserved in model:
            violations.append(f"state-machine.yml 出现 {reserved} 段（{hint}）；该段已收敛，禁止重建（lint 防回归）")
    agents = yaml.safe_load((_MODEL_DIR / "agent-contracts.yml").read_text(encoding="utf-8"))
    valid_roles = {"main"} | set(agents.get("agents", {}).keys())
    grammar = model.get("action_grammar", {})

    def check_state_doc(scope: str, name: str, val) -> None:
        if not isinstance(val, dict) or not val.get("semantic_doc"):
            violations.append(f"{scope}.{name} 缺 semantic_doc（值应为 dict{{description, semantic_doc}}）")
            return
        sem = val["semantic_doc"]
        if not (ROOT / sem).exists():
            violations.append(f"{scope}.{name}.semantic_doc 文件不存在: {sem}")

    for name, val in model["task_states"].items():
        check_state_doc("task_state", name, val)
    for name, val in model.get("milestone", {}).get("phase_values", {}).items():
        check_state_doc("phase", name, val)

    for act, meta in grammar.items():
        g_role = meta.get("agent_role") if isinstance(meta, dict) else None
        if not g_role:
            violations.append(f"action_grammar.{act} 缺 agent_role（单一来源，transition 不再重复）")
        elif g_role not in valid_roles:
            violations.append(f"action_grammar.{act}.agent_role {g_role!r} 不在 {{main}} ∪ agent-contracts#agents")

    skill = agents.get("skill", {})
    if skill.get("command") and skill.get("command") != "/" + (skill.get("name") or ""):
        violations.append(f"skill.command={skill['command']!r} 与 skill.name={skill.get('name')!r} 不一致（应为 /{{name}}）")

    for t in model["transitions"]:
        tid = t.get("id", "?")
        if "semantic_doc" in t:
            violations.append(f"transition {tid} 挂了 semantic_doc（应挂 state，不随 decision 变）")
        if "agent_role" in t:
            violations.append(f"transition {tid} 挂了 agent_role（单一来源在 action_grammar，transition 不重复）")
        act = t.get("action")
        if not act:
            violations.append(f"transition {tid} 缺 action（v2 元数据要求每个 transition 有 action）")
        elif act not in grammar:
            violations.append(f"transition {tid}.action {act!r} 不在 action_grammar")
    violations += check_gate_threshold()
    return violations


# ---------------- SIMPLE Gate 文件数阈值一致性 ----------------
# 单一数据源 model/policy.yml#simple_gate.max_files；events.schema 的 changed_file_count.maximum
# 只是宽松结构硬上限，不得低于 policy 任一有限 kind 的阈值（改阈值后须同步，机器强制防静默打架）。
# unlimited = 该类型不限制文件数（纯测试/纯文档/测试+文档），必须同步登记进 schema change_kind 枚举。


def _gate_threshold_mismatch(max_files: dict, schema_max) -> str | None:
    """schema 硬上限低于 policy 任一有限阈值时返回违规描述（unlimited 不参与比较，纯函数可单测）。"""
    if not max_files:
        return None
    if not isinstance(schema_max, int):
        return "events.schema 的 simple_gate.changed_file_count 缺 maximum（结构硬上限）"
    finite = [v for v in max_files.values() if isinstance(v, int)]
    if finite and schema_max < max(finite):
        top = max(finite)
        return (f"SIMPLE Gate 文件数阈值失配：model/policy.yml#simple_gate.max_files 最大 {top}（{max_files}），"
                f"events.schema 的 changed_file_count.maximum={schema_max} < {top}；改阈值后须同步 schema 上限")
    return None


def _unlimited_enum_coverage(max_files: dict, enum: list) -> str | None:
    """unlimited 类型必须声明在 schema change_kind 枚举；枚举类型必须登记阈值（纯函数，可单测）。"""
    unlimited = [k for k, v in max_files.items() if v == "unlimited"]
    missing = [k for k in unlimited if k not in enum]
    if missing:
        return f"max_files 标记 unlimited 的类型不在 schema change_kind 枚举: {missing}（须同步枚举）"
    missing_kind = [k for k in enum if k not in max_files]
    if missing_kind:
        return f"schema change_kind 枚举缺 policy max_files 阈值: {missing_kind}（须在 simple_gate.max_files 登记）"
    return None


def check_gate_threshold() -> list[str]:
    """SIMPLE Gate 文件数阈值一致性：policy（单一数据源）与 schema 硬上限不打架。"""
    policy = yaml.safe_load((_MODEL_DIR / "policy.yml").read_text(encoding="utf-8"))
    events = json.loads((_MODEL_DIR / "events.schema.json").read_text(encoding="utf-8"))
    max_files = policy.get("simple_gate", {}).get("max_files") or {}
    sg = events.get("definitions", {}).get("simple_gate", {})
    schema_max = sg.get("properties", {}).get("changed_file_count", {}).get("maximum")
    enum = sg.get("properties", {}).get("change_kind", {}).get("enum") or []
    violations = []
    for msg in (_gate_threshold_mismatch(max_files, schema_max),
                _unlimited_enum_coverage(max_files, enum)):
        if msg:
            violations.append(msg)
    return violations
