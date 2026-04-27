---
name: yunxiao-req-stats
description: 获取云效项目中所有工作项的统计数据。使用这个技能 whenever 用户需要统计项目需求
---

# 云效研发需求统计

## 参数

<organization_id>: 从上下文中获取
<space_id>: 云效项目ID
<yyyy_mm>: 统计月份, 默认是当前月份

## 功能

输出三个统计值：

1. **当前所有未解决技术需求数量** - 状态阶段处于未完成
2. **<yyyy_mm>创建的技术需求总数量** - 按创建时间筛选
3. **<yyyy_mm>关闭的技术需求总数量** - 状态阶段处于已完成/已取消 且状态更新于<yyyy_mm>

输出问题清单：

当前所有未解决研发需求

## 工作流

### Step 1：拉取所有研发需求工作项

使用 `mcp__yunxiao__search_workitems` 获取所有「技术类需求」类型工作项：
- `organizationId`: 组织ID
- `category`: `Req`
- `spaceId`: 项目ID
- `spaceType`: `Project`
- `perPage`: `200`

如需处理多页，检查返回的 `pagination.nextPage` 并循环调用直到所有数据获取完成。

MCP 返回数据格式示例：
```json
{
  "items": [
    {
      "id": "xxx",
      "subject": "需求标题",
      "statusStageId": 1,
      "assignedTo": {"name": "张三"},
      "workitemType": {"name": "技术类需求"},
      "gmtCreate": 1777019413000,
      "gmtModified": 1777024773000,
      "gmtStatusChanged": 1777024760000
    }
  ],
  "pagination": {"totalPages": 1, "total": 3}
}
```


### Step 2：数据格式转换（MCP → stats.py 兼容格式）

调用 `scripts/convert_mcp.py` 将 MCP 返回的数据转换为统计脚本兼容格式：

```bash
uv run scripts/convert_mcp.py <mcp-json-file> <output-json-file>
```

---

### Step 3：Python 统计分析

调用 `scripts/stats.py` 进行统计分析：

```bash
uv run scripts/stats.py <json-file> <year> <month> <organization_id>
```

stats.py 读取工作项列表并统计：
- 未解决：`statusStageIdentifier` 不在已关闭阶段集合中
- 创建于本月：`gmtCreate` 前7字符 == `<yyyy_mm>`
- 关闭于本月：`statusStageIdentifier` 在已关闭阶段 且 `gmtStatusChanged` 前7字符 == `<yyyy_mm>`

---

### Step 4：提取未解决需求清单

从统计结果中提取 `unresolved` 列表，生成问题清单。工作项链接格式：

```
https://devops.aliyun.com/organization/<organization_id>/work/workitems/<identifier>
```

## 输出格式

ALWAYS use this exact markdown table format:

| 统计项 | 数量 |
|--------|------|
| **当前所有未解决技术需求** | **N** |
| **<yyyy_mm>创建的技术需求** | **N** |
| **<yyyy_mm>关闭的技术需求** | **N** |

**统计说明:**
- 项目中总共有 **X** 个"技术需求"类型工作项
- **Y** 个已经关闭，**Z** 个仍处于未解决状态

**问题清单:**

| ID | 标题 | 负责人 | 优先级 | 链接 |                
|-----|------|-----|------|------|
| xxx | xxx | xxx | xxx | xxx |
