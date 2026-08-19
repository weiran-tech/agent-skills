# 阶段 4.0：开发总则与逐任务主流程（DEVELOPING）

> input: dev-tasks.md、design-baseline.md、当前 task_state ｜ output: done 报告（`.task/done/{范围}-{X.Y}.md`）
> agents: executor（编码）、simple-gate-checker（SIMPLE 复核）、team{executor}（并行）
> fail_modes: 见 stage-4.2 / stage-4.1；子 agent 失败按 `agent-protocol.md`
> 命令模板 `generated/commands.md`；路由 `generated/vocab.md`；决策矩阵 `generated/automation.md`；payload schema `model/events.schema.json`。

## 行为目标
每个任务闭环：复杂度判定 → 编码 → DoD → 多维 CR（或 SIMPLE 跳过）→ 复验 → DONE。

## 子 agent 返回后通用协议
① 读其产出文件（以文件为准）② 用 `statectl` 回写状态 ③ 输出摘要 ④ 明确下一步。禁止静默结束。

## 关键不变量
- COMPLEX 必须经 plan 门（stage-4.1）才能编码；SIMPLE/NORMAL 直接编码。
- SIMPLE 必须六字段 PASS 才能 SKIP_CR；任一不过 / risk_signals 非空 → 不提交 `simple_gate`，走 RUN_CR。
- DoD 必须有客观证据（单测 + 编译）；diff 越界不满足 SIMPLE 准入。
- 编码不允许越出 task change manifest（并行编码前必须建立 diff 归属基线，见 `agent-contracts.yml#diff_attribution`）。
- CR 汇总 → 分流 → 改写始终逐任务。

## 任务闭环概览
`① 复杂度判定→TASK_STARTED（COMPLEX→4.1；SIMPLE/NORMAL→CODING）→ ② 编码(executor)→done 报告 → ③ DoD→TASK_DOD_PASSED（RUN_CR→4.2 / SKIP_CR→⑥）→ ⑤ 改写→REWRITE_COMPLETED → ⑥ VERIFY_PASSED→DONE ｜ VERIFY_FAILED→回 CR_RECHECKING`

## 阶段4入口：init-tasks 全量登记任务（必做，仅一次）

进入 DEVELOPING 后、**首个 `TASK_STARTED` 之前**，必须调用一次：

```bash
python3 {skill根}/adapters/statectl.py init-tasks --state {状态文件} --config {配置} \
  --tasks '[{"id":"1.1","title":"…","complexity":"NORMAL"}, …]'
```

- 任务清单从 dev-tasks.md 读出（id + title + complexity），**一次性全量登记**；state 任务集即完整计划集。
- 登记后 `statectl next` 的"全部任务 DONE"按完整计划集判定——dev-tasks 规划到 1.9 就一个都不能漏；**只完成 1.1–1.5 不会误判进验收**。
- init-tasks 是 **split 截止锚点**：`/workflow split` 只能在任何任务启动前执行（`validate.py --check-split` 校验，任一任务离开 TODO 即拒绝）。**若需拆里程碑，必须在 init-tasks 前决定**；开发开始后禁止中途拆分——否则已完成任务与剩余任务归属被撕裂、可能漏登记。
- 幂等约束：仅当 state 任务集为空时允许；重复调用、phase 非 DEVELOPING、任务 id 非 `X.Y`、complexity 非法都会拒绝。
- `TASK_STARTED` 仍兼容补充任务（`/workflow rework` 追加的 dev-tasks 任务在首次启动时自动登记），不影响"全部任务 DONE"判定。

## ① 复杂度判定 → TASK_STARTED
按 `model/policy.yml#complexity` 判定 SIMPLE|NORMAL|COMPLEX，提交 `TASK_STARTED{complexity}`。
判定前必须打开 `model/policy.yml#complexity`，按 COMPLEX → NORMAL → SIMPLE 顺序逐级核对（先排除最严重再逐级降）；命中 COMPLEX 任一条件的任务不得降级为 NORMAL/SIMPLE。

## ② 编码 → ③ DoD → TASK_DOD_PASSED
编码用 `executor`（模板 `prompts/agents.md`「executor 编码」）→ 写 done 报告。DoD：模块级单测 + 语法/编译（按项目 `.claude/rules/`）。提交 `TASK_DOD_PASSED`（SIMPLE 带完整 `simple_gate`）。

## SIMPLE Gate 与独立复核
- 主 Agent 从实际 diff 重建变更清单（不采信 executor 摘要），记录命令与退出结果，按 `model/policy.yml` 复核风险填 Gate。
- 独立复核：diff 归属可靠后派 `simple-gate-checker` 从 diff 重建 + 实际跑测试，把六字段证据与裁决（PASS|FAIL|INCOMPLETE）追加写入 `done/{范围标签}-{X.Y}.md` 的 `#gate` 段；**主 Agent 以该段为裁决依据（不采信返回文本自述）**。
- gate 段缺失/为空/不可读 → 视为 INCOMPLETE：先新上下文重跑一次；仍失败直接落 `RUN_CR`，不空等。
- Gate 失败 → RUN_CR：不提交有效 `simple_gate`（schema 各字段 const PASS），失败细节记入 done 报告。

### SIMPLE Gate（值必须从实际 diff 计算，不得抄模板）
| 字段 | 取值 | 填写依据 |
|------|------|---------|
| `change_kind` | CODE / DOCS_ONLY / TESTS_ONLY / TESTS_DOCS | 从实际 diff 文件清单推导（证据）：任一生产代码文件 → `CODE`；全部为文档（`docs/`、`*.md`）→ `DOCS_ONLY`；全部为测试（`tests/`、`testing/`、`*Test.*`）→ `TESTS_ONLY`；仅含测试+文档、无生产代码 → `TESTS_DOCS` |
| `changed_file_count` | CODE≤2；test/doc 类型（DOCS_ONLY/TESTS_ONLY/TESTS_DOCS）不限 | 实际 diff 去重文件数（test/doc 类型记录值但不受限）。仅 `CODE` 超 2 → RUN_CR。**change_kind 只放宽这一项，其余门条件不变**。阈值定义于 `model/policy.yml#simple_gate.max_files`，改只改那一处 |
| `scope_check` | PASS | 全部文件在任务工作范围内，无越界 |
| `tests` | PASS | 模块级单测实际执行且通过（记录命令 + 退出码）；纯文档无执行测试记 PASS 并在 evidence 说明 |
| `static_checks` | PASS | 语法/编译/静态检查按项目 rules 通过；未配置记 PASS 并在 evidence 说明 |
| `diff_integrity` | PASS | diff 归属可靠（对照 task change manifest） |
| `risk_signals` | [] | 涉权限/敏感数据/查询性能/并发/契约变化必须列入 → 走完整 CR；文档/测试变更若描述契约语义变化同样标 `CONTRACT`（**change_kind 不影响此项，照常生效**） |
| `evidence_path` | {路径} | done 报告中记录命令与退出结果的证据位置 |

## ⑥ 复验
`VERIFY_PASSED` → DONE；失败 `VERIFY_FAILED{evidence, is_fix_related, cr_round}`——`is_fix_related` 必须确定性判定（失败测试依赖闭包 ∩ 修复 diff ≠ ∅，非主观）。

## 任务推进控制

主 Agent 在任务闭环之间运行 `statectl next --state {S} --config {C} [--task {X.Y}]`，按返回的 `action` 执行，不自行判断配置：

| action | 主 Agent 执行 |
|--------|--------------|
| `CONTINUE` | 当前任务未完成，继续当前闭环 |
| `START_NEXT_TASK` | 从 dev-tasks 依赖图选**下一依赖就绪**任务，提交 `TASK_STARTED{complexity}` 进入下一闭环；不询问 |
| `ASK_NEXT_TASK` | 停止，向用户输出当前任务结果与"是否继续下一个任务"的提示，确认后再 `TASK_STARTED` |
| `ADVANCE_TO_ACCEPT` | 全部任务 DONE，自动提交 `STAGE_COMPLETED`（DEVELOPING → ACCEPTING）进阶段 5；不询问 |
| `ASK_ADVANCE_TO_ACCEPT` | 全部任务 DONE，停在 DEVELOPING，向用户提示"是否进入验收阶段"，确认后才提交 `STAGE_COMPLETED` |
| `WAIT_GATE` | 存在人工门，等待用户裁决 |
| `NONE` | 无推进动作，结束本轮 |

> 推进判定由 `statectl next` 计算并返回动作；本表只消费动作，不承载配置判断。

> **进度派生视图（按需）**：progress.md 不随每次 statectl 变更强制重算——仅人读时生成（`/workflow status`、任务 DONE、阶段切换时跑 `progress_render.py`）。

## 批量提交（statectl batch，可选提速）
确定成功的无分支段可用 `batch` 一次提交（原子回滚）。只放 decision 不需后续动作的事件；`WAIT_USER_APPROVAL` / `FIX_CR_ISSUES` / `RUN_CR` / `REQUEST_DESIGN_REWORK` / `AUTONOMOUS_BLOCK` 单独 transit。

## 全部任务 DONE 后
提交 `STAGE_COMPLETED`（DEVELOPING → ACCEPTING）；`ADVANCE_WORKFLOW` 立即进阶段 5。
