---
name: devops-sentry-exception
description: 查询 Sentry 指定项目的异常事件并按指定格式输出 Markdown 表格
---

# Sentry 项目异常输出

从 Sentry 中查询指定项目（或项目前缀）的异常事件，按事件数量过滤后，以 Markdown 表格格式输出

## 参数

| 参数        | 说明                                                                                       | 必填 | 默认值 |
| ----------- | ------------------------------------------------------------------------------------------ | ---- | ------ |
| `projects`  | 项目前缀或项目列表，例如 `"kjs_*"`（通配符模式）或 `["kjs_product", "kjs_kf"]`（枚举模式） | 是   | -      |
| `threshold` | 异常事件阈值，仅输出 >= threshold 事件数的异常事件                                         | 否   | 100    |
| `title`     | 项目标题                                                                                   | 否   | -      |
| `period`    | 查询时间窗口：`24h` / `7d` / `14d` / `30d` / `90d`                                          | 否   | 30d    |

> ⚠️ `period` 必须在报告里显式声明。它与 SLS/慢日志的 `days`、云效的 `range` 往往不同，
> 不标注会让读者把不同窗口的数字当成同一口径。


## 前置须知

**Sentry API 限制**：组织级别（不传 `projectSlugOrId`）的 `search_issues` 查询常返回空结果。必须逐 project 调用。

> ⚠️ 工具名是 `mcp__sentry__search_issues`。**不存在 `mcp__sentry__list_issues`**，写错会直接调用失败。

## 执行步骤

### 1. 获取组织信息
调用 `mcp__sentry__find_organizations` 获取组织 slug 和 region URL，后续链接格式为 `{regionUrl}/organizations/{slug}/issues/{issueId}`

### 2. 获取项目列表
- 如果 projects 是模式匹配方式（包含 "*"），调用 `mcp__sentry__find_projects` 获取所有列表, 并逐个按照 projects 中的模式筛选匹配的项目
- 如果 projects 是具体列表，直接使用
- 记录每个项目 slug 与其所属分组的关系

**模式匹配规则**：`*` 匹配任意字符，其余字符**字面匹配**。
`_` 与 `-` **不等价** —— `kjs_*` 不会匹配 `kjs-auto-grab-py`、`kjs-h5-path-vue`。
若需同时覆盖两种命名，配置里写两条：`kjs_*` 与 `kjs-*`。

> `find_projects` 单次最多返回 25 条。项目数超过 25 时必须用 `query` 参数分批检索
> （如 `query="kjs"`），否则会静默漏掉项目。

### 3. 逐项目获取 Issues
对每个项目 slug 调用 `mcp__sentry__search_issues`，参数为：
- `organizationSlug`、`regionUrl`（取自 Step 1）
- `projectSlugOrId`（取自 Step 2）
- `query="is:unresolved"`、`sort="freq"`、`limit=100`
- `period`（默认 `30d`，由调用方传入；需与报告中声明的时间窗口一致）
- 若某项目无 issue，跳过
- 将返回的 issue 带上对应的项目名一起收集

### 4. 阈值分类
遍历所有获取到的 issue，按事件数分类：
- **>= threshold**：进入表格展示，标记 high/medium 优先级
- **< threshold**：不计入表格，累计 low 列的 Issue 数和总事件数用于汇总统计

**截断处理与 LOW 计数口径（重要）**

`search_issues` 的 `limit` 上限为 100，且**无分页参数**。若某项目返回条数 == limit，说明结果已被截断：

1. 取最后一条的事件数 `X`，追加一次 `query="is:unresolved timesSeen:<X"` 继续下探，
   直到返回条数 < limit，或已确认低于 threshold 的部分不再需要精确计数
2. LOW（< threshold）一栏必须标注为**「采样窗口内实测」**，并在报告末尾声明实际低频 issue 可能更多
3. **不得**把截断后的计数当作全量上报

> `timesSeen:<X` 里的 `<` 必须是裸字符。

### 5. 排序
按事件数量降序排列（仅展示 >= threshold 的行）

### 6. 提取与转换
从每个 issue 中提取：
- 项目名、问题 ID（shortId）、标题、事件数、状态
- **错误说明**：从异常类名或标题首段提取核心错误。规则：
  - 含 `Exception/Error/Fatal` 则取异常类名去掉尾部 `Exception`/`Error`
  - 例如 "AMQPConnectionClosedException: Broken pipe" → "RabbitMQ 连接断开"
  - 含 `retry connect` / `timeout` / `timeout exceeded` 等关键词则描述为对应含义
- **优先级标记**：high (>=1000)、medium (>=100 且 <1000)
- **链接**：用 `{regionUrl}/organizations/{orgSlug}/issues/{issueId}` 拼接，不可硬编码 trace.kejinxia.com

### 7. 输出表格
严格按照下方 Markdown 格式输出。若最终没有任何 issue 满足阈值（即全部 < threshold），输出"当前无满足条件的异常事件"并附上低优先级统计

## 异常处理

- 若 `search_issues` 返回 400 错误（查询语法无效），去掉多余 flag 后重试。只使用 `is:unresolved`，不要加 `is:open`
- 查询串里的 `<` `>` 必须是**裸字符**，不能写成 HTML 实体（`&lt;` 会报 `Invalid number`）
- 若某个项目查询失败，记录该项目的错误并跳过，继续查询其余项目
- 所有项目查询均失败时，输出"Sentry 数据获取失败"而非让工具挂起
- 连接超时或长时间无响应时，尝试降低 `limit` 参数值（如改为 50）


## 输出格式

**严格按照以下格式输出 Markdown 表格：**

**{title}**

| 项目   | 问题 ID    | 标题                      | 状态   | 事件数量 | 错误说明                  | 优先级 | 链接                                                                    |
| ------ | ---------- | ------------------------- | ------ | -------- | ------------------------- | ------ | ----------------------------------------------------------------------- |
| kjs_kf | KJS_KF-10N | 3 retry connect is failed | 待处理 | 68882    | Sentry Agent 连接重试失败 | high   | [查看](https://trace.kejinxia.com/organizations/kr36/issues/KJS_KF-10N) |
| ...    | ...        | ...                       | ...    | ...      | ...                       | ...    | ...                                                                     |

**项目统计**

| 优先级 | 高（>=1000） | 中（>=100 且 <1000） | 低（<threshold） | 合计 |
|--------|-------------|---------------------|-----------------|------|
| Issue 数 | N | N | N（未展示） | N |
| 总事件数 | N | N | N | N |

**核心问题**

1. **{最高频问题标题}** ({event_count} 次) - {简要分析和建议}
2. ...

**建议**

- {针对性建议 1}
- {针对性建议 2}

**注意：**
- Table 中只展示 >= threshold 的行，低于 threshold 的归入统计表的 low 列
- low 优先级的 issue 不展示在表格中，但在汇总表里显示数量和累计事件数
- 若 low 数量为 0，单元格内容写"无"

### 输出列说明

| 列名     | 说明                                                                                                                                                                    |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 项目     | Sentry 项目名称                                                                                                                                                         |
| 问题 ID  | Issue ID                                                                                                                                                                |
| 标题     | Issue 标题（截取前 80 字符，超长用 ... 结尾）                                                                                                                           |
| 事件数量 | 事件发生次数                                                                                                                                                            |
| 错误说明 | 对错误的简要描述，从标题推断                                                                                                                                              |
| 优先级   | 根据事件数量自动确定：<br>• **high**: 事件数 >= 1000<br>• **medium**: 事件数 >= 100 且 < 1000<br>• **low**: 事件数 < threshold（不输出在表格中，合并到汇总表）<br>• 注意：table 中只展示 >= threshold 的行，低于 threshold 的归入汇总 |
| 链接     | Issue 详情链接                                                                                                                                                          |