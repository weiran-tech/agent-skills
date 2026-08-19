# 阶段 1：需求讨论（start，DISCUSSING）

> input: 需求名、docs/ 参考文档
> output: discussion.md、初始化 state（DISCUSSING → ANALYZING）、活动指针
> agents: {skills.discuss}（多轮对话；skill 名见 config.yml#skills，默认 devops-discuss）
> fail_modes: preflight blocking 项失败即终止，不创建需求
> 命令模板见 `generated/commands.md`（STAGE_COMPLETED）；payload schema 见 `model/events.schema.json`。

## 行为目标
把模糊需求讨论成可进入分析与设计的输入，并初始化流程状态。

## 关键不变量
- 只有 `start` 执行 preflight；其他子命令不执行。
- 讨论完成才提交 `STAGE_COMPLETED`；`ADVANCE_WORKFLOW` 同轮进阶段 2，`WAIT_NEXT_COMMAND` 提示 `/workflow next`。

## 执行要点
1. Preflight：按 `references/protocols/preflight.md` 逐项检查（rules-dir + automation-policy），blocking 失败即终止。
2. 询问/推断业务域 → 建需求目录 `{讨论根目录}{域}/{需求名}/docs/`，提示放入参考文档。
3. 调 `/{skills.discuss}` 讨论（传需求名；docs/ 有文件则附加"讨论前先读取"）。
4. 讨论完成后提交 `STAGE_COMPLETED` 初始化状态（初始 phase=DISCUSSING → ANALYZING）。
5. 写活动指针 `{项目根}.claude/workflow/active`。
