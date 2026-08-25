# workflow agent prompt 模板（集中，唯一来源）

> 构造 agent prompt 时必须把 `{工单根}`、`{范围标签}`、`{X.Y}` 展开为实际路径/值——子 agent 无法解析变量。
> 每个模板末尾统一附加 Bash 约束：`Bash 静态分析约束：禁止 for/while/if/case/here-doc/嵌套 $()。`
> 契约（输入/输出/返回协议）见 `model/agent-contracts.yml`；本文件只放 prompt 模板。
> **reviewer 调度依赖配置 `cr.levels.{minor,major}.recheck`**（主 Agent 从 `configctl read` 读取派发维度；implementation + judge 恒跑，coordinator ≥2 维度自动）。

## 阶段 2 — analyst（模块分析，只读）

```text
分析模块 {范围标签}（工作范围: {工作范围目录}），产出 {工单根}analysis/{范围标签}.md。
参考：{工单根}discussion.md、docs/{范围标签}/ 架构文档、需求 docs/。
{Bash 约束}
```

## 阶段 2 — architect（汇总设计，只读）

```text
综合需求 {域}/{需求名} 的设计，产出：
- {工单根}design-baseline.md（设计基线，共识/契约层，必含清单）
- {工单根}dev-tasks.md（任务拆分：X.Y 编号 + 复杂度标注 + 依赖）
参考：discussion.md、docs/business/cross-module.md、需求 docs/，另有 {多模块：{工单根}analysis/ | 单模块：docs/business/{模块名}/ 架构文档}。
多模块时直接汇总 {工单根}analysis/；单模块直调（无 {工单根}analysis/）时先自行完成受影响模块分析再汇总设计。
{Bash 约束}
```

## 阶段 4 — planner（复杂任务 LLD，只读）

```text
为任务 [{范围标签} · {任务标题}] 产出任务级详细设计（LLD），写入 {工单根}plans/{范围标签}-{X.Y}.md。
参考：dev-tasks.md（任务定义/范围/依赖）、design-baseline.md（契约）、analysis/、docs/business/{模块名}/、需求 docs/。
如 plan 调整 design-baseline 契约（接口/事件/数据模型），在 plan 中显式标注 contract_changed 与调整项。
{Bash 约束}
```

## 阶段 4 — plan-validator（只读，只判断不评价方案优劣）

```text
校验任务 [{范围标签} · {任务标题}] 的任务级详细设计是否完整且可执行。
Plan：{工单根}plans/{范围标签}-{X.Y}.md。任务定义：{工单根}dev-tasks.md。设计基线：{工单根}design-baseline.md。
仅按输出契约返回 PASS、FAIL 或 INCOMPLETE（带 blockers），不修改任何文件。
{Bash 约束}
```

## 阶段 4 — executor（编码/改写，读写）

```text
{编码} 执行任务 [{范围标签} · {任务标题}]，工作范围: {工作范围目录}。
{复杂任务：对照已确认 plan {工单根}plans/{范围标签}-{X.Y}.md 严格实现}
{简单/普通任务：对照 {工单根}design-baseline.md 实现要点}
{如有依赖：参照 {工单根}done/{前序模块}.md 的接口/Event 契约}
完成后写入 {工单根}done/{范围标签}-{X.Y}.md（变更文件清单/命令与退出结果/风险证据）。
{hotfix 模式：done 报告写 {hotfix工单根}done.md（单文件，无 done/ 子目录与范围标签）；能力 hotfix_simple_skip_cr 开启时，done.md 追加 #regression 段——列改动文件/行 + 覆盖它的回归测试用例/断言行}
{Bash 约束}

{改写} 按已确认的多维 CR 裁决与修复契约修复任务 [{范围标签} · {任务标题}]，工作范围: {工作范围目录}。
裁决文件：{工单根}review/{范围标签}-{X.Y}/unified.md。
修复契约：{fix_contract_path}（只改契约允许的文件/符号，禁止改动契约列出的禁止项）。
只修改 ACCEPTED 和 MODIFIED 的实现级问题，不修改 REJECTED 或 DESIGN 根因问题。
修复契约含 baseline_align 段时，一并追齐 design-baseline（只追加既定意图的落地记录，禁止改任何契约值），确保基线文件被实际修改。
完成后重跑模块测试/语法/编译，把结果写成 {工单根}review/{范围标签}-{X.Y}/quality-gate-evidence.md，供主 Agent 提交 REWRITE_COMPLETED 时作证据（REWRITE_COMPLETED 的 fixed_has_major / fixed_has_baseline_align 必填字段由主 Agent 从已批准裁决计算，非本任务职责）。
{Bash 约束}
```

## 阶段 4 — reviewer（implementation/security/design/performance，只读）

```text
审查任务 [{范围标签} · {任务标题}]，工作范围: {工作范围目录}。
报告写入 {工单根}review/{范围标签}-{X.Y}/{维度}.md。
调度计划: {工单根}review/{范围标签}-{X.Y}/review-plan.md。
参考: {工单根}done/{范围标签}-{X.Y}.md、design-baseline.md、{复杂任务 plan 路径或 N/A}、docs/business/{模块名}/、项目 CLAUDE.md 与 .claude/rules/。
每个问题必须含：定位（文件+行数范围，多锚点，无法精确定位标 N/A）/触发条件/根因/证据/影响/建议；严重度 MAJOR|MINOR；根因层级 IMPLEMENTATION|DESIGN|REQUIREMENT。
缺失输入时返回 INCOMPLETE，不得误报 PASSED。
{Bash 约束}
```

## 阶段 4 — reviewer-coordinator（汇总，只读）

```text
汇总任务 [{范围标签} · {任务标题}] 的多维 CR 报告。
调度计划：{工单根}review/{范围标签}-{X.Y}/review-plan.md。
源报告：{仅列出 review-plan 中"是否执行 = YES"的报告路径，每行一个}
统一报告写入 {工单根}review/{范围标签}-{X.Y}/unified.md。
承担报告内容校验（主 Agent 不逐份读原始报告）：确认每个源报告存在且含 维度/结果/摘要/已完成检查项/问题清单，每个问题必须含 定位（文件+行数范围）/触发条件/根因/证据/影响/建议。
任一分组报告缺失或无效 → 返回 INCOMPLETE 并指明是哪份报告、缺什么；校验全部通过 → 只去重/合并，不重新审码，每个问题保留 verdict/disposition 两字段与来源 ID，返回 COMPLETE。
{Bash 约束}
```

## 阶段 4 — reviewer-judge（独立裁决，只读）

```text
对任务 [{范围标签} · {任务标题}] 的统一 CR 报告执行独立裁决，写入 {工单根}review/{范围标签}-{X.Y}/judge.md。
输入：{工单根}review/{范围标签}-{X.Y}/unified.md（每条问题 裁决=PENDING）、review-plan.md、design-baseline.md、dev-tasks.md。
逐条裁决 verdict=ACCEPTED|REJECTED|MODIFIED|DESIGN_REWORK|UNCERTAIN，每条带 confidence（0-1）、处置（IMPLEMENT_FIX|BASELINE_ALIGN|DESIGN_REWORK）与定位（必须原样继承 unified.md 的定位锚点=文件+行数范围，多锚点逐行重复，unified 未给行号时标 N/A 并说明原因）。
处置三档判别树（逐条问题按序判定）：
- Q1 修复是否动 design-baseline？否 → IMPLEMENT_FIX（纯实现）。
- 是 → Q2 是否改变契约值（接口签名 / 事件名 / 状态码 / 数据模型）或牵动其他任务设计 / 核心流程 / 跨模块契约？
  - 否（只补既定意图的落地记录）→ BASELINE_ALIGN（实现 + 基线补记，不改契约值）。
  - 是 → DESIGN_REWORK（设计/契约要改）。
锚定证据：裁 DESIGN_REWORK 必须指得出要改的具体契约值（design-baseline 哪段，from→to）或受牵动的下游任务编号；指不出的一律降为 BASELINE_ALIGN 或 IMPLEMENT_FIX。
不属于设计级的常见情形（不得升格）：dev-tasks 任务定义/登记补全、纯实现遗漏不碰基线 → IMPLEMENT_FIX；实现遗漏同时需补基线记录 → BASELINE_ALIGN。
每条裁 DESIGN_REWORK 的问题必须在 judge.md 标注命中的契约值/下游任务锚点；BASELINE_ALIGN 注明「仅同步、无契约变更」。
独立判断，不凭 coordinator 严重度自动接受；证据不足时按需打开对应 source 报告核对（不预读全部报告），仍不足则裁 UNCERTAIN。
产出聚合：accepted_count（ACCEPTED+MODIFIED）/ rejected_count / uncertain_count / min_confidence / has_design_rework / has_baseline_align。
min_confidence = 已采纳问题（ACCEPTED+MODIFIED）的置信度最小值；无已采纳问题（accepted_count=0）时填 1.0（不参与阈值判断，policy 仅在 accepted_count>0 时评估）。
unified.md 缺失或任一问题缺裁决字段 → 返回 INCOMPLETE 并指明缺失。
最终返回（用户 Done 后直接可见，主 Agent 依此展示；格式固定，首行必为路径）：
第一行：judge.md 的实际绝对路径（可直接打开查看，禁止占位符）
第二行：状态（COMPLETE | INCOMPLETE）+ 一行聚合摘要（accepted/rejected/uncertain/min_confidence/has_design_rework/has_baseline_align）
{Bash 约束}
```

## 阶段 5 — verifier（收尾验收，只读）

```text
对需求 {域}/{需求名} 做收尾验收，报告写入 {工单根}acceptance/acceptance.md。
参考：{工单根}design-baseline.md（以返工修订和 plan 同步后的最新契约为准）、docs/business/cross-module.md。
只产出问题清单（严重度 + 根因层级 + 报告完整性），绝不修改代码。
{Bash 约束}
```

## 独立命令 — summary（主 Agent 直接编写，只读；非子 agent）

```text
为需求 {域}/{需求名} 产出交付对接清单，写入 {工单根}change-manifest.md。
受众是 DBA（DDL）、运维（Job·MQ）、前端（API），只关心"改哪些表、加哪些队列、有哪些接口"，不关心类名/方法/文件位置。
数据来源（交叉核对，以实际代码为准）：
- {工单根}dev-tasks.md、design-baseline.md 的契约
- 各任务 {工单根}done/{范围标签}-{X.Y}.md、CR 裁决 {工单根}review/{范围标签}-{X.Y}/unified.md、验收 {工单根}acceptance/acceptance.md
- 实际代码中的数据库迁移文件、定时任务/队列定义、路由与接口定义
按 change-manifest 模板分三块输出：
- DDL（DBA）：逐表可直接执行的 SQL（新建表含全部字段/索引/注释；改表用 ALTER TABLE ADD COLUMN / ADD INDEX）
- Job·MQ（运维）：本需求新增/变更的定时任务与队列，一行一个名称。若 {配置目录}templates/change-manifest.md 存在，按语言模板的 Job·MQ 结构产出（java 含 MQ Topic/Tag/ConsumerGroup；php 含 Event/Job）
- API（前端）：Method + Path | 入参(字段+类型+必填) | 出参要点 | 用途
无变更的块写「本次无 DDL 变更」/「本次无新增队列」/「本次无接口变更」。
{Bash 约束}
```

## SIMPLE Gate — simple-gate-checker（独立复核）

```text
独立复核任务 [{范围标签} · {任务标题}] 的 SIMPLE Gate。
必须从实际任务 diff 重建变更文件清单（不采信 done 报告自述），并按文件路径推导 change_kind：任一生产代码文件 → CODE；全部为文档（docs/、*.md）→ DOCS_ONLY；全部为测试（tests/、testing/、*Test.*）→ TESTS_ONLY；仅含测试+文档、无生产代码 → TESTS_DOCS。test/doc 类型不限文件数（仅 CODE 限 2，阈值定义于 model/policy.yml#simple_gate.max_files），其余门条件不变。
实际执行测试/静态检查并记录命令与退出结果，校验工作范围（无越界文件）并复核风险信号：文档/测试变更若描述契约语义变化同样标 CONTRACT。对照 task change manifest 确认 diff 归属。
将复核结论（变更文件清单 + change_kind + 各门字段证据 + 裁决 PASS | FAIL | INCOMPLETE）追加写入 {工单根}done/{范围标签}-{X.Y}.md 的 `#gate` 段（文件不存在则创建）。
最终返回该文件实际路径 + 裁决；归属不可靠时裁决 INCOMPLETE。未写入文件视为未完成。
{Bash 约束}
```
