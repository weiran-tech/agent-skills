# Preflight — 流程启动前置检查

> 仅 `/workflow start` 执行。按顺序逐项检查，任何 `blocking: true` 项未通过立即终止并输出错误与修复指引，不创建需求。其他子命令不执行 preflight。

## 检查清单

### 1. rules-dir — 项目规则目录
| 字段 | 值 |
|------|------|
| id | `rules-dir` |
| check | `.claude/rules/` 目录存在且包含至少一个 `.md` 文件 |
| blocking | true |
| error | 项目缺少 `.claude/rules/` 规则目录，workflow 无法确定测试命令和编码规范 |
| fix | 先执行 `{skills.arch_rules}` skill 生成项目规则，再启动 workflow |

### 2. automation-policy — 自动化策略有效
| 字段 | 值 |
|------|------|
| id | `automation-policy` |
| check | `{项目根}.claude/workflow/config.yml` 存在且按 `model/config.schema.json` 校验通过 |
| blocking | true |
| error | 自动化 Profile 不存在或不符合当前 Schema |
| fix | 执行 `/workflow config guarded`（或 `manual` / `autonomous`） |

## 执行协议
1. 按编号顺序逐项检查。
2. blocking 项失败即终止：输出该项 error + fix，不继续、不执行命令。
3. 全部通过后输出一行确认（如 `✓ preflight passed`），继续正常逻辑。
4. 新增检查项只需在"检查清单"追加条目，SKILL.md 无需修改。
