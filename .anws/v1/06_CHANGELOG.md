# 变更日志 - .anws v1

> 此文件记录本版本迭代过程中的微调变更（由 /change 处理）。新增功能/任务需创建新版本（由 /genesis 处理）。

## 格式说明
- **[CHANGE]** 微调已有任务（由 /change 处理）
- **[FIX]** 修复问题
- **[REMOVE]** 移除内容

---

## 2026-05-10 - Challenge Round 2 修复 (CH-R2-01 ~ CH-R2-07)

**用户原话**: "批准了，请修复这些吧，都修复就可以"

### High 修复
- [FIX] CH-R2-01: `config.detail.md` — `cost_missing_strategy` 默认值从 \"ignore\" 同步为 \"warn\"（与 ADR-007 一致）
- [FIX] CH-R2-02: `core-agent.md` + `cli-system.md` — 配置加载失败（Jinja2 StrictUndefined / YAML 错误）时，CLI 层捕获 ConfigError 并写入最小化诊断文件，不启动 Core Agent
- [FIX] CH-R2-03: `cli-system.md` — 批处理轨迹文件命名策略：`{output_dir}/trajectory_{instance_id}.jsonl`，由 CLI 层构造路径并传入 Core Agent
- [FIX] CH-R2-04: `core-agent.detail.md` — 状态机终态前 `save_trajectory()` 增加 OSError 处理（磁盘满/权限不足），尝试备用临时路径
- [FIX] CH-R2-05: `core-agent.detail.md` + `ADR-006` — ExecutionResult 增加 `stdout_original` 字段；提交标记检测基于原始 stdout，不受观测截断影响
- [FIX] CH-R2-06: `core-agent.detail.md` — `observe_result()` 中 `render_observation_template()` 失败时降级为原始输出，不中断状态机
- [FIX] CH-R2-07: `ADR-001` + `core-agent.detail.md` — execute_command 增加 Windows 平台检测（`os.name != \"nt\"`），ADR-001 风险点补充 Windows 兼容性说明

## 2026-05-10 - Challenge Report 修复（Round 2）

**用户原话**: "批准了，不过我觉得你可以全部修复，从头到尾"

### Critical 修复
- [FIX] C1: `core-agent.detail.md` — `execute_command` 已使用 `shlex.split` + `shell=False`（v1.1 已修复，本轮确认）
- [FIX] C2: 终态→returncode 映射 — `core-agent.detail.md` 主循环返回结构化 `AgentResult`（含 final_state + returncode）；`cli-system.detail.md` 新增 CLI 层退出码映射表

### High 修复
- [FIX] H1: `core-agent.detail.md` — 主循环提取并传递 `tool_call_id`（v1.1 已修复，本轮确认）
- [FIX] H2: `core-agent.detail.md` — `confirm_mode` 默认 `True`；`config.detail.md` 统一 `agent.confirm_mode` 命名（原 `yolo`）
- [FIX] H3: `core-agent.detail.md` — Parser 冲突检测改为基于提取结果（v1.1 已修复，本轮确认）
- [FIX] H4: `core-agent.detail.md` — `FormatError` 改为普通 `Exception` 类（v1.1 已修复，本轮确认）
- [FIX] H5: `cli-system.detail.md` — `PredEntry` 增加 `model_name_or_path` 字段，`to_dict()` 输出 SWE-bench 兼容 schema
- [FIX] H6: `cli-system.detail.md` — CLI `--model` 改为 `config["model"]["name"] = model`，避免覆盖 `api_key`/`max_retries`
- [FIX] H7: `cli-system.detail.md` — `_should_run_instance` 增加轨迹 JSON 完整性校验（检查 `final_state`）
- [FIX] H8: `config.detail.md` — `ConfigManager` 增加 `SENSITIVE_KEYS` + `_redact()` 脱敏逻辑
- [FIX] H9: `config.detail.md` — YAML 配置文件加载使用 `DebugUndefined`（允许可选变量），观测模板仍保持 `StrictUndefined`
- [FIX] H10: ADR-003/004/007 — 明确 litellm 异常类型重试范围、模板缓存策略、`cost_missing_strategy` 配置项

### CLI 退出码调整
- [CHANGE] `cli-system.detail.md` — `EXIT_CODES` 拆分：新增 `USER_DECLINED`(21)、`AGENT_LIMIT_STEP`(10) 等，原 `INTERRUPTED`(130) 仅保留给 SIGINT

## 2026-05-11 - Challenge Round 3 修复 (CH-R3-06 / TK-R3-01~02 / CH-R3-08~10)

**用户原话**: "批准"

### High 修复
- [FIX] CH-R3-06: `core-agent.detail.md` §3.3 `observe_result()` — 增加 ConfigError 捕获逻辑：观测模板渲染失败时降级为 `result.stdout_original or result.stdout`，不中断状态机（原 CH-R2-06 修复不充分，进入 UNKNOWN_ERROR 终态语义不精确，本轮补充降级策略）

### Medium 修复
- [CHANGE] TK-R3-01: `05A_TASKS.md` S3 — 新增任务 **T3.1.6 [REQ-010] 编写 README 完整文档**，承接 ADR-001/002/004 的文档契约（安装指南、配置优先级、环境变量 `MINI_SWE_ENABLE_E2E` / `MINI_SWE_ENABLE_LIVE_API`、退出码语义、风险警示）
- [CHANGE] TK-R3-02: `05A_TASKS.md` §T1.1.1 — 验收标准调整：删除 `python -m mini_swe_agent --help` 可执行性要求（与 T3.1.1 循环依赖），改为目录树完整性验证；CLI `--help` 可执行性移至 T3.1.1 验收
- [CHANGE] CH-R3-08: `core-agent.detail.md` §2 `increment_step()` + `01_PRD.md` US-001 — 钉死步数定义语义：进入 OBSERVE 状态（命令执行完成）后增加，无论 returncode 值；仅命令未执行（FormatError/ValidationError/超时异常）时不增加
- [CHANGE] CH-R3-09: `core-agent.detail.md` §4 MODEL 状态 — 钉死成本上限检查时机：调用模型前做预防性检查（`accumulated + estimated_next_call > cost_limit`），避免最后一次调用超限

### Low 修复
- [CHANGE] CH-R3-10: `01_PRD.md` US-001 — 边界条件补充 FATAL_CONFIG（配置加载失败）和 UNKNOWN_ERROR（连续 FormatError >= 5）终态定义

### 任务调整
- [CHANGE] `05A_TASKS.md` §INT-S3 — 依赖列表增加 T3.1.6

## 2026-05-11 - Challenge Round 4 修复 (CH-R4-01 / CH-R4-02 / CH-R4-03 / TK-R4-01)

**用户原话**: "可以，请你修复这些问题吧，全部修复吧，不要保留了"

### Critical 修复
- [FIX] CH-R4-01: `core-agent.detail.md` §4.1 状态机主循环 — 补充 `consecutive_format_errors` 防循环计数器完整逻辑：
  - `StateMachineContext` 增加 `consecutive_format_errors: int = 0` 字段
  - PARSE 状态 FormatError 分支递增计数器，超阈值（默认 5）进入 UNKNOWN_ERROR 终态
  - 恰好一个动作分支和 EXECUTE 状态均归零计数器
  - `config.detail.md` 默认配置增加 `max_consecutive_format_errors: 5`

### Medium 修复
- [FIX] CH-R4-02: `core-agent.detail.md` — 统一 VALIDATE 子步骤 L0/L1 文档一致性：
  - 新增 §3.1b `validate_command` 完整伪代码（黑名单正则、危险标志组合、CommandValidationError）
  - 主循环 PARSE 状态"恰好一个动作"分支后插入 `validate_command()` 调用点，校验失败抛 CommandValidationError 后返回 MODEL 状态
- [FIX] CH-R4-03: `config.detail.md` §1.3 — 默认配置增加 `cost_estimate_per_call: 0.05`（成本上限预防性检查估算值）
- [FIX] TK-R4-01: `05B_VERIFICATION_PLAN.md` — 补充 T3.1.6 验证条目（文档完整性手动验证）

## 2026-05-10 - 初始化
- [ADD] 创建 `.anws` v1 版本