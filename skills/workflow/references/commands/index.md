# workflow 命令路由索引

> 执行任意 `/workflow` 子命令前读本文件。状态数据一律从 `model/` 或 `statectl get` 获取，不从本文件复制。

**统一解析规则**：`next` / `approve` / `status` / `rework` 确定目标时，省略参数按「显式参数 > 活动指针（`{项目根}.claude/workflow/active`）> 旧回退规则」解析。显式传参不改变活动指针；要持久切换用 `use`。所有解析支持前缀/子串模糊匹配，唯一即定位，多个列出让选。

**粘性指针（单规则）**：解析出唯一里程碑后写回 `{项目根}.claude/workflow/active`（补成 `{需求ID}#里程碑`）并**回显"活动指针已切换至 …"**；该里程碑 COMPLETED 后，只保留一条规则——自动改指剩余唯一进行中里程碑（回显），否则提示重新 `use`。`next`/`status`/`use` 描述同一策略。

---

## `/workflow use [需求ID][#里程碑]`
1. 解析入参（模糊匹配）；不传参显示当前活动上下文（不修改）
2. 校验存在（需求目录/里程碑存在）
3. 写入 `{项目根}.claude/workflow/active`（覆盖）
4. 回显：`当前活动: {需求ID}[#里程碑] — phase {phase} {pending_gate}`

## `/workflow start {需求名}`
- 按 `references/protocols/preflight.md` 逐项检查（rules-dir + automation-policy），blocking 项失败即终止。
- 创建需求目录 → 放入参考文档 → 调 `/{skills.discuss}` 讨论 → 用 `statectl` 初始化 `{状态文件}`（phase=DISCUSSING）。
- 详见 `references/stages/stage-1-discuss.md`。

## `/workflow next [需求ID][#里程碑]`
1. 解析目标；`statectl get` 读当前状态
2. 按 `phase` + `pending_gate` 分发：
   - 有 pending_gate → 提示先 `/workflow approve`（不推进）
   - 按 phase 进入对应 stage 文档（阶段 2/3/4/5）
3. 阶段完成后提交 `STAGE_COMPLETED`；返回 `ADVANCE_WORKFLOW` 时**同轮立即**继续下一任务/阶段，禁止询问"是否继续"
4. 只允许 `WAIT_NEXT_COMMAND` / `WAIT_USER_APPROVAL` / `REQUEST_DESIGN_REWORK` 等动作把控制权交还用户

## `/workflow approve [需求ID][#里程碑]`
1. `statectl get` 读 `pending_gate`
2. 按 `pending_gate.type` 分发到对应 stage 的门处理：
   | gate | 处理文档 |
   |------|---------|
   | DESIGN | stage-3-review |
   | PLAN | stage-4.1-plan |
   | CR | stage-4.2-cr |
   | ACCEPT | stage-5-accept |
   > 批准/打回事件与门类型以 `model/state-machine.yml#milestone.gate_events` 与 `generated/vocab.md` 为准，不在此表重复（新增/改名门事件只改 model）。
3. **只有显式 `/approve` 才提交门事件**；其他消息一律视为反馈。

## `/workflow status [需求ID][#里程碑]`
1. 读取状态并校验不变量。可作为两条独立 Bash tool call（可并行）：
   ```text
   python3 {skill根}/adapters/statectl.py get --state {状态文件}
   ```
   ```text
   python3 {skill根}/adapters/validate.py --state {状态文件} --log {转换日志}
   ```
   也可在同一 Bash tool call 使用显式 `&&` 顺序执行：
   ```text
   python3 {skill根}/adapters/statectl.py get --state {状态文件} && python3 {skill根}/adapters/validate.py --state {状态文件} --log {转换日志}
   ```
   禁止无分隔符地拼为一条 argv；任一工具失败即停止 status 处理并报告错误。
2. 省略目标且有活动指针 → 高亮显示；无活动指针 → 扫描全部。
3. 输出 phase / lifecycle / pending_gate / blocker / 任务进度。
4. 同时生成/刷新 `progress.md` 派生视图（惰性生成的唯一人读时机）。

## `/workflow list`
扫描 `{讨论根目录}` 下所有 `state/workflow-state.yml`，显示未完成（phase != COMPLETED）需求。

## `/workflow split [需求ID] {里程碑列表}`
确认里程碑划分 → 抽公共设计骨架 `design-foundation.md` → 建 `milestones/{里程碑}/` 目录 → 改写状态结构。

**时机（强制）**：拆分是设计/规划期的交付切片决策，只允许在**开发开始前**执行——即任何任务启动前（阶段 1–3，或阶段 4 首个 `TASK_STARTED` 之前）。执行前必须先跑 `python3 {skill根}/adapters/validate.py --state {状态文件} --check-split`：返回 `ok:true` 才允许继续；`ok:false`（任一任务已离开 TODO）→ **拒绝拆分**，剩余任务仍属当前里程碑交付，按"不拆、继续开发"处理。**禁止完成一部分任务后再拆**——会把已完成任务与剩余任务归属撕裂、导致后续任务漏登记（`stage-4.0-dev.md#阶段4入口` 的 init-tasks 即为 split 截止锚点）。

## `/workflow rework [需求ID][#里程碑]`
**必须先读 `references/commands/rework.md`**。任务调整通道，两种变体：
- **缺陷返工**：与用户确认缺陷与根因层级 → 算依赖扩散（列给用户确认）→ 提交 `REWORK_STARTED{level, affected_tasks}`（受影响任务回 TODO + 里程碑按层级回退）→ 写返工单。
- **补充任务**（当前需求内新增子任务）：确认任务定义 → 追加 dev-tasks（编号顺延）→ 评估是否牵动设计；纯追加直接 `TASK_STARTED`，牵动设计提交 `REWORK_STARTED{level=DESIGN}` 回退 ANALYZING，重做阶段 2 后经 `STAGE_COMPLETED` 进 DESIGN_REVIEW 设门。

## `/workflow summary [需求ID][#里程碑]`
详见 `references/commands/summary.md`。验收通过后产出 change-manifest.md（DDL / Job·MQ / API）。

## `/workflow hotfix {bug描述}`
详见 `references/commands/hotfix.md`。单次闭环（不走 5 阶段状态机）：定位 → 编码 → 校验分叉（SIMPLE Gate 通过可跳过单维度 CR）→ 裁决 → 改写。

## `/workflow config [preset]`
初始化/校验 `{项目根}.claude/workflow/config.yml`。**详见 `references/commands/config.md`**（configctl init/read 映射、Schema、生效时机）。
