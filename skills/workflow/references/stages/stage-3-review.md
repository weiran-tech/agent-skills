# 阶段 3：设计审核门（DESIGN_REVIEW）

> input: design-baseline.md、dev-tasks.md
> output: `DESIGN_APPROVED` / `DESIGN_REJECTED{gaps}`
> agents: main（主 Agent 自查 + 复核）
> fail_modes: 缺项 → DESIGN_REJECTED 回 ANALYZING；非 approve 消息视为反馈回到 A
> 命令模板见 `generated/commands.md`（DESIGN_APPROVED / DESIGN_REJECTED）。

## 行为目标
清单式人工门：逐项核对，缺项打回，不能只走确认流程；一个门只允许一次 approve。

## 关键不变量
- **审批规则**：只有显式 `/workflow approve` 才算审批通过；对设计的讨论/补充/确认细节都不等于 approve。
- 一个门只允许一次 approve。

## 审核清单（主 Agent 先自查，结论附在提示里）
- [ ] 对外契约齐全（接口/Event/Listener/跨模块调用）
- [ ] 模块边界清晰
- [ ] 关键机制决策有"为什么"
- [ ] 验收标准可执行
- [ ] 未决项已登记且有处置（不许悬空 TODO）
- [ ] 简单任务实现要点足以直接开工；复杂任务已标 `复杂`

## 执行要点
1. **进入门**：输出自查清单 + 设计文档路径 + 未决项摘要 + 复杂任务列表，提示 `/workflow approve`。
2. **收到 approve（唯一推进途径）**：重新读取最新 design-baseline / dev-tasks，按清单快速复核。
   - 缺项 → 提交 `DESIGN_REJECTED{gaps}`（→ ANALYZING），提示 `/workflow next` 补充，**不得**再次提示 approve。
   - 通过 → 提交 `DESIGN_APPROVED`（→ DEVELOPING，清 DESIGN 门），返回 `ADVANCE_WORKFLOW` 则立即进入阶段 4。
