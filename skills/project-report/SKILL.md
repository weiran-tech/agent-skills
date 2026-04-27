---
name: project-report
description: 独立项目日报汇总技能。为单个项目生成独立的日报报告，支持 SLS 阈值调整，按时间戳命名输出文件。当用户提到"日报"、"项目报告"、"汇总"、"统计 bugs/req/sentry/sls"、"运行日报"、"生成报告"、"数据统计"、"线上故障统计"、"Sentry 异常统计"、"SLS 接口统计"、"需求统计"时，必须使用此技能。即使没有明确指定技能名称，只要涉及项目数据汇总和报告生成，就应该使用此技能。
compatibility: Python 3.8+, uv
---

# Project Report Skill

为单个项目生成独立的报告，支持多种数据源（云效故障、技术需求、Sentry 异常、SLS 接口统计）。

## 核心特性

1. **项目独立**：每个项目生成独立的报告文件，不再输出多项目合并报告
2. **配置独立**：每个项目有独立的 YAML 配置文件 `config/{项目名}.yaml`，可自定义 Sentry 分组、SLS 配置等
3. **智能模块识别**：未指定模块时自动使用**所有非空**的模块（只要 sentry/sls 配置非空就执行）
4. **指定模块输出**：传入 types 参数时只输出指定的非空模块
5. **SLS 阈值可调**：支持自定义 SLS 统计的阈值参数
6. **时间戳命名**：输出文件按 `{project}-{yyyy-mm-dd-hh-mm}.md` 格式命名

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `project` | string | 是 | - | 项目名称，如 "氪金兽" |
| `date` | string | 否 | 今天 | 报告日期，格式 YYYY-MM-DD |
| `types` | string | 否 | 全部启用类型 | 内容类型，逗号分隔，如 "bugs,req,sentry,sls" |
| `sls_threshold` | number | 否 | 100 | SLS 接口统计的最小调用次数阈值 |
| `sls_percentile` | number | 否 | 80 | SLS 帕累托分析百分比阈值 (0-100) |

## 使用示例

```
# 基础用法
/project-report project=氪金兽

# 指定日期和类型
/project-daily-report project=氪金联盟 date=2026-04-25 types=bugs,sentry

# 自定义 SLS 阈值
/project-daily-report project=聚单云 sls_threshold=50 sls_percentile=90
```

## 执行流程

### Step 1: 读取配置文件

使用 Read 工具读取项目配置文件：
- `config/{项目名}.yaml` - 项目独立配置

**内容类型定义（内置）**：
| 类型 | 技能 | 标题 |
|------|------|------|
| bugs | `/yunxiao-bug-stats` | 线上故障 |
| req | `/yunxiao-req-stats` | 技术需求 |
| sentry | `/sentry-exception-output` | Sentry |
| sls | `/aliyun-sls-stats` | 接口高频统计 |

**配置过滤规则**：
1. 根据 `project` 参数读取对应的项目配置文件
2. 若传入 `types` 参数，只保留指定的类型；否则使用**所有非空**的模块（只要 sentry/sls 配置非空就执行）
3. bugs 和 req 类型始终执行（只要在 types 中指定或未指定时默认执行）
4. 对该项目，跳过 sentry/sls 字段为空的对应类型

### Step 2: 执行数据采集

根据过滤后的类型，依次调用对应的技能收集数据：

| 类型 | 技能调用 | 说明 |
|------|----------|------|
| bugs | `/yunxiao-bug-stats space_id={space_id} date={date}` | 云效线上故障 |
| req | `/yunxiao-req-stats space_id={space_id} date={date}` | 云效技术需求 |
| sentry | `/sentry-exception-output projects={projects} title={title}` | 按分组调用，title 格式: `{项目名}-{分组名}` |
| sls | `/aliyun-sls-stats project={project} logstore={logstore} region={region} host={host}` | 按每个 SLS 条目调用 |

**SLS 特殊参数**：
- 若传入 `sls_threshold`，添加参数 `threshold={sls_threshold}`
- 若传入 `sls_percentile`，添加参数 `percentile={sls_percentile}`

### Step 3: 生成报告文件

**输出目录**：`report/project/`（不存在则自动创建）

**文件名格式**：`{project}-{yyyy-mm-dd-hh-mm}.md`

**文件内容格式**：
```markdown
# {项目名} - {date}

## 线上故障
{bugs 结果；未采集则填"（本次未采集）"}

## 技术需求
{req 结果；未采集则填"（本次未采集）"}

## Sentry
{sentry 结果，按分组输出小节；未采集则填"（本次未采集）"}

### {分组名}
{该分组的 Sentry 统计结果}

## 接口高频统计
{sls 结果，每个 host 一个小节；未采集则填"（本次未采集）"}

### {host}
{该 host 的 SLS 统计结果}
```

**异常处理**：
- 若某类型数据获取失败，对应部分填写"数据获取失败"
- SLS 配置中若 `project` 或 `logstore` 为 `~`，跳过该条目

## 项目配置文件结构

每个项目在 `config/` 目录下有独立的 YAML 配置文件：

```yaml
name: 项目名称
enabled: true
space_id: 云效项目 space_id

# Sentry 分组配置
sentry:
  分组名:
    - 项目模式1
    - 项目模式2

# SLS 配置
sls:
  - host: domain.com
    project: sls-project
    logstore: logstore-name
    region: cn-hangzhou
```

## 输出约定

1. 使用 Write 工具写入报告文件
2. 只返回最终生成的文件路径，不输出中间结果
3. 报告文件使用 UTF-8 编码
4. 时间戳使用当前执行时间（精确到分钟）
