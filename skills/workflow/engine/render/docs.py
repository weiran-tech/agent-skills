# ============================================================
# model → generated/*.md 渲染器（纯函数，dev：_internal/generate_docs.py 消费）
# 输出带 GENERATED 标记；generated/* 漂移由维护侧 generate_docs.py --check 兜底
# 拆自原 engine/renderer.py 的文档渲染部分
# ============================================================
from __future__ import annotations

from . import _GENERATED_HEADER


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def render_automation(policy: dict) -> str:
    out = [_GENERATED_HEADER, "# Automation 策略（生成）\n"]
    out.append("> 配置全显式（无 profile 运行时概念）；内置预设（manual/guarded/autonomous）仅为 "
               "`configctl init` 模板，见 `model/presets.yml`。决策矩阵直接引用配置显式能力标志。\n")
    # 决策矩阵
    out.append("## 事件决策（顺序判断，首中即返）")
    for event, rules in policy["decisions"].items():
        out.append(f"### {event}")
        out.append(_table(["#", "条件", "Decision"], [[i + 1, r["when"], r["decision"]] for i, r in enumerate(rules)]))
        out.append("")
    # 固定安全规则
    out.append("## 固定安全规则（Profile 不能覆盖）")
    for r in policy["fixed_safety_rules"]:
        out.append(f"- **{r['id']}** {r['rule']}")
    return "\n".join(out) + "\n"


def render_templates(sm: dict) -> str:
    out = [_GENERATED_HEADER, "# progress.md 模板 / 状态枚举（生成）\n"]
    out.append("## 里程碑/需求级正交维度")
    ms = sm["milestone"]
    out.append(f"- **phase**: {', '.join(ms['phase_values'].keys())}")
    out.append(f"- **lifecycle**: {', '.join(ms['lifecycle_values'].keys())}")
    out.append(f"- **pending_gate**: {', '.join(ms['gate_types'])}（单门不变量：同里程碑最多一个）")
    out.append("")
    out.append("## 任务级状态")
    out.append(", ".join(sm["task_states"].keys()))
    out.append("")
    out.append("## 事件")
    for ev, desc in sm["events"].items():
        out.append(f"- `{ev}`：{desc}")
    out.append("")
    out.append("## 任务编号与产出物命名（强制）")
    out.append("- 任务统一 **`X.Y`** 编号（X=任务组，Y=组内子任务，从 1 起始；禁止 T1/0.1/波次1 等非标格式）")
    out.append("- plan: `.task/plans/{范围标签}-{X.Y}.md`")
    out.append("- done 报告: `.task/done/{范围标签}-{X.Y}.md`")
    out.append("- review-plan: `.task/review/{范围标签}-{X.Y}/review-plan.md`")
    out.append("- CR 维度报告: `.task/review/{范围标签}-{X.Y}/{implementation|security|design|performance}.md`")
    out.append("- CR 统一报告: `.task/review/{范围标签}-{X.Y}/unified.md`")
    out.append("")
    out.append("## 任务清单行模板")
    out.append("```\n- [ ] {X.Y} {范围标签} · {任务标题} [{简单|普通|复杂}] — 状态: {task_state}\n```")
    return "\n".join(out) + "\n"


def render_readme(sm: dict, policy: dict) -> str:
    out = [_GENERATED_HEADER, "# workflow（生成概览）\n"]
    out.append("## 五阶段 + 四道人工门")
    out.append("```")
    out.append("阶段1 需求讨论 → 阶段2 分析与设计 →[★设计审核]→ 阶段4 开发逐任务审查 → 阶段5 收尾验收 →[★验收确认]→ COMPLETED")
    out.append("阶段4 内：复杂任务[★plan门]；每任务 CR 汇总后[★CR 裁决门]")
    out.append("```")
    out.append("")
    out.append("## 任务级闭环")
    out.append("```")
    out.append("TODO → (复杂: PLANNING → PLAN_AWAITING_DECISION → PLAN_CONFIRMED) → CODING → CR_REVIEWING → CR_AWAITING_DECISION → CR_FIXING → VERIFYING → DONE")
    out.append("SIMPLE 且 SKIP_CR: CODING → VERIFYING → DONE")
    out.append("```")
    out.append("")
    out.append("## 预设（Presets，init 模板）")
    out.append("配置全显式，无 profile 运行时概念；预设（manual/guarded/autonomous）仅为 `configctl init` 模板，见 `model/presets.yml`。")
    out.append("")
    return "\n".join(out) + "\n"


def _event_scopes(model: dict) -> dict[str, dict]:
    """事件 → {task, milestone} scope 标记（从 transitions 派生，单一来源）。"""
    scopes: dict[str, dict] = {}
    for t in model["transitions"]:
        scopes.setdefault(t["event"], {"task": False, "milestone": False})[t["scope"]] = True
    return scopes


def render_vocab(policy: dict, model: dict) -> str:
    """词表与路由参考（生成）：状态/事件(scope+决策来源)/Decision/人工门/能力键。

    消费方：SKILL.md 护栏、commands/index.md 分发表引用，避免手写 md 重复维护词汇表。
    """
    out = [_GENERATED_HEADER, "# 词表与路由（生成）\n"]
    ms = model["milestone"]

    out.append("## 里程碑 phase")
    for k, v in ms["phase_values"].items():
        if isinstance(v, dict):  # v2 元数据：{description, semantic_doc}
            desc = v.get("description", "")
            sem = v.get("semantic_doc", "")
            out.append(f"- **{k}**：{desc}" + (f"（{sem}）" if sem else ""))
        else:  # 兼容旧字符串值
            out.append(f"- **{k}**：{v}")
    out.append("")
    out.append("## 里程碑 lifecycle")
    out.append(", ".join(ms["lifecycle_values"].keys()))
    out.append("")
    out.append("## 任务级状态")
    out.append(", ".join(model["task_states"].keys()))
    out.append("")

    # 事件：scope + 决策来源
    out.append("## 事件（scope + 决策来源）")
    matrix = set(policy.get("decisions", {}).keys())
    implicit = policy.get("implicit_decisions", {})
    rows = []
    for ev in sorted(_event_scopes(model)):
        sc = _event_scopes(model)[ev]
        scope = ("task" if sc["task"] and not sc["milestone"]
                 else "milestone" if sc["milestone"] and not sc["task"] else "task+milestone")
        if ev in matrix:
            src = "Policy 矩阵"
        elif ev in implicit:
            src = f"implicit_decisions → {implicit[ev]}"
        else:
            src = "转换表固定（无 Policy）"
        rows.append([ev, scope, src, model["events"].get(ev, "")])
    out.append(_table(["事件", "scope", "决策来源", "说明"], rows))
    out.append("")

    # Decision 清单
    out.append("## Decision 清单")
    decisions: set[str] = set()
    for rules in policy.get("decisions", {}).values():
        decisions.update(r["decision"] for r in rules)
    decisions.update(policy.get("implicit_decisions", {}).values())
    decisions.update(t["decision"] for t in model["transitions"] if t.get("decision"))
    out.append(", ".join(sorted(decisions)))
    out.append("")

    # 人工门
    out.append("## 人工门（gate_types + gate_events）")
    out.append(f"- gate_types: {', '.join(ms['gate_types'])}")
    for ev, gt in ms.get("gate_events", {}).items():
        out.append(f"- `{ev}` → {gt}")
    out.append("")

    out.append(_render_dispatch(model))

    return "\n".join(out) + "\n"


def _fmt_val(v) -> str:
    """when 守卫值渲染（列表 → [A, B]；None → null，与 model YAML 词表一致；其余 str）。"""
    if v is None:
        return "null"
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    return str(v)


def _guard_label(t: dict) -> str:
    """转换守卫的紧凑描述：when 条件 + decision（如 'when=complexity in [SIMPLE,NORMAL], decision=CONFIRM_CR'）。"""
    parts = []
    for cond in t.get("when", []) or []:
        path = str(cond.get("path", "")).replace("payload.", "")
        parts.append(f"when={path} {cond.get('op', '')} {_fmt_val(cond.get('value'))}")
    if t.get("decision") is not None:
        parts.append(f"decision={t['decision']}")
    return ", ".join(parts) if parts else "guard=*"


def _render_dispatch(model: dict) -> str:
    """状态 → 路由（派生，并入 vocab.md）：从 transitions 派生，事件列 = transition.event。

    覆盖 task + milestone 两级；universal（from="*"）转换先渲染置顶；每行带 when/decision guard。
    semantic_doc 取自 state 元数据（source 语义）。
    """
    out = ["## 状态 → 路由（派生，LLM 照读）\n"]
    task_states = model.get("task_states", {})
    phase_values = model.get("milestone", {}).get("phase_values", {})

    def doc_for(scope: str, state: str) -> str:
        src = task_states if scope == "task" else phase_values
        v = src.get(state, {})
        return v.get("semantic_doc", "?") if isinstance(v, dict) else "?"

    def row(t: dict) -> str:
        to = t.get("to")
        if to is None and t.get("to_same"):
            to = "same"
        return (f"- {_guard_label(t)} → action={t.get('action', '?')} "
                f"→ event={t['event']} → to={to if to is not None else '?'}")

    for scope, scope_name in (("task", "task"), ("milestone", "milestone")):
        scoped = [t for t in model["transitions"] if t.get("scope", "task") == scope]
        univ = [t for t in scoped if t["from"] == "*"]
        if univ:
            out.append(f"### {scope}.universal（from=*，适用于该 scope 所有状态）")
            for t in sorted(univ, key=lambda x: x["event"]):
                out.append(row(t))
            out.append("")
        by_from: dict = {}
        for t in scoped:
            if t["from"] != "*":
                by_from.setdefault(t["from"], []).append(t)
        for from_state in sorted(by_from):
            sem = doc_for(scope, from_state)
            note = "（另有 universal 转换见顶部）" if univ else ""
            out.append(f"### {scope}.{from_state} → doc=`{sem}`{note}")
            for t in sorted(by_from[from_state], key=lambda x: (str(x.get('decision')), x['event'])):
                out.append(row(t))
            out.append("")
    return "\n".join(out) + "\n"


def render_commands(model: dict, events_schema: dict) -> str:
    """statectl 命令模板（生成）：每个事件的 transit 骨架 + 必填 payload 字段。

    消费方：stage-N 文档的 bash 示例以本文件为命令契约，示例值仍留在各 stage。
    必填字段来自 model/events.schema.json；占位符 {S}/{C}/{X.Y} 由调用方展开。
    时间戳由 statectl 内部生成（`_now_iso`），命令不携带 --since。
    """
    out = [_GENERATED_HEADER, "# statectl 命令模板（生成）\n"]
    out.append("> `statectl.py transit --state {S} --config {C} --event {EVENT} ...` 骨架。"
               "必填 payload 字段来自 `model/events.schema.json`；具体示例值见各 stage 文档。\n")

    scopes = _event_scopes(model)
    for ev in sorted(scopes):
        is_task = scopes[ev]["task"]
        is_ms = scopes[ev]["milestone"]
        required = events_schema["properties"].get(ev, {}).get("required", [])
        payload_hint = ""
        if required:
            fields = ", ".join(f'"{f}": ...' for f in required)
            payload_hint = f" --payload '{{{fields}}}'"
        if ev == "REWORK_STARTED":
            cmd = ("statectl.py transit --state {S} --config {C} --event REWORK_STARTED"
                   " --payload '{\"level\":\"...\",\"affected_tasks\":[\"...\"]}'")
            note = "task+milestone（里程碑级提交：受影响任务回 TODO）"
        elif is_task and not is_ms:
            cmd = (f"statectl.py transit --state {{S}} --config {{C}} --event {ev}"
                   f" --task {{X.Y}}{payload_hint}")
            note = "task"
        else:
            cmd = (f"statectl.py transit --state {{S}} --config {{C}} --event {ev}"
                   f"{payload_hint}")
            note = "milestone" if is_ms and not is_task else "task+milestone（按上下文）"
        out.append(f"### {ev}（{note}）")
        out.append("```bash")
        out.append(cmd)
        out.append("```")
        out.append("")
    return "\n".join(out) + "\n"


def render_command_dict(agents: dict) -> str:
    """子命令字典（生成）：由 agent-contracts.yml#commands 派生，append 到 commands.md。

    命令根来自 agent-contracts.yml#skill.command（单源，无硬编码），改名只改 model。
    无 GENERATED 头（与 render_commands 合并为一个文档）。
    """
    cmd_root = agents.get("skill", {}).get("command", "/workflow")
    out = [f"\n## {cmd_root} 命令字典（生成）\n"]
    out.append(f"> 由 `model/agent-contracts.yml#commands` 派生；命令根 `{cmd_root}` 单源（skill.command）。\n")
    cmds = agents.get("commands", [])
    out.append("| 命令 | 前置状态 | 读哪 |")
    out.append("|---|---|---|")
    for c in cmds:
        out.append(f"| `{cmd_root} {c['id']}` | {c.get('state_prereq', 'any')} | `{c.get('semantic_doc', '')}` |")
    return "\n".join(out) + "\n"
