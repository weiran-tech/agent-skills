# reviewer-dispatch — 多维 CR 风险调度规范

> 阶段 4 编码 + DoD 完成、`TASK_DOD_PASSED` 返回 `RUN_CR` 后读本文件。本文件只负责**生成 review-plan 与选择 reviewer**，不负责汇总、裁决或状态流转。
> 角色契约见 `model/agent-contracts.yml`；prompt 模板见 `prompts/agents.md`；调用形式见 `references/protocols/agent-protocol.md`。

## 输入与产出

**必读输入**：dev-tasks.md 任务描述与工作范围、done 报告、design-baseline.md、复杂任务已确认 plan、任务范围实际 diff。
**产出**：`{工单根}review/{范围标签}-{X.Y}/review-plan.md`。

**缺少 diff、任务范围或设计基线时，调度状态必须为 `INCOMPLETE`，不得启动任何 Reviewer。**

## 调度规则（确定部分，强制）

| 维度 | agent（agent-contracts id） | 调度条件 |
|------|------------------------------|---------|
| IMPLEMENTATION | `reviewer-implementation` | **固定执行**（所有进入 CR 的任务） |
| DESIGN | `reviewer-design` | 业务流程、状态流转、接口/Event/数据契约、事务或模块边界发生变化 |
| SECURITY | `reviewer-security` | 涉及身份、权限、租户、外部输入、敏感数据、密钥、签名、回调、支付安全 |
| PERFORMANCE | `reviewer-performance` | 涉及查询、索引、分页、批处理、远程 IO、缓存、锁、并发、大数据量 |

## 维度池（项目上限，配置 `cr.review.dimensions`）

- 首审维度 = `IMPLEMENTATION ∪ (风险标签候选 ∩ 维度池)`；维度池默认 = 全部四维（`implementation/design/security/performance`），业务方可缩减（如纯数据管道项目 `[implementation, design]`）以控制速度。
- 维度池是**项目上限**：`CORE` 不再强制全量兜底，同样受池约束（候选集 {design, security, performance} 再 ∩ 池）。
- **防静默丢弃**：风险标签命中但维度被池停用时，review-plan 必须显式记录「风险信号 {标签} 命中 {维度}，但项目池停用，已跳过（配置原因）」，不得无理由跳过。

## 风险标签 → 维度（从 diff 证据判定，不是从 done 报告自述）

| 风险标签 | 判定依据（必须基于实际 diff） | 候选调度 |
|----------|------------------------------|---------|
| `CONTRACT` | 业务流程、状态、接口、Event、数据模型、错误码、事务或模块边界变化 | DESIGN |
| `SECURITY` | 身份、权限、租户、外部输入、敏感数据、密钥、签名、回调、支付安全 | SECURITY |
| `PERFORMANCE` | 查询、索引、分页、批处理、远程 IO、缓存、锁、并发、大数据量 | PERFORMANCE |
| `CORE` | 核心链路、资金链路、跨模块高影响改动，或多个风险维度强耦合 | DESIGN + SECURITY + PERFORMANCE（候选，仍受维度池约束） |

**调度规则（强制）**：
1. IMPLEMENTATION 永远执行。
2. 风险标签映射出的候选维度须与 `cr.review.dimensions` 取交集；交集外的维度跳过并显式记录「项目池停用」原因。
3. 普通业务逻辑只要改变流程、状态或契约，必须标 `CONTRACT`。
4. 一个任务可同时具有多个风险标签。
5. **跳过维度必须写明理由（无风险证据 / 项目池停用），禁止只写"无风险"。**
6. 无法确定是否存在某类风险时，按保守策略执行对应 Reviewer（若该维度在池内）。
7. 复杂度只用于辅助判断，不得替代风险证据或直接决定维度。

## review-plan 格式

```markdown
## 调度状态: {READY | INCOMPLETE}

- 任务: {X.Y 范围标签 · 任务标题}
- 复杂度: {简单 | 普通 | 复杂}
- 风险标签: {NONE | CONTRACT, SECURITY, PERFORMANCE, CORE}
- 维度池: {implementation, design, security, performance}（配置 cr.review.dimensions）
- 调度维度: {IMPLEMENTATION, ...}（= 风险候选 ∩ 维度池；CORE 不强制全量）

## 变更证据
- {文件或设计条目}: {触发或不触发风险的事实}

## 调度明细
| 维度 | 是否执行 | 触发标签 | 依据 |
|------|---------|---------|------|
| IMPLEMENTATION | YES | BASELINE | 所有代码变更固定执行 |
| DESIGN | {YES | NO} | {CONTRACT | CORE | NONE} | {具体依据 / 风险信号但项目池停用 DESIGN} |
| SECURITY | {YES | NO} | {SECURITY | CORE | NONE} | {具体依据 / 风险信号但项目池停用 SECURITY} |
| PERFORMANCE | {YES | NO} | {PERFORMANCE | CORE | NONE} | {具体依据 / 风险信号但项目池停用 PERFORMANCE} |
```

## 调度后调用

`review-plan.md` 为 `READY` 后，只启动"是否执行 = YES"的 Reviewer，**同一轮消息内并行调用**（形式见 `agent-protocol.md`，模板见 `prompts/agents.md`）。

## coordinator 汇总协议（全部必选报告返回后，按序执行）

> **报告内容校验与合并全部由 `reviewer-coordinator` 承担**：主 Agent 不逐份读取原始维度报告（避免把全部报告载入主上下文），只依赖 reviewer 返回码 + 统一报告。

1. 主 Agent 收集全部必选 reviewer 的**返回码**（`COMPLETE | INCOMPLETE`，Agent 工具直接返回，不读报告文件）。任一 reviewer 返回 `INCOMPLETE` → 先补齐缺失输入，再**只重跑失败的 reviewer**（新上下文）。
2. 缺失输入无法补齐 → 任务保持 `CR_PLANNED`（reviewer 未全完成，尚未提交 `CR_SCANNED`），输出阻塞原因；不得进入汇总或推进。
3. 全部必选报告返回 `COMPLETE` → 启动 `reviewer-coordinator`（模板见 `prompts/agents.md`），prompt 传入全部必选报告路径；coordinator 校验每个报告存在且含（维度/结果/摘要/已完成检查项/问题清单，每个问题含定位（文件+行数范围）/触发条件/根因/证据/影响/建议），通过后去重合并，统一报告写入 `{工单根}review/{范围标签}-{X.Y}/unified.md`。
4. coordinator 返回 `INCOMPLETE`（某报告缺失/无效）→ 主 Agent 依其返回信息定位失败报告，**只重跑对应 reviewer**（新上下文）后重新汇总，不推进。
5. coordinator 返回 `COMPLETE` → 主 Agent **只读取 unified.md**（原始维度报告不进主上下文），提取 `report_complete / reviewer_count / unified_report_path`，组装 `CR_SCANNED{report_complete, reviewer_count, unified_report_path}` 提交 `statectl`（命令见 `stage-4.2-cr.md`）；任务进入 `CR_SCANNED` 后由主 Agent **派 `reviewer-judge` 独立裁决**（见 `stage-4.2-cr.md`「Judge 裁决」），读其 `judge.md` 后提交 `CR_JUDGED`。

> 所有 Reviewer 只产出维度报告，绝不修改代码；与编码、其他 Reviewer 均不共享上下文。
