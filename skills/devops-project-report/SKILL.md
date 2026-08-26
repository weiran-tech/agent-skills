---
name: devops-project-report
description: 独立项目日报汇总技能。为单个项目生成独立的日报报告，支持 SLS 阈值调整，按时间戳命名输出文件。当用户提到"日报"、"项目报告"、"汇总"、"统计 bugs/req/sentry/sls"、"运行日报"、"生成报告"、"数据统计"、"线上故障统计"、"Sentry 异常统计"、"SLS 接口统计"、"需求统计"时，必须使用此技能。即使没有明确指定技能名称，只要涉及项目数据汇总和报告生成，就应该使用此技能。
compatibility: Python 3.8+, uv
---

# Project Report Skill

为单个项目生成独立的报告，支持多种数据源（云效故障、技术需求、Sentry 异常、SLS 接口统计）。

## 参数说明

| 参数         | 类型   | 必填 | 默认值       | 说明                                                                                                                                                          |
| ------------ | ------ | ---- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project`    | string | 是   | -            | 项目名称，如 "氪金兽"                                                                                                                                         |
| `type`       | string | 否   | 全部启用类型 | 内容类型，逗号分隔。可选值：`req` / `bugs` / `sentry` / `sls` / `slow_log`                                                                                     |
| `type:param` | string | 否   | -            | 覆盖或过滤某类型的配置项，语法见下                                                                                                                            |

### `type:param` 语法

| 形式 | 含义 | 示例 |
| --- | --- | --- |
| `{type}:{key}={value}` | 覆盖该类型**所有**条目的 key | `sls:threshold=75` |
| `{type}[{key}={value}]` | 只保留 key 匹配的条目 | `sls[name=www]` |

- 两者可同时出现，**先过滤（`[]`）再覆盖（`:`）**
  `sls[name=www] sls:threshold=90` = 只跑 www 条目，且阈值改为 90
- 同一 type 可写多个 `[]`，条件之间为 AND
- 过滤后无条目命中：输出 `⏭ 跳过: {type} (过滤条件无匹配条目)`，不报错

## 使用示例

```
# 基础用法
/devops-project-report project=氪金兽

# 指定类型
/devops-project-report project=氪金兽 type=bugs

# 指定日期范围
/devops-project-report project=氪金兽 type=bugs,sentry bugs:range='-10 days'

# 自定义 SLS 阈值
/devops-project-report project=氪金兽 type=sls sls:threshold=75 sls[name=www]

# slow log
/devops-project-report project=氪金兽 type=slow_log slow_log[name=kjs-main]
```

## 执行流程

### Step 0: 前置门禁（涉及 sls / slow_log 时必须先过）

若本次启用的类型包含 `sls` 或 `slow_log`，**在采集任何数据之前**先校验阿里云凭证：

1. **profile 只从环境变量取**

   ```bash
   echo "${ALIYUN_PROFILE:?ALIYUN_PROFILE 未设置}"
   ```

   `ALIYUN_PROFILE` 未设置时：输出下面这段提示并**终止整个流程**，不要继续跑云效/Sentry，
   也**不要**替用户从 `aliyun configure list` 里挑一个 profile：

   ```
   ❌ 环境变量 ALIYUN_PROFILE 未设置，无法采集 sls / slow_log。
      请先执行: export ALIYUN_PROFILE=<profile 名>
      可用 profile: <aliyun configure list 的输出>
      注意: Valid 只表示凭证格式正确，不代表有目标资源的授权。
   ```

2. **授权校验实打一次**

   对本次配置里**每个** sls / slow_log 条目的目标资源各打一次最小查询
   （由子技能脚本自动完成，exit 2 即失败）。任一条目校验失败：
   - 记录该条目的失败原因与修复指引
   - 该条目标记为失败，**不再重试、不换 profile 试**
   - 其余条目与其他类型继续执行

> 为什么必须实打：`aliyun configure list` 只校验凭证格式。实测两个 profile 均显示
> `Valid`，但一个无 SLS 权限、一个 AccessKey 已失效 —— 只看 `Valid` 会一路跑到 401。

### Step 1: 读取配置文件

使用 Read 工具读取项目配置文件：
- `projects/{项目名}/config.yaml` - 项目独立配置(标准布局:`<仓库根>/projects/<项目名>/config.yaml`)
- 根据类型读取默认配置项

**配置过滤规则**：
1. 根据 `project` 参数读取对应的项目配置文件
2. 若传入 `type` 参数，只保留指定的类型；否则使用**所有非空**的模块（只要 sentry/sls 配置非空就执行）
3. 若传入 `type:param` 参数，根据参数替换对应类型的配置

### Step 2: 数据采集映射

根据过滤后的类型，依次调用对应的技能收集数据：

| 类型     | 标题       | 技能调用                                                                              | 特殊处理                           |
| -------- | ---------- | ------------------------------------------------------------------------------------- | ---------------------------------- |
| bugs     | 线上故障   | `/devops-yunxiao-bug-stats space_id={space_id} range={range}`                                | —                                  |
| req      | 需求统计   | `/devops-yunxiao-req-stats space_id={space_id} range={range}`                                | —                                  |
| sentry   | Sentry异常 | 按分组逐组调用 `/devops-sentry-exception projects={projects} title={项目名}-{分组名} period={sentry.period}` | 多分组循环执行                     |
| sls      | 高频接口   | `/devops-aliyun-sls-stats {sls 段落配置, 除 name 参数外, 所有参数均透传}`                    | 每条配置独立执行，为空则跳过该条目 |
| slow_log | SQL慢日志  | `/devops-aliyun-sql-slow-log {slow_log 段落配置, 除 name 参数外, 所有参数均透传}`            | 每条配置独立执行，为空则跳过该条目 |



### Step 2.5: 进度反馈与耗时统计

执行每个数据源时，实时输出阶段化进度信息：

```
[1/5] 查询线上故障统计... ✓ 完成 ({耗时}ms) - 共 {N} 个故障，{N} 个未解决
[2/5] 查询需求生命周期统计... ✓ 完成 ({耗时}ms) - 共 {N} 个工作项，{N} 个需求
[3/5] 查询 Sentry 异常统计... ✓ 完成 ({耗时}ms) - {分组}: {N} 个 HIGH; ...
[4/5] 查询 SLS 接口高频统计... ✗ 权限校验失败 ({耗时}ms) - {profile} 无 log:GetLogStoreLogs
[5/5] 查询 SQL 慢日志统计... ✓ 完成 ({耗时}ms) - {N} 个 SQLHash，TOP1 {N}ms
```

**每条进度包含：**
- 序号/总数、名称
- 结果状态：✓ 成功 / ✗ 无数据 / ⚠ 部分失败
- 耗时（毫秒）
- 关键指标摘要（如未解决数、总事件数、接口数等）

**耗时采集方式（强制）**

macOS 的 BSD `date` 不支持 `%N`，用 python3 取毫秒：

```bash
_t0=$(python3 -c 'import time;print(int(time.time()*1000))')
# ... 执行查询 ...
echo "耗时: $(( $(python3 -c 'import time;print(int(time.time()*1000))') - _t0 ))ms"
```

> ⚠️ **禁止填写估算耗时。** 未实际计时的步骤，进度行与 execution.log 中一律写
> `耗时: 未计时`；Summary 的 `总耗时` 若无真实数据则整项省略。
> 本文档中所有示例耗时均为占位，**不得照抄进报告**。

### Step 2.6: 跳过低配模块

若配置文件中某模块为空，需显式提示并跳过：

```
⏭ 跳过模块: bugs (space_id 未配置)
⏭ 跳过模块: req (range 未配置)
⏭ 跳过模块: sentry (配置为空)
```

若**全部模块都被跳过**，输出 `"所有模块均未配置，无法生成报告"` 并终止。

### Step 3: 生成报告文件

**输出目录**：`projects/{project}/QA/{YYYY-MM-DD}/`

- 目录不存在则创建；**已存在则保留**，只覆盖本次执行实际涉及的类型文件
- `Summary.md` 与 `execution.log` 每次重写

> 🚫 **禁止 `rm -rf` 输出目录。**
> 按 `type` 补采是常规操作（例如权限修复后重跑 `type=sls`）。若先删目录，
> 会连带删掉本次未请求的其他类型上次生成的文件 —— 这与「未请求的类型不生成文件」
> 叠加就是静默丢数据。
>
> 补采时 `Summary.md` 必须标注每个类型的数据来自本次采集还是沿用上次，
> 沿用的附上次采集时间，例如：`| 线上故障 | 当月 | ♻️ 沿用 2026-08-25 10:49 | ... |`

**输出规则**：每种数据采集类型独立保存为一个 `.md` 文件

| 文件            | 内容                                |
| --------------- | ----------------------------------- |
| `线上故障.md`   | 线上故障统计数据                    |
| `需求统计.md`   | 需求统计数据                        |
| `Sentry异常.md` | Sentry 异常统计（按分组输出小节）   |
| `高频接口.md`   | 接口高频统计（每个 name 一个小节）  |
| `SQL慢日志.md`  | slow log 统计（每个 name 一个小节） |

**文件名格式示例**：`projects/{project}/QA/{YYYY-MM-DD}/线上故障.md`

**文件内容格式**：各文件仅包含对应类型的标题与数据，不合并其他类型。

```markdown
# {项目名} - {date} — 线上故障
{bugs 结果；未采集则填"（本次未采集）"}
```

```markdown
# {项目名} - {date} — 需求统计
{req 结果；未采集则填"（本次未采集）"}
```

```markdown
# {项目名} - {date} — Sentry

### {分组名}
{该分组的 Sentry 统计结果}
```

```markdown
# {项目名} - {date} — 接口高频统计

### {name}
{该 name 的 SLS 统计结果}
```

```markdown
# {项目名} - {date} — slow log

### {name}
{该 name 的 slow log 统计结果}
```

**异常处理**：
- 若某类型数据获取失败，对应文件内容为"数据获取失败"
- SLS 配置中若 `project` 或 `logstore` 为空，跳过该条目并输出 `⏭ 跳过: {name} (缺少必要配置)`
- 如果某类型未在当前执行中被请求，则不生成对应文件

### Step 4: 生成汇总面板

所有报告文件生成完毕后，在终端输出一个统一的汇总 Markdown 表格, 并将概览保存到：

`projects/{project}/QA/{YYYY-MM-DD}/Summary.md`



```markdown
## 📊 {项目名} 日报汇总 — {date}

| 数据源      | 窗口      | 状态 | 关键指标                              |
| ----------- | --------- | ---- | ------------------------------------- |
| 线上故障    | {range}   | ✅    | {N} 未解决 · 新建 {N} · 关闭 {N}      |
| 需求统计    | {range}   | ✅    | 积压 {N} · 新建 {N} · 关闭 {N}        |
| Sentry 异常 | {period}  | ✅    | {N} HIGH · 累计 {N} 事件              |
| SLS 接口    | {days} 天 | ✅    | {name}({N} 接口) · ...                |
| SQL 慢日志  | {days} 天 | ✅    | {N} 个 SQLHash · TOP1 {N}ms           |

> 报告路径: projects/{project}/QA/{YYYY-MM-DD}/
> 成功: {N}/{N} | 跳过: {N} | 失败: {N}
```

> ⚠️ **窗口列必填。** 各数据源默认窗口并不一致（云效按 `range`、SLS/慢日志按 `days`、
> Sentry 按 `period`），并排展示却不标注会被读成同一口径。

若某数据源存在严重问题（HIGH 优先级的 Sentry issue ≥ 10 或 SQL 最大耗时 > 5s），在表格后用警告框标注：

```markdown
> ⚠️ **关注:** {项目}-{issue} {简述}超 {N} 事件
```

### Step 5: 写执行日志

在输出目录下同步写入 `execution.log`（纯文本），记录完整执行轨迹：

```
========================================
{项目名} 报告生成 — {YYYY-MM-DD HH:MM:SS}
========================================
配置: projects/{项目名}/config.yaml
组织: {organization_id}
日期范围解析: "{range 原文}" -> label={label}, {start_iso} ~ {end_iso}
启用模块: {本次实际执行的 type 列表}
ALIYUN_PROFILE: {profile}（sls/slow_log 门禁已通过）

[1/N] 线上故障
  space_id: {space_id}
  range: {range}
  查询方式: search_workitems + advancedConditions (perPage=0 计数 / 200 明细)
  ✓ 未解决: {N} (耗时: {耗时}ms)
  ✓ {label}创建: {N}
  ✓ {label}关闭: {N}
  状态分布: {状态}: {N} / ...
  优先级分布: {优先级}: {N} / ...
  负责人 TOP3: {姓名} {N} / ...

[2/N] 需求统计
  space_id: {space_id}
  range: {range}
  ✓ 未评审(待处理): 产品类 {N}, 技术类 {N}
  ✓ 待人工评审: 产品类 {N}, 技术类 {N}
  ✓ {label}创建: 产品类 {N}, 技术类 {N}
  ✓ {label}关闭: 产品类 {N}, 技术类 {N}   [口径: status IN (100014, 141230)]
  ✓ 已评审待计划: 产品类 {N}, 技术类 {N}
  共 {N} 次 MCP 调用 (耗时: {耗时}ms)

[3/N] Sentry 异常统计
  org: {slug} | regionUrl: {regionUrl}
  查询: is:unresolved, sort=freq, period={period}, threshold={threshold}
  分组 1/N: {分组名} — 匹配 {N} 个项目
    {project}  ✓ {N} issue  累计 {N}  TOP {N}
    {project}  ✗ 无 issue
    小计: HIGH {N} ({N} 事件) / MEDIUM {N} ({N}) / LOW {N} ({N})
  ✓ 合计: {N} issue | HIGH {N} / MEDIUM {N} / LOW {N} | 总事件 {N} (耗时: {耗时}ms)
  采样说明: {是否触发 limit 截断、是否做了 timesSeen 下探}

[4/N] SLS 接口高频统计
  profile: {ALIYUN_PROFILE}
  [{name}] host={host}, project={project}, logstore={logstore}, days={days}, threshold={threshold}
    ✓ 返回: {N} 个接口 (耗时: {耗时}ms) | 总 PV: {N}
    或
    ✗ 权限校验失败 (exit 2): {原始错误}
      原因: {分类结果} | 修复: {指引}

[5/N] SQL 慢日志统计
  profile: {ALIYUN_PROFILE}
  [{name}] instance={instance-id}, db={db-name}, threshold={max-time-threshold}ms, days={days}
    ✓ 返回: {N} 个 SQLHash (耗时: {耗时}ms) | 原始记录: {N} 条
    TOP1: {hash} ({N}ms, {N} 次)

----------------------------------------
汇总: 生成文件 {N} 个 + Summary.md + execution.log
成功: {N}/{N} | 跳过: {N} | 失败: {N}
总耗时: {真实值，未计时则省略此行}
========================================
```

执行日志字段要求：
- 每条查询记录**参数**（source_id, range, threshold, limit, profile 等）、**耗时**、**返回结果数**
- 失败时记录**原始错误 + 分类结果 + 修复指引**三者，不要只写"失败"
- 跳过时记录原因（如 "space_id 缺失"、"过滤条件无匹配条目"）
- 补采场景标注哪些类型沿用上次结果
- **上方模板中的 `{...}` 全是占位符，必须替换为真实值；无真实值的字段写「未计时」/「无数据」，不得编造**

## 项目配置文件结构

每个项目在 `projects/` 目录下有独立的子目录,内含 `config.yaml`：

```
projects/<项目名>/config.yaml
projects/<项目名>/QA/<日期>/     # 日报历史落点
projects/<项目名>/需求/          # 需求原始文档
projects/<项目名>/看板/          # 周会看板截图
```

```yaml
name: 项目名称
space_id: 云效项目 space_id

req:
  range: 当月          # 云效时间窗口
bugs:
  range: 当月

# Sentry
sentry:
  period: 30d          # 查询窗口: 24h / 7d / 14d / 30d / 90d
  groups:              # 分组名 -> 项目模式列表
    分组名:
      - 项目模式1       # `*` 通配；`_` 与 `-` 不等价，需要都覆盖就写两条
      - 项目模式2

# SLS
sls:
  - name: domain       # 仅用于报告分节标题，不透传给子技能
    host: domain.com
    project: sls-project
    logstore: logstore-name
    region: cn-hangzhou
    threshold: 50
    days: 7

# RDS 慢日志
slow_log:
  - name: domain       # 仅用于报告分节标题，不透传给子技能
    instance-id: instance-id
    db-name: db_name
    region: cn-hangzhou
    max-time-threshold: 500
    days: 7            # 必填：东八区下缺省值会返回空数据
```

**关于凭证**

配置文件里**不放** aliyun profile。profile 一律由环境变量 `ALIYUN_PROFILE` 提供
（见 Step 0），避免凭证选择被写死在仓库里、也避免不同机器上 profile 名不一致。

**判空规则**

| 模块 | 判定为「未配置、跳过」的条件 |
| --- | --- |
| `bugs` / `req` | 缺 `space_id` 或缺 `range` |
| `sentry` | `sentry.groups` 缺失或为空 |
| `sls` / `slow_log` | 列表为空；单条目缺 `project`/`logstore`（sls）或 `instance-id`（slow_log）则跳过该条目 |

> `test_repos` 由 `devops-yunxiao-testcase-*` 系列技能消费，**本技能不读取**。

## 输出约定

1. 使用 Write 工具写入报告文件，每种类型独立保存为一个文件
2. 返回所有生成的文件路径列表
3. 报告文件使用 UTF-8 编码
