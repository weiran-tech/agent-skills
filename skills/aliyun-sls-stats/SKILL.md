---
name: aliyun-sls-stats
description: 查询阿里云日志服务（SLS）统计数据并输出 Markdown 表格。支持多种日志格式：nginx, apisix, k8s-ingress, spring-boot, custom。当用户提到"日志统计"、"SLS统计"、"接口流量"、"请求统计"、"日志分析"时触发。
---

# 阿里云 SLS 日志统计

支持多种日志格式的 SLS 统计分析，基于帕累托分析法输出占前 50% 流量的接口列表。

## 支持的日志格式

| 格式名称    | 描述                          | URI 字段     | 响应时间字段           |
| ----------- | ----------------------------- | ------------ | ---------------------- |
| nginx       | Nginx 标准日志格式            | request_uri  | upstream_response_time |
| mwcs        | Mogu 网关日志格式             | request_path | upstream_response_time |
| apisix      | Apache APISIX 日志格式        | request_uri  | upstream_response_time |
| k8s-ingress | Kubernetes Ingress Nginx 格式 | request_uri  | request_length         |
| spring-boot | Spring Boot 应用日志          | uri          | duration               |
| custom      | 自定义日志格式                | 可配置       | 可配置                 |

## 前置检查

先确认 aliyun-cli 已配置：

```bash
aliyun configure list
```

如果未配置，提示用户执行 `aliyun configure` 完成 AccessKey 配置。

## 命令参数

### 通用参数

| 参数          | 必填 | 默认值       | 说明                                                          |
| ------------- | ---- | ------------ | ------------------------------------------------------------- |
| `--project`   | 是   | -            | SLS Project 名称                                              |
| `--logstore`  | 是   | -            | SLS Logstore 名称                                             |
| `--region`    | 否   | cn-hangzhou  | SLS 地域                                                      |
| `--host`      | 否   | -            | Hostname 过滤条件                                             |
| `--format`    | 否   | nginx        | 日志格式：nginx / apisix / k8s-ingress / spring-boot / custom |
| `--days`      | 否   | 7            | 统计天数                                                      |
| `--threshold` | 否   | 50           | 帕累托分析阈值（%）                                           |
| `--title`     | 否   | 接口流量分布 | 报告标题                                                      |
| `--dry-run`   | 否   | false        | 仅打印查询语句，不执行                                        |

### Custom 格式专属参数

| 参数           | 必填 | 说明                                                 |
| -------------- | ---- | ---------------------------------------------------- |
| `--field-uri`  | 否   | 自定义 URI 字段名（默认: request_uri）               |
| `--field-time` | 否   | 自定义响应时间字段名（默认: upstream_response_time） |

## 使用示例

### 示例 1: Nginx 标准格式（默认）

```bash
uv run .claude/skills/aliyun-sls-stats/scripts/stats.py analyze \
  --project my-project \
  --logstore nginx-log \
  --host api.example.com \
  --days 7 \
  --threshold 50
```

### 示例 2: APISIX 格式

```bash
uv run .claude/skills/aliyun-sls-stats/scripts/stats.py analyze \
  --project my-project \
  --logstore apisix-log \
  --format apisix \
  --days 14 \
  --title "网关接口流量分析"
```

### 示例 3: Spring Boot 应用日志

```bash
uv run .claude/skills/aliyun-sls-stats/scripts/stats.py analyze \
  --project my-project \
  --logstore app-log \
  --format spring-boot \
  --host "*.example.com"
```

### 示例 4: 自定义字段格式

```bash
uv run .claude/skills/aliyun-sls-stats/scripts/stats.py analyze \
  --project my-project \
  --logstore custom-log \
  --format custom \
  --field-uri path \
  --field-time latency \
  --days 3
```

### 示例 5: 仅预览查询语句（Dry Run）

```bash
uv run .claude/skills/aliyun-sls-stats/scripts/stats.py analyze \
  --project my-project \
  --logstore nginx-log \
  --dry-run
```

### 示例 6: 列出支持的所有日志格式

```bash
uv run .claude/skills/aliyun-sls-stats/scripts/stats.py list-formats
```

## 执行流程

1. **参数校验**: 验证必填参数和日志格式配置
2. **时间计算**: 根据 `--days` 计算 Unix 时间戳范围
3. **查询构建**: 根据所选日志格式动态生成 SLS SQL 查询
4. **执行查询**: 调用 aliyun-cli 执行 SLS GetLogs API
5. **结果解析**: 解析 JSON 响应并计算统计数据
6. **格式化输出**: 以 Markdown 表格形式输出

## 输出示例

```markdown
## 接口流量分布 - 2026-04-25

> 统计范围：最近 7 天 | 数据来源：SLS (nginx 格式) | 分析方法：帕累托（前50%流量）

| 接口             | PV/天  | 占比   | 累计占比 | 平均响应时间 | 最大响应时间 |
| ---------------- | ------ | ------ | -------- | ------------ | ------------ |
| /api/v1/users    | 12,345 | 15.23% | 15.23%   | 0.45         | 2.34         |
| /api/v1/orders   | 8,901  | 11.78% | 27.01%   | 0.56         | 3.12         |
| /api/v1/products | 6,543  | 8.67%  | 35.68%   | 0.23         | 1.56         |

**汇总**
- 总 PV：198,765
- 上榜接口数：8 个
- 处理日志行数：1,234,567
- 前 50% 流量集中在以上接口
```

## 帕累托分析说明

帕累托原则（80/20 法则）指出：80% 的结果来自 20% 的原因。在接口流量分析中：
- 找出占总流量前 X%（默认 50%）的接口
- 优先优化这些核心接口能获得最大的性能收益
- 支持通过 `--threshold` 参数自定义阈值

## SQL 查询逻辑

自动根据日志格式构建 SQL，核心逻辑：
1. 按 URI 分组统计 PV、平均/最大响应时间
2. 计算每个接口的流量占比
3. 按 PV 降序计算累计占比
4. 使用窗口函数 LAG() 找出刚好超过阈值的临界接口
5. 返回所有累计占比 ≤ 阈值 或临界接口的记录
