---
name: workflow
description: 单体多模块项目的需求开发全流程编排（确定性内核 + LLM 编排）。模型驱动状态机，自动调度讨论/架构分析等外部 skill 与多维 reviewer，串联需求讨论到代码审查的 5 个阶段（架构文档复用项目 docs/business/{模块名}/）。外部 skill 名由项目 config.yml#skills 配置，默认 devops-discuss / arch-analyzer。当用户说 "workflow"、"单体开发流程"、"单体需求流程"、"模块开发流程" 时触发。
---

# workflow — 单体多模块需求开发流程编排

> 本 skill 是**路由器**：状态、策略、事件契约一律以 `model/` 为准并经 `adapters/` 执行，**禁止按散文推断状态或决策**。状态机单一权威是 `model/state-machine.yml`（生成视图见 `generated/`）。编排细节按需读 `references/`。

## 目录约定

- **{项目根}** = 仓库根目录（`.claude/` 所在；skill 项目级配置统一在此）
- **{配置目录}** = `{项目根}.claude/workflow/`（skill 统一加载点：config.yml committed；templates/ 产出文档模板）
- **{skills.discuss}** / **{skills.arch_rules}** / **{skills.arch_analyzer}** = 外部 skill 名占位符，取第 1 步 Automation Context 的 `skills` 段（config.yml#skills 可换用项目 skill，缺省 devops-discuss / arch-rules / arch-analyzer）
- **{讨论根目录}** = `docs/discuss/`
- **{工单根}** = `{讨论根目录}{域}/{需求名}/.task/`
- **{hotfix工单根}** = `{讨论根目录}hotfix/{YYYY-MM-DD}-{主题}/.task/`（`/workflow hotfix` 轻量修复产物目录；不走状态机、无 `state/`，done/review 产物落此）
- **{状态目录}** = `{工单根}state/`（机器控制面，statectl / validate 读写；Agent 不手改）
- **{状态文件}** = `{状态目录}workflow-state.yml`（机器状态源，statectl 写，含 mode 字段）
- **{转换日志}** = `{状态目录}transition.log`（append-only，审计/恢复副产物）
- **progress.md** = 派生视图（`adapters/progress_render.py` **按需生成**——`/workflow status`、任务 DONE、阶段切换时；人工只读，不手改）

## 命令速查

| 命令 | 作用 |
|------|------|
| `/workflow use [需求ID][#里程碑]` | 设定活动上下文（粘性，写入 `{项目根}.claude/workflow/active`） |
| `/workflow start {需求名}` | 创建需求，进入阶段 1 讨论（执行 preflight） |
| `/workflow next [需求ID][#里程碑]` | 推进到下一阶段 / 下一个任务 |
| `/workflow approve [需求ID][#里程碑]` | 确认当前人工门（自动按 pending_gate 分发） |
| `/workflow status [需求ID][#里程碑]` | 查看进度并刷新 `progress.md`（默认附带 `validate.py` 校验） |
| `/workflow list` | 列出未完成需求 |
| `/workflow split [需求ID] {里程碑列表}` | 大需求拆里程碑 |
| `/workflow rework [需求ID][#里程碑]` | 任务调整：缺陷返工（按根因层级回退）或补充任务（当前需求内新增子任务，牵动设计自动回退 DESIGN 门） |
| `/workflow summary [需求ID][#里程碑]` | 产出交付清单 |
| `/workflow hotfix {bug描述}` | 轻量 bug 修复（不走 5 阶段状态机；SIMPLE Gate 通过可跳过单维度 CR） |
| `/workflow config [preset]` | 按预设（manual\|guarded\|autonomous）初始化或校验配置 |
| `/workflow dispatch [需求ID] {执行单元}` | **[dual]** 设计通过后，按语言模板裁剪 design-package 下发到执行仓（`adapters/dispatchctl.py dispatch`） |
| `/workflow report [需求ID]` | **[dual]** 执行仓上报对外契约变更到 arch-docs（`adapters/dispatchctl.py report`），供 arch-docs rework 重审 |

- **需求名** = `{YYYY-MM-DD}-{简称}`；**需求 ID** = `{域}/{需求名}`；**`#里程碑`** 仅多里程碑需求需要
- **仓库拓扑 `mode`**：`single`（默认，单体多模块单仓）/ `dual`（规划仓 + 执行仓双仓/多仓）。首次 `start`/`use` 用 `--mode dual` 声明并烘焙进状态文件，后续命令从状态读取
- 命令详细处理见 `references/commands/index.md`

## 双仓模式（mode: dual）

`dual` = 规划仓（arch-docs，阶段 1-3 + dispatch）+ 一个或多个执行仓（阶段 4-5）。`mode` 从状态/配置读取，命令面按 mode 分流。

**阶段流转**：`DESIGN_APPROVED` 带 `mode: dual` → 进 `DISPATCHING` → 逐执行单元 dispatch → 全部下发后 `DISPATCH_COMPLETED` → `DEVELOPING`（阶段 4-5 在执行仓内跑）。

**dispatch（arch-docs 内）**：读 `{配置目录}templates/design-package.md`（语言模板，{skills.arch_rules} 生成）→ 按执行单元契约面裁剪 design-baseline 出每单元 design-package → 调 `dispatchctl.py dispatch --units '{json}'` 落地工作包（state + dev-tasks + design-package + config + arch-docs-path）+ 回写台账 → 全部完成后 `DISPATCH_COMPLETED`。

**report（执行仓内）**：执行仓发现需要改对外契约 → 调 `dispatchctl.py report`（用 `arch-docs-path` 指针回指）写入 arch-docs 的 reports 台账 → arch-docs 主 Agent 读报告后走 `/workflow rework`（设计层完整重审）→ re-dispatch。

**跨仓拦截（强制）**：arch-docs 只规划/下发（阶段 1-3 + dispatch + rework），执行仓只执行（阶段 4-5 + report）。在错误仓库执行对方命令时**必须拒绝并提示切换**，禁止自动 cd 到另一仓库——否则阶段 2 共识层与阶段 4 实现层设计分层被破坏。

**执行仓路径**：`{配置目录}repo-paths` 维护 `{执行单元}={本地仓库路径}` 映射，dispatch 时解析。

## 强制前置（每个子命令执行前必须做，禁止跳过）

1. **加载 Automation Context**：`python3 {skill根}/adapters/configctl.py read --config {项目根}.claude/workflow/config.yml`，校验后得到 `mode`/`limits`/`quality`/`capabilities`/`cr.levels`/`skills`（全显式，无 profile）。命令内只读一次，Stage 禁止再次读配置。
2. **读活动指针**：读 `{项目根}.claude/workflow/active`；存在且非空则设为当前活动上下文。
3. **解析目标**：显式参数 > 活动指针 > 旧回退（唯一进行中自动选中；多个列出让选；无则提示 `start`）。支持前缀/子串模糊匹配。
4. **禁止跳过此步骤**——不得在未读取指针的情况下声称"没有活动流程"。

## 工具调用协议（关键，必须遵守）

**Adapter CLI 组合（强制）**：每条 adapter 命令必须以自己的 `python3 {skill根}/adapters/{entrypoint}.py` 开始。需要在同一 Bash tool call 执行多个 adapter 时，只能用显式 `&&`（前一条成功后继续）或 `;`（无条件继续）分隔；禁止以空格、续行或未分隔的文本把 `statectl.py`、`validate.py`、`progress_render.py`、`configctl.py` 与 `dispatchctl.py` 拼进同一 argv。互不依赖的调用可使用多个独立 Bash tool call 并行执行。

**所有状态读写与流转一律调 `adapters/statectl.py`，禁止按散文自行推断状态或决策。** 状态机的枚举、转换、决策只在 `model/` 定义，由 engine 执行。

| 工具 | 用途 |
|------|------|
| `python3 {skill根}/adapters/statectl.py transit --state {状态文件} --config {配置} --event {EVENT} --payload '{json}' [--task {X.Y}]` | 提交事件：Schema 校验 → 决策 → 转换 → 写状态 + 日志 → 返回 `{decision, phase, pending_gate, task_state}`。**返回的 decision 必须立即执行，不得改写成用户确认门。** 日志时间戳由 statectl 系统生成（`_now_iso`），调用方不得传入。 |
| `statectl.py batch --state {状态文件} --config {配置} --events '[{event,task?,payload?},...]'` | **批量提交无分支事件链**：原子应用（任一失败整批不写状态/日志），状态写一次、日志逐事件。只用于确定会成功的段（如 CR 通过后 `TASK_CR_PASSED`+`VERIFY_PASSED` 一次到 DONE）；涉及 `WAIT_USER_APPROVAL`/`FIX_CR_ISSUES`/`RUN_CR` 等需后续动作的 decision 的事件**不得入 batch**，必须单独 transit 并按 decision 执行。 |
| `statectl.py init-tasks --state {状态文件} --config {配置} --tasks '[{id,title?,complexity}]'` | **阶段4入口必做一次**：从 dev-tasks 全量登记任务到 state（全部 TODO；`next` 的"全部任务 DONE"按完整计划集判定；`/workflow split` 的截止锚点）。仅 state 任务集为空时允许，开发开始后禁止。 |
| `statectl.py get --state {状态文件}` | 读取结构化状态（不要靠 LLM 猜） |
| `statectl.py log --log {转换日志}` | 查看转换日志 |
| `configctl.py read --config ...` | 读配置（强制前置第 1 步） |
| `validate.py --state ... --log ...` | 不变量校验（status 默认附带；违规必须停） |
| `progress_render.py --state ... --out ...` | 生成 progress.md 派生视图 |

> 各事件的 `statectl transit` 命令模板与必填 payload 见 `generated/commands.md`；状态/事件/Decision/门/能力键词表见 `generated/vocab.md`；自动化策略见 `generated/automation.md`。这些文件由维护侧从 `model/` 生成，skill 只读、不手改。

事件名、payload 结构见 `model/events.schema.json`（如 `TASK_DOD_PASSED`、`CR_SCANNED`、`CR_JUDGED`、`ACCEPTANCE_FAILED`）。**人工门事件（`DESIGN_APPROVED`/`PLAN_APPROVED`/`CR_APPROVED`/`ACCEPTANCE_APPROVED`）只在用户显式 `/workflow approve` 时提交，且必须携带正确目标任务。**

## 流程护栏（不变量，不随阶段文档加载与否改变）

1. **审批规则（approval）**：只有用户显式输入 `/workflow approve` 才算审批通过。任何其他消息（讨论、确认细节、说"没问题"）都不等于 approve，绝不推断审批意图。
2. **子 agent 返回 ≠ 流程推进**：每次子 agent 返回后必须 ① 读其产出文件（以文件为准）② 回写状态（statectl）③ 输出摘要 ④ 明确下一步。绝不允许静默结束。
3. **编码与审查分离**：编码、各维度 reviewer、coordinator、改写各自独立上下文；reviewer/verifier 只产出问题清单，绝不直接改代码。
4. **回写是阻塞步骤**：状态流转必须经 statectl 写回；未完成不得推进下一任务。
5. **未决项不许悬空**：design-baseline 的 `待确认/TODO` 必须登记成表并有处置。
6. **设计/需求层缺陷走 rework**：CR 改写只解决"设计对、改当前任务小问题"；牵动设计或多任务用 `/workflow rework`。
7. **单门不变量**：同一里程碑最多一个未决人工门（engine 强制）；`approve` 必须定位 `pending_gate.target_task`。
8. **plan 改契约重审**：若任务级 plan 改变已批准的 design-baseline 契约，必须重新进入设计人工门，不得只自动同步后继续编码。
9. **Bash 静态分析约束**：所有 agent prompt 必须含"禁止 for/while/if/case/here-doc/嵌套 $()"。产出物只落 `{工单根}`（hotfix 模式为 `{hotfix工单根}`，均位于项目内 `docs/discuss/` 下，禁止落在仓库根 `.task/`），禁止写 home 或仓库外。
10. **风险驱动 CR 完整性**：每个进入 CR 的任务必须先生成有效的 review-plan。IMPLEMENTATION 固定执行，DESIGN/SECURITY/PERFORMANCE 按风险证据调度并与项目维度池 `cr.review.dimensions` 取交集（CORE 不再强制全量，同样受池约束）；全部必选报告汇总为 `COMPLETE` 后提交 `CR_SCANNED`，Judge 裁决后再提交 `CR_JUDGED`（修复后重审提交 `CR_RECHECKED`）。SIMPLE 仅在 `model/policy.yml` 的 Gate 全部通过且返回 `SKIP_CR` 时例外。
11. **自动动作立即执行（不得把自动动作伪装成人工门）**：statectl 返回的自动动作必须在当前命令内立即执行并持续到明确等待动作、真实阻塞或流程完成。动作清单与路由以 `generated/vocab.md`（Decision 清单 + 事件决策来源）与 `references/protocols/automation.md`（动作语义字典）为准，不在本护栏复制；禁止说"自动推进"后再问用户是否继续。
12. **配置严格匹配 Schema v2**：Automation Context 只接受 `version: 2` 与域块 `flow`/`cr`/`plan`/`accept`/`rework`（配置全显式，无 profile 字段）。各域字段名/类型/取值域一律以 `model/config.schema.json` 为准（`configctl read` 校验失败即停），本护栏不逐字段复述——改字段只改 schema，不得在文档二次定义。预设（`manual|guarded|autonomous`）仅为 `configctl init` 模板，不属运行时字段。字段缺失、类型错误或存在未知字段时停止当前命令。
13. **payload 值从证据计算，不抄模板**：generated 文档只提供 schema 与字段占位（含来源列），不提供具体值。LLM 提交事件前必须从实际产物（diff / 测试 / 评审）核算 payload 字段值，不得照抄示例；引用的产物文件（evidence_path / fix_contract_path / quality_gate_evidence 等）不存在时 statectl 会拒绝。禁止把模板具体值当作下次的提交。
14. **judge 结果必须回显裁决文件路径**：`reviewer-judge` 返回后、提交 `CR_JUDGED`（重审 `CR_RECHECKED`）前，主 Agent 输出必须以 `📄 裁决文件: {实际路径}` 开头（取 judge 返回首行，禁止占位符），再列逐条裁决（编号/严重度/定位/裁决/置信度）+ 聚合统计，最后提示 `/workflow approve` 逐条裁决。该路径同时写入 `judge_report_path`，statectl 校验其指向的 judge.md 存在；单维 CR（`/workflow hotfix`）同样以报告文件路径开头展示。
15. **任务集完整登记 + split 截止**：进入阶段4（DEVELOPING）后、首个 `TASK_STARTED` 前，必须 `statectl init-tasks` 一次性登记 dev-tasks 全部任务；"全部任务 DONE"以该完整计划集判定，dev-tasks 已规划但未启动的任务不得被跳过。`/workflow split` 只能在此窗口内（任何任务启动前，`validate.py --check-split` 为 `ok:true`）执行；开发开始后禁止中途拆分。

## references 索引（按需读取，别一次性全载）

| 当你要做 | 先读 |
|---------|------|
| 任何命令的路由与解析 | `references/commands/index.md` |
| **子 agent 调用规范（调任何 agent 前）** | `references/protocols/agent-protocol.md` |
| 自动化标准动作清单（动作语义字典） | `references/protocols/automation.md` |
| 多维 CR reviewer 风险调度（派哪几个 reviewer） | `references/protocols/reviewer-dispatch.md` |
| 流程启动前置检查（仅 start） | `references/protocols/preflight.md` |
| 任务编号与项目约定 | `references/protocols/conventions.md` |
| 阶段 1 需求讨论（start） | `references/stages/stage-1-discuss.md` |
| 阶段 2 分析与设计 | `references/stages/stage-2-design.md` |
| 阶段 3 设计审核门 | `references/stages/stage-3-review.md` |
| 阶段 4 开发（总则/编码/SIMPLE/复验，入口） | `references/stages/stage-4.0-dev.md` |
| 阶段 4 复杂任务 plan | `references/stages/stage-4.1-plan.md` |
| 阶段 4 多维 CR / 裁决 / 改写 | `references/stages/stage-4.2-cr.md` |
| 阶段 5 收尾验收 | `references/stages/stage-5-accept.md` |
| 独立命令 | `references/commands/{hotfix,rework,summary,config}.md` |
| 状态/事件/决策权威 | `model/`（state-machine.yml / policy.yml / events.schema.json / agent-contracts.yml / config.schema.json） |
| 快速参考（生成） | `generated/`（README / automation / templates） |
| agent prompt 模板 | `prompts/agents.md` |

> **执行某阶段/命令前，必须先读对应 reference 文件**再行动——凭记忆执行易漏步、易卡死。状态数据一律从 `model/` 或 `statectl get` 获取，不从文档复制。
