# 阶段 4.2：多维 CR、Judge 裁决与修复闭环（CR_PLANNED → CR_PASSED → DONE）

> input: done 报告、任务范围 diff、review-plan
> output: `review/{范围}-{X.Y}/`（review-plan + 维度报告 + unified.md + judge.md + fix-contract.md）
> agents: reviewer-implementation（固定）、reviewer-security/design/performance（按风险）、reviewer-coordinator（汇总）、reviewer-judge（独立裁决）、executor（改写）
> fail_modes: 风险调度 `reviewer-dispatch.md`；decision 分流 `generated/automation.md` + `generated/vocab.md`
> 命令模板 `generated/commands.md`（CR_SCANNED/CR_JUDGED/CR_RECHECKED/CR_APPROVED/TASK_CR_PASSED/VERIFY_PASSED/VERIFY_FAILED）；payload schema `model/events.schema.json`。

## 行为目标
每个任务经多维审查 → Judge 独立裁决 → 修复/通过闭环，以客观质量门证据进入复验。CR 分流永远逐任务。

## 关键不变量
- 编码与审查分离：reviewer/coordinator/judge 只产出清单与裁决，不改代码；各自独立上下文。
- 修复后二次审核（`CR_FIXING → CR_RECHECKING`）由 `cr.capabilities.recheck` 控制（默认开启；false = 只审核一次）。二次审核可按严重度跳过：`cr.capabilities.minor_fix_auto_confirm`（默认 true）下，纯 MINOR+IMPLEMENT_FIX 修复且带 `quality_gate_evidence` → 直接 `CONFIRM_CR` 进复验；`fixed_has_major=true` 或 `fixed_has_baseline_align=true` 仍强制 `CR_RECHECK`。`CR_PASSED` 必须有 `quality_gate_evidence`；`CR_FIXING` 必须有 `fix_contract_path`。
- 裁决护栏（fixed safety）：`uncertain_count>0` 或 `min_confidence < cr.quality.judge.min_confidence`（config 值）必须阻塞；`has_design_rework=true` 不得伪装实现级修复。
- **处置三档门槛**：judge 依 `agent-contracts.yml#reviewer-judge.judging_rules` 判别树裁三档——`IMPLEMENT_FIX`（纯实现）/ `BASELINE_ALIGN`（实现+基线补记，不改契约值）/ `DESIGN_REWORK`（契约值要改或牵动他任务，须带锚定证据）。主 Agent 提交 `CR_JUDGED` 前按此门槛核对 judge 的 `has_design_rework` / `has_baseline_align`，误升格则退回 judge 重裁，不得静默降级。
- `REQUEST_DESIGN_REWORK` / `has_design_rework=true` → 走 `/workflow rework`，不得进 CR_FIXING（不变量 `design_rework_exit`）。
- `regression_detected` / `is_fix_related` 必须确定性判定（测试退化 / diff 越界 / 依赖闭包），非主观。

## 执行要点

### ④ 多维 CR（CR_PLANNED → CR_SCANNED）
1. 读 `reviewer-dispatch.md`：依实际 diff 证据判风险标签，候选维度与项目维度池 `cr.review.dimensions` 取交集，生成 `review-plan.md`（调度 INCOMPLETE 则不启动 reviewer）。
2. 并行启动必选 reviewer（IMPLEMENTATION 固定 + 池内命中维度的风险 reviewer）。
3. 按 `reviewer-dispatch.md「coordinator 汇总协议」`收集返回码、重跑失败、启动 coordinator、读取统一报告。
4. 统一报告 `COMPLETE` → 提交 `CR_SCANNED{report_complete, reviewer_count, unified_report_path}`。

### Judge 裁决（CR_SCANNED → CR_JUDGED）
派 `reviewer-judge` 独立裁决（独立上下文，契约见 `agent-contracts.yml#reviewer-judge`）：逐条 `ACCEPTED/REJECTED/MODIFIED/DESIGN_REWORK/UNCERTAIN` + `confidence` + 处置三档（`IMPLEMENT_FIX`/`BASELINE_ALIGN`/`DESIGN_REWORK`），产出 `judge.md`（含 `has_design_rework` / `has_baseline_align` 聚合）；REJECTED/UNCERTAIN 或与来源冲突时按需打开 source 报告取证。

**主 Agent 读 judge.md 后、提交 `CR_JUDGED` 前，必须向用户展示 judge 摘要**，供用户快速裁决（展示格式见 SKILL.md 护栏 #14：首行必须以 `📄 裁决文件: {judge 返回的实际路径}` 开头，禁止占位符；每条保留定位锚点，文件:行数范围，多锚点逐行列出，N/A 附原因）。
随后补 `judge_report_path`（必填，statectl 校验 judge.md 存在）、`quality_gate_evidence` 与 `fix_contract_path`（如有修复）→ 提交 `CR_JUDGED`。

返回 decision 由 `statectl` 给出（矩阵 `generated/automation.md`），本表只列执行动作：

| decision | 执行动作 |
|---|---|
| `CONFIRM_CR` | 提交 `TASK_CR_PASSED` 进 ⑥ 复验 |
| `FIX_CR_ISSUES` | ⑤ 修复（先写修复契约，见下） |
| `REQUEST_DESIGN_REWORK` | 走 `/workflow rework`（不得进 CR_FIXING） |
| `AUTONOMOUS_BLOCK` | 可信阻塞终态，保存完整证据 |
| `WAIT_USER_APPROVAL` | CR 人工门（见下） |

### 客观质量门证据（CR_PASSED 前置）
Judge 判 clean 前，把**当前已在跑的确定性检查**结果落成 `quality_gate_evidence` 文件（模块测试、语法/编译、scope 越界检查）。**CR_PASSED 必须有客观证据，不能只依赖 Agent 结论。**

### 修复契约（CR_FIXING 前置）
进入修复前落简版契约文件（允许改的文件/符号、禁止改动、成功条件、回滚条件）→ `fix_contract_path`。Executor 只按契约改，不自行扩大范围。
含 `BASELINE_ALIGN` 处置时，契约必须带 `baseline_align` 段：声明 design-baseline 允许追加的章节 + 禁止改任何契约值；Executor 按此段一并追齐基线（statectl 以基线指纹校验已实际修改）。

### CR 人工门（pending_gate.type=CR）
Judge 摘要已由主 Agent 在 `CR_JUDGED` 前展示（见上，含 judge.md 路径 + 逐条 + 聚合）。用户依据摘要对每条 `ACCEPTED/REJECTED/MODIFIED`（带 `disposition: IMPLEMENT_FIX|BASELINE_ALIGN|DESIGN_REWORK`）。只有显式 `/workflow approve` 才提交 `CR_APPROVED{adjudications, has_implement_fix, has_baseline_align, has_design_rework}`，必须匹配 `pending_gate.target_task`；`has_design_rework=true` 时走 rework，`has_baseline_align=true` 时修复契约须带 `baseline_align` 段。

### CR 裁决后同步 design-baseline（防设计漂移）
approve 后、修复前检查 MODIFIED 是否调整接口签名/状态码/事件名/数据模型（契约值）——有 → 属 `DESIGN_REWORK` 根因，必须走 rework；无 → 需补基线记录时按 `BASELINE_ALIGN` 在修复契约声明 `baseline_align` 段并同步追齐。

### ⑤ 修复（CR_FIXING → 二次审核或直接确认）
调 `executor`（模板「executor 改写」，只改 ACCEPTED/MODIFIED 实现级问题）→ 主 Agent 提交 `REWRITE_COMPLETED`。**`fixed_has_major` / `fixed_has_baseline_align` 是 schema 必填字段，漏填 statectl 拒绝**（防静默回退到恒重审）——由主 Agent 从已批准裁决（CR_APPROVED adjudications）计算：任一已采纳问题严重度为 MAJOR → `fixed_has_major=true`；任一处置为 BASELINE_ALIGN → `fixed_has_baseline_align=true`。命中自动确认路径或 recheck=false 时带 `quality_gate_evidence`。
- `fixed_has_major=true` 或 `fixed_has_baseline_align=true` → 强制进重审（`CR_RECHECK`）。
- 两者均 false（纯 MINOR+IMPLEMENT_FIX）且 `cr.capabilities.minor_fix_auto_confirm=true` + `quality_gate_evidence` → 直接 `CONFIRM_CR` 进复验（跳重审，凭修复契约边界 + 质量门证据兜底）。
- 其余（含 minor 自动确认但缺质量门证据）→ 保守 `CR_RECHECK`。

### 重审（CR_RECHECKING → CR_RECHECKED，仅 `cr.capabilities.recheck=true` 且未命中 minor 自动确认时进入）
运行 `statectl review-dispatch --config {C} --severity {MAJOR|MINOR}`，按返回的 `reviewers` 列表派发重审维度（返回已与维度池 `cr.review.dimensions` 取交集，池停用维度在 reason 中显式记录）→ coordinator（≥2 维度）合并 → judge 重新裁决 → **主 Agent 同样向用户展示 judge 摘要**（同首轮格式，见 SKILL.md 护栏 #14）→ 提交 `CR_RECHECKED{cr_round, resolved/new_issue_count, regression_detected, judge_report_path}`。`FIX_CR_ISSUES` → 下一轮（`cr_round` 自动递增）；`AUTONOMOUS_BLOCK` → 质量劣化/超 `cr.limits.fix_max` 熔断。

### ⑥ 复验（CR_PASSED → VERIFYING → DONE）
提交 `TASK_CR_PASSED` → 检查已采纳问题均修复 + 单测 + 语法/编译 → `VERIFY_PASSED` → DONE。失败 `VERIFY_FAILED{evidence, is_fix_related, cr_round}`：`is_fix_related=true` 且未超限 → 回重审；否则 → `AUTONOMOUS_BLOCKED`。
