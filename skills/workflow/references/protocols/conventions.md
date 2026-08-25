# conventions — 任务编号与项目约定

> 阶段 2 产出 dev-tasks.md、阶段 4 写产出物时读本文件。任务编号与产出物命名的**权威定义**在 `generated/templates.md`（从 `model/` 生成）；本文件承载**项目约定**——项目特定事实，不属于状态机/策略数据，故不放入 `model/`。

## 任务编号与产出物命名（强制）

- 任务统一 **`X.Y`** 编号（X=任务组，Y=组内子任务，从 1 起始；禁止 T1 / 0.1 / 波次1 等非标格式）。
- 编号在阶段 2 产出 dev-tasks.md 时确定，全流程所有产出物文件名引用同一编号（plan / done / review 命名表见 `generated/templates.md#任务编号与产出物命名`）。
- 运行态以任务级状态为准；任务的细粒度子项是否完成由 done 报告 + DoD 记录，**不**在 dev-tasks.md 用 `[x]` 重复记账（见下文「运行时状态与派生视图」）。

## 项目约定

- **单体仓库**：默认已在项目仓库根目录；产出物存于 `{工单根}`（`{讨论根目录}{域}/{需求名}/.task/`）。
- **需求级参考文档**：`{工单根}docs/`，用户在 `/workflow start` 时放入（业务说明、接口文档、原始需求材料）。
- **前置检查（强制）**：见 `references/protocols/preflight.md`（仅 `start` 执行）。
- **工作范围**：每个任务在 dev-tasks.md 标注工作范围目录（一个或多个）；executor / 各维度 reviewer / verifier 均以此为工作边界，不假设特定目录结构。
- **架构文档**：`docs/business/{模块名}/`（overview / business / contracts / flows）+ `docs/business/cross-module.md`；来源与缺失处理见 `stage-2-design.md`。
- **验收基线（强制）**：按项目 `.claude/rules/` 定义的测试命令执行模块级单测通过 + 按项目规则执行语法/编译检查通过。
- **静态分析**：是否纳入 DoD / 验收由项目 `.claude/rules/` 决定，workflow 不强制。
- **单仓库单分支**：所有模块共用一条 feature 分支，无独立分支 / PR；diff 按 `{工作范围目录}` 隔离。

## 运行时状态与派生视图

- **运行时状态唯一源**：`{工单根}state/workflow-state.yml`（`adapters/statectl.py` 读写）。`dev-tasks.md` 只保存任务定义与 DoD，**不再重复保存运行状态**。
- **任务集登记**：阶段4入口用 `statectl init-tasks` 把 dev-tasks 全部任务一次性登记进状态（`{X.Y: {state: TODO, complexity}}`），此后 `next` 的"全部任务 DONE"按完整计划集判定；补充任务经 `TASK_STARTED` 惰性追加，不影响该判定。**`/workflow split` 只允许在 init-tasks 前 / 任何任务启动前执行**（`validate.py --check-split` 校验）。
- **派生视图**：`progress.md` 由 `adapters/progress_render.py` 从状态文件生成，人工只读不手改；**按需生成**（`/workflow status` 时、任务 DONE 时、里程碑阶段切换时），不随每次状态变更重算。
