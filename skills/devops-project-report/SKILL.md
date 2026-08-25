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
| `type`       | string | 否   | 全部启用类型 | 内容类型，逗号分隔，如 "req,bugs,sentry,sls,sql"                                                                                                              |
| `type:param` | string | 否   | 灵活参数     | 替换不同类型的参数，如 "sls:threshold" 会覆盖掉项目配置中 sls 中的 threshold 参数, sls[host=host.com] 会搜索项目配置中 sls 中的 host 参数 = 'host.com' 的条目 |

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
| sentry   | Sentry异常 | 按分组逐组调用 `/devops-sentry-exception projects={projects} title={项目名}-{分组名}` | 多分组循环执行                     |
| sls      | 高频接口   | `/devops-aliyun-sls-stats {sls 段落配置, 除 name 参数外, 所有参数均透传}`                    | 每条配置独立执行，为空则跳过该条目 |
| slow_log | SQL慢日志  | `/devops-aliyun-sql-slow-log {slow_log 段落配置, 除 name 参数外, 所有参数均透传}`            | 每条配置独立执行，为空则跳过该条目 |



### Step 2.5: 进度反馈与耗时统计

执行每个数据源时，实时输出阶段化进度信息：

```
[1/5] 查询线上故障统计... ✓ 完成 (120ms) - 共 50 个故障，21 个未解决
[2/5] 查询需求生命周期统计... ✓ 完成 (95ms) - 共 258 个工作项，146 个需求
[3/5] 查询 Sentry 异常统计... ✓ 完成 (3200ms) - 前端(kejinshou-nuxt-h5): 15 个 HIGH; Java(kjs_product): 3 个问题; ...
[4/5] 查询 SLS 接口高频统计... ✓ 完成 (2340ms) - www(10 个接口), api(7 个接口), m(静态资源为主)
[5/5] 查询 SQL 慢日志统计... ✗ 无数据 (kjs-notify 无慢 SQL，其余 2 个实例共 5 个 SQLHash)
```

**每条进度包含：**
- 序号/总数、名称
- 结果状态：✓ 成功 / ✗ 无数据 / ⚠ 部分失败
- 耗时（毫秒）
- 关键指标摘要（如未解决数、总事件数、接口数等）

### Step 2.6: 跳过低配模块

若配置文件中某模块为空，需显式提示并跳过：

```
⏭ 跳过模块: bugs (space_id 未配置)
⏭ 跳过模块: req (range 未配置)
⏭ 跳过模块: sentry (配置为空)
```

若**全部模块都被跳过**，输出 `"所有模块均未配置，无法生成报告"` 并终止。

### Step 3: 生成报告文件

**输出目录**：`projects/{project}/QA/{MM-DD-HH-MM}/`（不存在则自动创建，时间戳使用当前执行时间，精确到分钟）

**输出规则**：每种数据采集类型独立保存为一个 `.md` 文件

| 文件            | 内容                                |
| --------------- | ----------------------------------- |
| `线上故障.md`   | 线上故障统计数据                    |
| `需求统计.md`   | 需求统计数据                        |
| `Sentry异常.md` | Sentry 异常统计（按分组输出小节）   |
| `高频接口.md`   | 接口高频统计（每个 name 一个小节）  |
| `SQL慢日志.md`  | slow log 统计（每个 name 一个小节） |

**文件名格式示例**：`projects/{project}/QA/{MM-DD-HH-MM}/线上故障.md`

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

`projects/{project}/QA/{MM-DD-HH-MM}/Summary.md`



```markdown
## 📊 {项目名} 日报汇总 — {date}

| 数据源      | 状态 | 关键指标                               |
| ----------- | ---- | -------------------------------------- |
| 线上故障    | ✅    | 50 个故障 · 21 未解决 · 10 已修复      |
| 需求统计    | ✅    | 258 工作项 · 146 需求 · 积压 112       |
| Sentry 异常 | ✅    | 14 HIGH · 累计 11M+ 事件               |
| SLS 接口    | ✅    | www(216万PV) · api(360万调用)          |
| SQL 慢日志  | ✅    | kjs-v3(4个SQLHash, TOP1 1.8s) · kjs-im |

> 报告路径: projects/{project}/QA/{MM-DD-HH-MM}/
> 总耗时: 6.5s | 成功: 5/5 | 跳过: 0 | 失败: 0
```

若某数据源存在严重问题（HIGH 优先级的 Sentry issue ≥ 10 或 SQL 最大耗时 > 5s），在表格后用警告框标注：

```markdown
> ⚠️ **关注:** kejinshou-vue-h5 imSocket-chat WebSocket 断开超 370 万事件
```

### Step 5: 写执行日志

在输出目录下同步写入 `execution.log`（纯文本），记录完整执行轨迹：

```
========================================
{项目名} 报告生成 — 2026-05-12 18:42:00
========================================

[1/5] 线上故障
  space_id: 6258e4a36f6aff30b539406206
  range: 当月
  ✓ 返回: 50 条故障记录 (耗时: 120ms)
  未解决: 21 个 (待确认 2, 处理中 9, 其他 10)
  已修复: 10 个
  暂不修复: 1 个
  推迟修复: 20 个

[2/5] 需求统计
  space_id: 6258e4a36f6aff30b539406206
  range: 当月
  ✓ 返回: 258 个工作项 (耗时: 95ms)
  产品类需求: 146 (待处理 112, 已完成 12)
  技术类需求: 54 (待处理 42, 已完成 4)

[3/5] Sentry 异常统计
  分组 1/3: 前端 - kejinshou-nuxt-h5
    projects: [kejinshou-nuxt-h5, kejinshou-nuxt-h5-node]
    ✓ 返回: 100 个 issue (耗时: 1200ms)
    HIGH: 9 个 (累计 ~5.5M 事件)
    MEDIUM: 0
    LOW (<100): 91 个 (计入汇总)
  分组 2/3: Java
    ...
  ✓ 分组合计: 168 个 issue

[4/5] SLS 接口高频统计
  [www] host=www.kejinshou.com, days=30, threshold=70
    ✓ 返回: 10 个接口 (耗时: 2340ms)
    总 PV: 21,585,330
  [api] format=mwcs, days=30, threshold=70
    ✓ 返回: 7 个接口 (耗时: 1100ms)
    总 PV: 138,687,720
  [m] host=m.kejinshou.com, days=30, threshold=70
    ✓ 返回: 静态资源为主 (耗时: 980ms)

[5/5] SQL 慢日志统计
  [kjs-v3] instance=rm-bp10to8bxux58854c, db=kjs_v3, threshold=500ms
    ✓ 返回: 4 个 SQLHash (耗时: 1500ms)
    TOP1: 30d0258c (1,889ms, 1 次)
  [kjs-notify] instance=rm-bp10to8bxux58854c, db=kjs_notify, threshold=500ms
    ✗ 返回: 无数据 (耗时: 300ms)
  [kjs-im] instance=rm-bp1r8sln5j20oyvk5, db=im_v1, threshold=500ms
    ✓ 返回: 1 个 SQLHash (耗时: 800ms)
    TOP1: ae28a3ea (1,159ms, 19 次)

----------------------------------------
汇总: 生成文件 5 个 + 执行日志 1 个
总耗时: 6.5s
========================================
```

执行日志字段要求：
- 每条查询记录**参数**（source_id, range, threshold, limit 等）、**耗时**、**返回结果数**
- 失败时记录错误原因
- 跳过时记录原因（如 "空间 ID 缺失"）

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

# Sentry 分组配置
sentry:
  分组名:
    - 项目模式1
    - 项目模式2

# SLS 配置
sls:
  - name: domain
    host: domain.com
    project: sls-project
    logstore: logstore-name
    region: cn-hangzhou
    threshold: 50

slow_log:
  - name: domain
    instance-id: instance-id
```

## 输出约定

1. 使用 Write 工具写入报告文件，每种类型独立保存为一个文件
2. 返回所有生成的文件路径列表
3. 报告文件使用 UTF-8 编码
