# config — 按 preset 初始化或校验配置

> 处理 `/workflow config [preset]` 时读本文件。Schema 权威见 `model/config.schema.json`；**字段注释来源见 `model/presets.yml` 的 `docs` 字段注释字典**；工具实现见 `adapters/configctl.py`。

## 配置位置与创建方式

路径：`{项目根}.claude/workflow/config.yml`

配置**全显式**（无 profile 运行时概念），由内置预设（`model/presets.yml`）一次性生成：

```bash
configctl.py init --config {项目根}.claude/workflow/config.yml --preset {manual|guarded|autonomous} [--fix-max {0-10}]
```

- 预设档位：`manual`（保守，全等人工）/ `guarded`（自动推进 + 跳 SIMPLE CR + 零问题确认）/ `autonomous`（同 guarded + MINOR 自动修 + 终态清单）
- 生成的配置即普通 YAML，可随意编辑；每个字段的语义来自 `model/presets.yml` 的 `docs` 字段注释字典（改注释只改这里）
- `init` 原子写入（临时文件 + rename），不会产生半写文件

## 命令映射

| 场景 | 命令 |
|------|------|
| 初始化/重建配置 | `configctl.py init --config {路径} --preset {manual\|guarded\|autonomous} [--fix-max {0-10}]` |
| 读取并校验当前配置 | `configctl.py read --config {路径}` |

`preset` 省略默认 `guarded`；`fix-max` 省略默认 `2`。

## 关键规则

- **严格 Schema**：`version` 固定 `2`；域块 `automation`/`cr`/`plan`/`accept`/`rework`/`hotfix` + 可选 `skills` 块结构严格（`automation` 的 `advance_stage`/`advance_task`/`advance_accept`/`advance_summary` 布尔、`limits` 各字段 0-10 整数、`capabilities` 布尔、`cr.levels` 严重度、`cr.review.dimensions` 枚举数组（`implementation/design/security/performance`）、`cr.quality.judge.min_confidence` 0-1、`hotfix.capabilities.simple_skip_cr` 布尔、`skills.discuss`/`skills.arch_rules`/`skills.arch_analyzer` 字符串）。字段缺失、类型错误或存在未知字段 → 命令失败（`SchemaError`），**禁止解释或容忍 Schema 外配置**。
- **外部 skill 映射（`skills` 块，可选）**：workflow 按角色调用项目提供的 skill，缺省用内置默认（`devops-discuss` / `arch-rules` / `arch-analyzer`）。示例：不同语言项目可把 `discuss` 换成自己的讨论 skill，`arch_analyzer` 换成自己的架构分析 skill。主 Agent 从 Automation Context 的 `skills` 段解析，文档占位符 `{skills.discuss}` / `{skills.arch_rules}` / `{skills.arch_analyzer}` 即指此。
- **生效时机**：配置变更后，下一次 `/workflow` 命令加载新值。当前命令内只读一次（强制前置第 1 步），Stage 禁止再次读配置。
- **校验失败提示**：`read` 失败时输出分类错误（缺失文件 / 非对象 / 字段缺失 / 未知字段 / 类型错误），引导执行 `configctl init` 重建。
