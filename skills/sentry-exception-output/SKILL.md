---
name: sentry-exception-output
description: 查询 Sentry 指定项目的异常事件并按指定格式输出 Markdown 表格。当用户提到 "获取 sentry 项目异常"、"sentry 错误统计"、"sentry 异常表格"、"sentry kjs_* 异常" 等相关内容时使用此技能。支持自定义项目前缀/列表、事件数量阈值、按数量降序排序、自动按数量确定优先级。
---

# Sentry 项目异常输出

从 Sentry 中查询指定项目（或项目前缀）的异常事件，按事件数量过滤后，以 Markdown 表格格式输出

## 参数

<projects> : 项目前缀或项目列表，例如 "kjs_*"(通配符模式) 或 ["kjs_product", "kjs_kf"](枚举模式)
<threshold:100> : 事件数量阈值，只显示事件数大于等于此值的异常，默认值 100
<title> : 项目标题


## 执行步骤

1. **获取组织信息**：调用 `mcp__sentry__find_organizations` 获取组织 slug 和 region URL
2. **获取项目列表**：
   - 如果 projects 是前缀（包含 "*"），调用 `mcp__sentry__find_projects` 搜索匹配的项目
   - 如果 projects 是具体列表，直接使用
3. **获取 Issues**：调用 `mcp__sentry__list_issues` 获取所有 unresolved issues, 并按照时间数量降序排列
4. **过滤和转换**：
   - 只保留匹配项目前缀或在项目列表中的 issue
   - 只保留事件数 >= threshold 的 issue
   - 提取所需字段：项目名、issueId、标题、事件数、URL
   - 根据标题内容生成"错误说明"
   - 根据事件数量确定"优先级"
5. **排序**：按事件数量降序排列
6. **输出表格**：严格按照上述 Markdown 格式输出


## 输出格式

**严格按照以下格式输出 Markdown 表格：**

```markdown
**{title}**

| 项目 | 问题 ID | 标题 | 状态 |事件数量 | 错误说明 | 优先级 | 链接 |
|------|---------|------|-----|------|---------|--------|------|
| kjs_kf | KJS_KF-10N | 3 retry connect is failed | 待处理 | 68882 | Sentry Agent 连接重试失败 | high | [查看](https://trace.kejinxia.com/organizations/kr36/issues/KJS_KF-10N) |
| ... | ... | ... | ... | ... | ... | ... | ... |

**项目总结**

输出当前所有未项目异常事件数量 / 总结 / 建议
```

### 输出列说明

| 列名 | 说明 |
|------|------|
| 项目 | Sentry 项目名称 |
| 问题 ID | Issue ID |
| 标题 | Issue 标题（截取前 80 字符，超长用 ... 结尾） |
| 事件数量 | 事件发生次数 |
| 错误说明 | 对错误的简要描述，从标题推断 |
| 优先级 | 根据事件数量自动确定：<br>• high: 事件数 >= 1000<br>• medium: 事件数 >= 100 且 < 1000<br>• low: 事件数 < 100 |
| 链接 | Issue 详情链接 |