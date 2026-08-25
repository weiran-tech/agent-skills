# 阶段 4.1：复杂任务 plan（PLANNING → PLAN_CONFIRMED）

> input: dev-tasks.md、design-baseline.md、docs/business/{模块名}/
> output: `plans/{范围标签}-{X.Y}.md`、PLAN_CONFIRMED
> agents: planner（出 plan，只读）、plan-validator（自动校验，只返回 PASS|FAIL|INCOMPLETE 不修改文件）
> fail_modes: PLAN_VALIDATED FAIL → 新 planner 修订（最多 `plan.limits.retry_max`）→ 仍 FAIL → PLAN 人工门；INCOMPLETE → 补齐输入重跑
> 命令模板见 `generated/commands.md`（PLAN_READY / PLAN_VALIDATED / PLAN_APPROVED / TASK_STARTED）；payload schema 见 `model/events.schema.json`。

## 行为目标
COMPLEX 任务编码前必须先出 plan 并经确认；SIMPLE/NORMAL 直接编码不出 plan。

## 关键不变量
- COMPLEX 判定：跨范围/核心流程/权限安全/资金链路/查询性能/并发一致性/迁移风险/设计未决 → COMPLEX；拿不准按 NORMAL + 完整 CR 兜底。
- plan 调整已批准契约（`PLAN_APPROVED.contract_changed=true`）必须重新进入设计人工门，不得自动继续编码；不得只靠"plan 同步 design-baseline"绕过（不变量 #8）。

## 执行要点
1. **① planner 出 plan**：调 `planner`（模板见 `prompts/agents.md`，只读）→ `plans/{范围标签}-{X.Y}.md`（LLD/改动清单/测试清单）。若 plan 调整 design-baseline 契约，标注 `contract_changed` 与调整项。
2. **② PLAN_READY**：提交 `PLAN_READY{plan_path}` → PLAN_AWAITING_DECISION（设 PLAN 门）。decision：manual → `WAIT_USER_APPROVAL`；guarded/autonomous → `VALIDATE_PLAN`。
3. **③ plan-validator 自动校验**：`VALIDATE_PLAN` 时派 `plan-validator` → 提交 `PLAN_VALIDATED{result}`（PASS → PLAN_CONFIRMED 进编码；FAIL → 修订重跑；INCOMPLETE → 补齐输入）。
4. **④ plan 人工门**：`WAIT_USER_APPROVAL` 时输出 plan 摘要（改动文件清单 + 关键步骤 + 数据模型变更 + 测试清单），等用户显式 `/workflow approve` → 提交 `PLAN_APPROVED{contract_changed}`。
5. **确认后**：提交 `TASK_STARTED` 进入 CODING（PLAN_CONFIRMED → CODING，stage-4.0 ②）。

## plan 契约重审模板
```markdown
## Plan 同步 [{X.Y} {范围标签} · {任务标题}]
- 调整项：{接口签名 / 数据模型 / 事件契约}
- 原契约：{...}
- 新契约：{...}
- 调整原因：{...}
```
