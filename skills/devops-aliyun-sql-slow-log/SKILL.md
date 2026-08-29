---
name: devops-aliyun-sql-slow-log
description: 查询阿里云 RDS 数据库慢 SQL 并生成 Markdown 统计报告。按 SQLHash 分组聚合，支持最大耗时过滤、多表扫描分析、执行频率排行。当用户提到"慢SQL"、"慢查询"、"RDS 慢日志"、"数据库慢SQL"、"获取 slow log"时触发。
---
# 阿里云 RDS 慢 SQL 统计

基于帕累托分析法输出慢 SQL 排行榜，按 SQLHash 分组聚合统计，自动识别高频慢查询和全表扫描嫌疑语句。

## 前置检查（强制门禁）

### 1. profile 只从环境变量取

aliyun-cli profile **必须**由环境变量 `ALIYUN_PROFILE` 指定，脚本不猜测、不回退到默认 profile：

```bash
export ALIYUN_PROFILE=<profile 名>
```

未设置时脚本直接退出（exit 2）并列出可用 profile。**不要替用户挑一个 profile 重试。**

### 2. 授权校验必须实打一次

`aliyun configure list` **只能确认凭证格式，不能确认授权**。实测两个 profile 均显示 `Valid`，
但一个无 SLS 权限、一个 AccessKey 已失效 —— 仅凭 `Valid` 继续执行会拿到 401。

脚本在执行统计查询前会自动对目标实例打一次最小慢日志查询（`--page-size 30`，1 小时窗口）。
**校验不通过即终止，不进入下一步。**

失败时按错误分类给出修复指引：

| 错误信息                                               | 含义                   | 修复                                                                 |
| ------------------------------------------------------ | ---------------------- | -------------------------------------------------------------------- |
| `denied by sts or ram` / `NoPermission`            | 凭证有效，无授权       | 补`AliyunRDSReadOnlyAccess`，或授予 `rds:DescribeSlowLogRecords` |
| `AccessKeyId not found`                              | AccessKey 已删除/轮换  | `aliyun configure --profile $ALIYUN_PROFILE`                       |
| `InvalidAccessKeySecret` / `SignatureDoesNotMatch` | Secret 不匹配          | `aliyun configure --profile $ALIYUN_PROFILE`                       |
| `InvalidDBInstanceId` / `NotFound`                 | 实例 ID 或 region 不对 | 核对 config.yaml                                                     |
| plugin`not found`                                    | rds 插件未装           | `aliyun plugin install --names aliyun-cli-rds && hash -r`          |

> ⚠️ 校验失败时**不要重试、不要换 profile 试**，直接把上表对应的修复指引写进报告。

### 3. rds 插件

```bash
aliyun plugin install --names aliyun-cli-rds
hash -r
```

## 命令参数

| 参数                     | 必填 | 默认值          | 说明                              |
| ------------------------ | ---- | --------------- | --------------------------------- |
| `--instance-id`        | 是   | -               | RDS 实例 ID                       |
| `--region`             | 否   | cn-hangzhou     | 地域 ID                           |
| `--db-name`            | 否   | -               | 数据库名过滤                      |
| `--days`               | 否   | 7               | 统计天数                          |
| `--max-time-threshold` | 否   | 0               | 仅显示最大耗时 >= 此值(ms) 的 SQL |
| `--page-size`          | 否   | 100             | 每页记录数（30~100）              |
| `--top-N`              | 否   | 20              | 输出排名前 N 个不同 SQL           |
| `--title`              | 否   | 慢 SQL 统计报告 | 报告标题                          |
| `--dry-run`            | 否   | false           | 仅打印 API 调用信息，不执行       |

**⚠️ 时区注意：** 脚本内部使用本地时区计算时间戳，但阿里云 API 需要 UTC 格式。东八区环境下 `--days` 非 1 的默认值可能返回空数据，建议始终显式指定 `--days` 参数（如 `--days 7`）。

## 使用示例

### 示例 1: 查看最近 7 天慢 SQL TOP 20

```bash
uv run .claude/skills/aliyun-sql-slow-log/scripts/stats.py analyze \
  --instance-id rm-bp15v1z1h4qh9hw44 \
  --region cn-hangzhou
```

### 示例 2: 指定数据库 + 只查慢于 1 秒的 SQL

```bash
uv run .claude/skills/aliyun-sql-slow-log/scripts/stats.py analyze \
  --instance-id rm-bp15v1z1h4qh9hw44 \
  --db-name kr_v1 \
  --max-time-threshold 1000 \
  --days 7 \
  --top-N 30
```

### 示例 3: 自定义报告标题

```bash
uv run .claude/skills/aliyun-sql-slow-log/scripts/stats.py analyze \
  --instance-id rm-bp15v1z1h4qh9hw44 \
  --days 1 \
  --title "生产环境昨日慢 SQL 分析"
```

### 示例 4: Dry Run 预览

```bash
uv run .claude/skills/aliyun-sql-slow-log/scripts/stats.py analyze \
  --instance-id rm-bp15v1z1h4qh9hw44 \
  --days 3 \
  --dry-run
```

## 执行流程

1. **参数校验**: 验证必填参数
2. **时间计算**: 根据 `--days` 计算 UTC 时间戳范围
3. **API 调用**: 调用 `describe-slow-log-records` 获取原始慢 SQL 记录
4. **SQLHash 聚合**: 按 SQLHash 分组，计算最大耗时、出现次数、平均扫描行数等
5. **过滤排序**: 按最大耗时降序，应用阈值过滤
6. **格式化输出**: 以 Markdown 表格形式输出 TOP N 结果及详细 SQL

## 输出示例

```markdown
## 慢 SQL 统计报告 - 2026-05-11

> 统计范围：最近 7 天 | 实例：rm-bp15v1z1h4qh9hw44 (cn-hangzhou)

### TOP 10 最慢 SQL 排行

| 排名 | 最大耗时(ms) | 出现次数 | 累计执行 | 平均扫描行数 | SQLHash  | 数据库 |
| ---- | ------------ | -------- | -------- | ------------ | -------- | ------ |
| 1    | 88,192       | 12       | 275      | 2,336,456    | 59ceebc1 | kr_v1  |
| 2    | 19,414       | 3        | 27       | 2,263,388    | c4f7ce15 | kr_v1  |
| 3    | 9,711        | 3        | 17       | 27,787       | af8f737a | kr_v1  |
...

### 详细信息

[1] Hash: 59ceebc1946afcd872070d96bcb4e415 | 最大耗时: 88,192ms | 出现: 12 次 | 累计执行: 275 次
   SQL: select third_goods_append.*, third_goods.status as kjs_status, ... from third_goods_append left join ... where platform_name = 'KeJinShou' ...

[2] Hash: c4f7ce15afc51a3f59ea20eddd523f44 | 最大耗时: 19,414ms | 出现: 3 次 | 累计执行: 27 次
   SQL: select third_goods_append.*, third_goods.status as yy_status, ... from third_goods_append left join ... where platform_name = 'YY' ...
```

## 报告生成要求

在 project-report 等场景中调用本技能时，需按以下格式输出完整报告：

### 报告结构

每个慢 SQLHash 详情需包含：

1. **基本信息** — Hash、最大耗时、出现次数、累计执行、来源主机、时间范围
2. **SQL 原文** — 截取前 200 字符（去除反引号）+ `...` 省略符
3. **优化建议** — 根据 SQL 特征分析潜在问题，逐条列出可执行的优化方案
4. **优先级判断** — 在汇总中给出 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW 分级

#### 优化建议判定规则

| SQL 特征                                     | 优化方向                    |
| -------------------------------------------- | --------------------------- |
| 多表 JOIN + COUNT + 扫描行数大 (>10万)       | 建索引 / 引入缓存宽表预计算 |
| WHERE 条件列无索引嫌疑                       | 确认字段索引覆盖情况        |
| SELECT * + 大数据量扫描                      | 精确指定查询列 + LIMIT 控制 |
| 锁等待时间长 (LockTimeMS > 0)                | 排查长事务 / 行锁竞争       |
| 全表扫描 (ParseRowCounts >> ReturnRowCounts) | 添加 WHERE 过滤列的复合索引 |

#### 优先级判定

| 条件                                          | 级别      |
| --------------------------------------------- | --------- |
| 最大耗时 > 5s 或 累计执行 > 100 次且耗时 > 2s | 🔴 HIGH   |
| 最大耗时 > 1s 或 扫描行数 > 50万              | 🟡 MEDIUM |
| 最大耗时 > 500ms 但未达 medium 标准           | 🟢 LOW    |

### 报告模板

完整的 Markdown 报告模板：

```markdown
### {项目名}

已采集：近 {days} 天共 {hash_count} 个 SQLHash 存在慢查询，TOP1 最大耗时 **{top_max_ms}ms**

#### {name}
| 排名 | 最大耗时(ms) | 出现次数 | 累计执行 | 平均扫描行数 | SQLHash | 数据库 |
|------|-------------|---------|---------|-------------|---------|--------|
| {row data}

#### 详细信息

**[1] Hash: `{hash}` | 最大耗时: {max_ms}ms | 出现: {count} 次 | 累计执行: {exec} 次**
- 来源主机: `{host_ip}`
- 时间范围: {first_time} ~ {last_time}
- SQL: `{sql_text_snippet}`
- ⚠️ **优化建议:**
  1. {建议1}
  2. {建议2}

---
**汇总**
- 查看地址 : https://rdsnext.console.aliyun.com/{region}/i/{instance-id}/log?selectTab=logDetail
- RDS 实例: `{instance_id}` ({region})
- 过滤条件: max-time-threshold = {threshold}ms
- 统计天数: {days} 天
- 涉及不同 SQLHash 数: {unique_count} 个
- 原始慢 SQL 记录: {total_records} 条
- **优先级判断:**
  - 🔴 HIGH: `{描述}`
  - 🟡 MEDIUM: `{描述}`
```
