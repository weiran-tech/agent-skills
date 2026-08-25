# `/workflow hotfix` — 轻量 Bug 修复（不走 5 阶段状态机）

> 子 agent 调用规范见 `references/protocols/agent-protocol.md`；模板见 `prompts/agents.md`。

## 产物目录约定（强制，产物不落仓库根）

- **{hotfix工单根}** = `{讨论根目录}hotfix/{YYYY-MM-DD}-{主题}/.task/`（`{讨论根目录}` = `docs/discuss/`，见 SKILL.md 目录约定）
- 产物路径（派 executor / reviewer 时，把 prompt 模板中的 `{工单根}` 展开为 `{hotfix工单根}`）：
  - executor done 报告 → `{hotfix工单根}done.md`
  - reviewer 报告 → `{hotfix工单根}review/{维度}.md`（单维度 CR 即 `implementation.md`）

## 流程
```
① 确认问题 → ② 定位根因 → ③ 编码修复 → ④ 校验分叉 → 完成
                        └─ 涉及设计变更 → 升级 /workflow rework
          ④a Gate 通过（能力开 + 证据全 + 非空转）→ 跳过 CR
          ④b 其余 → 单维度 CR →[裁决]→ ⑤ 改写 → 完成
```

1. **确认问题**：业务域 + 影响范围（模块/文件）；记录复现步骤/日志。
2. **定位根因**：读取影响范围代码，输出根因摘要 + 修复方案 + 影响判定。**升级判定（强制）**：需改接口签名/数据模型/跨模块契约/多个不相关模块 → 停止 hotfix，提示升级 `/workflow rework`。
3. **编码修复**：`executor`（`prompts/agents.md`，`{工单根}` 展开为 `{hotfix工单根}`），完成后模块级单测 + 语法/编译检查。done 报告写入 `{hotfix工单根}done.md`。**能力 `hotfix_simple_skip_cr` 开启时**，done.md 追加 `#regression` 段：列改动文件/行 + 覆盖它的回归测试用例/断言行；无回归测试覆盖改动行 = 空转，视为 Gate 失败。
4. **校验分叉（主 Agent 裁决）**：读 done.md 与 `git diff`，按序判定——
   a. **升级判定（恒先）**：需改接口签名/数据模型/跨模块契约/多个不相关模块 → 停止 hotfix，升级 `/workflow rework`（同步骤 2）。
   b. **跳过 CR（特权，须全部满足）**：能力 `hotfix_simple_skip_cr` 开启 且 下方 SIMPLE Gate 有效 且 `#regression` 非空转 → 跳过 `reviewer-implementation`，确认模块级测试 + 语法/编译检查后完成。
   c. **其余 → 单维度 CR**：`reviewer-implementation` 单维度审查（关注修复完整/新引入问题/是否涉及设计层），报告写入 `{hotfix工单根}review/implementation.md`。零问题 → 完成；有问题 → 逐条展示等待裁决。
5. **改写**：approve 后 `executor` 按裁决改，确认测试通过结束。

> **跳过 CR 是特权不是默认**：Gate 不完整/失败/存在风险信号 → 必须走单维度 CR（对齐 fs-2）。

### SIMPLE Gate 判定（hotfix 跳过 CR 前置；主 Agent 自算，全部从实际 diff/证据，不采信自述）

| 字段 | 判定来源 | 通过条件 |
|------|---------|---------|
| change_kind / changed_file_count | `git diff --name-only` 推导 | 阈值对齐 `model/policy.yml#simple_gate.max_files`：CODE ≤ 2；TESTS_ONLY / TESTS_DOCS / DOCS_ONLY 不限 |
| scope_check / diff_integrity | diff 对照步骤 2 根因方案 | 改动文件都在单模块/范围内；diff 与修复方案一致、无无关文件 |
| tests / static_checks | done.md 记录的命令 + 退出码 | 命令实际执行且退出码 0 |
| risk_signals | 主 Agent 读 diff 判定 | 空（权限/敏感数据/查询性能/并发；对齐 `model/policy.yml#complexity` 的 SIMPLE 条件） |
| evidence_path | `{hotfix工单根}done.md` | 文件存在 |
| #regression 非空转 | 主 Agent 读测试文件对照 diff | 改动行确有回归测试/断言覆盖；无覆盖 = 空转 = 失败 |

> 与需求流程区别：无持久化状态机、无 design-baseline；CR 为条件门（能力 `hotfix_simple_skip_cr` 开启且 SIMPLE Gate 通过时可跳过）。所有 agent prompt 含 Bash 约束；编码与审查分两轮不共享上下文。
