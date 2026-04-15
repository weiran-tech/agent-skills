---
name: arch-analyzer
description: 分析 Java 微服务项目（多模块 Maven/Gradle 结构）的服务架构。当用户说 "arch-analyzer"、"分析服务架构"、"生成服务文档"、"架构分析"、"文档化服务"、"analyze service architecture" 时触发。
---

# Arch Analyzer

分析当前 Java 微服务项目代码，生成四份文档。每份文档服务于不同的读者和场景：

| 文件 | 作用 | 参考指南 |
|------|------|---------|
| `docs/overview.md` | 服务名片，快速定向 | `references/overview-md.md` |
| `docs/business.md` | 业务逻辑与规则 | `references/business-md.md` |
| `docs/contracts.md` | 跨服务 MQ 契约与接口 | `references/contracts-md.md` |
| `docs/flows.md` | 业务执行流程与影响分析 | `references/flows-md.md` |

## 第一步：并行扫描项目

在生成任何文档之前，先建立对项目的全面认知。以下扫描并行执行：

**模块结构：**
- 读取根目录 `pom.xml` / `build.gradle`，获取 `<modules>` 列表
- 读取 `application.yml` / `bootstrap.yml` 获取 `spring.application.name`

**MQ 消费方扫描：**
- 搜索 `@RocketMQMessageListener`、`@KafkaListener`、`@RabbitListener`
- 读取每个监听器类，记录：topic、tag/consumerGroup、消费后调用的 Service 方法

**MQ 发布方扫描：**
- 搜索 `syncSend`、`asyncSend`、`sendDelayLevel`、`syncSendDeliverTimeMills`、`convertAndSend`
- 记录每处发布的：topic、tag、触发该发布的业务方法

**Feign 接口扫描：**
- 搜索 `@FeignClient`，区分本服务暴露的（`*-api` 模块）和调用外部的（`*-infrastructure` 模块）

**业务逻辑扫描：**
- 读取 `*-core` / `*-domain` / `*-application` 模块下的 `@Service` 类
- 查找状态枚举（含 `Status`、`State`）、路由/分发逻辑（Router、Dispatcher、Strategy、Handler）、`@Scheduled` 定时任务

## 第二步：增量更新原则

写文件前先检查是否已存在：

- **不存在**：直接生成完整内容
- **已存在**：读取现有内容，保留手动补充的部分（业务背景、决策原因等），只更新可从代码推断的表格和列表，追加新发现的内容

手动补充的内容比代码扫描结果更有价值，不要覆盖。

## 第三步：逐份生成文档

按以下顺序生成，每份文档读取对应的 reference 文件获取详细规则和模板：

1. **docs/overview.md** → 读取 `references/overview-md.md`
2. **docs/business.md** → 读取 `references/business-md.md`
3. **docs/contracts.md** → 读取 `references/contracts-md.md`
4. **docs/flows.md** → 读取 `references/flows-md.md`

如果用户只要求生成某一份文档，只读取对应的 reference 文件即可。

## 第四步：完成摘要

输出简短摘要：
- 扫描结果：模块数、MQ 监听器数、发布点数、Feign 接口数
- 标注了"待确认"的字段（信息不足处）
- 保留了哪些已有内容（增量更新时）

## 第五步：自动触发 arch-publish

文档生成完成后，**无需用户额外指令**，立即执行 `arch-publish` skill，将本次生成的文档推送到 arch-docs。

按照 arch-publish skill 的完整流程执行，包括：确定 arch-docs 路径、确定服务名称、推送文档、更新索引。
