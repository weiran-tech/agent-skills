---
name: yunxiao-req-ai-review
description: AI 自动评审云效需求并生成评审意见。当用户提到"需求评审"、"评审需求"、"AI 评审"、"自动评审"、"待处理需求评审"、"评审待处理"等词时触发。工作流：选择项目 → 选择迭代 → 获取"待处理"状态的需求 → 逐条执行 AI 评审 → 评审驳回/待人工评审 → 回写评论和状态到云效。适用于迭代前需求批量评审、需求质量把控、评审自动化等场景。
---

# 云效 AI 需求评审

## 参数

从 CLAUDE.md 读取（勿硬编码，以 CLAUDE.md 为准）：
- `<organization_id>`: 云效组织ID
- `<space_id>`: 云效项目ID（如未指定，先列出所有项目供用户选择）

---

## 核心 MCP 工具速查表（减少思考时间）

**必须使用以下工具，不要思考工具名称，直接复制调用**：

| 工具名称 | 用途 | 必填参数 |
|----------|------|----------|
| `mcp__yunxiao__search_projects` | 获取项目列表 | 无参数 |
| `mcp__yunxiao__list_sprints` | 获取迭代列表 | `organizationId`, `id` |
| `mcp__yunxiao__search_workitems` | 搜索需求列表 | `organizationId`, `spaceId`, `spaceType`, `category`, `sprint`, `status`, `perPage` |
| `mcp__yunxiao__get_work_item` | 获取单条需求详情 | `organizationId`, `workItemId` |
| `mcp__yunxiao__create_work_item_comment` | 给需求添加评论 | `organizationId`, `workItemId`, `content` |
| `mcp__yunxiao__update_work_item` | 更新需求状态/字段 | `organizationId`, `workItemId`, `updateWorkItemFields` |
| `mcp__yunxiao__get_workitem_type_field_config` | 获取需求类型字段配置 | `organizationId`, `workItemTypeId` |

---

## 完整工作流

### Phase 1：选择范围

**Step 1.1 — 选择项目（如未指定 space_id）**

调用 `mcp__yunxiao__search_projects` 获取项目列表，展示给用户选择：

以表格形式展示，只显示序号和项目名称，不显示项目ID：

| 序号 | 项目名称 |
|------|---------|
| 1 | xxx项目 |
| 2 | xxx项目 |

让用户通过输入序号来选择项目。

**Step 1.2 — 选择迭代**

调用 `mcp__yunxiao__list_sprints` 获取迭代列表：

```python
mcp__yunxiao__list_sprints(
  organizationId="<organization_id>",
  id="<space_id>"
)
```

以表格形式展示，只显示序号和迭代名称，不显示迭代ID：

| 序号 | 迭代名称 |
|------|---------|
| 1 | xxx迭代 |
| 2 | xxx迭代 |

必须让用户选择一个具体迭代，不支持"当前迭代"、"所有未完成迭代"等快捷选项。

---

### Phase 2：筛选待评审需求

**Step 2.1 — 获取"待处理"状态的需求**

调用 `mcp__yunxiao__search_workitems` 分页拉取指定迭代中状态为"待处理"的需求：

```python
mcp__yunxiao__search_workitems(
  organizationId="<organization_id>",
  spaceId="<space_id>",
  spaceType="Project",
  category="Req",
  perPage=200,
  advancedConditions={"conditionGroups":[[{"fieldIdentifier":"status","operator":"CONTAINS","value":["100005"],"className":"status","format":"list"},{"fieldIdentifier":"sprint","operator":"CONTAINS","value":["<sprint_id>"],"className":"sprint","format":"list"}]]}
)
```

**重要：必须使用 `advancedConditions` 同时筛选迭代和状态，不要使用第一层的 `status` 或 `sprint` 参数，不要从结果中过滤。**

循环处理直到所有数据拉取完成。

**Step 2.2 — 确认评审数量**

- 忽略"评审结论"字段，即使已有 [AI] 评审标记也进行重新评审

如果结果 > 10 条，先告知用户数量，询问是否全量处理。

---

### Phase 3：AI 逐条评审

对每一条待评审需求，告知用户"正在评审第 N/M 条：[标题]"，然后依次执行：

**Step 3.1 — 获取需求详情**

调用 `mcp__yunxiao__get_work_item` 获取完整需求详情：

```python
mcp__yunxiao__get_work_item(
  organizationId="<organization_id>",
  workItemId="<workitem_id>"
)
```

提取完整信息：
- 需求类型（产品类/技术类）
- 标题、描述、验收标准
- 负责人、优先级、关联附件
- 关联的子任务、依赖项
- customFieldValues 中的"评审结论"字段ID

**Step 3.2 — 执行评审判断**

根据需求类型使用不同的评审标准：

#### 📋 产品类需求评审标准
| 评审项 | 通过条件 |
|--------|----------|
| 需求完整性 | 内容完整、描述清晰、范围明确 |
| 业务逻辑 | 逻辑通顺、前后自洽、无明显冲突 |
| 场景覆盖 | 核心场景完整、关键规则清晰 |
| 交互规范 | 交互/文案/异常提示合理，符合产品习惯 |
| 验收标准 | 明确可测，研发/测试可清晰理解 |
| 共识达成 | 需求范围、实现规则无明显争议 |

#### 🔧 技术类需求评审标准
| 评审项 | 通过条件 |
|--------|----------|
| 方案清晰度 | 技术方案描述清晰，改造范围明确 |
| 架构合理性 | 整体架构、代码设计符合团队规范 |
| 数据兼容性 | 数据变更、接口调整兼容现有业务 |
| 稳定性设计 | 考虑容错、无严重性能/安全隐患 |
| 上线风险 | 影响范围清晰、有回滚/兜底方案 |
| 方案对齐 | 研发/测试对齐实现方案，无重大争议 |

**评审结论判定规则**：
- **✅ 评审通过**：满足所有核心评审项，无需额外评论
- **评审驳回**：有 2 项以上核心项不满足，或有明显严重缺陷（包括需求描述为空/过于简略）
  - 更新状态为"评审驳回"（statusIdentifier: `62a829f0a33157f511cc6379a5`）
  - **必须调用 `mcp__yunxiao__create_work_item_comment` 写详细评论说明驳回原因**
  - 更新"评审结论"自定义字段为 `"[AI] 驳回：{简要原因}"`
- **待人工评审**：部分项不满足，或有模糊点需人工确认
  - 更新状态为"待评审"（status: `b6d1af1f9bd7ed8b3a79e27a11`）
  - **必须调用 `mcp__yunxiao__create_work_item_comment` 写详细评审意见评论**

**Step 3.3 — 生成评论内容**

**评审驳回评论模板**：
```
AI 评审结论：驳回
━━━━━━━━━━━━━━━━━━━━━
问题清单：
1. {问题1}
2. {问题2}
...

改进建议：
- {建议1}
- {建议2}

建议修改后重新提交评审
```

**待人工评审评论模板**：
```
AI 评审意见：待人工确认
━━━━━━━━━━━━━━━━━━━━━
关注点：
1. {关注点1}
2. {关注点2}
...

建议讨论方向：
- {建议1}
- {建议2}
```

**Step 3.4 — 回写云效**

**发布评论（必须执行，不要思考工具名称，直接调用）**：
```python
mcp__yunxiao__create_work_item_comment(
  organizationId="<organization_id>",
  workItemId="<workitem_id>",
  content="<评审评论内容>"
)
```

更新工作项状态：
```python
# 状态常量（直接使用，不要思考或查询）：
# 待处理 → 100005
# 待评审 → b6d1af1f9bd7ed8b3a79e27a11
# 评审驳回 → 62a829f0a33157f511cc6379a5
# 评审通过 → bc5e4a3a72ef6f7c0ecdac11ee

mcp__yunxiao__update_work_item(
  organizationId="<organization_id>",
  workItemId="<workitem_id>",
  updateWorkItemFields={
    "status": "<new_status_id>"
  }
)
```

更新"评审结论"自定义字段（如存在）：
```python
# 从需求详情的 customFieldValues 中找到"评审结论"的 fieldId
# 遍历 customFieldValues 数组，找到 fieldName == "评审结论" 的项
# 使用该项的 fieldId 作为 key 更新 customFieldValues
# 如果找不到，跳过更新，不要中断流程

mcp__yunxiao__update_work_item(
  organizationId="<organization_id>",
  workItemId="<workitem_id>",
  updateWorkItemFields={
    "customFieldValues": {
      "<review_conclusion_field_id>": "[AI] 驳回/待评审：..."
    }
  }
)
```

**重要**：如果工具调用失败，不继续执行并告知用户。

---

### Phase 4：汇总报告

所有需求评审完毕后输出统计报告：

```
AI 需求评审完成
━━━━━━━━━━━━━━━━━━━━━
统计结果：
总计评审：{N} 条
评审通过：{N} 条
评审驳回：{N} 条
待人工评审：{N} 条

驳回需求清单：
- [需求标题](云效链接) → 原因：{简要}

待人工评审清单：
- [需求标题](云效链接) → 关注点：{简要}
```

---

## 注意事项

- **状态ID校准**：如更新状态失败，先用 `mcp__yunxiao__get_work_item` 查一条状态为"评审驳回"/"待评审"的需求，确认其 statusIdentifier
- **评审边界**：需求描述为空或极简短的，直接标记"评审驳回"并注明"[AI] 需求描述为空 / 过于简略，无法进行评审"
- **评论去重**：如果工作项已有 🤖 开头的 AI 评论，追加新评论时标注"(第2次评审)"
- **自定义字段容错**："评审结论"字段可能不存在于某些项目，不存在时跳过更新，不要中断流程
- **限速保护**：每次更新间隔 1-2 秒，避免触发 API 限流
- **评论失败处理**：如果评论工具调用失败，继续执行状态更新，不要中断整个评审流程，最后在汇总报告中标注哪些需求评论失败
