---
name: repo-api-scan
description: 扫描项目接口，按模块/业务域整理功能清单大纲并输出到 .md 文件。支持 PHP/Laravel 和 Java/Spring Boot。当用户说 "api-scan"、"功能清单"、"接口扫描"、"feature scan"、"功能大纲" 时触发。
---

# API Scan

扫描项目全部接口端点，按业务模块分组，生成功能清单大纲。只关注"做什么"，不分析实现细节。

## 第一步：识别项目类型

按优先级检测：

| 标志文件 | 项目类型 |
|---------|---------|
| `composer.json` + `modules/` 目录 | PHP / Laravel 模块化 |
| `composer.json`（无 modules） | PHP / Laravel 单体 |
| `pom.xml` 或 `build.gradle` | Java / Spring Boot |

检测失败时询问用户。

## 第二步：扫描接口

### PHP / Laravel

1. **模块化项目**：遍历 `modules/*/src/Http/Routes/*.php`，提取 `Route::any/get/post/put/delete/patch` 的 URI 和控制器方法
2. **单体项目**：扫描 `routes/*.php`
3. 读取控制器类（`modules/*/src/Http/Request/**/*Controller.php` 或 `app/Http/Controllers/`），提取 public 方法名
4. 用 URI 路径 + 方法名推断功能点名称

### Java / Spring Boot

1. 搜索所有 `@RestController` / `@Controller` 类
2. 提取类级 `@RequestMapping` 作为路径前缀
3. 提取方法级 `@GetMapping` / `@PostMapping` / `@PutMapping` / `@DeleteMapping` / `@RequestMapping` 的路径和 HTTP 方法
4. 用路径 + 方法名推断功能点名称
5. 按 Maven/Gradle 子模块或包路径分组

### 功能点命名规则

从接口路径和方法名推断中文功能名称，例如：
- `POST auth.login/1.0` → 用户登录
- `GET /api/account/bid/my` → 我的竞价列表
- `DELETE /category/{id}` → 删除分类

无法推断时保留原始路径 + 方法名。

## 第三步：分组整理

按以下层次组织：

```
模块/业务域
  └── 功能组（按控制器或路径前缀）
        └── 功能点（一个接口 = 一个功能点）
```

**模块来源**（翻译为中文，无法推断时才保留英文）：
- PHP：`modules/` 目录名翻译，如 `account` → 账户、`finance` → 财务、`market` → 市场
- Java：Maven 子模块名或顶层包名翻译，如 `kjs-auth` → 认证、`kjs-order` → 订单

**功能组来源**（不能直接用模块名，需实际分析）：
- PHP：按 Controller 类名拆分，如 `BidController` → 竞价、`GameController` → 游戏
- Java：按 Controller 类名或路径前缀拆分，如 `AuthController` → 认证登录、`CaptchaController` → 验证码
- 同一个 Controller 内方法职责差异大时，可按路径前缀再细分

## 第四步：生成文档

输出文件：项目根目录下 `docs/feature-list.md`（目录不存在则创建）。

所有模块合并为一张表格，通过「模块」和「功能组」列区分归属，便于后续导出 Excel。

格式：

```markdown
# {项目名} 功能清单

> 接口总数：{N}

| 模块 | 功能组 | 功能点 | 接口 | 方法 |
|------|--------|--------|------|------|
| 账户 | 竞价 | 我的竞价列表 | /api/account/bid/my | POST |
| 账户 | 竞价 | 创建回收竞价 | /api/account/bid_recycle/create | POST |
| 认证 | 登录 | 用户登录 | auth.login/1.0 | POST |
| 认证 | 登录 | 支付宝App登录 | auth.aliAppLogin/1.0 | POST |
| 认证 | 验证码 | 发送验证码 | captcha.send/1.0 | POST |
```

## 第五步：输出摘要

完成后输出：
- 检测到的项目类型
- 模块数 / 功能组数 / 接口总数
- 文件路径
