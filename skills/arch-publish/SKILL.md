---
name: arch-publish
description: 将当前微服务的架构分析文档推送到系统架构汇总目录（arch-docs）下，按服务名称分层存储。当用户说 "arch-publish"、"推送架构文档"、"同步到 arch-docs"、"发布服务文档"、"publish to arch-docs" 时触发。
---

# Arch Publish

将当前服务的架构文档推送到 arch-docs 目录下，按服务名称分层存储。

自动发现并推送以下文件（无需枚举，新增文档无需修改此 skill）：
- `docs/` 目录下所有 `.md` 文件（overview.md、business.md、contracts.md、flows.md 及未来新增的任何文档）

目标结构：
```
{arch-docs}/
└── system-design/
    └── services/
        └── {service-name}/
            └── {docs/ 下每个 .md 文件，去掉 docs/ 前缀}
```

## 第一步：确定 arch-docs 路径

按优先级查找：

1. 读取项目根目录 `.arch-docs.yml`：
   ```yaml
   arch_docs_path: ../arch-docs
   ```
   路径支持相对路径（相对于当前项目根目录）和绝对路径。

2. 若配置文件不存在，直接告知用户将使用默认路径并请求确认，**不要展示空输入框**：
   > "将使用默认路径 `../arch-docs` 作为 arch-docs 目录。回复「yes」或直接回车继续，如需使用其他路径请直接回复路径。"

3. 获取路径后询问是否保存到 `.arch-docs.yml`，同意则创建：
   ```yaml
   arch_docs_path: {路径}
   ```

4. 验证目录是否存在，不存在则询问用户是否创建。

## 第二步：确定服务名称

按优先级获取：
1. `application.yml` / `bootstrap.yml` 中的 `spring.application.name`
2. `.arch-docs.yml` 中的 `service_name`
3. 根目录 `pom.xml` 的 `<artifactId>`
4. 以上都找不到则询问用户

## 第三步：自动发现并推送文档

目标目录：`{arch-docs}/system-design/services/{service-name}/`

**使用 shell 命令直接复制文件，禁止读取文件内容再写入**：

```bash
# 创建目标目录
mkdir -p {target}

# 复制 docs/ 下所有 .md 文件（若目录存在）
[ -d docs ] && cp docs/*.md {target}/
```

如果 `docs/` 不存在，提示用户先运行 `arch-analyzer` 生成文档。

**覆盖策略**：直接覆盖目标文件，以当前服务的文档为准。arch-docs 下的服务文档不应手动修改，修改应在服务自身的 repo 中进行后重新 publish。

## 第四步：更新 arch-docs 索引

读取 `{arch-docs}/README.md`，在服务目录表中添加或更新当前服务的条目。

若 `README.md` 不存在则创建：

```markdown
# 系统架构文档

## 服务目录

| 服务 | 职责 | 文档 |
|------|------|------|
| {service-name} | {从 overview.md 提取一句话职责} | [详情](system-design/services/{service-name}/overview.md) |

## 说明

- 各服务文档由各自 repo 运行 `arch-publish` 自动同步，请勿直接修改 `system-design/services/` 下的内容
- 跨服务流程请在 `system-design/flows/` 下手动维护
```

若已存在，只在服务目录表中**插入或更新**当前服务对应的行，不修改其他内容。

## 第五步：输出结果

动态列出实际推送的文件（不是固定模板，有几个列几个）：

```
✅ arch-publish 完成

服务：{service-name}
推送到：{arch-docs绝对路径}/system-design/services/{service-name}/

推送的文件：
  ✓ overview.md
  ✓ business.md
  ✓ contracts.md
  ✓ flows.md
  ✓ {其他发现的文件}

README.md 索引已更新。
```
