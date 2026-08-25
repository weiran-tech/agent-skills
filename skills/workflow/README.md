# Workflow — 单体多模块需求开发全流程编排

模型驱动状态机的开发流程 skill。把"需求讨论 → 分析设计 → 开发 → 审查 → 验收"串成一个统一入口。**确定性内核（状态机 / Policy / 不变量）由 `model/` + `engine/` 执行**，灵活编排（agent 调度、并行判断、裁决对话）由 LLM 按 `references/` 驱动。

面向单体项目：代码同仓，审查按任务工作范围过滤 diff，架构上下文取自项目文档目录（`{skills.arch_analyzer}` 产出）。测试/校验命令由项目 `.claude/rules/` 中的规则定义，workflow 不硬编码具体命令和目录结构。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **CR 状态机拆分** | `CR_PLANNED → CR_SCANNED → CR_JUDGED → (CR_PASSED / CR_FIXING / CR_RECHECKING / AUTONOMOUS_BLOCKED)` |
| **独立 Judge 裁决** | 统一报告后逐条裁决 `ACCEPTED/REJECTED/MODIFIED/DESIGN_REWORK/UNCERTAIN + confidence`，处置三档 `IMPLEMENT_FIX / BASELINE_ALIGN / DESIGN_REWORK`；低置信度/不确定 → 阻塞 |
| **修复后二次审核（可配置）** | `CR_FIXING → CR_RECHECKING` 重跑 IMPLEMENTATION + Judge（其他维度按 `cr.levels` 派发），收敛才 PASSED；由 `cr.capabilities.recheck` 控制（默认开启，false = 只审核一次）。按严重度缩放：`cr.capabilities.minor_fix_auto_confirm`（默认 true）下纯 MINOR+IMPLEMENT_FIX 修复带质量门证据直接确认，`fixed_has_major`/`fixed_has_baseline_align` 仍强制重审 |
| **可信终态** | 任务级 `AUTONOMOUS_BLOCKED`（无法证明安全完成 → 保守停止 + 证据保存）；里程碑级 `AUTONOMOUS_COMPLETED`（零阻塞 + 全质量门通过） |
| **客观证据门** | `CR_PASSED` 必须有 `quality_gate_evidence`；`CR_FIXING` 必须有 `fix_contract_path`（转换守卫 + 不变量，双保险） |
| **Preset 预设模板** | `configctl init --preset {manual\|guarded\|autonomous}` 把预设值烘焙成**全显式配置**；配置无 profile 运行时概念，fixed safety 不可覆盖 |
| **配置** | 域优先结构（`flow`/`cr`/`plan`/`accept`/`rework`）+ `skills`（外部 skill 映射）：各域 `limits` + `capabilities` + `cr.levels`（严重度）+ `cr.review.dimensions`（项目审核维度池）+ `cr.quality.judge` |

---

## 设计理念

| 原则 | 含义                                                                                                                                    |
|------|-----------------------------------------------------------------------------------------------------------------------------------------|
| **模型单一数据源** | `model/state-machine.yml` 是状态唯一权威；状态写入 `{工单根}state/workflow-state.yml`（statectl），`progress.md` 是派生视图，只读不手改 |
| **事件=证据，Decision=路由** | 事件名不承载方向；Policy 从 payload 证据字段推导路由（P1），Guard 只做结构校验（P3），方向只出现在 Decision                             |
| **阈值进 Policy** | `cr.quality.judge.min_confidence` / `cr.limits.fix_max` / `plan.limits.retry_max` 只由 Policy 裁决（guard 拿不到配置）                  |
| **修复后二次审核** | 修复后重跑 IMPLEMENTATION + Judge（其他维度按 `cr.levels` 派发）；`VERIFY_FAILED` 回重审而非直跳。由 `cr.capabilities.recheck` 控制（默认开启；false 时复验失败走 AUTONOMOUS_BLOCK；纯 MINOR+IMPLEMENT_FIX 修复 `minor_fix_auto_confirm=true` + 质量门证据则跳重审直接复验）               |
| **不变量机器执行** | 单门、plan-before-code、design-rework-exit、CR 契约/质量门证据、零阻塞终态，全部 machine-enforced                                       |
| **Preset 管初始化，配置管全部** | 预设（manual/guarded/autonomous）仅 init 模板；fixed safety 不可覆盖                                                                    |
| **可信终态兜底** | autonomous 只能进 `AUTONOMOUS_COMPLETED`（零阻塞 + 全质量门）或 `AUTONOMOUS_BLOCKED`，禁止"自动解释成通过"                              |
| **风险驱动审查** | 实现审查固定执行，安全、流程契约、性能 reviewer 按变更风险调度，独立汇总后由 Judge 统一裁决                                             |
| **设计错可回退** | rework 通道按根因层级（实现/设计/需求）回退 + 依赖级联重做；仅 `DESIGN_REWORK` 触发，`BASELINE_ALIGN` 只在 CR 内补基线、不回退                                                                              |

---

## 五阶段 + 质量门 主流程

```
  阶段1 需求讨论        /workflow start  → {skills.discuss} 多轮对话
     │ (产出 docs/discuss/{域}/{需求名}/discussion.md)
     ▼
  阶段2 分析与设计      /workflow next   → 单模块直调 architect / 多模块并行 analyst + 汇总设计
     │ (产出 analysis/、design-baseline.md、dev-tasks.md)
     ▼
 ┌─────────────────────────────────────────────────────┐
 │ 阶段3 设计审核门  ★人工★  DESIGN_REVIEW           │  ← 清单式审核，缺项打回阶段2
 │   /workflow approve                                 │
 └─────────────────────────────────────────────────────┘
     ▼
  阶段4 开发与逐任务审查  /workflow next  （见下方"任务级闭环"）
     ▼
  阶段5 收尾验收        /workflow next   → verifier 全量回归 + 一致性把关（只读，不改代码）
     │ (产出 acceptance/acceptance.md 问题清单)
     ├─ 通过 → COMPLETED（manual/guarded）或 AUTONOMOUS_COMPLETED（autonomous，零阻塞）
     ▼ 有问题
 ┌────────────────────────────────────────────────────┐
 │ 阶段5 验收确认门 ★人工★  ACCEPTING               │  ← 逐条裁决 ACCEPTED/REJECTED/MODIFIED
 │   /workflow approve                                │
 └────────────────────────────────────────────────────┘
     ▼
  自动修复已采纳项（accept.auto_fix 开启时）→ 重跑收尾验收
     ▼
  COMPLETED ──→ /workflow summary  → 交付清单 change-manifest.md（DDL / Job·MQ / API）
                ※ 任意阶段也可 /workflow summary（产出当前变更快照；验收通过后重出最终清单）

  ※ 阶段4/5 若发现设计/需求层缺陷 → /workflow rework 回退重做
```

---

## 阶段4 任务级闭环（每个任务独立走完）

```
TODO
 │ ⓪ 复杂度判断（Claude）
 ├─ SIMPLE ───────────────────────────────────────────────────┐
 ├─ NORMAL ───────────────────────────────────────────────────┤
 └─ COMPLEX → planner 出 plan/LLD → PLAN_READY                │
              ├──── VALIDATE_PLAN → plan-validator PASS ────┐ │
              └─ WAIT_USER_APPROVAL / 校验未通过            │ │
                 → plan 人工门 → /workflow approve ─────────┘ │
              ▼ PLAN_CONFIRMED                                │
 ┌────────────────────────────────────────────────────────────┘
 │ ① 编码 (executor；COMPLEX 对照已确认 plan)
 ▼ CODING
 │ ② DoD：模块级单测 + 语法/编译检查（按项目 .claude/rules/）
 ▼ TASK_DOD_PASSED → Policy
 ├─ SKIP_CR（guarded/autonomous + SIMPLE + Gate 通过）→ VERIFYING
 └─ RUN_CR
    │ ③ 风险调度 + 多维 CR (实现固定，其他维度按风险并行 → coordinator 统一汇总)
    ▼ CR_SCANNED
    │ ④ Judge 逐条裁决（ACCEPTED/REJECTED/MODIFIED/DESIGN_REWORK/UNCERTAIN + confidence）
    │    处置三档：IMPLEMENT_FIX / BASELINE_ALIGN / DESIGN_REWORK（判别见下方专节）
    ▼ CR_JUDGED → Policy 分流
    ├─ CONFIRM_CR ────────────────────────────► CR_PASSED
    ├─ FIX_CR_ISSUES → 先落修复契约 → CR_FIXING
    │     └─ 含 BASELINE_ALIGN：修复契约强制带基线对齐段
    ├─ REQUEST_DESIGN_REWORK → /workflow rework（仅 DESIGN_REWORK，不进 CR_FIXING）
    ├─ AUTONOMOUS_BLOCK → AUTONOMOUS_BLOCKED（低置信度/不确定）
    └─ WAIT_USER_APPROVAL → CR 人工门（/workflow approve）
    ▼ CR_FIXING → REWRITE_COMPLETED
    │  ├─ 纯 MINOR+IMPLEMENT_FIX + minor_fix_auto_confirm + 质量门证据 → CR_PASSED（跳重审）
    │  └─ fixed_has_major / fixed_has_baseline_align → CR_RECHECKING
    ▼ CR_RECHECKING ⑤ 重跑 IMPLEMENTATION + Judge（其他维度按 cr.levels 派发）
    ▼ CR_RECHECKED → Policy 分流
    ├─ CONFIRM_CR → CR_PASSED（须 quality_gate_evidence）
    ├─ FIX_CR_ISSUES → CR_JUDGED（下一轮，cr_round 自动递增；达 cr.limits.fix_max 熔断）
    └─ AUTONOMOUS_BLOCK → AUTONOMOUS_BLOCKED（质量劣化 → 回滚 + 阻塞）
    ▼ CR_PASSED → TASK_CR_PASSED
    ▼ VERIFYING
    ├─ VERIFY_PASSED → DONE
    └─ VERIFY_FAILED → CR_RECHECKING（fix 相关）/ AUTONOMOUS_BLOCKED（无关）
```

> **重审按严重度缩放**：`REWRITE_COMPLETED` 后 `fixed_has_major=true` 或 `fixed_has_baseline_align=true` 必进 CR_RECHECKING；纯 MINOR+IMPLEMENT_FIX 且 `cr.capabilities.minor_fix_auto_confirm=true` + `quality_gate_evidence` → 直接 CR_PASSED 进复验（凭修复契约边界 + 质量门证据兜底）。
> **CR 角色隔离**：主 Agent 先产出可追溯的 review-plan；被调度的 reviewer 只产出维度报告；coordinator 只校验、去重、汇总；Judge 独立裁决；executor 只按修复契约改。均不修改代码。
> **客观证据门**：Judge 判 clean 前必须产出 `quality_gate_evidence`（模块测试/编译/scope 检查结果）；进修复前必须产出 `fix_contract_path`（允许改的文件/符号/禁止项）。
> **进度回写是阻塞步骤**：每次状态流转都经 `statectl` 即时写回 `workflow-state`；不回写不得推进下一任务。

---

## CR 处置三档：IMPLEMENT_FIX / BASELINE_ALIGN / DESIGN_REWORK

Judge 对每条问题先裁 `verdict`，再按判别树落到处置档：

```
每条问题
  ├─ Q1: 修复是否要动 design-baseline？
  │     ├─ 否 ─────────────────────────────► IMPLEMENT_FIX（纯实现修复）
  │     └─ 是 ──► Q2: 是否改变契约值（接口签名 / 事件名 / 状态码 / 数据模型），
  │                 或牵动其他任务设计 / 核心流程 / 跨模块契约？
  │              ├─ 否（只补既定意图的落地记录）──► BASELINE_ALIGN（修实现 + 基线文档追齐）
  │              └─ 是 ───────────────────────► DESIGN_REWORK（设计/契约要改）
```

| 处置 | 改什么 | 通道 | 里程碑 |
|------|--------|------|--------|
| `IMPLEMENT_FIX` | 只改实现 | CR_FIXING（普通修复契约） | 不动 |
| `BASELINE_ALIGN` | 实现 + design-baseline 补记（**不改任何契约值**） | CR_FIXING（修复契约强制带基线对齐段）→ executor 追齐基线 → 重审时 reviewer-design 复查基线 diff | 不动 |
| `DESIGN_REWORK` | 改设计/契约值 | rework → 受影响任务回 TODO → 重做阶段2 → 阶段3 重审 | 回退 ANALYZING |

- **锚定证据**：`DESIGN_REWORK` 必须指得出要改的具体契约值（design-baseline 哪段，from→to）或受牵动的下游任务编号；指不出的一律降为 `BASELINE_ALIGN` 或 `IMPLEMENT_FIX`。
- `BASELINE_ALIGN` 的 verdict 是 `MODIFIED` → 计入 `accepted_count`，不会被误判成 clean；`has_design_rework=false` 永不触发 rework。
- `CR_JUDGED` 分流顺序：uncertain→人工门 > 低置信度→人工门 > `has_design_rework`→rework > 零问题自动确认 > 兜底人工门。

---

## 内置预设（Preset）+ 全显式配置

配置**全显式**（无 profile 运行时概念）；`configctl init --preset {manual|guarded|autonomous}` 把预设值一次性烘焙进配置，之后可随意编辑。预设仅作为 init 模板（`model/presets.yml`），运行时 policy 只读配置里的显式值。

| 预设 | 阶段自动推进 | SIMPLE 跳 CR | Plan 自动校验 | 零问题 CR 确认 | MINOR 自动修 | 验收自动修 | AUTONOMOUS_COMPLETED |
|------|------|------|------|------|------|------|------|
| `manual` | NO | NO | NO | NO | NO | NO | NO |
| `guarded` | YES | YES | YES | YES | NO | YES | NO |
| `autonomous` | YES | YES | YES | YES | YES | YES | YES |

阶段3 设计审核固定为人工门，不属于预设可放宽的能力。
预设烘焙后即为普通配置：改 `cr.levels.zero.auto_confirm: false` 即可让零问题 CR 也等人工；改 `automation.advance_summary: true` 即启用 `AUTONOMOUS_COMPLETED`。

**外部 skill 映射（`skills` 块）**：workflow 按角色调用项目提供的 skill（讨论、规则/模板生成、架构分析），由 `config.yml` 的 `skills` 块配置，缺省为内置默认（`devops-discuss` / `arch-rules` / `arch-analyzer`）。不同语言/项目可换用各自的 skill 名，主 Agent 从 Automation Context 的 `skills` 段解析，文档占位符 `{skills.discuss}` / `{skills.arch_rules}` / `{skills.arch_analyzer}` 即指此。

### 示例：`configctl init --preset guarded` 生成的配置

完整示例见 `generated/example-guarded.yml`（由 `model/presets.yml` 渲染，带逐字段注释；**勿手改**，改预设后跑 `_internal/setup.sh` 同步）。等价产出：`configctl init --preset guarded`。

**不可覆盖的固定安全规则**：低置信度/不确定必须阻塞、设计根因必须 rework、CR_PASSED 必须质量门证据、自动修复仅限 MINOR+IMPLEMENTATION。任何配置组合下都强制。修复后二次审核由 `cr.capabilities.recheck` 配置（默认开启）。

---

## 里程碑（默认单里程碑）

- **默认**：一个需求 = 一个里程碑，整套 5 阶段直接在需求层跑，无需关心里程碑。
- **大需求**：用 `/workflow split` 按交付切片拆成多个里程碑。拆分后每个里程碑独立跑阶段 2→5，公共设计骨架（`design-foundation.md`）须先于各里程碑定稿；用 `#里程碑` 选择符分别推进。
- **拆分时机（强制）**：`split` 只能在开发开始前（任何任务启动前）执行——`validate.py --check-split` 返回 `ok:true` 才允许；一旦首个 `TASK_STARTED`，拆分窗口关闭，剩余任务仍属当前里程碑交付。**开发开始后不得中途拆里程碑**，否则已完成/未完成任务归属被撕裂、可能漏任务。
- **阶段4入口全量登记**：进入开发后首个动作是 `statectl init-tasks`，把 dev-tasks 全部任务一次性登记进状态（`{X.Y: {state: TODO, complexity}}`）；此后"全部任务 DONE"按完整计划集判定，dev-tasks 规划的任务一个都不能漏。

---

## rework 返工通道

开发+CR 完成后发现设计/实现有根本性问题时用。按根因层级决定回退深度：

| 根因层级 | 含义 | 回退动作 | 重跑范围 |
|---------|------|---------|---------|
| 实现级 | 设计对、代码错 | 不动设计契约（`IMPLEMENT_FIX` 不碰基线；`BASELINE_ALIGN` 仅补记基线、不改契约值） | 受影响任务回 TODO → 重 code → 重 CR |
| **设计级** | design-baseline 错 | 标返工修订 → 退回阶段2修订 → 阶段3重审 | 受影响任务 + 依赖该设计的下游任务级联回 TODO（复杂任务重出 plan）|
| 需求级 | 需求本身错 | 回阶段1 重新讨论 | 视讨论结论，可能整体重来 |

依赖扩散：自动从 dev-tasks 依赖图算出下游受影响任务，**列给人工确认**后才标重做；未受影响的 DONE 任务保留。

> 边界：只改当前任务能解决 → `IMPLEMENT_FIX` / `BASELINE_ALIGN` 走 CR 修复；牵动设计或别的任务 → `DESIGN_REWORK` 走 rework。CR 裁决 `has_design_rework=true`（或 `REQUEST_DESIGN_REWORK`）时必须走 rework；`BASELINE_ALIGN` 不进 rework。

---

## 命令速查

| 命令 | 作用 |
|------|------|
| `/workflow use [需求ID][#里程碑]` | 设定活动上下文（粘性），之后裸命令默认作用于它 |
| `/workflow start {需求名}` | 创建需求，进入阶段1讨论（自动设为活动）|
| `/workflow next [需求ID][#里程碑]` | 推进到下一阶段 / 下一个任务（省略=活动上下文）|
| `/workflow approve [需求ID][#里程碑]` | 确认当前人工门（设计审核 / plan / CR 裁决 / 验收裁决，按状态自动分发）|
| `/workflow status [需求ID][#里程碑]` | 查看进度（默认附带 validate.py 不变量校验；违规必须停）|
| `/workflow list` | 列出未完成的需求 |
| `/workflow split [需求ID] {里程碑列表}` | 大需求拆里程碑 |
| `/workflow rework [需求ID][#里程碑]` | 任务调整：缺陷返工（按根因层级回退）或补充任务（当前需求内新增子任务，牵动设计自动回退 DESIGN 门） |
| `/workflow summary [需求ID][#里程碑]` | 产出交付清单（DDL / Job·MQ / API）给 DBA 与前端 |
| `/workflow hotfix {bug描述}` | **轻量 bug 修复**（不走 5 阶段状态机，独立小流程） |
| `/workflow config [manual|guarded|autonomous]` | 初始化或校验自动化 Profile（配置） |

- 自动化配置路径是 `{项目根}.claude/workflow/config.yml`（version + mode + 域块 flow/cr/plan/accept/rework，严格 Schema v2，全显式）。
- **需求 ID** = `{域}/{需求名}`（如 `order/订单取消优化`），与 `docs/discuss/` 目录一致。
- **`#里程碑`** 仅多里程碑需求需要（如 `payment/支付渠道重构#alipay`）。
- **活动上下文（推荐）**：`/workflow use` 选一次当前在搞的需求/里程碑（存于 `{项目根}.claude/workflow/active`），之后裸命令省略参数即默认指向它。
- 模糊匹配：`use` / 显式传参支持前缀子串，唯一即定位；省略且无活动上下文时唯一进行中的自动选中，多个则列出让你选。

---

## 使用示例

### 示例一：普通需求（单里程碑，最常见）

```bash
# 1. 起需求，进入讨论
/workflow start 订单取消优化
#   → 询问业务域=order，多轮讨论，产出 discuss/order/订单取消优化.md

# 2. 分析与设计
/workflow next
#   → 状态停在 DESIGN_REVIEW，给出设计审核清单自查结论

# 3. 设计审核门（你逐项核对必含清单）
/workflow approve
#   → design-baseline 标 APPROVED，进入开发

# 4. 开发：逐任务闭环（NORMAL 任务）
/workflow next
#   → 任务1 编码完成、CR 扫描 → Judge 裁决出问题清单，停在 CR 人工门（guarded）或自动修复（autonomous）
#   guarded 下你裁决：#1 ACCEPTED、#2 REJECTED(理由)、#3 MODIFIED(说明)
/workflow approve
#   → 落修复契约 → executor 修已采纳项 → 重跑 reviewer + Judge 重审 → 复验绿 → 任务1 DONE

/workflow next       # 推进任务2…… 直到全部 DONE

# 5. 收尾验收（verifier 全量单测 + 语法/编译 + 跨模块一致性）
/workflow next
#   → 通过则 COMPLETED（guarded）或 AUTONOMOUS_COMPLETED（autonomous，零阻塞）
#   → 有问题则停在验收人工门，你逐条裁决
/workflow approve
#   → 修已采纳项 → 重跑验收
```

### 示例二：大需求（多里程碑 + 复杂任务 plan 门）

```bash
/workflow split payment/支付渠道重构 alipay,wechat
#   → 确认 alipay/wechat 划分 + 抽出 design-foundation.md（公共骨架，先定稿）

/workflow use payment/支付渠道重构#alipay     # 选一次活动上下文，之后裸命令默认指向它

/workflow next        # 阶段2 分析设计 → DESIGN_REVIEW
/workflow approve     # 设计审核通过

/workflow next        # 阶段4：某任务判为【复杂】→ planner 出 plan，停在 PLAN 门
/workflow approve     # plan 确认 → 编码 → CR 扫描 → Judge 裁决 …

/workflow use #wechat # 切到另一个里程碑
/workflow next

/workflow status      # 看进度（活动高亮 + 全局进度表 + 不变量校验）
```

### 示例三：需求完成后追加功能 → start 新需求

```bash
/workflow start 订单取消原因统计
#   → 全新需求，从阶段 1 讨论走标准 5 阶段（不复用已完成的订单取消优化上下文）
```

### 示例四：收尾验收发现设计错 → rework

```bash
/workflow rework payment/支付渠道重构#alipay
#   → 确认根因层级 = 设计级
#   → design-baseline 标 "## 返工修订 R1"，里程碑退回阶段2
#   → 自动算出依赖该设计的下游任务，列给你确认（可增删）
#   → 确认后这些任务回 TODO(标 返工R1)，未受影响的 DONE 保留

/workflow next payment/支付渠道重构#alipay     # 阶段2 修订 design-baseline
/workflow approve payment/支付渠道重构#alipay  # 阶段3 重审通过
/workflow next payment/支付渠道重构#alipay     # 复杂任务重出 plan → 重 code → 重 CR
```

### 示例五：轻量 bug 修复 → hotfix

```bash
/workflow hotfix "下单接口偶发 500，日志显示 NPE"
#   → 不走 5 阶段状态机，独立轻量流程：定位 → 修 → 测试 → 汇报
#   → 能力 hotfix.simple_skip_cr 开启且 SIMPLE Gate 通过（含非空转回归测试）时跳过单维度 CR
```

---

## 产出物目录

```
.claude/workflow/
  config.yml                     # 自动化配置（v2 域结构 + mode + skills，全显式，committed）
  active                         # 活动上下文指针（单行 {需求ID}[#里程碑]）
  repo-paths                     # 执行仓名 → 本地路径映射（仅 dual 模式）
  templates/                     # 产出文档模板（design-package / change-manifest，{skills.arch_rules} 生成）
docs/discuss/
  {域}/{需求名}/
  discussion.md                  # 阶段1 讨论文档
  docs/                          # 需求级参考文档（业务说明、接口文档、原始材料，用户手动放入）
  .task/
    state/                       # 机器控制面（statectl / validate 读写，Agent 不手改）
      workflow-state.yml         # ★机器状态源（statectl 写，validate.py 校验）
      transition.log             # 追加式转换日志（审计/恢复副产物）
    progress.md                  # 派生视图（progress_render 生成，人工只读不手改）
    analysis/                    # 阶段2 逐模块分析
    design-baseline.md          # 阶段2 设计基线（共识/契约层，必含清单）
    dev-tasks.md                 # 阶段2 任务拆分（标注 简单|普通|复杂 + 依赖）
    plans/                       # 阶段4 复杂任务的 plan/LLD
    done/                        # 阶段4 各任务完成标记
    review/                      # 阶段4 CR：一个任务一个目录，产物内聚
      {范围标签}-{X.Y}/          # review-plan.md + 维度报告 + fix-contract.md + unified.md
    rework/                      # 返工单（缺陷返工时才有）
    acceptance/                  # 阶段5 验收报告目录
      acceptance.md              # 收尾验收报告
    change-manifest.md           # /workflow summary 交付清单
  # 多里程碑时，analysis/design-baseline/dev-tasks/plans/done/review/rework 下沉到
  # .task/milestones/{里程碑}/，design-foundation.md 留在 .task/ 根作公共骨架
```

---

## 依赖与约定

- **依赖 skill/agent**：`{skills.discuss}`（阶段1）、`{skills.arch_analyzer}`（架构文档）、`analyst`/`architect`/`planner`/`plan-validator`/`executor`/`reviewer-implementation`/`reviewer-security`/`reviewer-design`/`reviewer-performance`/`reviewer-coordinator`/`reviewer-judge`/`verifier`（agents）。外部 skill 名由 `config.yml#skills` 配置，缺省同内置默认。
- **测试/校验**：验收基线 = 按项目 `.claude/rules/` 定义测试命令执行模块级单测通过 + 语法/编译检查通过。质量门证据（`quality_gate_evidence`）记录这些确定性检查结果。
- **单仓库单分支**：共用一条 feature 分支，diff 按任务工作范围隔离；**无独立分支/PR**。
- **架构规则**：遵守项目 `CLAUDE.md` 与 `.claude/rules/` 的架构与编码规范。
- **产出物只落项目内** `docs/discuss/{域}/{需求名}/.task/`，禁止写入 home 或仓库外。
- **Bash 约束**：所有 agent prompt 必须含"禁止 for/while/if/case/here-doc/嵌套 $()"；产出物只落项目内。

---

## Skill 目录与职责

```
claude/skills/workflow/
├── SKILL.md                  # 薄路由器：命令速查 + 强制前置 + 流程护栏 + references 索引
├── README.md                 # 使用说明（本文档）
├── model/                    # 确定性模型（唯一权威，零依赖）
│   ├── state-machine.yml     # 状态机：状态 / 事件 / 转换 / 终态
│   ├── policy.yml            # Profile 能力 + 决策矩阵 + 固定安全规则
│   ├── events.schema.json    # 事件 payload 契约（严格 Schema）
│   ├── config.schema.json    # 配置 Schema（v2 域结构）
│   └── agent-contracts.yml   # 子 agent 输入输出契约
├── engine/                   # 纯函数引擎（无状态副作用，不读写文件）
│   ├── state_machine.py      # 状态机加载（transitions 分组扁平化）+ 转换应用
│   ├── policy.py             # Policy 决策解析（安全谓词求值，非 eval）
│   ├── invariants.py         # 不变量检查（machine-enforced）
│   ├── render/               # 渲染包（docs=generated 文档 / progress=progress.md，纯函数）
│   └── vocab.py              # 词汇枚举常量（从 model 派生，代码禁止硬编码字面量）
├── adapters/                 # 运行时 CLI 适配器（I/O + 编排，调用 engine）
│   ├── statectl.py           # 状态控制：唯一转换写入口（写 workflow-state + transition.log）
│   ├── configctl.py          # 配置读写 / 校验（含 capabilities 单调校验）
│   ├── progress_render.py    # progress.md 派生视图生成
│   └── validate.py           # 不变量校验 CLI（status 默认附带）
├── references/               # LLM 编排指导（按需读，禁止据此推断状态/决策）
│   ├── stages/               # 各阶段执行细则（stage-1..5）
│   ├── protocols/            # 协议（agent-protocol / automation / reviewer-dispatch / …）
│   └── commands/             # 独立命令细则（fix / rework / summary / config）
├── prompts/                  # 子 agent prompt 模板
├── generated/                # 从 model 生成的派生文档（勿手改，_internal/generate_docs.py 管）
└── _internal/                # 非运行时：开发/维护/测试/设计史（skill 本体不接触）
    ├── setup.sh              # 一键重建 + 校验（生成 + lint + 测试）
    ├── generate_docs.py      # generated/ 再生成（改 model/ 后运行；--check 漂移检测）
    ├── lint/                 # 一致性检查包（`python3 -m _internal.lint`：词表 + model 元数据）
    ├── tests/                # 单元测试（state_machine / policy / invariants / lint / …）
    ├── state-v2.md           # v2 设计评审（历史）
```

### 分层职责（核心设计）

| 层 | 职责 | 约束 |
|----|------|------|
| **model/** | 确定性真相：状态、事件、决策、配置、契约 | **唯一权威**；禁止在代码/文档里复制模型数据 |
| **engine/** | 纯函数：加载、校验、转换、裁决、不变量、词汇枚举（model 派生） | 无状态副作用；不读写文件（I/O 在 adapters）；`vocab.py` 枚举禁止手写字符串 |
| **adapters/** | 运行时 CLI + 文件 I/O：提交事件、读写状态、生成视图 | 只调 engine；不含业务规则 |
| **references/** | LLM 编排指导：主 Agent 怎么调度 agent、怎么执行 | 按需读；禁止据此推断状态/决策 |
| **generated/** | 从 model 派生的文档 | 勿手改；改 model/ 后运行 `_internal/setup.sh` 一键重建（生成 + lint + 测试），或手动 `_internal/generate_docs.py` + `python3 -m _internal.lint` |
| **SKILL.md** | 薄路由器：命令入口 + 强制前置 + 护栏 + 索引 | 不承载状态/决策细节 |
| **_internal/** | 开发/维护/测试/设计史（重建、校验、单测、历史评审） | **非运行时**；skill 本体不读取；改 model/ 后在此跑 `setup.sh` |

> **一句话**：`model/` 定义"该发生什么"，`engine/` 执行确定性逻辑，`adapters/` 提供命令入口，`references/` 指导主 Agent 编排，`generated/` 消灭文档漂移；`_internal/` 是开发侧（skill 运行时不接触）。

### 快速索引

| 内容 | 位置 |
|------|------|
| 状态机（唯一权威） | `model/state-machine.yml` |
| 事件 payload 契约 | `model/events.schema.json` |
| Profile / 决策矩阵 | `model/policy.yml` |
| 配置 Schema | `model/config.schema.json` |
| Agent 契约 | `model/agent-contracts.yml` |
| 自动动作语义字典 | `references/protocols/automation.md` |
| 阶段执行细则 | `references/stages/` |
| 子 agent 调用规范 | `references/protocols/agent-protocol.md` |
| CR 风险调度 / coordinator | `references/protocols/reviewer-dispatch.md` |
