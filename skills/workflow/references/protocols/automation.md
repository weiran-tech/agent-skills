# 自动化标准动作清单（Automation Actions）

> 本文档只做**动作语义字典**——每个 Policy Decision 的执行语义。决策矩阵（哪个事件返回什么 Decision、Profile 能力、固定安全规则）以 **`generated/automation.md`**（model 生成）为权威；执行协议（同轮连续执行、终止条件、禁止确认、配置严格模式）见 **`SKILL.md`** 护栏 #11/#12 与「强制前置」。本文档禁止复制决策表与执行协议，避免双源漂移。

## 标准动作清单

| 动作标识 | 语义 | 适用事件 |
|---------|------|---------|
| `ADVANCE_WORKFLOW` | 自动进入下一个任务或阶段 | STAGE_COMPLETED |
| `WAIT_NEXT_COMMAND` | 停止自动推进，等用户触发下一步 | STAGE_COMPLETED |
| `SKIP_CR` | SIMPLE Gate 通过后跳过 CR，进复验 | TASK_DOD_PASSED |
| `RUN_CR` | 进入多维 CR 流程 | TASK_DOD_PASSED |
| `VALIDATE_PLAN` | 派 plan-validator 自动检查 plan | PLAN_READY |
| `WAIT_USER_APPROVAL` | 停在人工确认门，等用户裁决 | PLAN_READY / CR_JUDGED / CR_APPROVED / ACCEPTANCE_FAILED |
| `CONFIRM_CR` | 自动确认 CR 干净 → CR_PASSED | CR_JUDGED / CR_RECHECKED / REWRITE_COMPLETED（minor 自动确认） |
| `FIX_CR_ISSUES` | 自动进入修复（先落修复契约 `fix_contract_path`） | CR_JUDGED / CR_RECHECKED |
| `REQUEST_DESIGN_REWORK` | 设计根因 → 走 rework，不得进 CR_FIXING | CR_JUDGED / ACCEPTANCE_FAILED |
| `AUTONOMOUS_BLOCK` | 低置信度 / 劣化 / 超限 → 可信阻塞终态（保存证据） | CR_JUDGED / CR_RECHECKED / VERIFY_FAILED |
| `CR_RECHECK` | 复验失败且 fix 相关 → 回重审 | VERIFY_FAILED |
| `FIX_ACCEPTANCE_ISSUES` | 自动修复验收实现问题 | ACCEPTANCE_FAILED |
| `FINISH_ACCEPTANCE` | 完成验收 → COMPLETED | ACCEPTANCE_COMPLETED |
| `GENERATE_SUMMARY` | 完成验收 → AUTONOMOUS_COMPLETED + 自动汇总 | ACCEPTANCE_COMPLETED |

## 决策权威引用

- 决策矩阵 / Profile 能力 / 固定安全规则 → **`generated/automation.md`**（由 `engine/renderer.py` 从 `model/policy.yml` 派生；skill 只读，禁止手写复制）
- 状态 / 转换 / 终态 → **`model/state-machine.yml`**
- 事件 payload 契约 → **`model/events.schema.json`**
- 配置 Schema → **`model/config.schema.json`**
