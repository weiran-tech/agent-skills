# ============================================================
# workflow-state → progress.md 渲染器（纯函数，运行时：adapters/progress_render.py 消费）
# progress.md 是派生视图（人工可读，只读不手改）
# 拆自原 engine/renderer.py 的 progress 渲染部分
# ============================================================
from __future__ import annotations

from engine import vocab

from . import _GENERATED_HEADER

# 展示层三段命名：模型层事件两段 + Decision，合成人类可读三段（证据信号 → 路由方向）
_EVENT_DISPLAY = {
    (vocab.Event.CR_JUDGED.value, vocab.Decision.CONFIRM_CR.value): "cr.judged.all_clean → CONFIRM_CR",
    (vocab.Event.CR_JUDGED.value, vocab.Decision.FIX_CR_ISSUES.value): "cr.judged.has_implementation → FIX_CR_ISSUES",
    (vocab.Event.CR_JUDGED.value, vocab.Decision.REQUEST_DESIGN_REWORK.value): "cr.judged.has_design → REQUEST_DESIGN_REWORK",
    (vocab.Event.CR_JUDGED.value, vocab.Decision.AUTONOMOUS_BLOCK.value): "cr.judged.uncertain → AUTONOMOUS_BLOCK",
    (vocab.Event.CR_RECHECKED.value, vocab.Decision.CONFIRM_CR.value): "cr.rechecked.all_clean → CONFIRM_CR",
    (vocab.Event.CR_RECHECKED.value, vocab.Decision.FIX_CR_ISSUES.value): "cr.rechecked.has_issues → FIX_CR_ISSUES",
    (vocab.Event.CR_RECHECKED.value, vocab.Decision.AUTONOMOUS_BLOCK.value): "cr.rechecked.regressed → AUTONOMOUS_BLOCK",
    (vocab.Event.VERIFY_FAILED.value, vocab.Decision.CR_RECHECK.value): "verify.failed.fix_related → CR_RECHECK",
    (vocab.Event.VERIFY_FAILED.value, vocab.Decision.AUTONOMOUS_BLOCK.value): "verify.failed.unrelated → AUTONOMOUS_BLOCK",
}


def event_display(event: str, decision: str | None = None) -> str:
    """transition.log 展示层合成：`{event} → {decision}`，命中 CR/Judge 关键路径时用三段自描述名。"""
    key = (event, decision)
    if key in _EVENT_DISPLAY:
        return _EVENT_DISPLAY[key]
    if decision:
        return f"{event} → {decision}"
    return event


def _cr_path_label(t: dict) -> str:
    """任务完成质量标签（证据推导 cr_path，非手工枚举）。"""
    p = t.get("cr_path")
    if p == "SIMPLE_SKIP":
        return " [SIMPLE]"
    if p == "FULL_CR":
        return " [FULL-CR]"
    if p == "FULL_CR_RECHECK":
        return " [FULL-CR+RECHECK]"
    return ""


def render_progress(state: dict, meta: dict | None = None) -> str:
    """workflow-state → progress.md 派生视图（人工可读，只读不手改）。"""
    meta = meta or {}
    ms = state.get("milestone") or {}
    tasks = state.get("tasks") or {}
    lines = [_GENERATED_HEADER, f"# {meta.get('name', '')} 开发进度", ""]
    lines.append("## 基本信息")
    lines.append(f"- 需求ID: {meta.get('id', '')}")
    lines.append(f"- 里程碑模式: {meta.get('milestone_mode', '单里程碑')}")
    lines.append(f"- 当前阶段: {ms.get('phase', '')}")
    lines.append(f"- 生命周期: {ms.get('lifecycle', '')}")
    pg = ms.get("pending_gate")
    if pg:
        target = f"（target: {pg.get('target_task')}）" if pg.get("target_task") else ""
        lines.append(f"- 待决人工门: {pg.get('type')}{target}")
    blk = ms.get("blocker")
    if blk:
        lines.append(f"- 阻塞: {blk.get('reason')}（恢复事件: {blk.get('resume_event')}）")
    lines.append("")
    lines.append("## 任务清单（派生视图，与 workflow-state 一致）")
    for tid in sorted(tasks.keys()):
        t = tasks[tid]
        done = "[x]" if t.get("state") == vocab.State.DONE else "[ ]"
        label = _cr_path_label(t)
        if t.get("rolled_back"):
            label += " [ROLLBACK]"
        if t.get("state") == vocab.State.AUTONOMOUS_BLOCKED:
            label += " [BLOCKED]"
        lines.append(f"- {done} {tid} · {t.get('title', '')} — 状态: {t.get('state')}{label}")
    return "\n".join(lines) + "\n"
