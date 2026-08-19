# `/workflow rework` — 任务调整通道（缺陷返工 / 补充任务）

> **⛔ 防跳步声明（强制）**：rework 是任务调整协议。执行时必须**先与用户确认调整内容**，再按步骤执行。禁止跳过确认直接制定新计划或开始编码。两种变体：**缺陷返工**（既有任务缺陷按根因层级回退）与**补充任务**（当前需求内新增子任务，可能牵动设计）。

## 变体 A：缺陷返工

### 流程
1. 解析需求/里程碑；`statectl get` 读当前状态。
2. **与用户确认缺陷描述 + 根因层级**（实现级 / 设计级 / 需求级），写返工单 `{工单根}rework/R{轮次}-{YYYY-MM-DD}.md`。
3. **依赖扩散**：从 dev-tasks 依赖图自动算出"依赖被改设计/被改任务"的下游任务，连同初判受影响任务**列给用户确认**（可增删）；确认后才回退。
4. 提交 `REWORK_STARTED`：
   ```bash
   statectl.py transit --state {S} --config {C} --event REWORK_STARTED \
     --payload '{"level":"DESIGN","affected_tasks":["1.2","1.3"],"rework_id":"R1"}'
   # 受影响任务 → TODO；里程碑按层级回退（DESIGN→ANALYZING，REQUIREMENT→DISCUSSING）
   ```
5. 回写进度 + 追加返工记录。之后按回退后的阶段推进：设计级回退 ANALYZING → 重做阶段 2 → `STAGE_COMPLETED` 进入 DESIGN_REVIEW 并设 DESIGN 门 → 阶段 3 一次 approve（`/workflow approve`）。

> 边界：只改当前任务能解决 → CR 修复；牵动设计或别的任务 → rework。CR 裁决存在 `has_design_rework=true`（或 `CR_JUDGED` 返回 `REQUEST_DESIGN_REWORK`）时**必须**走 rework，不得由 CR executor 直接修复（不变量 `design_rework_exit`）。

## 变体 B：补充任务

在**当前进行中需求内部**新增一个 dev-tasks 未规划的子任务。补充任务可能牵动设计契约，需自动评估并触发设计回退。

> 注意：`/workflow followup` 已删除。若要在**已完成需求上新增功能**（原 followup 场景），用 `/workflow start {新需求名}` 手动发起，不复用 `docs/parent/` 上下文。

### 流程
1. **确认任务定义**：与用户确认标题 / 工作范围 / 复杂度（`model/policy.yml#complexity`：SIMPLE|NORMAL|COMPLEX）/ 依赖。
2. **追加 dev-tasks**：在 `dev-tasks.md` 追加任务定义，编号 `X.Y` **顺延**（不重排既有编号，产出物文件名引用编号）：
   ```markdown
   - [ ] 2.3 {范围标签} · 补充任务标题 [普通] — 状态: TODO
   ```
3. **评估是否牵动设计契约**（改接口签名 / 新增依赖模块 / 数据模型变化 / 跨模块契约）：
   - **纯追加**（不动现有契约）→ 直接开始任务：
     ```bash
     statectl.py transit --state {S} --config {C} --event TASK_STARTED --task 2.3 \
       --payload '{"complexity":"NORMAL"}'
     ```
   - **牵动设计** → 触发设计回退（复用 rework 回退机制）：
     ```bash
     statectl.py transit --state {S} --config {C} --event REWORK_STARTED \
       --payload '{"level":"DESIGN","affected_tasks":["2.3"],"rework_id":"R1"}'
     # 里程碑回退 ANALYZING（无门；affected_tasks 仅新任务，既有任务是否受影响人工确认）
     ```
4. 牵动设计分支：回退后**重做阶段 2** 分析 → 提交 `STAGE_COMPLETED` 进入 DESIGN_REVIEW 并设 `DESIGN` 门 → 阶段 3 approve → 重新设计（design-baseline + dev-tasks 更新）→ 再 `TASK_STARTED` 开始新任务。

> 边界：补充任务编号必须沿用 `X.Y` 顺延；`_next_action` 自动识别新任务（未 DONE 即回到 `START_NEXT_TASK`，不会误推进验收）。若新任务牵动既有任务设计，`affected_tasks` 须把受影响的既有任务一并列出（按依赖图人工确认）。设计回退后 DESIGN 门由 `STAGE_COMPLETED`（ANALYZING → DESIGN_REVIEW）设置，不是 rework 直接设置。
