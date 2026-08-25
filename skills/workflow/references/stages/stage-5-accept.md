# 阶段 5：收尾验收（ACCEPTING）+ 异常处理

> input: design-baseline.md（含返工/plan 同步，最新契约）、全部任务范围
> output: `acceptance/acceptance.md`、`ACCEPTANCE_COMPLETED`
> agents: verifier（只读，不改码）
> fail_modes: 见「回退路径表」；BLOCKED 正交 overlay
> 命令模板见 `generated/commands.md`（ACCEPTANCE_FAILED / ACCEPTANCE_APPROVED / ACCEPTANCE_COMPLETED / STAGE_BLOCKED / BLOCKER_RESOLVED）；payload schema 见 `model/events.schema.json`。

## 行为目标
全量回归 + 一致性把关；验收问题按根因层级分流（自动修复 / 人工门 / rework）。

## 关键不变量
- verifier 只读不改码；验收报告必须带 `report_complete`、严重度、根因层级。
- `AUTONOMOUS_COMPLETED`（`ACCEPTANCE_COMPLETED` 返回 `GENERATE_SUMMARY` 时）要求零阻塞：**无任何任务处于 `AUTONOMOUS_BLOCKED`**（若曾阻塞需人工解决并重新通过验收），否则 lifecycle 应为 `BLOCKED`。
- 审批规则：只有显式 `/workflow approve` 才提交 `ACCEPTANCE_APPROVED`。

## 执行要点
1. **启动 verifier**：确认阶段 4 全部任务 DONE + `statectl get` 确认 phase=ACCEPTING → 调 `verifier` 产出 `acceptance.md`（问题清单 + 严重度 + 根因层级 + 报告完整性）。
2. **verifier 返回后**：读 acceptance.md（以文件为准）→ 提交 `ACCEPTANCE_FAILED{report_complete, major/minor_count, root_causes, fix_attempts}`，按返回 decision 分流：
   - `REQUEST_DESIGN_REWORK`：验收存在 DESIGN/REQUIREMENT 根因 → 提示 `/workflow rework`
   - `WAIT_USER_APPROVAL`：进入 ACCEPT 人工门，逐条裁决 ACCEPTED/REJECTED/MODIFIED
   - `FIX_ACCEPTANCE_ISSUES`：自动修复循环（`fix_attempts` 由 statectl 递增）→ 重跑 verifier → 再提交，直到通过或达上限
3. **ACCEPT 人工门**：`approve` 提交 `ACCEPTANCE_APPROVED{adjudications, has_implement_fix}` → 按关联任务分组派 executor 修复 → 重跑 verifier（重新走本阶段完整流程）。
4. **验收通过**：零阻塞检查后提交 `ACCEPTANCE_COMPLETED` → `FINISH_ACCEPTANCE` → COMPLETED；`GENERATE_SUMMARY` → AUTONOMOUS_COMPLETED。输出固定完成摘要（讨论文档 / 设计文档 / 逐任务审查 / 收尾验收 / 影响模块 / 后续人工操作）。

### 验收总结（终态分流）

提交 `ACCEPTANCE_COMPLETED` 后，按 `statectl` 返回的 `decision` 分流：
- `GENERATE_SUMMARY` → `AUTONOMOUS_COMPLETED`（自动交付清单）
- `FINISH_ACCEPTANCE` → `COMPLETED`

## 回退路径表（触发场景 → 事件 → 回退目标）
| 触发场景 | 事件 | 回退目标 |
|---|---|---|
| 阶段 3 设计审核缺项 | `DESIGN_REJECTED{gaps}` | ANALYZING |
| 阶段 5 验收实现问题 | `ACCEPTANCE_FAILED` + `FIX_ACCEPTANCE_ISSUES` | 保持 ACCEPTING，executor 修受影响任务后重验 |
| 阶段 5 验收设计/需求问题 | `ACCEPTANCE_FAILED` + `REQUEST_DESIGN_REWORK` | 提示 `/workflow rework` |
| rework 设计级 | `REWORK_STARTED{level: DESIGN}` | ANALYZING |
| rework 需求级 | `REWORK_STARTED{level: REQUIREMENT}` | DISCUSSING |
| rework 实现级 | `REWORK_STARTED{level: IMPLEMENTATION}` | 里程碑 phase 不变，受影响任务回 TODO |
| 中断恢复 | 下次 `/workflow next` | 从 `state/workflow-state` 的 phase/pending_gate 恢复 |

## BLOCKED（正交 overlay）
接口冲突等阻塞：提交 `STAGE_BLOCKED{reason, resume_event}` → lifecycle=BLOCKED + blocker。用户解决后提交 `BLOCKER_RESOLVED` 恢复。

## 中断恢复
任意阶段可中断。下次 `/workflow next` 从 `state/workflow-state` 的 phase/pending_gate 恢复（多里程碑下从选中里程碑恢复）。
