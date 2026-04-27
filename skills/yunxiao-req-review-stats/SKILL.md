---
name: yunxiao-req-review-stats
description: 获取云效项目中指定迭代的需求评审结果统计。使用这个技能 whenever 用户需要统计迭代评审情况、查看迭代中需求的评审结论、通过/未通过数量、负责人分布，支持通过迭代ID或迭代名称查询
---

# 云效迭代需求评审统计

## 参数

<sprint>: (可选) 如果用户未提供，先列出当前项目中的所有迭代供用户选择
<organization_id>: (可选) 云效组织ID, 从上下文中获取
<space_id:cbf6b94fbf645e67ec6626fac1>: (可选) 云效项目ID

## 功能

统计指定迭代中的所有需求工作项的评审情况：

1. **总需求数量** - 迭代中的所有需求工作项总数
2. **通过评审数量** - 评审结论为"通过"的需求数量
3. **未通过评审数量** - 评审结论为"未通过"或其他非通过状态的需求数量
4. **按负责人统计** - 统计每个负责人的需求数量和评审通过情况

输出评审结论清单：

- 未通过评审的需求清单
- 所有需求的评审结论汇总表

## 工作流

### Step 0：解析迭代标识并获取 sprint_id

**使用 MCP 工具** `mcp__yunxiao__list_sprints` 获取迭代列表。

用户提供的 `<sprint>` 是迭代名称

**情况 A：如果提供的是迭代名称（包含中文字符）**

调用 `mcp__yunxiao__list_sprints` 获取迭代列表，根据名称匹配找到对应的迭代 ID：

- 精确匹配 `name` 字段
- 如果没有精确匹配，尝试模糊匹配（包含关键词）
- 展示匹配结果供用户确认，或如果有多个匹配让用户选择

**情况 B：如果用户未提供迭代标识**

- 调用 `mcp__yunxiao__list_sprints` 获取所有迭代列表并展示给用户选择
- 用户 **必须** 选择迭代后才能继续执行后续步骤

### Step 1：拉取迭代中的所有需求工作项

使用 `mcp__yunxiao__search_workitems` 获取迭代中的所有需求工作项：

- `organizationId`: <organization_id>
- `category`: `Req`
- `spaceId`: <space_id>
- `spaceType`: `Project`
- `sprint`: 迭代ID
- `perPage`: `200`

如需处理多页，检查返回的 `pagination.nextPage` 并循环调用直到所有数据获取完成。

MCP 返回数据格式示例：

```json
{
  "items": [
    {
      "id": "xxx",
      "subject": "需求标题",
      "statusStageId": "1",
      "assignedTo": { "name": "张三" },
      "customFieldValues": [
        { "fieldName": "评审结论", "values": [{ "displayValue": "通过" }] }
      ],
      "sprint": { "name": "迭代名称" }
    }
  ],
  "pagination": { "totalPages": 1, "total": 3 }
}
```

### Step 2：数据格式转换（MCP → stats.py 兼容格式）

将 MCP 返回的数据转换为统计脚本兼容格式后写入临时 JSON 文件：

```python
converted = []
for item in mcp_data["items"]:
    # 提取评审结论
    review_conclusion = ""
    for cf in item.get("customFieldValues", []):
        if cf.get("fieldName") == "评审结论" and cf.get("values"):
            review_conclusion = cf["values"][0].get("displayValue", "")
            break

    converted.append({
        "identifier": item["id"],
        "subject": item["subject"],
        "statusStageIdentifier": str(item.get("statusStageId", "")),
        "assignedTo": [{"name": item.get("assignedTo", {}).get("name", "")}] if item.get("assignedTo") else [],
        "customFieldValues": {"评审结论": review_conclusion} if review_conclusion else {},
        "sprint": [{"name": item.get("sprint", {}).get("name", "")}] if item.get("sprint") else []
    })
```

---

### Step 3：Python 统计分析

调用 `scripts/stats.py` 进行统计分析：

```bash
uv run scripts/stats.py <json-file> <sprint_id> <sprint_name> <organization_id>
```

stats.py 读取工作项列表并统计：

- 总需求数：迭代中的所有需求
- 通过数：评审结论包含"通过"
- 未通过数：评审结论包含"未通过"或为空或其他值
- 按负责人分组统计

---

### Step 4：生成评审清单

从统计结果中提取未通过评审的需求清单，生成汇总表。工作项链接格式：

```
https://devops.aliyun.com/organization/<organization_id>/work/workitems/<identifier>
```

## 输出格式

ALWAYS use this exact markdown table format：

```
## <sprint> 迭代评审概况

| 统计项           | 数量     |
| ---------------- | -------- |
| **迭代总需求数** | **N**    |
| **评审通过数**   | **N**    |
| **评审未通过数** | **N**    |
| **评审通过率**   | **X.X%** |

## 按负责人通过率统计

| 负责人 | 总需求数 | 通过数 | 未通过数 | 通过率 |
| ------ | -------- | ------ | -------- | ------ |
| xxx    | N        | N      | N        | X.X%   |

## 评审未通过清单

**<负责人> 提交的需求：**

| ID  | 标题 | 评审结论 | 链接 |
| --- | ---- | -------- | ---- |
| xxx | xxx  | xxx      | [详细](url)  |
```
