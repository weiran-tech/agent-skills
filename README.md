## 安装

```
npx skills add weiran-tech/agent-skills --skill nuxt3-qa-analysis
```

## 清单说明

```
# Nuxt / 前端
| nuxt3-qa-analysis | Nuxt3 项目分析 |

# Weiran 框架
| weiran-openapi-writer | OpenAPI 文档写作 |
| weiran-project-qa-analysis | 项目分析 |

# 其他
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

