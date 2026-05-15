# mini SWE Agent 质疑报告 (Challenge Report) — Round 5

> **审查日期**: 2026-05-15  
> **TARGET_DIR**: `.anws/v1`  
> **REVIEW_MODE**: `CODE` — 用户明确要求静态代码审查  
> **静态边界**: 仅读取契约、源码、测试与 README；未启动项目、未运行测试、未连接外部服务  
> **执行说明**: `code-reviewer` 要求优先委派子代理，但当前宿主规则仅允许用户显式要求子代理时委派，因此本轮由当前会话完整执行 Lens 1-6  

---

## 问题总览

| 轮次 | 模式 | Critical | High | Medium | Low | 状态 |
|------|------|:--------:|:----:|:------:|:---:|------|
| Round 4 | FULL | 1 | 0 | 3 | 0 | 历史详细正文已归档；本轮仅继承为背景 |
| Round 5 | CODE | 0 | 3 | 2 | 0 | 待修复 |

**整体判断**: Partial Pass。核心状态机闭环、FormatError 防循环、成本统计、轨迹保存路径均有实现侧证据，但存在 3 个 High 级安全/控制契约漂移，继续交付前需要修复或由用户显式签收。

---

## 审查摘要

| 项目 | 结论 | 证据来源 |
|------|------|----------|
| 架构版本定位 | Pass | `.anws/v1` 是 `.anws/` 下最大版本目录 |
| 审查模式 | Pass | 用户要求 “code review”，判定 `REVIEW_MODE=CODE` |
| Design review | Skipped | CODE 模式下跳过设计专审，本轮仅将设计文档作为代码契约锚点 |
| Task review | Skipped | CODE 模式下跳过任务专审，本轮仅检查实现与 `05A/05B` 的兑现关系 |
| Code review | Partial Pass | Lens 1-6 已覆盖，发现 3 High + 2 Medium |
| 验证执行 | Not run | `code-reviewer` 规定纯静态，不运行测试 |

### 证据来源

| 类型 | 路径 |
|------|------|
| PRD | `.anws/v1/01_PRD.md` |
| ADR | `.anws/v1/03_ADR/ADR_003_ERROR_HANDLING.md`, `ADR_007_MODEL_ADAPTER_PROTOCOL.md`, `ADR_008_TRAJECTORY_FORMAT.md` |
| 系统设计 | `.anws/v1/04_SYSTEM_DESIGN/config.detail.md` |
| 任务与验证 | `.anws/v1/05A_TASKS.md`, `.anws/v1/05B_VERIFICATION_PLAN.md` |
| 实现 | `src/core/`, `src/cli/`, `src/config/` |
| 测试 | `tests/unit/`, `tests/integration/` |

---

## 契约模型摘要

| 类型 | 摘要 | 来源 | 失真风险 |
|------|------|------|----------|
| 结果 | CLI 参数必须真实影响 agent 行为，包含 `--exit-immediately` | `01_PRD.md:201`, `config.detail.md:68` | 参数只写入 config 但运行时不消费 |
| 安全 | `command.whitelist` 配置后仅允许白名单命令通过 | `ADR_003_ERROR_HANDLING.md:74`, `05B_VERIFICATION_PLAN.md:258` | 安全策略在 Validator 接口中缺席 |
| 安全 | 日志绝对不可包含明文密钥或敏感内容 | `01_PRD.md:250` | 模型调用日志打印消息内容片段 |
| 数据格式 | 轨迹 JSON 的 schema version 应与任务/验证契约一致 | `05A_TASKS.md:353`, `05B_VERIFICATION_PLAN.md:315` | 实现与测试共同固化为另一版本 |
| 错误 | ConfigError 诊断文件命名与可追踪路径须符合验收断言 | `05A_TASKS.md:454`, `05B_VERIFICATION_PLAN.md:393` | 实现和测试偏离验收命名 |

---

## Pre-Mortem 摘要

使用 `sequential-thinking` CLI 执行 5 步 audit，session 位于 `C:\Users\11341\AppData\Local\sthink\sessions\mini-swe-agent-code-challenge`。

| 失败原因 | 失真契约 | Root Cause | 证据 | 概率 |
|----------|----------|------------|------|------|
| 用户启用控制选项后 agent 继续多步执行 | CLI/config 结果契约 | `exit_immediately` 未进入状态机决策 | `src/cli/main.py:202`, `src/core/state_machine.py:223` | High |
| 用户配置白名单后非白名单命令仍可执行 | 安全契约 | Validator 无 whitelist 参数且状态机不传 config | `src/core/validator.py:35`, `src/core/state_machine.py:198` | High |
| INFO 日志泄露任务或命令输出中的敏感内容 | 安全/观测契约 | ModelAdapter 记录 message preview | `src/core/model_adapter.py:191`, `src/core/model_adapter.py:196` | Medium |
| 轨迹消费者按任务契约校验 schema 时失败 | 数据格式契约 | 实现与测试断言 `v1` 而任务/验证要求 `v1_jsonl` | `src/core/models.py:111`, `tests/unit/test_trajectory.py:38` | High |
| 测试证明当前实现而不是证明契约 | 验证承接 | 诊断文件与 schema 测试跟随实现漂移 | `tests/integration/test_cli_run.py:113`, `tests/unit/test_trajectory.py:82` | High |

---

## Lens 结果摘要

| Lens | 结论 | 证据 |
|------|------|------|
| L1 契约忠实度 | Partial | `--exit-immediately`、trajectory schema、ConfigError 诊断命名均与契约漂移 |
| L2 任务兑现与交付闭合 | Partial | 白名单模式、schema 版本、诊断文件断言未按 `05A/05B` 兑现 |
| L3 架构适配与复杂度健康 | Pass | Core/CLI/Config 边界总体清楚，未见阻断级耦合漂移 |
| L4 静态运行风险与安全边界 | Partial | 白名单未生效且模型消息内容进入 INFO 日志 |
| L5 验证证据与可观测性 | Partial | 多处测试验证实现现状而非验证计划断言 |
| L6 回流一致性与交接证据 | Partial | README 覆盖 E2E/live API 环境变量，但诊断命名和 schema 回流不一致 |

---

## 核心发现清单

| ID | 严重度 | Lens | 位置 | 发现 | 影响 | 建议 |
|----|--------|------|------|------|------|------|
| CH-R5-01 | High | L1+L4 | `src/cli/main.py:202`, `src/core/state_machine.py:223` | `--exit-immediately` 只写入 `cfg["agent"]`，状态机在 OBSERVE 后仍按普通循环返回 MODEL。 | 用户以为只执行首步时，agent 可能继续执行后续模型生成的 Shell 命令。 | 将该选项接入状态机或移除公共契约，并补覆盖首步后终止语义的集成测试。 |
| CH-R5-02 | High | L2+L4+L5 | `src/core/validator.py:35`, `src/core/state_machine.py:198` | ADR 和验证计划要求 `command.whitelist`，但 Validator 既无 whitelist 参数，状态机也未传入配置。 | 配置白名单时非白名单命令仍可能通过黑名单校验进入执行路径。 | 为 `validate_command` 增加 whitelist 参数，从 `cfg["command"]["whitelist"]` 传入并补 `grep` 被拒绝测试。 |
| CH-R5-03 | High | L4+L5 | `src/core/model_adapter.py:191`, `src/core/model_adapter.py:196` | ModelAdapter 在 INFO 级日志输出每条消息的前 120 字符。 | 用户任务、命令输出或工具反馈中的密钥片段可能绕过 ConfigManager 脱敏进入日志。 | 删除消息内容日志或默认仅记录 role/长度，并对 preview 走统一脱敏函数与测试。 |
| CH-R5-04 | Medium | L1+L2+L5 | `src/core/models.py:109`, `src/core/models.py:111`, `tests/unit/test_trajectory.py:38` | Trajectory 文档字符串写 schema v1_jsonl，但默认值和测试断言为 v1。 | 下游按 `05A/05B` 的 `v1_jsonl` 契约校验时会拒绝当前轨迹。 | 在 ADR/任务/实现中选定单一版本名并同步修改实现、测试与 checker 兼容说明。 |
| CH-R5-05 | Medium | L1+L6 | `src/cli/main.py:54`, `src/cli/main.py:64`, `tests/integration/test_cli_run.py:113` | T3.1.2 验收要求 `config_error_<timestamp>.txt`，实现和测试使用 `diagnostic_<timestamp>.json`。 | 配置失败证据路径与验收断言不一致，自动化交接或文档排障会找错文件。 | 统一为契约命名或正式修订 `05A/05B`，并让测试断言回到同一来源。 |

---

## Issues 明细

### CH-R5-01

`Severity` High | `Lens` L1+L4 | `Title` Exit-immediately Contract Drift | `Evidence` `01_PRD.md:201`, `config.detail.md:68`, `src/cli/main.py:202`, `src/cli/main.py:205`, `src/core/state_machine.py:223`, `src/core/state_machine.py:250` | `Impact` 用户请求首步后立即退出时仍可能继续进入下一轮 MODEL。 | `Minimum fix` 在 OBSERVE 后读取 `agent.exit_immediately` 并进入明确终态，或将 CLI 覆盖转换为 `step_limit=1` 并文档化。 | `Anchor` REQ-010 + Config default contract。

### CH-R5-02

`Severity` High | `Lens` L2+L4+L5 | `Title` Command Whitelist Missing | `Evidence` `ADR_003_ERROR_HANDLING.md:74`, `05A_TASKS.md:275`, `05A_TASKS.md:291`, `05B_VERIFICATION_PLAN.md:258`, `src/core/validator.py:35`, `src/core/state_machine.py:198`, `tests/unit/test_validator.py:14` | `Impact` 白名单配置无法限制命令集合，安全边界比文档承诺更宽。 | `Minimum fix` 实现 `validate_command(command, whitelist=None)`，从状态机传入配置并补白名单拒绝用例。 | `Anchor` ADR-003 command validation + T2.2.3/T223。

### CH-R5-03

`Severity` High | `Lens` L4+L5 | `Title` Sensitive Data Exposure via ModelAdapter Logs | `Evidence` `01_PRD.md:250`, `src/core/model_adapter.py:191`, `src/core/model_adapter.py:194`, `src/core/model_adapter.py:195`, `src/core/model_adapter.py:196` | `Impact` INFO 日志可能记录用户输入、命令输出或工具反馈中的密钥和隐私内容。 | `Minimum fix` 默认不记录 message content，必要时只记录长度/哈希或使用统一脱敏函数后再输出。 | `Anchor` PRD 6.2 data security + sensitive redaction contract。

### CH-R5-04

`Severity` Medium | `Lens` L1+L2+L5 | `Title` Trajectory Schema Version Drift | `Evidence` `05A_TASKS.md:353`, `05A_TASKS.md:361`, `05B_VERIFICATION_PLAN.md:315`, `05B_VERIFICATION_PLAN.md:513`, `src/core/models.py:109`, `src/core/models.py:111`, `tests/unit/test_trajectory.py:38`, `tests/unit/test_trajectory.py:82` | `Impact` 任务与验证承诺要求 `v1_jsonl`，实现与测试却发布 `v1`。 | `Minimum fix` 统一版本名并更新 `Trajectory.schema_version`、保存测试、读取兼容检查和文档。 | `Anchor` T2.2.6 + REQ-006 trajectory format。

### CH-R5-05

`Severity` Medium | `Lens` L1+L6 | `Title` ConfigError Diagnostic Filename Drift | `Evidence` `05A_TASKS.md:454`, `05B_VERIFICATION_PLAN.md:393`, `src/cli/main.py:54`, `src/cli/main.py:64`, `tests/integration/test_cli_run.py:113` | `Impact` 验收计划和实际诊断产物命名不一致，失败排障和自动收集会漂移。 | `Minimum fix` 按契约改为 `config_error_<timestamp>.txt`，或提交正式契约修订并同步测试与 README。 | `Anchor` T3.1.2 ConfigError diagnostic contract。

---

## 安全 / 测试覆盖补充

| 项目 | 结论 | 证据 |
|------|------|------|
| 破坏性命令黑名单 | Basically covered | `src/core/validator.py:21`, `tests/unit/test_validator.py:15` |
| 白名单安全模式 | Missing | `05B_VERIFICATION_PLAN.md:258` 有断言，但 `tests/unit/test_validator.py` 无对应用例 |
| 日志脱敏 | Insufficient | `ConfigManager` 有配置脱敏，但 `ModelAdapter` 消息日志不走脱敏 |
| FormatError 防循环 | Basically covered | `src/core/models.py:160`, `src/core/state_machine.py:178`, `tests/integration/test_format_error_loop.py:19` |
| 轨迹运行时统计 | Basically covered | `src/core/trajectory.py:75`, `tests/unit/test_trajectory.py:54` |
| E2E / live API | Cannot confirm | 静态审查只确认 README 提到 `MINI_SWE_ENABLE_E2E` 与 `MINI_SWE_ENABLE_LIVE_API` |

---

## 承诺闭合验证

| 维度 | 结论 | 证据 | 对应问题 |
|------|------|------|----------|
| 重复态 | Pass | FormatError 计数器与阈值存在 | 无 |
| 失败态 | Partial | ConfigError 退出码存在但诊断命名漂移 | CH-R5-05 |
| 默认态 | Partial | `exit_immediately` 默认存在但运行时未消费 | CH-R5-01 |
| 运行态 | Partial | OBSERVE 后无 exit-immediately 分支 | CH-R5-01 |
| 并发态 | Cannot confirm | batch 使用 ProcessPoolExecutor，未运行并发测试 | 无单列问题 |
| 观测态 | Partial | INFO 级消息 preview 存在敏感信息风险 | CH-R5-03 |
| 配置与密钥 | Partial | 配置脱敏存在，但消息日志不受保护 | CH-R5-03 |
| 接口 schema | Partial | 轨迹 schema 版本漂移 | CH-R5-04 |
| 验证承接 | Partial | 测试断言跟实现漂移而非契约 | CH-R5-02, CH-R5-04, CH-R5-05 |

---

## 建议行动

### P1 — forge / 交付前修复或显式签收

1. 修复 CH-R5-01：接入 `exit_immediately` 的真实运行语义，并补覆盖首步退出的测试。
2. 修复 CH-R5-02：实现 `command.whitelist` 并补白名单拒绝测试。
3. 修复 CH-R5-03：移除或脱敏 ModelAdapter 的 message preview 日志。

### P2 — 本轮修复后同步收敛

1. 修复 CH-R5-04：统一 trajectory schema version，并同步测试与文档。
2. 修复 CH-R5-05：统一 ConfigError 诊断文件命名，并同步测试与验收计划。

---

## 最终判断

本轮没有发现 Critical，但存在 3 个 High。按照 `/challenge` Step 4.5，含 High 时不得自动穿越门禁；若继续进入 `/forge` 或交付，需要用户显式签收风险，推荐先用 `/change` 收敛上述契约漂移。

