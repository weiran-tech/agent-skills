---
name: yunxiao-testcase-import
description: 将 AI 评审优化后的测试用例批量导入到云效测试用例库。当用户提到"导入测试用例"、"用例导入"、"创建优化用例"、"批量导入测试用例"、"导入用例到云效"、"批量创建用例"等词时触发。内置快速执行流程，减少重复思考。
---

# 云效测试用例批量导入

## 参数

- `<organization_id>`: 云效组织ID (从 CLAUDE.md 上下文获取)

---

## 核心 MCP 工具速查表

| 工具名称 | 用途 | 必填参数 |
|----------|------|----------|
| `mcp__yunxiao__list_testcase_directories` | 获取测试用例目录树 | `organizationId`, `testRepoId` |
| `mcp__yunxiao__search_testcases` | 按目录搜索测试用例（查重用） | `organizationId`, `testRepoId`, `directoryId` |
| `mcp__yunxiao__create_testcase_directory` | 创建测试用例目录（支持级联目录） | `organizationId`, `testRepoId`, `name`, `parentIdentifier` |
| `mcp__yunxiao__create_testcase` | 创建测试用例 | `organizationId`, `testRepoId`, `subject`, `preCondition`, `directoryId`, `testSteps` |
| `AskUserQuestion` | 交互式选择测试用例库和目标目录 | `questions` |

---

## 输入文件格式

从 `report/{项目名}/testcase/` 目录下 JSON 文件读取数据，必须包含 `testcases` 数组，每个用例包含：

```javascript
{
  "subject": "用例标题",
  "directory": "来源目录名",
  "optimized": {
    "preCondition": "优化后的前置条件",
    "subject": "优化后的标题",
    "directory": "目标目录名",
    "testSteps": [
      {"step": "步骤1", "expected": "预期结果1"},
      {"step": "步骤2", "expected": "预期结果2"}
    ]
  }
}
```

---

## 完整工作流

### Phase 1：选择导入源和目标

**Step 1.1 — 选择导入源 JSON 文件**

扫描 `report/` 目录下所有项目的 `testcase/` 子目录，列出所有可用的 JSON 文件：

```bash
find report/*/testcase -name "*.json" -type f
```

使用 `AskUserQuestion` 让用户选择源文件：

```javascript
{
  question: "请选择要导入的测试用例源文件：",
  header: "源文件选择",
  options: [
    {label: "登录-2026-04-25.json (氪金兽, 17条)", description: "包含登录模块优化后的测试用例"},
    // ... 更多选项
  ],
  multiSelect: false
}
```

**Step 1.2 — 选择目标测试用例库**

读取 `config/` 目录下所有 YAML 配置文件，提取所有项目的 `test_repos` 配置，合并为测试用例库列表。

使用 `AskUserQuestion` 让用户选择：

```javascript
{
  question: "请选择目标测试用例库：",
  header: "用例库选择",
  options: [
    {label: "氪金兽", description: "氪金兽项目主测试用例库"},
    {label: "氪金兽Java", description: "氪金兽Java后端测试用例库"},
    // ... 更多选项
  ],
  multiSelect: false
}
```

**Step 1.3 — 选择目标目录**

调用 `mcp__yunxiao__list_testcase_directories` 获取目录树，构建扁平化的目录列表（缩进显示层级），使用 `AskUserQuestion` 让用户选择：

```javascript
{
  question: "请选择导入的目标目录：",
  header: "目标目录选择",
  options: [
    {label: "客户端/H5 > 登录注册", description: "H5端登录注册模块测试用例目录"},
    {label: "客户端/H5 > 登录注册 > 登录（New）", description: "新版登录模块目录"},
    {label: "微信小程序 > 登录/注册", description: "微信小程序登录模块目录"},
    // ... 更多选项
  ],
  multiSelect: false
}
```

---

### Phase 2：去重检查与预览

**Step 2.1 — 获取目标目录现有用例**

调用 `mcp__yunxiao__search_testcases` 获取目标目录下所有现有测试用例标题，用于查重：

```python
mcp__yunxiao__search_testcases(
  organizationId="<organization_id>",
  testRepoId="<testRepoId>",
  directoryId="<directory_id>",
  page=1,
  perPage=200
)
```

循环分页处理，直到该目录下所有用例拉取完成，收集所有现有用例的标题。

**Step 2.2 — 进行去重检查**

读取源 JSON 文件中的所有用例，对每个用例的 `optimized.subject` 与目标目录现有标题进行精确匹配：

- **完全匹配**：判定为重复，跳过创建
- **不匹配**：可以创建

构建导入计划数据结构：

```javascript
{
  toCreate: [
    {
      sourceTitle: "原标题",
      targetTitle: "优化后标题",
      directory: "目录",
      preCondition: "前置条件",
      testSteps: []
    }
  ],
  duplicates: [
    {
      sourceTitle: "原标题",
      duplicateTitle: "目标目录已存在标题"
    }
  ]
}
```

**Step 2.3 — 展示导入预览并确认**

展示导入预览统计：

```
🤖 测试用例导入预览
━━━━━━━━━━━━━━━━━━━━━
源文件：{文件名}
目标用例库：{用例库名称}
目标目录：{目录名称}

统计：
总计读取：{N} 条
✅ 可创建：{N} 条
⚠️ 重复跳过：{N} 条

━━━━━━━━━━━━━━━━━━━━━
即将创建的用例（前 10 条）：
- [用例标题1]
- [用例标题2]
...

重复将跳过的用例：
- [用例标题1]
- [用例标题2]
...
```

使用 `AskUserQuestion` 让用户确认是否开始导入：

```javascript
{
  question: "是否确认开始导入？",
  header: "确认导入",
  options: [
    {label: "✅ 确认导入全部", description: "创建所有可创建的测试用例"},
    {label: "📋 只导入前 10 条", description: "分批处理，先导入前10条验证效果"},
    {label: "❌ 取消导入", description: "取消本次导入操作"}
  ],
  multiSelect: false
}
```

---

### Phase 3：批量创建测试用例

根据用户选择的导入范围，逐条创建测试用例。

**Step 3.1 — 构造测试用例数据**

从 `optimized` 字段提取：
- `subject`: `optimized.subject`
- `preCondition`: `optimized.preCondition`
- `directoryId`: 选中的目标目录 ID
- `testSteps`: 按 TABLE 格式：

```javascript
{
  "contentType": "TABLE",
  "content": [
    {"step": "步骤1", "expected": "预期1"},
    {"step": "步骤2", "expected": "预期2"}
  ]
}
```

**Step 3.2 — 调用创建接口**

```python
mcp__yunxiao__create_testcase(
  organizationId="<organization_id>",
  testRepoId="<testRepoId>",
  subject="优化后的标题",
  preCondition="优化后的前置条件",
  directoryId="<目标目录ID>",
  testSteps=testSteps_object
)
```

**Step 3.3 — 记录创建结果**

构建创建结果数据：

```javascript
{
  created: [
    {
      id: "新创建的用例ID",
      subject: "用例标题",
      directory: "目录名称"
    }
  ],
  failed: [
    {
      subject: "用例标题",
      error: "错误信息"
    }
  ],
  skipped: [
    {
      subject: "用例标题",
      reason: "重复标题"
    }
  ]
}
```

**重要**：每次创建间隔 1 秒，避免触发 API 限流。

创建过程中实时显示进度：`正在创建第 {current}/{total} 条：{用例标题}`

---

### Phase 4：输出导入结果报告

```
🤖 测试用例导入完成
━━━━━━━━━━━━━━━━━━━━━
源文件：{文件名}
目标用例库：{用例库名称}
目标目录：{目录名称}

统计结果：
总计处理：{N} 条
✅ 创建成功：{N} 条
⚠️ 重复跳过：{N} 条
❌ 创建失败：{N} 条

━━━━━━━━━━━━━━━━━━━━━
创建成功的用例（前 10 条）：
- [用例标题1] → ID: xxx
- [用例标题2] → ID: xxx
...

创建失败的用例：
- [用例标题1] → 原因：{错误信息}
- [用例标题2] → 原因：{错误信息}
...
```

---

## 注意事项

- **去重规则**：标题精确匹配判定为重复，重复用例跳过
- **数据来源**：仅使用 `optimized` 字段的优化后内容进行创建
- **限速保护**：每次创建间隔 1 秒，避免触发 API 限流
- **容错处理**：任何工具调用失败都不中断整体流程，在最终报告中汇总失败列表
- **目录选择**：只能选择单个目录作为导入目标
- **字段映射**：所有用例都导入到用户选中的目标目录下，忽略源文件中的目录信息
- **空值处理**：如果 `optimized.preCondition` 为空，使用空字符串
- **分批导入**：如果可创建数量 > 20 条，提供分批导入选项

---
## 🔴 快速执行流程（减少思考）

### 前置条件检查
**第一步：获取当前用户ID（必须首先执行）**
```python
mcp__yunxiao__get_current_organization_info()
```
从返回结果中提取 `userId` 字段，作为测试用例负责人。

### 源文件数据结构说明
从 `report/{项目名}/testcase/*.json` 读取，直接使用 `testcases` 数组：
```javascript
// 每个 testcase 对象结构：
{
  "optimized": {                // 优先使用 optimized 字段
    "subject": "用例标题",
    "preCondition": "前置条件",
    "testSteps": [{"step": "", "expected": ""}]
  },
  "subject": "原始标题",        // optimized 为 null 时回退
  "original": {
    "preCondition": "原始前置",  // optimized 为 null 时回退
    "testSteps": {"content": [...]}
  }
}
```

### 批量创建模板（直接套用）
```python
mcp__yunxiao__create_testcase(
  organizationId="62ac9a6364c8a06be2d5db5d",  # 固定值
  testRepoId="<目标用例库ID>",
  subject="<用例标题>",
  preCondition="<前置条件内容>",
  directoryId="<目标目录ID>",
  assignedTo="<userId from get_current_organization_info>",  # 必填！
  testSteps={"contentType": "TABLE", "content": [<步骤数组>]}
)
```

### 极简步骤（3步完成）
1. **获取负责人ID**：调用 `get_current_organization_info()` 取 userId
2. **读取源文件**：直接读取 JSON 文件，遍历 testcases 数组
3. **循环创建**：按上述模板调用 `create_testcase`，每条间隔 1 秒

### 常见错误修复
- **错误**：负责人不能为空 → **解决方案**：添加 `assignedTo` 参数，值为 userId
- **参数名**：必须是 `assignedTo`（不是 ownerId、creatorId、chargeUserId）
