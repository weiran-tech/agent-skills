# ============================================================
# 不变量检查 — 纯函数
# transition log 是审计副产物，状态文件为唯一路由源
# 由 adapters/validate.py 调用；status 命令默认附带
# ============================================================
from __future__ import annotations

from . import state_machine as sm
from . import vocab


def check_enum(model: dict, state: dict) -> list[str]:
    """状态枚举合法性检查。返回违规列表。"""
    violations = []
    ms = state.get("milestone") or {}
    phase = ms.get("phase")
    lifecycle = ms.get("lifecycle")
    if phase not in model["milestone"]["phase_values"]:
        violations.append(f"里程碑 phase 非法: {phase!r}")
    if lifecycle not in model["milestone"]["lifecycle_values"]:
        violations.append(f"里程碑 lifecycle 非法: {lifecycle!r}")
    valid_task = set(model["task_states"].keys())
    for tid, task in (state.get("tasks") or {}).items():
        if task.get("state") not in valid_task:
            violations.append(f"任务 {tid} 状态非法: {task.get('state')!r}")
    return violations


def check_single_gate(state: dict, model: dict | None = None) -> list[str]:
    """单门不变量：pending_gate 不得与任务级门共存多余一个。

    gate_types 唯一来源 model/state-machine.yml#milestone.gate_types（禁止硬编码）。
    """
    violations = []
    ms = state.get("milestone") or {}
    pg = ms.get("pending_gate")
    if pg is not None:
        if model is None:
            model = sm.load_model()
        gate_types = set(model["milestone"]["gate_types"])
        if pg.get("type") not in gate_types:
            violations.append(f"pending_gate.type 非法: {pg.get('type')!r}")
        if pg.get("type") in (vocab.Gate.PLAN, vocab.Gate.CR) and not pg.get("target_task"):
            violations.append(f"任务级门缺少 target_task: {pg!r}")
    return violations


def check_done_via_verify(state: dict, log: list[dict] | None = None) -> list[str]:
    """任务 DONE 必须来自 VERIFYING + VERIFY_PASSED；里程碑 COMPLETED 必须来自 ACCEPTING。"""
    violations = []
    if log:
        for tid, task in (state.get("tasks") or {}).items():
            if task.get("state") == vocab.State.DONE:
                last = next((e for e in reversed(log) if e.get("task_id") == tid), None)
                if last and last.get("event") != vocab.Event.VERIFY_PASSED:
                    violations.append(f"任务 {tid} DONE 但最近事件为 {last.get('event')!r}")
    ms = state.get("milestone") or {}
    if ms.get("phase") == vocab.Phase.COMPLETED:
        last = log[-1] if log else None
        if last and last.get("event") != vocab.Event.ACCEPTANCE_COMPLETED:
            violations.append("里程碑 COMPLETED 但最近事件非 ACCEPTANCE_COMPLETED")
    return violations


def check_log_consistency(state: dict, log: list[dict]) -> list[str]:
    """transition log 为审计副产物：不得与状态矛盾（最近状态写入应可回溯）。"""
    violations = []
    if not log:
        return violations
    # 事件名必须在模型事件集内
    model = sm.load_model()
    valid_events = set(model["events"].keys())
    for e in log:
        if e.get("event") not in valid_events:
            violations.append(f"日志含未知事件: {e.get('event')!r}")
    return violations


def check_design_rework_exit(state: dict, log: list[dict]) -> list[str]:
    """design_rework_exit：CR 裁决 REQUEST_DESIGN_REWORK 后任务不得进入 CR_FIXING（G-6 修复）。"""
    violations = []
    for tid, task in (state.get("tasks") or {}).items():
        if task.get("state") != vocab.State.CR_FIXING:
            continue
        last_cr = next((e for e in reversed(log)
                        if e.get("task_id") == tid and e.get("event") == vocab.Event.CR_JUDGED), None)
        if last_cr and last_cr.get("decision") == vocab.Decision.REQUEST_DESIGN_REWORK:
            violations.append(f"任务 {tid} CR_JUDGED 裁决为设计返工，但状态为 CR_FIXING")
    return violations


def check_plan_before_code(state: dict, log: list[dict] | None = None) -> list[str]:
    """task_plan_before_code：COMPLEX 任务必须经 plan 确认（PLAN_CONFIRMED）才能进入编码态。"""
    coding_states = (vocab.State.CODING, vocab.State.CR_PLANNED, vocab.State.CR_SCANNED,
                     vocab.State.CR_JUDGED, vocab.State.CR_FIXING, vocab.State.CR_RECHECKING,
                     vocab.State.CR_PASSED, vocab.State.VERIFYING)
    violations = []
    for tid, task in (state.get("tasks") or {}).items():
        if task.get("complexity") == vocab.Complexity.COMPLEX and task.get("state") in coding_states:
            if not task.get("plan_confirmed"):
                violations.append(f"任务 {tid} 为 COMPLEX 但未经 plan 确认即进入编码态 {task.get('state')}")
    return violations


def check_fix_contract_required(state: dict, log: list[dict] | None = None) -> list[str]:
    """fix_contract_required：任务处于 CR_FIXING 必须已有修复契约（fix_contract_path 非空）。"""
    violations = []
    for tid, task in (state.get("tasks") or {}).items():
        if task.get("state") == vocab.State.CR_FIXING and not task.get("fix_contract_path"):
            violations.append(f"任务 {tid} 处于 CR_FIXING 但缺少修复契约 fix_contract_path")
    return violations


def check_baseline_align_requires_update(state: dict, log: list[dict] | None = None) -> list[str]:
    """baseline_align_requires_update：经 BASELINE_ALIGN 进 CR_FIXING 的任务，脱离修复前必须已真改基线。

    baseline_align / baseline_fp_before / baseline_updated 由 statectl 簿记写入；
    statectl 在 REWRITE_COMPLETED 时校验 design-baseline.md 指纹确实变化，通过才置 baseline_updated。
    此处只做状态/元数据一致性机器校验。
    """
    violations = []
    post_fix = (vocab.State.CR_RECHECKING, vocab.State.CR_PASSED, vocab.State.VERIFYING,
                vocab.State.DONE, vocab.State.AUTONOMOUS_BLOCKED)
    for tid, task in (state.get("tasks") or {}).items():
        if task.get("baseline_align") and task.get("state") in post_fix and not task.get("baseline_updated"):
            violations.append(f"任务 {tid} 经 BASELINE_ALIGN 修复但未记录基线已更新 baseline_updated")
        if task.get("baseline_align") and task.get("state") == vocab.State.CR_FIXING \
                and "baseline_fp_before" not in task:
            violations.append(f"任务 {tid} 处于 CR_FIXING 但 BASELINE_ALIGN 未捕获基线指纹 baseline_fp_before")
    return violations


def check_cr_pass_quality_gate(state: dict, log: list[dict] | None = None) -> list[str]:
    """cr_pass_requires_quality_gate：任务处于 CR_PASSED 必须已有客观质量门证据（非空）。"""
    violations = []
    for tid, task in (state.get("tasks") or {}).items():
        if task.get("state") == vocab.State.CR_PASSED and not task.get("quality_gate_evidence"):
            violations.append(f"任务 {tid} 处于 CR_PASSED 但缺少客观质量门证据 quality_gate_evidence")
    return violations


def check_zero_autonomous_blocked(state: dict, log: list[dict] | None = None) -> list[str]:
    """AUTONOMOUS_COMPLETED 前置：任何任务不得处于或曾经处于 AUTONOMOUS_BLOCKED（零发生）。

    若里程碑声称自治高质量完成（phase=AUTONOMOUS_COMPLETED），
    则不得存在任务级阻塞（当前状态或历史 decision 均算违规）。
    """
    violations = []
    ms = state.get("milestone") or {}
    if ms.get("phase") != vocab.Phase.AUTONOMOUS_COMPLETED:
        return violations
    tasks = state.get("tasks") or {}
    for tid, task in tasks.items():
        if task.get("state") == vocab.State.AUTONOMOUS_BLOCKED:
            violations.append(f"里程碑为 AUTONOMOUS_COMPLETED 但任务 {tid} 处于 AUTONOMOUS_BLOCKED")
    if log:
        blocked_tasks = {e.get("task_id") for e in log if e.get("decision") == vocab.Decision.AUTONOMOUS_BLOCK}
        for tid in sorted(blocked_tasks):
            violations.append(f"里程碑为 AUTONOMOUS_COMPLETED 但任务 {tid} 曾触发 AUTONOMOUS_BLOCK")
    return violations


_SPLIT_OK_PHASES = {"DISCUSSING", "ANALYZING", "DESIGN_REVIEW", "DISPATCHING", "DEVELOPING"}


def check_split_window(state: dict, model: dict | None = None) -> tuple[bool, str]:
    """split 窗口：开发开始前允许拆里程碑；任一任务离开 TODO（首个 TASK_STARTED）即关闭。

    拆分是设计/规划期的交付切片决策，必须发生在任何任务启动之前——完成部分任务后再拆
    会撕裂任务归属、导致 dev-tasks 与 state 任务集不一致而漏任务。init-tasks 全量登记后
    任务仍为 TODO，窗口关闭锚点 = 首个任务离开 TODO（而非登记本身）。
    """
    ms = state.get("milestone") or {}
    phase = ms.get("phase")
    if model is None:
        model = sm.load_model()
    if phase not in model["milestone"]["phase_values"]:
        return False, f"里程碑 phase 非法: {phase!r}"
    if phase not in _SPLIT_OK_PHASES:
        return False, f"阶段 {phase} 已过开发窗口，禁止 split"
    tasks = state.get("tasks") or {}
    for tid in sorted(tasks):
        if tasks[tid].get("state") != vocab.State.TODO.value:
            return False, f"开发已开始：任务 {tid} 处于 {tasks[tid].get('state')!r}，禁止 split（拆分须在任何任务启动前）"
    return True, "无任务离开 TODO（未开发），可 split"


def check_all(model: dict, state: dict, log: list[dict] | None = None) -> list[str]:
    """汇总所有不变量检查。"""
    out = []
    out += check_enum(model, state)
    out += check_single_gate(state, model)
    out += check_done_via_verify(state, log)
    out += check_log_consistency(state, log or [])
    out += check_design_rework_exit(state, log or [])
    out += check_plan_before_code(state, log)
    out += check_fix_contract_required(state, log)
    out += check_baseline_align_requires_update(state, log)
    out += check_cr_pass_quality_gate(state, log)
    out += check_zero_autonomous_blocked(state, log)
    return out
