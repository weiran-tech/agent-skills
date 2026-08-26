---
name: devops-yunxiao-bug-stats
description: 获取云效项目中「线上故障」类型工作项的统计数据。使用分页优先模式，通过 advancedConditions 服务端过滤，直接取 pagination.total 提升性能，无需拉取全量数据。
---

# 云效线上故障统计

## 参数

| 参数              | 说明                                                      | 必填 | 默认值   |
| ----------------- | --------------------------------------------------------- | ---- | -------- |
| `organization_id` | 云效组织ID（从 CLAUDE.md 上下文中获取）                   | 否   | -        |
| `space_id`        | 云效项目ID                                                | 是   | -        |
| `range`           | 创建/关闭的日期范围，自然语言解析如 `"昨天"`、`"最近7天"` | 否   | 本月至今 |

## 固定常量

以下 ID 为硬编码固定值，无需调用 API 动态获取：

**工作项类型 : workitemType** 值定义
| 状态     | ID                         |
| -------- | -------------------------- |
| 线上故障 | `bba77181ef64f834248a0175` |

**状态阶段 : statusStage** 值定义：
| 状态     | ID   |
| -------- | ---- |
| 确认阶段 | `1`  |
| 分析阶段 | `6`  |
| 处理阶段 | `2`  |
| 设计阶段 | `7`  |
| 开发阶段 | `11` |
| 测试阶段 | `12` |
| 验证阶段 | `3`  |
| 发布阶段 | `13` |
| 正常结束 | `4`  |
| 异常结束 | `5`  |

## 查询约定

- **计数查询一律用 `perPage: 0`**：返回 `items: []` 且 `pagination.total` 有效，
  避免每次带回一条完整 item 的无效 payload。
- 只有需要明细清单时才用 `perPage: 200`，且配 `includeDetails: false`。

## advancedConditions 模板

使用 `advancedConditions` 组合查询条件，直接从服务端获取统计数量, **注意**：advancedConditions 的值是 json 字符串, 并非 json 对象

```json
// 组合条件：AND 关系写在同一个 conditionGroups 数组内
{"conditionGroups":[[
    {"fieldIdentifier":"workitemType","..."},
    {"fieldIdentifier":"statusStage","..."},
    {"fieldIdentifier":"updateStatusAt","..."}
]]}

// condition : 限定工作项类型为线上故障
{"fieldIdentifier":"workitemType","operator":"CONTAINS","value":["bba77181ef64f834248a0175"],"className":"workitemType","format":"list"}

// 状态阶段组合
{"fieldIdentifier":"statusStage","operator":"CONTAINS","value":["1"],"className":"statusStage","format":"list"}

// condition : 创建时间日期范围查询 (BETWEEN)
{"fieldIdentifier":"gmtCreate","operator":"BETWEEN","value":["<start_iso> 00:00:00"],"toValue":"<end_iso> 23:59:59","className":"dateTime","format":"input"}

// condition : 状态变更时间日期范围查询 (BETWEEN)
{"fieldIdentifier":"updateStatusAt","operator":"BETWEEN","value":["<start_iso> 00:00:00"],"toValue":"<end_iso> 23:59:59","className":"dateTime","format":"input"}
```

## 功能

输出三个维度的线上故障统计 + 未解决清单：

1. **当前所有未解决的线上故障** 
2. **当前时间范围内创建的线上故障总数** 
3. **当前时间范围内关闭的线上故障总数** 
4. **未解决故障详细清单** 


## 工作流

### Step 0：交互式询问参数（单独调用时）

当用户直接调用 `/devops-yunxiao-bug-stats` 且未提供参数时，使用 `AskUserQuestion` 交互式询问：

| 参数       | 说明     | 必填 | 默认值   | 询问方式                                                            |
| ---------- | -------- | ---- | -------- | ------------------------------------------------------------------- |
| `space_id` | 项目ID   | 是   | -        | 单选，先调用 `mcp__yunxiao__search_projects` 列出用户可见项目供选择 |
| `range`    | 日期范围 | 否   | 本月至今 | 接受自然语言，如 `"昨天"`、`"最近7天"`、`"2026-05-01 - 2026-05-11"` |

> 注意：如果用户已在对话中明确了参数（如 `/devops-yunxiao-bug-stats space_id=xxx`），跳过对应询问。

### Step 1：解析日期范围

使用 `scripts/stats.py` 中的 `parse_days()` 函数解析日期范围：

```bash
uv run scripts/stats.py --parse-days "<range>"
```

返回格式：
```json
{"label": "5月", "start_iso": "2026-05-01", "end_iso": "2026-05-31"}
```

> Step 2-5 中的日期范围使用 `advancedConditions` 中的日期 BETWEEN 查询，无需使用 MCP 内置时间参数。

---

### Step 2：未解决线上故障数量

查询条件: 
- 工作项类型 : 线上故障
- 状态阶段 : [确认阶段, 分析阶段, 处理阶段, 设计阶段, 开发阶段, 测试阶段, 验证阶段, 发布阶段]

```
mcp__yunxiao__search_workitems(
    organizationId, spaceId, category: Bug, perPage: 0, includeDetails: false,
    advancedConditions: '...'
)
→ pagination.total = 未解决线上故障总数
```

**共 1 次 MCP 调用**

### Step 3：范围内创建的线上故障数量

查询条件: 
- 工作项类型 : 线上故障
- 创建时间日期范围查询 (BETWEEN)

```
mcp__yunxiao__search_workitems(
    organizationId, spaceId: '<space_id>', category: Bug, perPage: 0, includeDetails: false,
    advancedConditions: '...'
)
→ pagination.total = 范围内创建的线上故障总数
```

**共 1 次 MCP 调用**

### Step 4：范围内关闭的线上故障数量

查询条件: 
- 工作项类型 : 线上故障
- 状态阶段 : [正常结束 + 异常结束]
- 状态变更时间日期范围查询 (BETWEEN)


```
mcp__yunxiao__search_workitems(
    organizationId, spaceId: '<space_id>', category: Bug, perPage: 0, includeDetails: false,
    advancedConditions: '...'
)
→ pagination.total = 范围内关闭的线上故障总数
```

**共 1 次 MCP 调用**

### Step 5：未解决线上故障明细清单

拉取一页数据用于展示清单, 查询条件: 
- 工作项类型 : 线上故障
- 状态阶段 : [确认阶段, 分析阶段, 处理阶段, 设计阶段, 开发阶段, 测试阶段, 验证阶段, 发布阶段]

```
mcp__yunxiao__search_workitems(
    organizationId, spaceId: '<space_id>', category: Bug,
    perPage: 200, includeDetails: false,
    advancedConditions: '...'
)
```

若 `total > 200`，仅展示第一页内的清单并注明范围限制。

> ⚠️ **必须 `includeDetails: false`。** 清单所需的 `priority` / `seriousLevel` 已在
> `customFieldValues` 基础字段中返回；置 `true` 会额外拉取全部描述正文 ——
> 实测 61 条即达 123,348 字符，超出工具返回上限被迫落盘再解析。

**共 1 次 MCP 调用**

---

### Step 6：组装数据并运行统计分析

将 Step 2-5 的结果组装为 JSON 写入临时文件：

```json
{
  "_counts": {
    "total": N,
    "unresolved": N,
    "created": N,
    "closed": N
  },
  "_items": [未解决故障明细列表]
}
```

调用 stats.py：

```bash
uv run scripts/stats.py <json-file> "<label>" <organization_id>
```

stats.py 检测到 `_counts` 存在时进入**分页优先模式**，直接使用该字段作为统计来源。

---

## 输出格式

ALWAYS use this exact markdown table format：

```
## 线上故障统计

| 统计项                      | 数量  |
| --------------------------- | ----- |
| **当前所有未解决线上故障**  | **N** |
| **`{label}`创建的线上故障** | **N** |
| **`{label}`关闭的线上故障** | **N** |

### 未解决故障清单（按负责人分组）

#### 👤 负责人A（X 个故障）

| 优先级 | 严重程度 | 状态     | 编号 | 标题 | 创建时间         | 链接        |
| ------ | -------- | -------- | ---- | ---- | ---------------- | ----------- |
| 🟡 中   | ⚠️ 一般   | 🔧 处理中 | xxx  | xxx  | 2026-05-12 10:30 | [查看](...) |

#### ❌ 未分配（X 个故障）

| 优先级 | 严重程度 | 状态     | 编号 | 标题 | 创建时间         | 链接        |
| ------ | -------- | -------- | ---- | ---- | ---------------- | ----------- |
| 🔴 紧急 | 💥 致命   | ❓ 待确认 | xxx  | xxx  | 2026-05-12 10:30 | [查看](...) |

### 状态统计摘要

| 状态     | 数量 |
| -------- | ---- |
| 🔧 处理中 | X    |
| ❓ 待确认 | X    |

### 优先级统计摘要

| 优先级 | 数量 |
| ------ | ---- |
| 🔴 紧急 | X    |
| 🟠 高   | X    |
| 🟡 中   | X    |
```

#### Emoji 说明

| 类型         | 标识 | 值            |
| ------------ | ---- | ------------- |
| **优先级**   | 🔴    | 紧急/最高     |
|              | 🟠    | 高/较高       |
|              | 🟡    | 中/普通       |
|              | 🟢    | 低/较低       |
| **严重程度** | 💥    | 致命          |
|              | 🔥    | 严重          |
|              | ⚠️    | 一般          |
|              | 📝    | 轻微          |
| **状态**     | ❓    | 待确认        |
|              | 📋    | 待处理        |
|              | 🔧    | 处理中/进行中 |
|              | ✅    | 已修复/已解决 |
|              | ⏸️    | 挂起中/暂停   |
|              | 🔒    | 已关闭        |
|              | 💻    | 开发中        |
|              | 🧪    | 测试中        |
|              | 🔍    | 验证中        |
|              | 🚀    | 发布中        |