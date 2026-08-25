# 阶段 2：分析与设计（ANALYZING）

> input: discussion.md、docs/business/{模块名}/ 架构文档、docs/business/cross-module.md
> output: analysis/{模块}.md（多模块）、design-baseline.md、dev-tasks.md
> agents: analyst（多模块并行，只读）、architect（汇总，只读）；{skills.arch_analyzer}（架构文档来源，项目提供时；skill 名见 config.yml#skills，默认 arch-analyzer）
> fail_modes: 未决项（待确认/TODO）必须登记成表并有处置，不许悬空
> 任务编号与项目约定见 `references/protocols/conventions.md`；prompt 模板见 `prompts/agents.md`；子 agent 调用见 `references/protocols/agent-protocol.md`。
> 命令模板见 `generated/commands.md`（STAGE_COMPLETED）。

## 行为目标
产出契约层设计（design-baseline）与任务拆分（dev-tasks），供阶段 3 审核。

## 关键不变量
- 单模块直调 `architect`（省一次 analyst spawn）；多模块先并行 `analyst` 再 `architect` 汇总。
- 架构文档优先复用 `docs/business/{模块名}/`；缺失/过期才新分析（项目提供 {skills.arch_analyzer} 则用其产出）。

## 执行要点
1. 判断影响面：从讨论文档提取影响模块 → 写入状态；决定单模块直调 or 多模块并行。
2. 调 `architect` 产出 `design-baseline.md`（设计基线，共识/契约层）+ `dev-tasks.md`（X.Y 编号 + 复杂度 + 依赖）。
3. 完成后提交 `STAGE_COMPLETED`（ANALYZING → DESIGN_REVIEW + 设 DESIGN 门），随后按 `stage-3-review.md` 进入设计审核门。

## 任务分解粒度（简单需求控重）

任务粒度直接决定阶段 4 闭环次数：每个任务独立付一次「编码→DoD→(CR/SIMPLE)→复验」的固定开销，粒度越细、开销越大，与需求复杂度无关。分解时遵循：

- **内聚改动合并成一个任务**：同一文件、同一信任边界、互相依赖的改动应合为一任务（如"Request 校验 + getter 归一 + Action 保存来源"合并为后端契约任务），不要按"每处改动一个任务"拆分。一次 CR 审一个有意义的组 diff，远优于三次 CR 审一行级 diff。
- **简单需求默认 3-5 个任务**：后端契约组 / 前端状态组 / 测试与验收组 / 文档与回归组（视规模裁剪）。一行级改动（<10 行、无分支逻辑）不单独成任务。
- **测试与文档可并入承载任务**：小改动的新增单测并入对应实现任务；文档同步并入实现任务或独立成尾任务（纯文档可走 `DOCS_ONLY` 放宽路径，见 `stage-4.0-dev.md`）。
- **复杂度标注面向风险而非改动量**：SIMPLE = "单范围、无契约变化、低风险"，不是"改动少"；多文件但纯文档/纯测试仍可 SIMPLE（配合 `change_kind`）。改动跨信任边界或多文件生产代码时按风险升级 NORMAL，不强压档位。
