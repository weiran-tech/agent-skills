---
name: yunxiao-bug-stats
description: 获取云效项目中「线上故障」类型工作项的统计数据。使用这个技能 whenever 用户需要统计线上故障数量，包括：(1) 当前未解决的线上故障总数；(2) 当前月份创建的线上故障总数；(3) 当前月份关闭的线上故障总数。Trigger this skill when the user asks for bug statistics, 故障统计, 线上故障统计, 获取这个项目中的 Bug 工作项, 统计 yiwan-judanyun.
---

# 云效线上故障统计

## 参数

<organization_id>: 云效组织ID, 从CLAUDE.md 上下文中获取
<space_id>: 云效项目ID
<yyyy_mm>: 统计月份, 默认是当前月份

## 功能

输出三个统计值：

1. **当前所有未解决线上故障数量** - 状态阶段处于：(确认阶段/分析阶段/处理阶段/设计阶段/开发阶段/测试阶段/验证阶段/发布阶段)
2. **<yyyy_mm>创建的线上故障总数量** - 按创建时间筛选
3. **<yyyy_mm>关闭的线上故障总数量** - 状态阶段处于(正常结束/异常结束)且状态更新于<yyyy_mm>

输出问题清单：

**⚠️ 必须按负责人分组展示所有未解决线上故障**

## 核心输出要求（强制执行）

1. 📋 **完整清单**：输出全部未解决故障问题，不遗漏
2. 👤 **按负责人分组**：问题清单必须按负责人分组，每组显示该负责人的故障数量
3. 🎯 **优先级可视化**：显示优先级 Emoji（🔴紧急/🟠高/🟡中/🟢低）
4. ⚠️ **严重程度可视化**：显示严重程度 Emoji（💥致命/🔥严重/⚠️一般/📝轻微）
5. 📊 **状态可视化**：显示状态 Emoji（❓待确认/🔧处理中/✅已修复/⏸️挂起中）
6. 📈 **统计摘要**：底部必须包含状态统计摘要和优先级统计摘要

## 工作流


### Step 0: 拉取所有线上项目

使用 `AskUserQuestion` 工具交互式询问用户以下参数：

| 参数 | 说明 | 必填 | 默认值 | 询问方式 |
|------|------|------|--------|----------|
| `space_id` | 项目ID | 是 | - | 单选，列出用户可见的项目供选择 |
| `yyyy_mm` | 统计月份 | 是 | - | 单选, 列出最近3个月的时间, 默认是当前月份, 格式是 <yyyy>-<mm> |

**注意**：
1. 先查询项目列表，让用户选择项目
2. 选择项目后，查询该项目的所有标签供用户多选
3. 标签筛选逻辑：包含任意一个选中的标签即匹配
4. 如果用户已在对话中明确了参数，可以跳过对应询问

**选择用户可见的项目**
调用项目列表接口并显示给用户选择：

```python
mcp__yunxiao__search_projects(organizationId="<organization_id>")
```


### Step 1：拉取所有线上故障工作项

使用 `mcp__yunxiao__search_workitems` 获取所有「线上故障」类型工作项：
- `organizationId`: 组织ID
- `category`: `Bug`
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
      "subject": "故障标题",
      "status": {"id": "100005", "name": "待处理"},
      "assignedTo": {"name": "张三"},
      "workitemType": {"id": "bba77181ef64f834248a0175", "name": "线上故障"},
      "gmtCreate": 1777019413000,
      "updateStatusAt": 1777024760000,
      "customFieldValues": [
        {"fieldId": "priority", "fieldName": "优先级", "values": [{"displayValue": "中"}]},
        {"fieldId": "seriousLevel", "fieldName": "严重程度", "values": [{"displayValue": "3-一般"}]}
      ]
    }
  ]
}
```


### Step 2：Python 统计分析

直接调用 `scripts/stats.py` 进行统计分析（脚本已内置支持 MCP 数据格式）：

```bash
uv run scripts/stats.py <json-file> <year> <month> [organization_id]
```

stats.py 读取工作项列表并统计：
- 未解决：`status.id` 不在已关闭状态集合中
- 创建于本月：`gmtCreate` 时间戳在指定月份范围内
- 关闭于本月：`status.id` 在已关闭状态 且 `updateStatusAt` 时间戳在指定月份范围内

---

### Step 3：提取未解决故障清单

从统计结果中提取未解决故障信息列表。工作项链接格式：

```
https://devops.aliyun.com/organization/<organization_id>/work/workitems/<identifier>
```

## 输出格式

### ⚠️ 强制性要求：必须按负责人分组展示故障清单

输出包含三部分：
1. **基础统计表** - 显示三个核心统计数字
2. **按负责人分组的故障清单（必须实现）**：
   - 每个负责人单独成组，组标题显示 `👤 姓名（N 个故障）`
   - 每组内使用 Markdown 表格展示，包含列：优先级、严重程度、状态、编号、标题、链接
   - 每组按故障数量降序排列（故障多的负责人在前）
   - 优先级、严重程度、状态三列必须带 Emoji 标识
3. **状态统计摘要和优先级统计摘要** - 两个汇总表格
