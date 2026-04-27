## 安装

```
npx skills add weiran-tech/agent-skills --skill nuxt3-qa-analysis
```

## 清单说明

```
# 前端
nuxt3-qa-analysis                : Nuxt3 项目分析
fe-backend-page                  : 后台页面
fe-kr36-ui-guide                 : UI 指南

# Weiran 框架
weiran-feature-module-workflow   : 功能模块全流程开发工作流（文档驱动七阶段）
weiran-openapi-writer            : OpenAPI 文档写作
weiran-project-qa-analysis       : 项目分析

# 架构
arch-analyzer                    : 架构分析
arch-publish                     : 架构发布


# 质量 / 工作流
project-report                   : 项目报告
sentry-exception-output          : Sentry 异常输出
yunxiao-bug-stats                : 云效 bug 统计
yunxiao-req-ai-review            : 云效需求 AI 审核
yunxiao-req-export-unplanned     : 云效需求导出未计划
yunxiao-req-import               : 云效需求导入
yunxiao-req-review-stats         : 云效需求审核统计
yunxiao-req-stats                : 云效需求统计
yunxiao-testcase-import          : 云效测试用例导入
yunxiao-testcase-review          : 云效测试用例审核
```

## 开发

**软链接**

软链接到本地的 skills 目录

```
ln -s ~/project/of/weiran-tech/agent-skills/skills/nuxt3-qa-analysis ~/.agents/skills/nuxt3-qa-analysis
```

**Claude --add-dir**

启动的时候添加目录

```
claude --add-dir ~/project/of/weiran-tech/agent-skills/skills
```

