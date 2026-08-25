# ============================================================
# 状态控制 CLI — 薄交易脚本，零业务逻辑
# 唯一转换写入口；Policy 纯判断；状态与日志同事务
# 职责：payload Schema 校验 → engine 决策/转换 → 写 workflow-state + 递增计数 → 追加 transition.log → 返回
# 业务逻辑全在 engine/；本文件只是 sequence + I/O 委托
# ============================================================
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml

# 使 engine 可导入（脚本可能在 skill 根或子目录被调用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import policy, state_machine as sm
from engine import vocab
from adapters import configctl
from adapters._schema import SchemaError, validate_event_payload

DEFAULT_STATE_FILENAME = "workflow-state.yml"
DEFAULT_LOG_FILENAME = "transition.log"


def _task_events(model: dict) -> set:
    """任务级事件集，从 model/state-machine.yml 的 transitions 按 scope=task 派生（单一来源，禁止硬编码）。

    REWORK_STARTED 是 task/milestone 双 scope 事件，由 _transit 显式分支先行处理，
    此处排除以防误入任务分支。
    """
    return {t["event"] for t in model["transitions"]
            if t.get("scope") == "task" and t["event"] != "REWORK_STARTED"}


class StatectlError(ValueError):
    pass


# ---------------- 状态读写 ----------------

def empty_state(meta: dict | None = None) -> dict:
    return {
        "milestone": {"phase": vocab.Phase.DISCUSSING.value, "lifecycle": vocab.Lifecycle.ACTIVE.value,
                      "pending_gate": None, "blocker": None, "fix_attempts": 0},
        "tasks": {},
        "meta": meta or {},
    }


def load_state(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return empty_state()
    with open(p) as fh:
        return yaml.safe_load(fh) or empty_state()


def write_state(path: str | Path, state: dict) -> None:
    """同目录临时文件 + 原子 rename 写入；自动创建父目录（state/ 控制面）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            yaml.safe_dump(state, fh, allow_unicode=True, sort_keys=False)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_log(path: str | Path, entry: dict) -> None:
    """append-only；与状态写入同命令执行，作为审计/恢复副产物。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_log(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with open(p) as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _now_iso() -> str:
    """取本地时区的真实当前时间（ISO 格式）。

    审计时间戳只信任系统时钟：外部传入的时间不可信（LLM 会假填/漏填导致日志全为同一时刻），
    因此日志 ts 与 pending_gate.since 一律由此生成，不再提供 --since/ts 覆盖入口。
    """
    from datetime import datetime

    return datetime.now().astimezone().isoformat()


# ---------------- 决策 ----------------

def _decide(event: str, payload: dict, limits: dict, quality: dict | None = None,
            capabilities: dict | None = None) -> str | None:
    pol = policy.load_policy()
    if event in pol["decisions"]:
        return policy.resolve(event, payload, limits, quality, capabilities)
    # 隐式决策唯一来源 model/policy.yml#implicit_decisions（转换表需要固定 decision 的事件）
    return pol.get("implicit_decisions", {}).get(event)


# payload 引用的产物文件路径字段（唯一来源 model/events.schema.json；新增路径字段须同步）
_PATH_FIELDS = ("plan_path", "unified_report_path", "quality_gate_evidence",
                "fix_contract_path", "acceptance_report_path", "judge_report_path")

# init-tasks 任务编号格式（dev-tasks 约定 X.Y）
_TASK_ID_RE = re.compile(r"^\d+\.\d+$")


def _validate_payload_refs(payload: dict, state_path: str | Path) -> None:
    """payload 引用的产物文件必须存在；不存在即拒（纵深防御，防 LLM 抄模板/虚报产物）。

    基准目录 = state 文件的 {工单根}（state/workflow-state.yml 的 parent.parent）。
    只校验真实存在的路径字段；字符串证据描述（如 VERIFY_FAILED.evidence）不受检。
    """
    base = Path(state_path).parent.parent
    for key in _PATH_FIELDS:
        ref = payload.get(key)
        if ref and not (base / ref).exists():
            raise StatectlError(f"{key} 引用的产物文件不存在: {ref}（payload 值必须从实际产物计算）")
    gate = payload.get("simple_gate") or {}
    ev = gate.get("evidence_path")
    if ev and not (base / ev).exists():
        raise StatectlError(f"simple_gate.evidence_path 引用的产物文件不存在: {ev}（payload 值必须从实际产物计算）")


# ---------------- 转换执行（委托 engine，仅组织副作用） ----------------

def _transit(state: dict, event: str, payload: dict, decision: str | None, context: dict) -> dict:
    model = sm.load_model()
    ms = state["milestone"]
    old_phase = ms["phase"]

    task_events = _task_events(model)
    if event == vocab.Event.REWORK_STARTED:
        # 双 scope 事件：显式分支先行（受影响任务回 TODO + 里程碑按层级回退）
        affected = payload.get("affected_tasks", [])
        for tid in affected:
            state.setdefault("tasks", {}).setdefault(tid, {})["state"] = "TODO"
        new_ms, err = sm.apply_milestone(model, ms, event, payload, decision, context)
        if err:
            raise StatectlError(str(err))
        state["milestone"] = new_ms
    elif event in task_events:
        if not context.get("task_id"):
            raise StatectlError(f"任务事件 {event} 需要 --task")
        tasks = state.setdefault("tasks", {})
        tid = context["task_id"]
        cur = tasks.get(tid, {}).get("state", "TODO")
        new_st, effects, err = sm.apply_task(model, cur, event, payload, decision)
        if err:
            raise StatectlError(str(err))
        tasks[tid] = {**(tasks.get(tid) or {}), "state": new_st}
        # 任务转换的上抛副作用（门）：应用到里程碑，遵守单门不变量
        if effects:
            if "set_pending_gate" in effects and ms.get("pending_gate") is not None:
                raise StatectlError("单门不变量：已有未决人工门，须先解决")
            new_ms = sm.apply_effects(ms, effects, context)
            state["milestone"] = new_ms
    else:
        new_ms, err = sm.apply_milestone(model, ms, event, payload, decision, context)
        if err:
            raise StatectlError(str(err))
        state["milestone"] = new_ms

    # 进入验收阶段时重置自动修复批次（新验收周期）
    if state["milestone"]["phase"] == vocab.Phase.ACCEPTING and old_phase != vocab.Phase.ACCEPTING:
        state["milestone"]["fix_attempts"] = 0
    return state


def _apply_bookkeeping(state: dict, event: str, payload: dict, decision: str | None,
                       task: str | None) -> None:
    """事件后元数据簿记（transit/batch 共用）。

    fixAttempts / complexity / cr_round / plan_confirmed / cr_path / 回滚 /
    fix_contract_path / quality_gate_evidence 都是任务或里程碑元数据，不建模成状态；
    与 _transit 同命令内执行，保证状态文件与元数据一致。
    """
    # fixAttempts：仅当 Decision=FIX_ACCEPTANCE_ISSUES 时由转换层递增
    if decision == vocab.Decision.FIX_ACCEPTANCE_ISSUES:
        state["milestone"]["fix_attempts"] = state["milestone"].get("fix_attempts", 0) + 1
    # 复杂度持久化到任务元数据（task_plan_before_code 不变量输入）
    if event == vocab.Event.TASK_STARTED and task:
        state.setdefault("tasks", {}).setdefault(task, {})["complexity"] = payload.get("complexity")
    # cr_round：CR_RECHECKED 判定继续下一轮时递增（对齐 fix_attempts 模式，权威计数在状态文件）
    if event == vocab.Event.CR_RECHECKED and decision == vocab.Decision.FIX_CR_ISSUES and task:
        t = state.setdefault("tasks", {}).setdefault(task, {})
        t["cr_round"] = t.get("cr_round", 0) + 1
    # REWORK_STARTED：受影响任务回 TODO，plan 确认作废（防 rework 后残留脏标记）
    if event == vocab.Event.REWORK_STARTED:
        for tid in payload.get("affected_tasks", []):
            state.setdefault("tasks", {}).get(tid, {}).pop("plan_confirmed", None)
    # plan 确认标记（task_plan_before_code 不变量输入）
    if task:
        t = state.setdefault("tasks", {}).setdefault(task, {})
        if t.get("state") == vocab.State.PLAN_CONFIRMED:
            t["plan_confirmed"] = True
    # cr_path / 回滚标记（progress 展示层输入，证据推导，非手工枚举）
    if task:
        t = state.setdefault("tasks", {}).setdefault(task, {})
        if event == vocab.Event.TASK_DOD_PASSED and decision == vocab.Decision.SKIP_CR:
            t["cr_path"] = "SIMPLE_SKIP"
        if event == vocab.Event.CR_RECHECKED:
            t["cr_rechecked"] = True
        if event == vocab.Event.CR_RECHECKED and decision == vocab.Decision.AUTONOMOUS_BLOCK \
                and payload.get("regression_detected"):
            t["rolled_back"] = True
        if t.get("state") == vocab.State.CR_PASSED:
            t["cr_path"] = "FULL_CR_RECHECK" if t.get("cr_rechecked") else "FULL_CR"
        # 修复契约 / 质量门证据持久化（fix_contract_required / cr_pass_requires_quality_gate 不变量输入）
        if payload.get("fix_contract_path"):
            t["fix_contract_path"] = payload["fix_contract_path"]
        if payload.get("quality_gate_evidence"):
            t["quality_gate_evidence"] = payload["quality_gate_evidence"]


def _baseline_fingerprint(state_path: str | Path) -> str | None:
    """design-baseline.md 的 SHA-256 指纹；工单根 = state 文件（state/workflow-state.yml）的 parent.parent。"""
    bp = Path(state_path).parent.parent / "design-baseline.md"
    if not bp.exists():
        return None
    return hashlib.sha256(bp.read_bytes()).hexdigest()


def _apply_baseline_bookkeeping(state: dict, event: str, payload: dict, task: str | None,
                                state_path: str | Path) -> None:
    """BASELINE_ALIGN 簿记：CR_APPROVED 进 CR_FIXING 时标记并捕获基线指纹；
    REWRITE_COMPLETED 时校验 design-baseline 已被实际修改（基线对齐必须真改基线，防 executor 跳步）。"""
    if not task:
        return
    t = state.setdefault("tasks", {}).setdefault(task, {})
    if payload.get("has_baseline_align") and t.get("state") == vocab.State.CR_FIXING:
        t["baseline_align"] = True
        t["baseline_fp_before"] = _baseline_fingerprint(state_path)
    if t.get("baseline_align") and event == vocab.Event.REWRITE_COMPLETED:
        fp = _baseline_fingerprint(state_path)
        if fp is None or fp == t.get("baseline_fp_before"):
            raise StatectlError("任务经 BASELINE_ALIGN 修复但 design-baseline.md 未被实际修改")
        t["baseline_updated"] = True


# ---------------- 模式解析 ----------------

def _resolve_mode(state: dict, args_mode: str | None, cfg_mode: str | None) -> str:
    """烘焙/解析仓库拓扑 mode：优先级 --mode 标志 > 状态 > 配置 > single。

    状态首次创建（无 mode 键）时持久化；后续命令从状态读（标志可临时覆盖，不覆写状态）。
    """
    mode = args_mode or state.get("mode") or cfg_mode or "single"
    if "mode" not in state:
        state["mode"] = mode
    return mode


# ---------------- CLI ----------------

def _cmd_transit(args) -> int:
    try:
        ctx = configctl.read_config(args.config)
        payload = json.loads(args.payload) if args.payload else {}
        validate_event_payload(args.event, payload)
        _validate_payload_refs(payload, args.state)
        decision = _decide(args.event, payload, ctx["limits"], ctx.get("quality"),
                           ctx.get("capabilities"))
        state = load_state(args.state)
        mode = _resolve_mode(state, args.mode, ctx.get("mode"))
        context = {"task_id": args.task, "since": _now_iso(),
                   "reason": payload.get("reason"), "resume_event": payload.get("resume_event")}
        state = _transit(state, args.event, payload, decision, context)
        _apply_bookkeeping(state, args.event, payload, decision, args.task)
        _apply_baseline_bookkeeping(state, args.event, payload, args.task, args.state)
        write_state(args.state, state)
        log_entry = {"event": args.event, "decision": decision, "task_id": args.task,
                     "ts": _now_iso(), "phase": state["milestone"]["phase"]}
        # cr_round 仅 CR_RECHECKED 携带（重审轮次）；其他事件不含该字段
        if "cr_round" in payload:
            log_entry["cr_round"] = payload["cr_round"]
        append_log(args.log, log_entry)
        print(json.dumps({"ok": True, "event": args.event, "decision": decision,
                          "mode": mode,
                          "phase": state["milestone"]["phase"],
                          "pending_gate": state["milestone"].get("pending_gate"),
                          "task": args.task,
                          "task_state": state.get("tasks", {}).get(args.task, {}).get("state"),
                          "fix_attempts": state["milestone"].get("fix_attempts")}))
        return 0
    except (SchemaError, StatectlError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _cmd_init_tasks(args) -> int:
    """阶段4入口全量登记任务：dev-tasks → state（一次性；首个任务离开 TODO 后禁止）。

    all_done 判定（_next_action）以 state 任务集为完整计划集；init-tasks 也是 split 截止锚点——
    登记后 tasks 非空，validate --check-split 即拒绝中途拆分，杜绝"拆分后漏任务"。
    """
    try:
        configctl.read_config(args.config)
        raw = json.loads(args.tasks)
        if not isinstance(raw, list) or not raw:
            raise StatectlError("--tasks 必须是非空 JSON 数组 [{id, title?, complexity}, ...]")
        state = load_state(args.state)
        if state["milestone"]["phase"] != vocab.Phase.DEVELOPING.value:
            raise StatectlError(f"init-tasks 仅限阶段4开发期（当前 phase={state['milestone']['phase']}）")
        if state.get("tasks"):
            raise StatectlError("任务已登记或已开始，禁止重复 init-tasks（开发开始后不可再全量登记）")
        valid_complexity = {vocab.Complexity.SIMPLE.value, vocab.Complexity.NORMAL.value,
                            vocab.Complexity.COMPLEX.value}
        registered: dict[str, dict] = {}
        for t in raw:
            if not isinstance(t, dict) or not t.get("id") or not t.get("complexity"):
                raise StatectlError(f"任务定义非法: {t!r}（需 id + complexity）")
            tid = str(t["id"])
            if not _TASK_ID_RE.match(tid):
                raise StatectlError(f"任务 ID 非法: {tid!r}（必须 X.Y）")
            if tid in registered:
                raise StatectlError(f"任务 ID 重复: {tid!r}")
            comp = t["complexity"]
            if comp not in valid_complexity:
                raise StatectlError(f"任务 {tid} complexity 非法: {comp!r}（SIMPLE|NORMAL|COMPLEX）")
            entry = {"state": vocab.State.TODO.value, "complexity": comp}
            if t.get("title"):
                entry["title"] = t["title"]
            registered[tid] = entry
        state["tasks"] = registered
        write_state(args.state, state)
        append_log(args.log, {"event": vocab.Event.INIT_TASKS.value, "decision": None, "task_id": None,
                              "ts": _now_iso(), "phase": state["milestone"]["phase"],
                              "task_count": len(registered)})
        print(json.dumps({"ok": True, "event": vocab.Event.INIT_TASKS.value, "task_count": len(registered),
                          "phase": state["milestone"]["phase"]}, ensure_ascii=False))
        return 0
    except (SchemaError, StatectlError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _cmd_batch(args) -> int:
    """批量提交无分支事件链：原子应用（任一失败整批不写状态/日志）。

    适合"确定会成功、无需中间决策动作"的段（如 CR 通过后的 TASK_CR_PASSED + VERIFY_PASSED）。
    返回结果含每事件 decision；涉及 WAIT_USER_APPROVAL / FIX_CR_ISSUES / RUN_CR 等
    需后续动作的 decision 的事件，主 Agent 不应放入 batch，应单独 transit 并按 Decision 执行。
    """
    try:
        ctx = configctl.read_config(args.config)
        events = json.loads(args.events)
        if not isinstance(events, list) or not events:
            raise StatectlError("--events 必须是非空 JSON 数组")
        state = load_state(args.state)
        results = []
        for i, ev in enumerate(events):
            if not isinstance(ev, dict) or not ev.get("event"):
                raise StatectlError(f"事件[{i}] 缺少 event")
            event = ev["event"]
            payload = ev.get("payload") or {}
            task = ev.get("task")
            validate_event_payload(event, payload)
            _validate_payload_refs(payload, args.state)
            decision = _decide(event, payload, ctx["limits"], ctx.get("quality"),
                               ctx.get("capabilities"))
            _resolve_mode(state, args.mode, ctx.get("mode"))
            context = {"task_id": task, "since": _now_iso(),
                       "reason": payload.get("reason"), "resume_event": payload.get("resume_event")}
            state = _transit(state, event, payload, decision, context)
            _apply_bookkeeping(state, event, payload, decision, task)
            _apply_baseline_bookkeeping(state, event, payload, task, args.state)
            results.append({"event": event, "decision": decision, "task": task,
                            "task_state": state.get("tasks", {}).get(task, {}).get("state")
                            if task else None})
        write_state(args.state, state)
        for i, ev in enumerate(events):
            r = results[i]
            log_entry = {"event": r["event"], "decision": r["decision"],
                         "task_id": r["task"], "ts": _now_iso(),
                         "phase": state["milestone"]["phase"]}
            ev_payload = ev.get("payload") or {}
            # cr_round 仅 CR_RECHECKED 携带（重审轮次）；其他事件不含该字段
            if "cr_round" in ev_payload:
                log_entry["cr_round"] = ev_payload["cr_round"]
            append_log(args.log, log_entry)
        print(json.dumps({"ok": True, "applied": len(events), "results": results,
                          "phase": state["milestone"]["phase"],
                          "pending_gate": state["milestone"].get("pending_gate"),
                          "fix_attempts": state["milestone"].get("fix_attempts")}))
        return 0
    except (SchemaError, StatectlError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _cmd_get(args) -> int:
    state = load_state(args.state)
    print(json.dumps({"milestone": state["milestone"], "tasks": state.get("tasks", {})}, ensure_ascii=False))
    return 0


def _cmd_log(args) -> int:
    entries = read_log(args.log)
    if args.limit:
        entries = entries[-args.limit:]
    print(json.dumps(entries, ensure_ascii=False))
    return 0


def _next_action(state: dict, caps: dict, current_task: str | None) -> dict:
    """计算下一推进动作（纯函数，不解析 dev-tasks 依赖图）。

    - 有未完成任务的推进/阻塞状态 → CONTINUE（继续当前，不推进）
    - 当前任务 DONE：
        - advance_task=true → START_NEXT_TASK（主 Agent 自行选下一依赖就绪任务）
        - advance_task=false → ASK_NEXT_TASK
    - 全部任务 DONE：
        - advance_accept=true → ADVANCE_TO_ACCEPT
        - advance_accept=false → ASK_ADVANCE_TO_ACCEPT
    - 其他 → NONE
    """
    tasks = state.get("tasks", {})
    pending_gate = state["milestone"].get("pending_gate")
    if pending_gate:
        return {"action": "WAIT_GATE", "gate": pending_gate.get("type"),
                "reason": f"存在 {pending_gate.get('type')} 人工门，等待用户裁决"}
    if not tasks:
        return {"action": "NONE", "reason": "尚无任务"}

    all_done = all(t.get("state") == vocab.State.DONE.value for t in tasks.values())
    if current_task:
        cur = tasks.get(current_task, {})
        cur_done = cur.get("state") == vocab.State.DONE.value
        if not cur_done:
            return {"action": "CONTINUE", "task": current_task,
                    "reason": f"当前任务 {current_task} 未完成"}
        if not all_done and caps.get("advance_task"):
            return {"action": "START_NEXT_TASK", "task": current_task,
                    "reason": "advance_task=true，自动开始下一依赖就绪任务（主 Agent 从 dev-tasks 选）"}
        if not all_done:
            return {"action": "ASK_NEXT_TASK", "task": current_task,
                    "reason": "advance_task=false，询问是否继续下一任务"}

    if all_done:
        if caps.get("advance_accept"):
            return {"action": "ADVANCE_TO_ACCEPT", "reason": "advance_accept=true 且全部任务 DONE，自动进验收"}
        return {"action": "ASK_ADVANCE_TO_ACCEPT", "reason": "advance_accept=false，询问是否进验收"}
    return {"action": "NONE", "reason": "无推进动作"}


def _cmd_next(args) -> int:
    try:
        ctx = configctl.read_config(args.config)
        state = load_state(args.state)
        result = _next_action(state, ctx.get("capabilities", {}), args.task)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (SchemaError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _review_dispatch(levels: dict, severity: str, dimensions: list | None = None) -> dict:
    """计算 CR 重审应派发的 reviewer 维度（IMPLEMENTATION 恒跑 + severity.recheck ∩ 维度池）。

    - severity=MINOR → minor.recheck ∩ 池（默认 [] → 仅 IMPLEMENTATION）
    - severity=MAJOR → major.recheck ∩ 池（默认 [design, security, performance]）
    维度池 cr.review.dimensions 为项目上限；recheck 命中但被池停用的维度不派发（reason 显式记录）。
    返回 {reviewers: [...], reason}。
    """
    sev = severity.upper() if severity else "MAJOR"
    if sev not in ("MINOR", "MAJOR"):
        return {"error": f"severity 非法: {severity!r}（MAJOR|MINOR）"}
    pool = list(dimensions or ["implementation", "design", "security", "performance"])
    level = levels.get("minor" if sev == "MINOR" else "major", {})
    extra = list(level.get("recheck", []))
    dispatched = [d for d in extra if d in pool and d != "implementation"]
    dropped = [d for d in extra if d not in pool]
    reviewers = ["implementation"] + dispatched
    reason = f"{sev} 重审：IMPLEMENTATION 恒跑 + recheck∩池 {dispatched}"
    if dropped:
        reason += f"；池停用跳过 {dropped}"
    return {"severity": sev, "reviewers": reviewers, "reason": reason}


def _cmd_review_dispatch(args) -> int:
    try:
        ctx = configctl.read_config(args.config)
        levels = ctx.get("cr", {}).get("levels", {})
        dimensions = ctx.get("cr", {}).get("review", {}).get("dimensions")
        result = _review_dispatch(levels, args.severity, dimensions)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (SchemaError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="statectl", description="workflow 状态控制（唯一转换写入口）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transit", help="提交事件：校验→决策→转换→写状态+日志→返回")
    t.add_argument("--state", required=True, help="workflow-state.yml 路径")
    t.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径")
    t.add_argument("--log", help="transition.log 路径（默认与 state 同目录）")
    t.add_argument("--event", required=True)
    t.add_argument("--payload", default="{}", help="JSON 字符串")
    t.add_argument("--task", help="任务 ID（任务事件必填）")
    t.add_argument("--mode", choices=["single", "dual"], help="仓库拓扑（默认从状态/配置解析）")
    t.set_defaults(handler=_cmd_transit)

    b = sub.add_parser("batch", help="批量提交无分支事件链：原子应用（任一失败整批不写状态/日志），状态写一次、日志逐事件")
    b.add_argument("--state", required=True, help="workflow-state.yml 路径")
    b.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径")
    b.add_argument("--log", help="transition.log 路径（默认与 state 同目录）")
    b.add_argument("--events", required=True, help="JSON 数组：[{event, task?, payload?}, ...]")
    b.add_argument("--mode", choices=["single", "dual"], help="仓库拓扑（默认从状态/配置解析）")
    b.set_defaults(handler=_cmd_batch)

    it = sub.add_parser("init-tasks", help="阶段4入口全量登记任务（dev-tasks → state；一次性，split 截止锚点）")
    it.add_argument("--state", required=True, help="workflow-state.yml 路径")
    it.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径")
    it.add_argument("--log", help="transition.log 路径（默认与 state 同目录）")
    it.add_argument("--tasks", required=True,
                    help="JSON 数组：[{id, title?, complexity}, ...]（来自 dev-tasks.md）")
    it.set_defaults(handler=_cmd_init_tasks)

    g = sub.add_parser("get")
    g.add_argument("--state", required=True)
    g.set_defaults(handler=_cmd_get)

    l = sub.add_parser("log")
    l.add_argument("--log", required=True)
    l.add_argument("--limit", type=int)
    l.set_defaults(handler=_cmd_log)

    n = sub.add_parser("next", help="计算下一推进动作（读 state + config，返回动作指令，不解析 dev-tasks）")
    n.add_argument("--state", required=True, help="workflow-state.yml 路径")
    n.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径")
    n.add_argument("--task", help="当前任务 ID（任务 DONE 后判断是否自动开下一个）")
    n.set_defaults(handler=_cmd_next)

    rd = sub.add_parser("review-dispatch", help="计算 CR 重审派发维度（读 config cr.levels + severity，返回 reviewer 列表）")
    rd.add_argument("--config", required=True, help=".claude/workflow/config.yml 路径")
    rd.add_argument("--severity", default="MAJOR", help="重审问题严重度（MAJOR|MINOR）")
    rd.set_defaults(handler=_cmd_review_dispatch)

    args = ap.parse_args(argv)
    # 补默认 log 路径
    if args.cmd in ("transit", "batch", "init-tasks") and not getattr(args, "log", None):
        args.log = str(Path(args.state).parent / DEFAULT_LOG_FILENAME)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
