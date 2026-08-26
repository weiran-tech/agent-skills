## 安装

```sh
npx skills add weiran-tech/skills --skill devops-discuss
```

单个技能对应 `skills/<skill-name>/`，可按需单独安装，也可参考 `README.local.md` 手动软链到 `.claude/skills`。

## 命名约定

```
bun-*         # Bun 项目相关
java-ss-*     # Java 单体服务 (Standalone Service)
php-*         # PHP / Laravel 相关
fe-*          # 前端相关
devops-*      # 需求/统计/评审/工作流等研发流程相关
arch-*        # 架构分析与文档相关
weiran-*      # Weiran Framework (Laravel) 专用
```

## 技能清单

### 前端

| 技能 | 说明 |
| --- | --- |
| `fe-workflow` | 前端项目功能开发流水线总控：需求分析 → 技术设计(自审) → 编码 → 验证(Lint/Test/QA+CR) → E2E，按分支归档，支持断点恢复 |
| `fe-backend-page` | 生成后台管理项目（Vue3 + TDesign + kr36-ui）的标准增删改查页面 |
| `fe-kr36-ui-guide` | kr36-ui 组件库 API 参考指南（KrForm/KrTable/KrDialog/KrCard 等） |
| `nuxt3-qa-analysis` | Nuxt3 + Vue3 H5 项目系统化质量分析（组件规范、SSR、Pinia、测试覆盖等） |
| `bun-analyzer` | 分析 Bun 项目架构，生成 overview/business/flows 文档 |
| `bun-rules` | 为 Bun 项目生成标准化 CLAUDE.md + `.claude/rules/` |

### Weiran Framework / PHP

| 技能 | 说明 |
| --- | --- |
| `weiran-feature-module-workflow` | 功能模块全流程开发工作流：需求调研 → 技术需求文档 → 方案设计 → 开发 → 文档 → 测试 → 代码审查（七阶段，人工确认门控） |
| `weiran-openapi-writer` | 为 Weiran Framework / Laravel API 控制器生成或 dry-run 审查 OpenAPI Attributes 文档 |
| `weiran-project-qa-analysis` | Weiran Framework / Laravel 10 + PHP 8.2 项目级质量分析（代码质量/单测/架构三维度） |
| `php-workflow` | 伪多模块单体项目需求开发全流程编排（状态机驱动，串联 discuss → analyzer → team → code-review） |
| `php-analyzer` | 分析 PHP/Laravel 伪多模块项目服务架构，支持按模块单独分析 |
| `php-rules` | 为 PHP/Laravel 伪多模块项目生成标准化 CLAUDE.md + `.claude/rules/` |
| `php-openapi-writer` | 为 poppy 框架 API 控制器补全 OpenAPI/Swagger 注解与 FormRequest 类 |
| `php-api-scan` | 按模块/业务域扫描接口，生成功能清单大纲（支持 PHP/Java） |
| `php-dead-routes` | 按模块扫描已注释路由，全链路追踪关联代码，生成废弃接口清理报告 |
| `repo-api-scan` | 按模块/业务方/功能组三级扫描接口，生成功能清单大纲（支持 PHP/Java） |

### Java

| 技能 | 说明 |
| --- | --- |
| `arch-analyzer` | 分析 Java 微服务项目（多模块 Maven/Gradle）架构，生成服务文档 |
| `arch-aggregate` | 聚合 `arch-docs` 下所有服务文档，生成整体项目视图（业务流程、服务速查、MQ 事件全景图等） |
| `arch-publish` | 将当前微服务架构分析文档推送到系统架构汇总目录 `arch-docs` |
| `arch-rules` | 为 Java 微服务项目生成标准化 CLAUDE.md + `.claude/rules/` |
| `java-ss-analyzer` | 分析 Java 单体项目（多模块 Maven/Gradle）服务架构 |
| `java-ss-rules` | 为 Java 独立服务项目生成标准化 CLAUDE.md + `.claude/rules/` |

### 需求 / 工作流编排

| 技能 | 说明 |
| --- | --- |
| `workflow` | 单体多模块项目需求开发全流程编排（确定性内核 + LLM 编排），外部 skill 由项目 `config.yml#skills` 配置 |
| `devops-workflow` | 单体多模块项目需求开发全流程编排，自动调度 discuss/arch-analyzer/team/code-reviewer |
| `devops-discuss` | 需求变更讨论：多轮对话分析目标、现有流程、影响范围与改动方向，自动保存结构化文档 |
| `devops-task` | 根据需求讨论文档生成可执行开发任务清单 |
| `devops-userstory` | 根据服务流程/约定限制生成用户故事 |

### 云效（需求 / 测试用例）

| 技能 | 说明 |
| --- | --- |
| `devops-yunxiao-req-stats` | 云效需求评审结果统计 |
| `devops-yunxiao-req-lifecycle-stats` | 云效需求生命周期统计（未评审/本月创建关闭/已评审待计划，按产品类/技术类） |
| `devops-yunxiao-req-review` | AI 自动评审需求文档并输出结构化报告（完整评审 12 项 / 快速评审 5 项基线） |
| `devops-yunxiao-req-ai-review` | 调用 `devops-yunxiao-req-review` 对云效需求执行标准化评审，支持参数或交互式调用 |
| `devops-yunxiao-req-review-stats` | 云效指定迭代的需求评审结果统计（通过/未通过数量、负责人分布） |
| `devops-yunxiao-req-export-unplanned` | 导出云效项目中未排期/未完成的需求，支持产品类/技术类与多标签筛选 |
| `devops-yunxiao-bug-stats` | 云效「线上故障」工作项统计数据（服务端过滤 + `pagination.total`） |
| `devops-yunxiao-testcase-review` | AI 自动评审云效测试用例目录下所有用例，回写评审结果与优化用例 |
| `devops-yunxiao-testcase-import` | 将 AI 评审优化后的测试用例批量导入云效测试用例库 |

### 监控与统计报告

| 技能 | 说明 |
| --- | --- |
| `devops-project-report` | 独立项目日报汇总（bugs/req/sentry/sls/slow_log 一键聚合，按天归档输出） |
| `devops-sentry-exception` | 查询 Sentry 指定项目异常事件，按分组/阈值输出 Markdown 表格 |
| `devops-aliyun-sls-stats` | 阿里云 SLS 日志统计（PV 帕累托榜单 + P99 长尾告警），支持 nginx/apisix/k8s-ingress/spring-boot/custom 格式 |
| `devops-aliyun-sql-slow-log` | 阿里云 RDS 慢 SQL 统计报告，按 SQLHash 聚合，支持全表扫描分析、执行频率排行 |

## 使用说明

1. **按需安装**：单个技能用 `npx skills add weiran-tech/skills --skill <name>` 安装；本地开发可参考 `README.local.md` 软链到 `.claude/skills`。
2. **依赖凭证的技能**（`devops-aliyun-sls-stats` / `devops-aliyun-sql-slow-log`）需要提前 `export ALIYUN_PROFILE=<profile 名>`，脚本不会猜测或回退默认 profile，未设置会直接终止并列出可用 profile。
3. **`devops-project-report`** 是聚合入口，会按项目 `config.yaml` 中启用的模块（`req` / `bugs` / `sentry` / `sls` / `slow_log`）分别调用对应子技能，输出目录按天保留（`projects/{project}/QA/{YYYY-MM-DD}/`），补采不会覆盖已有的其他类型文件。
4. **工作流类技能**（`fe-workflow` / `php-workflow` / `weiran-feature-module-workflow` / `workflow` / `devops-workflow`）都是多阶段编排，支持断点恢复，具体阶段划分与产出物见各自 `SKILL.md`。
5. 各技能的详细参数、模板与示例见 `skills/<name>/SKILL.md`；部分技能附带 `scripts/` 与 `references/` 目录。

## 改动记录

| 日期 | 改动 |
| --- | --- |
| 2026-08-26 | 加固 devops 系列技能：`aliyun-sls-stats`/`aliyun-sql-slow-log` 增加凭证门禁（`ALIYUN_PROFILE` 强制 + 权限预检）与 P99 长尾告警；`project-report` 补充前置门禁与 `type:param` 语法、输出目录改为按天保留；`sentry-exception` 修正工具名为 `search_issues` 并补充截断下探；`yunxiao-bug-stats`/`req-stats` 计数查询统一为 `perPage: 0` |
| 2026-08-25 | 删除云效需求导入（`devops-yunxiao-req-import`）技能 |
| 2026-08-19 | 新增 `workflow`（模型驱动开发工作流）技能；统一技能文档命令前缀为 `/devops-*` |
| 2026-07-27 | `devops-workflow` 新增轻量 bug 修复工作流；拆分并重组 references |
| 2026-07-22 | `devops-workflow` 引入 preflight 检查与 `auto_summary` 交付方式 |
| 2026-07-16 | 新增 `php-openapi-writer` 技能文档 |
| 2026-07-14 | 新增 `devops-workflow`，用于结构化需求开发编排 |
| 2026-07-08~09 | 技能包整理：`dev-*` 前缀统一重命名为 `devops-*`；重构项目结构，遗留文档与技能迁移至统一 `skills/` 目录 |
| 2026-06-11 | 新增需求讨论 / 任务拆解 / 用户故事生成技能（`devops-discuss`、`devops-task`、`devops-userstory`） |
| 2026-05-25 | 新增全套 PHP 模块化项目架构工具链与文档模板（`php-analyzer`、`php-rules` 等） |
| 2026-05-13~16 | 新增云效需求评审技能（`devops-yunxiao-req-review`、`devops-yunxiao-req-ai-review`）及回写规范；`aliyun-sls-stats` 修复空值处理；`project-report` 性能优化 |

> 完整提交历史见 `git log -- skills/`。
