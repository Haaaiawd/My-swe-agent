# mini SWE Agent 质疑报告 (Challenge Report) — Round 4

> **审查日期**: 2026-05-11
> **审查范围**: `.anws/v1/` 全部设计文档 + `05A_TASKS.md` + `05B_VERIFICATION_PLAN.md`
> **审查模式**: `FULL` — Design Review + Tasks Review 双重审查
> **审查方法**: 2 个并行子代理（DESIGN 维度 / TASKS 维度）+ 人工验证去重 + 与 Round 3 修复状态交叉验证 + Pre-Mortem 预演失败
> **累计轮次**: 4

---

## 问题总览

### 本轮审查结果

| 严重度 | 数量 | 摘要 | 状态 |
|--------|------|------|------|
| **Critical** | 1 | CH-R4-01: 防循环计数器（consecutive_format_errors）在状态机主循环中完全缺失 | 待修复 |
| **High** | 0 | — | — |
| **Medium** | 3 | CH-R4-02: VALIDATE 文档不一致；CH-R4-03: cost_estimate_per_call 配置缺定义；TK-R4-01: T3.1.6 验证计划缺失 | 待修复 |
| **Low** | 0 | — | — |

### 与历史轮次的对比

| 指标 | Round 1 | Round 2 | Round 3 | Round 4 | 累计 |
|------|:-------:|:-------:|:-------:|:-------:|:----:|
| Critical | 7 | 0 | 0 | **1** | 8 |
| High | 8 | 7 | 1 | 0 | 16 |
| Medium | 0 | 0 | 4 | **3** | 7 |
| Low | 0 | 0 | 1 | 0 | 1 |
| **Total** | **15** | **7** | **6** | **4** | **32** |

> **Round 3 修复状态验证**: 经人工交叉验证，Round 3 的 6 条问题已全部落地修复（见下文「Round 3 修复验证」）。本轮新发现的 Critical 问题（CH-R4-01）在 Round 3 中未被触及——因为它涉及状态机主循环的实现细节，而 Round 3 的审查重心在语义钉死和任务补充。

---

## 审查摘要

**整体判断**: ⚠️ **发现 1 个 Critical 问题，建议在修复后再进入 `/forge` 阶段**

Round 4 的双重审查结论：
- **设计维度**: 发现 1 个 Critical（防循环计数器缺失）+ 2 个 Medium（VALIDATE 文档不一致、配置默认值缺失）。防循环机制是 PRD 和 ADR 的硬性承诺，缺失会导致状态机无法正确终止。
- **任务维度**: 发现 1 个 Medium（T3.1.6 验证计划缺失），其余任务承接、验证覆盖、依赖关系均良好。
- **Pre-Mortem 结论**: 状态机错误分支的完备性是最大的单一风险领域。CH-R4-01 的缺失印证了 Pre-Mortem 中"异常传播路径需要系统性检查"的判断。

**高信号结论 (Round 4)**:
1. **防循环计数器完全缺失是本轮最大发现**: PRD US-001 边界条件5、ADR-003、core-agent.md L247 状态转换表均明确要求"连续 FormatError >= 5 时进入 UNKNOWN_ERROR 终态"，但 core-agent.detail.md §4.1 主循环伪代码中完全没有任何计数器逻辑。这是一个直接违反规范契约的 Critical 问题。
2. **VALIDATE 子步骤在 L0-L1 间存在结构性不一致**: core-agent.md 将 VALIDATE 列为状态机闭环的一个阶段，但 detail.md 中既没有 VALIDATE 状态，也没有 `validate_command` 的伪代码实现（§3.1b 不存在）。T2.2.3 任务要求实现 `validate_command`，但主循环中无调用点。
3. **配置默认值遗漏是细节但不可忽视**: `cost_estimate_per_call` 在成本上限预防性检查中被硬编码为 0.05，但 config 默认值中无此配置项，不同模型成本差异大。

---

## Round 3 遗留问题修复验证

| Round 3 ID | 问题 | 声称修复位置 | 验证结果 | 结论 |
|------------|------|-------------|---------|------|
| CH-R3-06 | 观测模板渲染失败降级策略 | core-agent.detail.md §3.3 L342-349 | try-catch ConfigError + fallback 到原始输出已落地 ✅ | **已修复** |
| TK-R3-01 | README 文档任务缺失 | 05A_TASKS.md S3 T3.1.6 | T3.1.6 任务已添加（06_CHANGELOG.md L56）✅ | **已修复** |
| TK-R3-02 | T1.1.1 循环依赖 | 05A_TASKS.md §T1.1.1 | 已删除 `--help` 可执行性要求，改为目录树验证 ✅ | **已修复** |
| CH-R3-08 | 步数定义歧义 | core-agent.detail.md §2 + 01_PRD.md | `increment_step()` 注释已钉死语义（L159-165）✅ | **已修复** |
| CH-R3-09 | 成本检查时机歧义 | core-agent.detail.md §4.1 MODEL 状态 | 预防性检查逻辑已添加（L498-504）✅ | **已修复** |
| CH-R3-10 | 终态映射文档不完整 | 01_PRD.md US-001 | 已补充 FATAL_CONFIG 和 UNKNOWN_ERROR 终态定义 ✅ | **已修复** |

---

## 子代理误判说明（人工校准后剔除）

DESIGN 子代理提出的以下指控，经人工验证**不成立**：

| 子代理 ID | 指控 | 不成立理由 | 结论 |
|-----------|------|-----------|------|
| D-H1 | 观测模板渲染失败仍不充分（CH-R2-06 重复） | Round 3 已明确采用降级策略（方案 A），06_CHANGELOG.md 已记录修复 | **不成立**（Round 3 已处理） |
| D-H2 | 成本上限检查时机存在二重性 | MODEL 预防性检查（CH-R3-09）+ OBSERVE 事后检查是防御性双保险，非 bug | **不成立** |
| D-M1 | 步数定义与增量时机歧义 | CH-R3-08 已钉死；`increment_step()` 注释与 `append_to_trajectory` 实现语义一致 | **不成立**（已修复） |

---

## 核心发现清单（Round 4 真实问题）

### Critical 级别

#### **[CH-R4-01] 防循环计数器（consecutive_format_errors）完全缺失**

| 属性 | 值 |
|------|-----|
| **类别** | 系统设计 / 运行模拟 |
| **严重度** | **Critical** |
| **契约/Pass** | 错误承诺 / Contract Missing |
| **位置** | `core-agent.detail.md` §4.1 状态机主循环（L482-617） |
| **发现** | PRD US-001 边界条件5 明确要求"连续 FormatError >= 5 次时进入 UNKNOWN_ERROR 终态"；ADR-003 定义了防循环机制；`core-agent.md` L247 状态转换表定义了"任意状态 \| 连续 FormatError >= max（默认 5） \| UNKNOWN_ERROR"。但在 `core-agent.detail.md` §4.1 主循环伪代码中，FormatError 处理分支（L523-530）仅有 `state = State.MODEL`，**没有任何 `consecutive_format_errors` 计数器的递增、归零或阈值检查逻辑**。 |
| **影响评估** | **根本性** — 若模型持续输出格式错误（如工具调用格式不稳定、围栏块嵌套等），状态机将无限循环（MODEL→PARSE→FormatError→MODEL→...），永不进入 UNKNOWN_ERROR 终态。这违反 PRD 的硬性承诺，且在实际运行中可能导致资源耗尽、API 费用失控、轨迹文件无限膨胀。 |
| **验证方式** | 1. 构造一个 Mock ModelAdapter，始终返回导致 FormatError 的响应；2. 运行状态机，观察是否超过 5 步后进入 UNKNOWN_ERROR；3. 实际结果：状态机会无限循环，不进入终态。 |
| **建议** | 在 `StateMachineContext` 中增加 `consecutive_format_errors: int = 0` 字段；在 PARSE 状态的 FormatError 分支（L523-530）中递增该计数器；在成功进入 EXECUTE 状态时归零；增加阈值检查：`if ctx.consecutive_format_errors >= config.get("max_consecutive_format_errors", 5): state = State.UNKNOWN_ERROR; break`。 |

---

### Medium 级别

#### **[CH-R4-02] VALIDATE 子步骤在 L0 与 L1 文档间不一致**

| 属性 | 值 |
|------|-----|
| **类别** | 系统设计 / 接口契约 |
| **严重度** | Medium |
| **位置** | `core-agent.md` L72（职责描述）、L283（操作契约表）；`core-agent.detail.md` 缺失 §3.1b |
| **发现** | `core-agent.md` L72 定义闭环为 "MODEL → PARSE → VALIDATE → EXECUTE → OBSERVE"，将 VALIDATE 列为状态机的一个阶段；操作契约表 L283 定义了 `validate_command(command)` 并引用 `[L1 §3.1b]`。但 `core-agent.detail.md` 中：1) 状态机主循环伪代码中没有 VALIDATE 状态（PARSE 后直接到 CONFIRM/EXECUTE）；2) 没有 §3.1b 章节；3) `validate_command` 的伪代码完全缺失。T2.2.3 任务要求实现 `validate_command`，但主循环中没有调用点。 |
| **影响评估** | 实现者不确定 VALIDATE 是独立状态还是 PARSE→EXECUTE 之间的函数调用。如果按 L0 理解为独立状态，则 L1 缺少实现；如果按 L1 忽略 VALIDATE，则 L0 的职责描述不准确，且 T2.2.3 的产出没有明确的消费位置。 |
| **验证方式** | 1. 搜索 `core-agent.detail.md` 中 "VALIDATE" 或 "validate_command" 的引用；2. 检查 §3 章节列表，确认无 §3.1b；3. 检查主循环伪代码中 PARSE→EXECUTE 的转换逻辑。 |
| **建议** | **方案 A（推荐）**: 在主循环中 PARSE→CONFIRM/EXECUTE 之前插入 VALIDATE 检查步骤（作为函数调用而非独立状态），并在 detail.md 中补充 §3.1b `validate_command` 的伪代码。**方案 B**: 修改 `core-agent.md` L72 的表述，将 VALIDATE 从"阶段"改为"子步骤/安全检查"。 |

#### **[CH-R4-03] cost_estimate_per_call 配置默认值未定义**

| 属性 | 值 |
|------|-----|
| **类别** | 系统设计 / 配置完整性 |
| **严重度** | Medium |
| **位置** | `core-agent.detail.md` §4.1 L501；`config.detail.md` |
| **发现** | 成本上限预防性检查使用 `estimated_next_call = config.get("cost_estimate_per_call", 0.05)`，但 `config.detail.md` 的默认配置中**没有定义 `cost_estimate_per_call` 字段**。该值被硬编码为 0.05 USD，而不同模型（如 gpt-4 vs gpt-3.5 vs Claude）的实际成本差异可达 10 倍以上。 |
| **影响评估** | 固定默认值可能导致：1) 对低成本模型过于保守，提前触发 LIMIT_COST；2) 对高成本模型过于激进，实际超支。影响 benchmark 的可复现性和成本控制准确性。 |
| **验证方式** | 搜索 `config.detail.md` 中 "cost_estimate_per_call" 或 "cost_estimate"。 |
| **建议** | 在 `config.detail.md` 默认配置中定义 `cost_estimate_per_call`，可按模型分级设置（如 gpt-4: 0.05, gpt-3.5: 0.005, 默认值: 0.01），或提供基于历史实际成本的自适应估算策略。 |

#### **[TK-R4-01] T3.1.6 验证计划缺失**

| 属性 | 值 |
|------|-----|
| **类别** | 任务承接 / 验证覆盖 |
| **严重度** | Medium |
| **位置** | `05B_VERIFICATION_PLAN.md` 全篇；`05A_TASKS.md` L536-555 |
| **发现** | T3.1.6（编写 README 完整文档）已在 `05A_TASKS.md` 中添加（06_CHANGELOG.md L56），但 `05B_VERIFICATION_PLAN.md` 中**缺少 T3.1.6 的验证条目**。验证计划中有 T3.1.1~T3.1.5 的详细验证说明，但没有 T3.1.6。 |
| **影响评估** | 文档任务无明确的验收标准和证据追踪路径，与其他任务的验证格式不一致。 |
| **验证方式** | `grep "T3.1.6" 05B_VERIFICATION_PLAN.md` → 无匹配。 |
| **建议** | 在 `05B_VERIFICATION_PLAN.md` 中补充 T3.1.6 验证条目：关联需求 REQ-010、验证类型手动验证、断言 README 覆盖 ADR 文档要求（安装、配置优先级、环境变量、退出码、风险警示）、证据为 `README.md` 文件内容。 |

---

## Pre-Mortem 关键结论

> 本次审查使用了 `sequential-thinking` 进行 Pre-Mortem 预演失败分析（ replay 见 `mini-swe-agent-pre-mortem-replay.md`）。

Pre-Mortem 识别的三大风险领域在本轮审查中得到印证：

1. **状态机错误分支的完备性** → **CH-R4-01 直接命中**：Pre-Mortem 第 1/5 步指出"状态机没有专门的错误分支，异常被泛化捕获"，而 CH-R4-01 发现 FormatError 防循环分支完全缺失，是比"泛化捕获"更严重的"完全缺失"。
2. **计数/上限语义的文档-代码一致性** → **CH-R4-03 命中**：Pre-Mortem 第 2/5 步指出"estimated_next_call 的计算策略不明确，预防性检查可能形同虚设"，CH-R4-03 发现 `cost_estimate_per_call` 配置缺定义，印证了计算策略的缺失。
3. **并发与文件 I/O 的鲁棒性** → 本轮未发现新增问题（Round 2 的 CH-R2-03/CH-R2-04 已修复）。

---

## 建议行动清单

### P0 — 必须在 forge 之前修复

1. **[CH-R4-01]** 在 `core-agent.detail.md` §4.1 主循环中补充 `consecutive_format_errors` 计数器逻辑，在 `StateMachineContext` 中增加字段，在 FormatError 分支递增、EXECUTE 分支归零，达到阈值进入 UNKNOWN_ERROR。

### P1 — 可在 forge 第一轮 Sprint 中修复

2. **[CH-R4-02]** 统一 L0/L1 文档中 VALIDATE 的定义：在 detail.md 中补充 §3.1b `validate_command` 伪代码，并在主循环中插入调用点；或修改 core-agent.md 的表述。
3. **[CH-R4-03]** 在 `config.detail.md` 默认配置中定义 `cost_estimate_per_call` 字段。
4. **[TK-R4-01]** 在 `05B_VERIFICATION_PLAN.md` 中补充 T3.1.6 验证条目。

---

## 最终判断

- [ ] **项目可继续，风险可控**
- [x] **项目需要修复 Critical 问题后再进入 `/forge`**

**判断依据**:

Round 1~3 的累计 28 个问题中，27 个已修复或已批准降级策略。Round 4 新发现 1 个 Critical + 3 个 Medium：

- **CH-R4-01 (Critical)**: 防循环计数器完全缺失，直接违反 PRD、ADR-003、core-agent.md 状态转换表的硬性承诺。不修复会导致状态机在 FormatError 场景下无限循环，这是不可接受的风险。
- **CH-R4-02 (Medium)**: 文档不一致，不影响功能但会导致实现困惑。
- **CH-R4-03 (Medium)**: 配置默认值缺失，影响成本控制的准确性。
- **TK-R4-01 (Medium)**: 验证计划缺失，影响文档任务的验收追踪。

**任务清单和验证计划的整体质量仍然良好**：
- 10 个 PRD 需求全部有任务承接 ✅
- 关键契约（状态机、动作协议、提交标记、轨迹格式、配置管理）均有验证覆盖 ✅
- ADR-002 的 P0 强制验收清单全部覆盖 ✅
- Sprint 划分可行，依赖关系清晰 ✅

**建议**: 优先修复 CH-R4-01（Critical，约 1-2 小时工作量），其余 3 个 Medium 问题可在 forge 启动后第一轮 Sprint 中同步修复。修复 CH-R4-01 后，项目可安全进入 `/forge`。

---

*报告生成方式：Pre-Mortem (sequential-thinking) + 2 个并行子代理分别审查 DESIGN / TASKS 维度 + 人工验证去重、与 Round 3 修复状态交叉验证、校准严重度后生成。*
