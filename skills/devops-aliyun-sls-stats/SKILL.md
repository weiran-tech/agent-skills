---
name: devops-aliyun-sls-stats
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

脚本在执行统计查询前会自动对目标 project/logstore 打一次最小查询（`--line 1`，1 小时窗口）。
**校验不通过即终止，不进入下一步。**

失败时按错误分类给出修复指引：

| 错误信息 | 含义 | 修复 |
| --- | --- | --- |
| `denied by sts or ram, action: log:GetLogStoreLogs` | 凭证有效，无授权 | 补 `AliyunLogReadOnlyAccess`，或对该 project 授予 `log:GetLogStoreLogs` |
| `AccessKeyId not found` | AccessKey 已删除/轮换 | `aliyun configure --profile $ALIYUN_PROFILE` |
| `InvalidAccessKeySecret` / `SignatureDoesNotMatch` | Secret 不匹配 | `aliyun configure --profile $ALIYUN_PROFILE` |
| `ProjectNotExist` / `LogStoreNotExist` | 名称写错 | 核对 config.yaml |

> ⚠️ 校验失败时**不要重试、不要换 profile 试**，直接把上表对应的修复指引写进报告。

## 命令参数

### 通用参数

| 参数          | 必填 | 默认值       | 说明                                                          |
| ------------- | ---- | ------------ | ------------------------------------------------------------- |
| `--project`   | 是   | -            | SLS Project 名称                                              |
| `--logstore`  | 是   | -            | SLS Logstore 名称                                             |
| `--region`    | 否   | cn-hangzhou  | SLS 地域                                                      |
| `--host`      | 否   | ''           | Hostname 过滤条件, 空参数不必进行透传                         |
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

| 接口             | PV/天  | 占比   | 累计占比 | 平均响应时间 | P99响应时间 | 最大响应时间 |
| ---------------- | ------ | ------ | -------- | ------------ | ----------- | ------------ |
| /api/v1/users    | 12,345 | 15.23% | 15.23%   | 0.45         | 0.52        | 2.34         |
| /api/v1/orders   | 8,901  | 11.78% | 27.01%   | 0.56         | 3.10        | 3.12         |
| /api/v1/products | 6,543  | 8.67%  | 35.68%   | 0.23         | 0.29        | 1.56         |

**汇总**
- 总 PV：198,765
- 上榜接口数：8 个
- 处理日志行数：1,234,567
- 前 50% 流量集中在以上接口

**⚠️ 长尾告警（P99 ≥ 500ms 且 P99 ≥ 3× 均值）**
- `/api/v1/orders`：P99 3.10s，均值 0.56s（6× 均值）
```

## P99 约定（为什么要看 P99，不只看均值/最大值）

**均值会被高频快请求掩盖长尾问题**：1 万次请求里 100 次很慢，均值几乎不变，但这 100 次
是真实存在的差体验。**最大值又太敏感**：一次网络抖动、一次 GC 卡顿就能把最大值推到很高，
但那只是极端个例，不代表接口普遍慢。P99（第 99 百分位）是两者之间的平衡点——它回答的是
「99% 的请求有多快，最慢的这 1% 有多慢」，比均值更能反映真实用户体验，比最大值更抗单次抖动。

### 输出列

统计表固定输出三列响应时间：`平均响应时间` / `P99响应时间` / `最大响应时间`。
P99 通过 `APPROX_PERCENTILE(CAST({time_field} AS DOUBLE), 0.99)` 在 SLS 端计算，
与均值、最大值同一次查询取得，不额外增加查询次数。

### 长尾判定规则（固定阈值，禁止臆测）

同时满足以下两个条件才计入「长尾告警」：

| 条件 | 说明 |
| --- | --- |
| P99 ≥ 500ms | 绝对下限，避免把「均值 10ms、P99 15ms」这种健康接口也标红 |
| P99 ≥ 3× 均值 | 相对倍数，只有长尾明显偏离主体分布才算问题 |

两个条件都是脚本里的硬编码常量（`stats.py` 中 `_num` 之后的判定逻辑），不是留给报告
撰写者临场判断的软指标。**满足才输出「长尾告警」区块，不满足就不提 P99 异常** ——
不要仅凭「最大响应时间看着很高」就在报告里下"需要优化"的结论；那正是均值/最大值会
误导人的地方，先看 P99 有没有真的抬升。

### 报告撰写约定

- 报告中提到「响应时间偏高」「长尾抖动」等判断，必须引用 P99 数值作为依据，不能只引用最大值
- 若 P99 与均值接近但最大值很高（如本例 avg=0.09s, P99=0.11s, max=3.16s）：
  这是**单次抖动**，不是系统性问题，报告应明确说明「非长尾问题，个例可忽略」
- 若 P99 触发了长尾告警：报告应引用脚本输出的「⚠️ 长尾告警」区块原文，并给出用户占比
  （若有）辅助判断影响面

## 帕累托分析说明

帕累托原则（80/20 法则）指出：80% 的结果来自 20% 的原因。在接口流量分析中：
- 找出占总流量前 X%（默认 50%）的接口
- 优先优化这些核心接口能获得最大的性能收益
- 支持通过 `--threshold` 参数自定义阈值

## SQL 查询逻辑

自动根据日志格式构建 SQL，核心逻辑：
1. 按 URI 分组统计 PV、平均/P99/最大响应时间（P99 用 `APPROX_PERCENTILE`）
2. 计算每个接口的流量占比
3. 按 PV 降序计算累计占比
4. 使用窗口函数 LAG() 找出刚好超过阈值的临界接口
5. 返回所有累计占比 ≤ 阈值 或临界接口的记录
6. 对上榜接口按长尾判定规则筛出需要关注的行，附加输出
