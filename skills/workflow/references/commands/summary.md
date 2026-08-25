# `/workflow summary` — 交付清单产出

> 处理 `/workflow summary [需求ID][#里程碑]` 时读本文件。给 DBA（DDL）、运维（Job·MQ）、前端（API）的**对接清单**，受众不关心实现细节。主 Agent 编写指引见 `prompts/agents.md`；产出物命名见 `generated/templates.md`。

## 流程
1. 确认目标需求已有可汇总内容（通常至少进入开发阶段）；**无阶段强制**。验收通过前执行产出的为当前变更快照，**验收通过后若内容有变须重新生成最终清单**。
2. **主 Agent 直接编写** `{工单根}change-manifest.md`（按 `prompts/agents.md` summary 模板，只读本里程碑产物 + 定向 grep 实际代码；不派子 agent）。**若 `{配置目录}templates/change-manifest.md` 存在（语言模板，{skills.arch_rules} 生成），Job·MQ 块按其结构产出**（java 的 MQ topic/tag/consumerGroup、php 的 Event/Job），否则用下文通用模板。
3. **★ 子 agent 返回后必须呈现结果**：读生成文件 → 输出三块条数摘要（DDL N 张表 / 队列 M 个 / API K 个）+ 文件路径，禁止静默结束。

多里程碑：每个里程碑各出一份；需求全部里程碑 COMPLETED 后可再出一份需求级合并清单（把各里程碑三块拼起来，标注来源里程碑）。

## change-manifest.md 模板

````markdown
# {需求ID} — 交付对接清单

- 影响模块: {模块列表}
- 生成时间: {YYYY-MM-DD}

## 一、DDL 变更（DBA）

### {表名} — 新建

```sql
CREATE TABLE `{表名}` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(64) NOT NULL DEFAULT '' COMMENT '名称',
  -- ...
  PRIMARY KEY (`id`),
  KEY `idx_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{表注释}';
```

### {表名} — 变更

```sql
ALTER TABLE `{表名}` ADD COLUMN `{字段}` varchar(32) NOT NULL DEFAULT '' COMMENT '{注释}' AFTER `{前字段}`;
ALTER TABLE `{表名}` ADD INDEX `idx_{字段}` (`{字段}`);
```

> 无 DDL 变更时写「本次无 DDL 变更」。

## 二、Job·MQ 变更（运维）

| 类型 | 名称 | 说明 |
|------|------|------|
| 定时任务 | {job_name} | {触发说明} |
| 队列/事件 | {queue_name} | {消费说明} |

> 本块为**通用兜底模板**；若 `{配置目录}templates/change-manifest.md` 存在，按语言模板的 Job·MQ 结构产出（java 含 MQ Topic/Tag/ConsumerGroup + 定时任务；php 含 Event/Job + 定时任务）。无新增队列时写「本次无新增队列」。

## 三、API 接口清单（前端）

| Method Path | 入参 | 出参要点 | 用途 |
|-------------|------|---------|------|
| POST /api/xxx | field1:string(必填), field2:int | {要点} | {一句话} |

> 无新增/变更接口时写「本次无接口变更」。
````

> 与验收报告的区别：summary 是面向下游的交付清单（机器可执行的变更点），验收报告是质量结论。
