# agent-protocol — 子 agent 调用规范（统一，唯一）

> 调用任何子 agent 前读本文件。角色契约（输入/输出/返回）见 `model/agent-contracts.yml`；prompt 模板见 `prompts/agents.md`。三者的职责分离：
> - **agent-contracts.yml**：角色定义、输入输出、返回协议（改 agent 只改这里）
> - **prompts/agents.md**：prompt 文本模板（唯一来源，改措辞只改这里）
> - **本文件**：调用形式与主 Agent 行为（如何调、返回后做什么）
> Stage 文档只引用本文件与模板名，**禁止内嵌完整 prompt 文本**（会制造第二份模板导致漂移）。

## 1. 调用形式（强制）

子 agent 通过 **Agent 工具**调用：

```text
>>> Agent(subagent_type="{agent_id}", prompt="{按 prompts/agents.md 对应模板展开}")
```

- `subagent_type`：必须等于 `model/agent-contracts.yml#agents` 中的 id（`executor`、`reviewer-implementation`、`reviewer-security`、`reviewer-design`、`reviewer-performance`、`reviewer-coordinator`、`reviewer-judge`、`planner`、`plan-validator`、`analyst`、`architect`、`verifier`、`simple-gate-checker`）。
- `prompt`：**只从 `prompts/agents.md` 取模板**，不得在 stage 文档重写或复制。
- `>>>` 标记 = 严格执行指令：主 Agent 必须按此调用，不得改为"建议"或自行换角色。

## 2. prompt 构造规范

1. 取 `prompts/agents.md` 对应角色的模板。
2. **展开占位符**：`{工单根}` → 实际绝对路径（子 agent 无法解析变量，只看到字面路径）；`{范围标签}`、`{X.Y}`、`{任务标题}` → 实际值。
3. 附加 Bash 约束：`Bash 静态分析约束：禁止 for/while/if/case/here-doc/嵌套 $()`（来自 `agent-contracts.yml#common.bash_constraint`，模板已含，不手抄）。
4. 产出路径与 `agent-contracts.yml` 该角色的 `outputs` 一致；禁止写入契约外路径或 home/仓库外。

## 3. 并行调用

- 同一波互不依赖的调用在同一轮消息内发出多个 Agent 调用（如阶段 2 多模块 analyst、阶段 4 多维 CR 必选 reviewer）。
- CR 汇总 → 分流 → 改写**始终逐任务**，不并行裁决。

## 4. 返回协议（强制）

- 子 agent 只返回 `COMPLETE | INCOMPLETE`（`plan-validator` / `simple-gate-checker` 返回 `PASS | FAIL | INCOMPLETE`）。
- **主 Agent 必须以产出文件为准**：读取该角色 `outputs` 声明的文件内容，**不采信返回文本自述**。`simple-gate-checker` 的产出是 `done/{范围标签}-{X.Y}.md` 的 `#gate` 段（返回文本只作辅助）。
- 产出文件缺失、为空或结构不合契约 → 视为 `INCOMPLETE`：先补齐缺失输入，再**新上下文**重跑同一角色。
- `INCOMPLETE` 无法补齐 → 保持当前状态（不推进、不进入汇总），输出阻塞原因。例外：`simple-gate-checker` 的 gate 段重跑一次仍缺失 → 直接落 `RUN_CR`（见 `stage-4.0-dev.md`），不空等。

## 5. 返回后四步（缺一不可，禁止静默结束本轮）

1. **读产出**：读取角色声明的 output 文件（以文件为准）。
2. **回写状态**：用 `statectl transit` 提交对应事件（不推进状态 = 不产生日志）。
3. **输出摘要**：向用户简述产出内容（改了哪些文件 / CR 扫出几条 / plan 要点）。
4. **明确下一步**：告知用户该执行什么命令，或主 Agent 将自动执行什么。

## 6. 与确定性内核的边界

- 子 agent **不**决定流程推进动作、**不**读 `.claude/workflow/config.yml`、**不**直接改状态文件——状态流转只经 `statectl`。
- 子 agent 返回的 `COMPLETE` 只是"产出完整"，**不等于流程推进**；推进由主 Agent 按 Policy Decision 执行。

## 7. 上下文隔离

- 编码、各维度 reviewer、coordinator、改写各自独立上下文，禁止同上下文自审。
- reviewer / coordinator / verifier 只产出问题清单，**绝不直接改代码**。
