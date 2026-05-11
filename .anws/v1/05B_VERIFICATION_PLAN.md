# 05B_VERIFICATION_PLAN.md — 验证计划

> 版本: v1
> 产出自: /blueprint
> 最后更新: 2026-05-11
>
> 执行主清单: [05A_TASKS.md](./05A_TASKS.md)（每个验证条目有对应 Task ID）

---

## 1. 范围与目标

本验证计划覆盖 v1 所有 P0/P1 任务，确保：

- 系统核心功能、关键业务逻辑、异常处理机制的正确性、稳定性和健壮性
- 项目验收必须同时包含**单元测试**与**集成测试**
- ADR-002 验收测试清单（P0 强制）全部覆盖
- 所有公共契约有明确的实现承接和验证承接

**ADR-002 验收测试清单（P0 强制，必须全覆盖）**：
- [ ] 解析：0 动作、2 动作、tool+文本冲突 → FormatError，无 Shell 执行
- [ ] 提交：成功路径；returncode!=0 且含标记 → 不提交
- [ ] 模板截断 >= 10000
- [ ] 轨迹存取；工具模式下 tool_call_id 关联字段存在
- [ ] batch preds.json schema 冒烟
- [ ] 真机/火测默认关闭；单一环境变量 `MINI_SWE_ENABLE_E2E` 在 README 中启用

---

## 2. 验证分层策略

| 层次 | 负责范围 | 主要工具 | 适用任务 |
|------|---------|---------|---------|
| 单元测试 | 局部逻辑、状态转换、异常处理、纯算法 | pytest + pytest-mock | T1.1.2~T1.1.5, T2.1.1~T2.2.6, T3.1.3, T3.1.5 |
| 集成测试 | 跨组件协作，核心闭环 | pytest + fixtures | T2.3.1, T3.1.2 |
| 冒烟测试 | Sprint 退出关口关键路径 | 绑定 INT-S{N} | INT-S1, INT-S2, INT-S3 |
| E2E测试 | 关键用户链路，真机验证 | 环境变量启用，默认关闭 | INT-S3（可选） |
| 手动验证 | TUI 渲染，CLI help 文案 | 人工检查 + 截图 | T3.1.1, T3.1.4 |
| 编译检查/Lint | 项目骨架，依赖正确性 | pip install + ruff | T1.1.1 |

---

## 3. 风险类别覆盖原则

- 按**风险类别闭合**，而非测试数量最大化
- 优先等价类划分、边界值、代表性错误样本、参数化测试/表驱动测试
- 禁止对所有字段与参数组合做笛卡尔积枚举
- 单元测试负责细粒度逻辑，集成测试负责跨组件协作，冒烟测试负责 Sprint 关口，E2E 只保留关键用户链路且默认关闭

---

## 4. 测试材料与证据要求

| 验证类型 | 测试材料位置 | 证据形式 |
|---------|------------|---------|
| 单元测试 | `tests/unit/test_*.py` | pytest 运行报告 / CI 日志 |
| 集成测试 | `tests/integration/test_*.py` | 集成测试报告 / CI 日志 |
| 冒烟测试 | 绑定 INT-S{N} 手动执行 | 关键路径截图 / pytest 输出 |
| E2E测试 | `tests/e2e/`（`MINI_SWE_ENABLE_E2E=1` 启用） | 截图 / 日志 |
| 手动验证 | 无专用目录 | 截图 / 终端输出记录 |
| 编译/Lint | CI 自动运行 | `logs/install.log`, `logs/lint.log` |

---

## 5. Task-by-Task 验证计划

### T1.1.1
- **关联需求**: 项目骨架（无直接 REQ）
- **关联契约**: 无
- **风险类别**: 基础设施 / 依赖兼容性
- **单元测试覆盖**: 不适用（基础设施任务）
- **集成/E2E/冒烟覆盖**: 不适用
- **前置数据**: 无
- **断言**:
  - `pip install -e ".[dev]"` 退出码 = 0
  - `ruff check src/` 无输出（无错误）
  - `python -m mini_swe_agent --help` 不崩溃
- **证据**: `logs/install.log`, `logs/lint.log`

---

### T1.1.2
- **关联需求**: REQ-007（配置管理）
- **关联契约**: 配置多源加载协议（YAML/env/default 三源，DebugUndefined 模式）
- **风险类别**: 配置加载 / 文件 IO / 环境变量解析
- **单元测试覆盖**:
  - `load_yaml_file` 正常加载：合法 YAML → 返回 dict（正常）
  - `load_yaml_file` 文件不存在 → 抛 `FileNotFoundError`（异常处理）
  - `load_yaml_file` YAML 语法错误 → 抛 `ConfigError`（异常处理）
  - `load_yaml_file` 含 Jinja2 变量且使用 DebugUndefined → 未定义变量保留原文（边界，DebugUndefined 不抛异常）
  - `load_env_vars("MINI_SWE")` 双下划线转嵌套 dict → `MINI_SWE_MODEL__NAME=x` → `{"model": {"name": "x"}}`（正常）
  - `load_env_vars` 无匹配前缀 → 返回 `{}`（边界）
  - `load_defaults()` → 返回含所有必须字段的 dict（正常）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S1 冒烟验证配置加载链路端到端
- **前置数据**: 测试用 YAML 文件（有效/无效），测试环境变量
- **断言**:
  - 正常加载返回 dict，键值符合 YAML 内容
  - `FileNotFoundError` 含文件路径信息
  - `ConfigError` 含 YAML 语法错误行号（如有）
  - DebugUndefined 模式下 `{{ undefined }}` 保留原样不抛异常
- **证据**: `tests/unit/test_config_loader.py`

---

### T1.1.3
- **关联需求**: REQ-007（配置管理）
- **关联契约**: 配置优先级协议（CLI > 文件 > 环境变量 > 默认值）
- **风险类别**: 合并策略正确性 / 边界 None 处理
- **单元测试覆盖**:
  - dict 嵌套合并：`base={"a": {"x":1}}` + `override={"a": {"y":2}}` → `{"a": {"x":1,"y":2}}`（正常）
  - list 覆盖：`base={"a":[1,2]}` + `override={"a":[3]}` → `{"a":[3]}`（边界，list 不递归合并）
  - `base=None` + `override={"k":"v"}` → `{"k":"v"}`（边界，None 等价于 {}）
  - `base={"k":"v"}` + `override=None` → `{"k":"v"}`（边界）
  - 三层优先级组合：default < env < file → 验证最终 merge 结果（正常）
  - 标量覆盖：`base={"timeout":120}` + `override={"timeout":60}` → `{"timeout":60}`（正常）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S1 验证 ConfigManager 多源合并端到端
- **前置数据**: 无（纯函数测试）
- **断言**: 每组输入对应明确的输出 dict（表驱动参数化测试）
- **证据**: `tests/unit/test_config_merger.py`

---

### T1.1.4
- **关联需求**: REQ-007（配置管理）
- **关联契约**: 观测截断协议（>=10000 截断为前5000+后5000，elided_chars 计算）
- **风险类别**: 截断边界精确性 / Jinja2 StrictUndefined / 模板缓存
- **单元测试覆盖**:
  - `render` 正常：含变量模板 + 合法 context → 返回渲染字符串（正常）
  - `render` StrictUndefined：未定义变量 → 抛 `ConfigError`（异常处理）
  - `truncate` len=9999 → 原样返回，无 warning（边界 < 阈值）
  - `truncate` len=10000 → 截断为前5000+后5000，warning 含 `elided_chars=0`（边界 = 阈值，需确认文档：`>=10000` 触发）
  - `truncate` len=10001 → 截断，warning 含 `elided_chars=1`（边界 = 阈值+1）
  - `truncate` len=20000 → 截断，`elided_chars=10000`（正常超长）
  - 模板缓存：同一模板内容第二次 render 使用缓存（性能，可通过 mock 验证 compile 调用次数）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S1 验证 Observer 实际使用截断的端到端
- **前置数据**: 测试用模板字符串（含/不含变量），不同长度的输出字符串
- **断言**:
  - 截断后 `len(result) == 10000`（当 len(input) >= 10000 时）
  - warning 日志含 `elided_chars` 值
  - `elided_chars == len(original) - 10000`
- **证据**: `tests/unit/test_config_renderer.py`

---

### T1.1.5
- **关联需求**: REQ-007（配置管理）
- **关联契约**: 配置管理完整接口契约；敏感信息脱敏协议
- **风险类别**: 脱敏遗漏 / 缓存失效 / 多源合并完整性
- **单元测试覆盖**:
  - `_redact` 顶层敏感 key：`{"api_key": "sk-abc"}` → `{"api_key": "***"}`（正常）
  - `_redact` 嵌套敏感 key：`{"model": {"api_key": "sk-abc"}}` → `{"model": {"api_key": "***"}}`（边界，嵌套脱敏）
  - `_redact` 非敏感 key 不脱敏：`{"name": "gpt-4"}` → 原样返回（正常）
  - `_redact` 敏感 key 值为 None → `{"api_key": None}` 原样返回（边界，None 不脱敏）
  - `load_config` 多源合并：四源全部提供时，CLI > 文件 > env > 默认值（正常）
  - `clear_cache` 后再次 `load_config` 不使用旧缓存（正常，缓存失效）
  - `repr(manager)` 含敏感 key → 输出中 api_key 显示 `***`（正常，日志脱敏）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S1 验证 ConfigManager 整体行为
- **前置数据**: 含敏感 key 的配置 dict，多个 YAML 测试文件，mock 环境变量
- **断言**:
  - repr 输出不含原始 api_key 值
  - 多源优先级：CLI 参数覆盖文件，文件覆盖 env
- **证据**: `tests/unit/test_config_manager.py`

---

### INT-S1
- **关联需求**: S1 退出标准
- **关联契约**: 所有 S1 完成任务的公共契约
- **风险类别**: 系统可用性 / Sprint 关口
- **单元测试覆盖**: 不适用（INT 任务不新增单元测试）
- **集成/E2E/冒烟覆盖**: 按 Sprint 路线图退出标准逐条执行冒烟测试
- **前置数据**: S1 所有任务已完成且产出可用
- **断言**:
  - `python -m mini_swe_agent --help` 无报错
  - `pytest tests/unit/test_config_*.py` 全绿
  - `ruff check src/` 通过
- **证据**: 截图 / pytest 输出 / lint 日志

---

### T2.1.1
- **关联需求**: REQ-001（状态机），REQ-006（轨迹记录）
- **关联契约**: 状态机终态协议（State 枚举 6 终态）；轨迹 JSON 数据结构（Trajectory）
- **风险类别**: 数据结构完整性 / 枚举覆盖
- **单元测试覆盖**:
  - `State` 枚举含 6 终态：SUBMITTED/LIMIT_STEP/LIMIT_COST/INTERRUPT/FATAL_CONFIG/UNKNOWN_ERROR（正常）
  - `ExecutionResult.stdout_original` 字段存在且为 `Optional[str]`（正常）
  - `ExecutionResult.is_success()` returncode=0 → True，!=0 → False（正常）
  - `Trajectory.increment_step()` 步数正确累加（正常）
  - `Trajectory.add_message(msg, tool_call_id)` → message 含 tool_call_id 和 timestamp（正常）
  - `FormatError(message, error_type)` 可构造，属性正确（正常）
  - `StateMachineContext` 各字段可赋值和读取（正常）
- **集成/E2E/冒烟覆盖**: 不适用（纯数据结构，集成在 T2.3.1 中验证）
- **前置数据**: 无
- **断言**: 每个数据结构可实例化，方法返回符合预期
- **证据**: `tests/unit/test_models.py`

---

### T2.2.1
- **关联需求**: REQ-002（严格动作协议）
- **关联契约**: 动作解析协议（tool-call/文本两模式，FormatError 触发条件）
- **风险类别**: 动作解析逻辑 / FormatError 触发精确性
- **单元测试覆盖**（严格覆盖 ADR-002 验收清单）：
  - tool-call 模式，0 个 tool_call → `FormatError(error_type="no_tool_call")`（ADR-002 P0）
  - tool-call 模式，2 个 tool_call → `FormatError(error_type="multiple_tool_calls")`（ADR-002 P0）
  - tool-call 模式，tool_call 类型不是 bash → `FormatError(error_type="wrong_tool_type")`（边界）
  - tool-call 模式，1 个 bash tool_call → 返回命令字符串（正常）
  - 文本模式，0 个围栏块 → `FormatError`（ADR-002 P0）
  - 文本模式，2 个围栏块 → `FormatError`（ADR-002 P0）
  - 文本模式，围栏块和 XML 块同时命中 → `FormatError(error_type="mixed_fence")`（ADR-002 P0）
  - tool-call 和文本块同时命中 → `FormatError(error_type="mixed_protocol")`（ADR-002 P0）
  - 命令字符串为空 → `FormatError(error_type="empty_command")`（边界）
  - 文本模式，恰好 1 个合法围栏块 → 返回命令字符串（正常）
  - 文本模式，恰好 1 个合法 XML 块 → 返回命令字符串（正常）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S2 验证 Parser 在状态机中的集成
- **前置数据**: 各种格式的 mock message dict
- **断言**:
  - 所有 FormatError 情况均不执行 Shell（由集成测试 T2.3.1 验证）
  - FormatError 含 error_type 属性
- **证据**: `tests/unit/test_parser.py`

---

### T2.2.2
- **关联需求**: REQ-003（本机执行）
- **关联契约**: 本机执行安全协议（shlex+shell=False，stdout_original，超时不重试）
- **风险类别**: subprocess 安全 / 超时处理 / 跨平台兼容
- **单元测试覆盖**:
  - `echo hello` → `returncode=0, stdout="hello\n", stdout_original="hello\n"`（正常）
  - `exit 1` → `returncode=1`（正常，非零退出码）
  - 超时命令（timeout=0.1）→ `exception_metadata["error_type"]="TIMEOUT"`，进程终止（边界）
  - `stderr` 捕获：`>&2 echo err` → `stderr="err\n"`（正常）
  - `stdout_original` 为原始值，`stdout` 为截断后值（当 stdout 超长时）（边界）
  - Windows 路径：`os.name="nt"` 时 `shlex.split(posix=False)`（mock os.name）（平台边界）
  - 空命令字符串 → 抛出适当异常（边界）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S2 验证 Executor 在 echo hello 闭环中的行为
- **前置数据**: 无（执行真实系统命令，使用短超时）
- **断言**:
  - `returncode` 类型为 int
  - 超时后进程不存在（已终止）
  - `stdout_original` 不被截断
- **证据**: `tests/unit/test_executor.py`

---

### T2.2.3
- **关联需求**: REQ-003（本机执行，安全基线）
- **关联契约**: 命令校验黑名单协议
- **风险类别**: 安全基线 / 黑名单漏洞 / 误拦截
- **单元测试覆盖**:
  - `rm -rf /` → 抛 `CommandValidationError`，含拒绝原因（正常，黑名单）
  - `dd if=/dev/zero of=/dev/sda` → 抛 `CommandValidationError`（正常，黑名单）
  - `mkfs.ext4 /dev/sda` → 抛 `CommandValidationError`（正常，黑名单）
  - `rm -f /etc/passwd`（危险标志+破坏性）→ 抛 `CommandValidationError`（边界，危险标志组合）
  - `echo hello` → 通过校验，返回 None（正常）
  - `ls -la /` → 通过校验（正常，-la 不是危险标志）
  - 配置白名单 `["echo", "ls"]` 时，`grep` 命令 → 抛 `CommandValidationError`（边界，白名单模式）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S2 验证 Validator 在状态机中的集成
- **前置数据**: 无
- **断言**: `CommandValidationError` 含拒绝原因字符串
- **证据**: `tests/unit/test_validator.py`

---

### T2.2.4
- **关联需求**: REQ-004（提交标记契约）
- **关联契约**: 提交标记契约（OVERALL_OUTPUT 定义 + ANSI/Unicode normalize + returncode==0 双重条件）
- **风险类别**: 提交判断精确性 / ANSI 去除 / Unicode normalize / 截断边界
- **单元测试覆盖**（严格覆盖 ADR-002 验收清单）：
  - 成功路径：`stdout_original="COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\npatch"`, `rc=0` → `submitted=True, submission_text="patch"`（ADR-002 P0）
  - returncode!=0 且含标记 → `submitted=False`（ADR-002 P0）
  - `stdout_original=None`，fallback 到 `stdout`（边界，CH-R2-05）
  - ANSI 包裹标记：`"\x1b[32mCOMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\x1b[0m\n..."`, `rc=0` → `submitted=True`（边界）
  - Unicode 前置空白：`"\u00a0COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n..."`, `rc=0` → `submitted=True`（边界）
  - 标记在 stderr 中，stdout 无标记 → `submitted=False`（边界，仅检测 stdout）
  - 标记后有额外字符（非首行）→ `submitted=False`（边界，精确匹配）
  - 观测模板渲染失败（UndefinedError）→ 降级为原始 stdout，`submitted` 按原始 stdout 判断（边界）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S2 验证 Observer 在状态机提交路径的集成
- **前置数据**: 含 ANSI/Unicode/多行的 mock ExecutionResult
- **断言**:
  - `submitted=True` 时 `submission_text` 为首行之后的内容
  - 降级路径不抛异常，状态机继续
- **证据**: `tests/unit/test_observer.py`

---

### T2.2.5
- **关联需求**: REQ-005（模型适配）
- **关联契约**: 模型 API 重试协议（RETRY_EXCEPTIONS 5次）；成本计费协议（cost_calculation_method）；消息扁平化协议
- **风险类别**: API 重试逻辑 / 成本计费策略 / 消息扁平化正确性
- **单元测试覆盖**:
  - Mock litellm 返回正常 tool-call 响应（含 cost） → `ModelResponse.cost=0.01`, `cost_calculation_method="api"`（正常）
  - Mock litellm 返回正常文本响应 → 正确提取 content（正常）
  - Mock litellm 连续抛 `litellm.Timeout` 5 次 → 重试 5 次后抛出（边界，重试上限）
  - `cost_missing_strategy="warn"` → cost=0，warning 日志，`cost_calculation_method="missing"`（正常）
  - `cost_missing_strategy="ignore"` → cost=0，无 warning，`cost_calculation_method="missing"`（正常）
  - `cost_missing_strategy="error"` → 抛 `CostMissingError`（边界）
  - 消息扁平化：output_items 列表 → 转换为 messages 数组，role 和 content 正确（正常）
  - token-based 估算：`cost_calculation_method="token_based"`，model 不在定价表 → cost=0，warn（边界）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S2 验证 ModelAdapter 在状态机中的集成（使用 Mock）
- **前置数据**: Mock litellm（pytest-mock），测试用 messages 列表
- **断言**:
  - 重试次数精确等于配置值（通过 mock call_count 验证）
  - `CostMissingError` 不被 tenacity 重试（verify 通过 mock 确认只调用 1 次）
- **证据**: `tests/unit/test_model_adapter.py`

---

### T2.2.6
- **关联需求**: REQ-006（轨迹记录）
- **关联契约**: 轨迹 JSON 格式契约（schema_version v1_jsonl，tool_call_id）；OSError 备用路径协议
- **风险类别**: JSON 格式正确性 / tool_call_id 关联 / 磁盘 IO 异常 / 防 OOM
- **单元测试覆盖**（严格覆盖 ADR-002 验收清单）：
  - 两步执行（含 tool_call_id）→ 保存 JSON 含 `schema_version="v1_jsonl"`, messages 中 tool 消息含 `tool_call_id`（ADR-002 P0：轨迹存取 + tool_call_id 关联）
  - 读取保存的 JSON → 可反序列化，字段完整（ADR-002 P0：轨迹存取）
  - `save_trajectory` OSError（mock 文件系统）→ 尝试备用临时路径，不抛异常（边界，CH-R2-04）
  - 100 步自动刷新：mock `step_counter=100` → 自动写入 jsonl 临时文件（边界，防 OOM）
  - `schema_version` 不兼容时读取 → 抛明确错误（边界）
  - cost_accumulator 和 step_counter 正确累加（正常）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S2 验证轨迹端到端写入
- **前置数据**: 临时目录（pytest tmp_path），mock 执行结果
- **断言**:
  - 保存后文件可读，JSON 可解析
  - `messages` 数组中 tool 消息含 `tool_call_id` 字段（非 None）
- **证据**: `tests/unit/test_trajectory.py`

---

### T2.3.1
- **关联需求**: REQ-001（核心状态机闭环）
- **关联契约**: 状态机终态协议（6 终态 + returncode 映射）；FormatError 防循环协议
- **风险类别**: 状态机闭环正确性 / 终态覆盖完整性 / 信号处理
- **集成测试覆盖**（严格覆盖 ADR-002 验收清单）：
  - 成功路径：Mock 模型返回 `echo hello`，执行成功 → 完整 MODEL→PARSE→VALIDATE→EXECUTE→OBSERVE 闭环，轨迹正确（ADR-002 P0）
  - FormatError 防循环：Mock 模型连续返回格式错误 5 次 → UNKNOWN_ERROR 终态，轨迹保存（ADR-002 P0）
  - 提交失败：Mock 模型返回提交命令，returncode!=0 → 不进入 SUBMITTED，继续循环（ADR-002 P0）
  - 提交成功：returncode=0 + 标记 → SUBMITTED 终态，`AgentResult.returncode=0`（ADR-002 P0）
  - LIMIT_STEP：步数达到 step_limit → LIMIT_STEP 终态，`AgentResult.returncode=2`（正常）
  - LIMIT_COST：成本累计达到 cost_limit → LIMIT_COST 终态，`AgentResult.returncode=3`（正常）
  - INTERRUPT：模拟 SIGINT → INTERRUPT 终态，轨迹尽力保存（边界）
  - FormatError 不增加步数：连续 FormatError 后步数仍为 0（边界，ADR-002 步数定义）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S2 冒烟验证整体行为可用
- **前置数据**: Mock ModelAdapter、Mock Executor（部分 case），临时轨迹目录
- **断言**:
  - 每次终态前 `trajectory.save()` 被调用（mock 验证）
  - `AgentResult.final_state` 与实际终态一致
  - `AgentResult.returncode` 与终态映射表一致
- **证据**: `tests/integration/test_state_machine.py`

---

### INT-S2
- **关联需求**: S2 退出标准
- **关联契约**: 所有 S2 完成任务的公共契约
- **风险类别**: 系统可用性 / Sprint 关口
- **单元测试覆盖**: 不适用
- **集成/E2E/冒烟覆盖**: 冒烟测试，按退出标准逐条验证
- **前置数据**: S2 所有任务完成
- **断言**:
  - `pytest tests/unit/ tests/integration/test_state_machine.py` 全绿
  - Mock `echo hello` 闭环日志可见
  - FormatError 防循环触发日志可见
- **证据**: pytest 输出 / 日志截图

---

### T3.1.1
- **关联需求**: REQ-010（CLI 主命令）
- **关联契约**: CLI 子命令结构协议（run/batch/check），风险警示文案协议
- **风险类别**: CLI 可用性 / 文案正确性
- **手动验证**:
  - `mini-swe-agent --help` 含 "run"、"batch"、"check" 子命令
  - `--help` 含风险警示文案（`⚠️` 或 `Warning`）
  - `mini-swe-agent --version` 输出版本号
- **证据**: `logs/cli_help.txt`（终端截图/输出记录）

---

### T3.1.2
- **关联需求**: REQ-010（CLI 主命令）
- **关联契约**: CLI 参数语义契约（--model 仅覆盖 model.name）；ConfigError 诊断文件写入；退出码映射协议
- **风险类别**: 参数传递正确性 / ConfigError 处理 / 退出码语义
- **集成测试覆盖**:
  - 正常执行（Mock Agent）：配置加载→Agent调用→退出码=0（正常）
  - ConfigError（YAML 语法错误）→ 诊断文件写入，exitcode=13（边界）
  - `--model gpt-4o-mini` + 配置含 api_key → `model.name` 被覆盖，`api_key` 不变（边界，ADR H6）
  - `--yolo` → `confirm_mode=False`，无 confirm 提示（正常）
  - 无 `--yolo` → 打印风险警示，等待 confirm（正常，使用 mock stdin）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S3 冒烟验证整体 run 链路
- **前置数据**: Mock Agent，测试用 YAML 配置，mock stdin
- **断言**:
  - 诊断文件路径含 `config_error_`，内容含错误描述
  - 退出码符合 EXIT_CODES 映射
- **证据**: `tests/integration/test_cli_run.py`

---

### T3.1.3
- **关联需求**: REQ-008（批处理模式）
- **关联契约**: preds.json schema（instance_id/model_name_or_path/model_patch）；批处理轨迹命名协议；_should_run_instance trajectory 完整性检查
- **风险类别**: preds.json schema 正确性 / workers cap / 跳过逻辑 / 并发安全
- **单元测试覆盖**:
  - `BatchConfig(workers=100)` → workers cap 到 64，warning（边界）
  - `BatchConfig(workers=0)` → 抛 `ValueError`（边界）
  - `BatchConfig(slice_range=(5, 3))` → 抛 `ValueError`（边界，start >= stop）
  - `PredEntry.to_dict()` → 含 `instance_id`、`model_name_or_path`、`model_patch` 三字段（正常，preds.json schema）
  - `_should_run_instance` 已有完整轨迹（含 `final_state`）+ `redo_existing=False` → 返回 False（边界）
  - `_should_run_instance` 轨迹缺 `final_state` + `redo_existing=False` → 返回 True（重新运行）（边界，ADR H7）
- **冒烟测试覆盖**（ADR-002 P0 要求）：
  - 真实执行（Mock Agent）2 个实例 → 生成 `preds.json`，schema 结构正确，每条含三必须字段（ADR-002 P0：batch preds.json schema 冒烟）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S3 冒烟验证
- **前置数据**: Mock Agent，测试用 instance.jsonl，临时输出目录
- **断言**:
  - `preds.json` 可被 `json.loads()` 解析
  - 每条记录含 `instance_id`、`model_name_or_path`、`model_patch`
  - 轨迹文件命名为 `trajectory_{instance_id}.jsonl`
- **证据**: `tests/unit/test_batch.py`, `tests/integration/test_batch_smoke.py`

---

### T3.1.4
- **关联需求**: REQ-009（Textual 检查器）
- **关联契约**: 无（TUI 终端用户界面）
- **风险类别**: TUI 渲染正确性 / ANSI 鲁棒性 / 键盘响应
- **手动验证**:
  - `mini-swe-agent check <traj.json>` 启动 TUI，显示步骤列表
  - 含 FormatError 步骤行以红色高亮
  - 含 ANSI 转义码的内容正常显示（ANSI 剥离）
  - 含 NUL 字符的内容替换为 `␀`，不崩溃
  - 按 `q` 正常退出
- **E2E触发设想**: `MINI_SWE_ENABLE_E2E=1` 时，使用 textual pilot 自动化验证 TUI 渲染和键盘交互
- **前置数据**: 含 FormatError 步骤的测试轨迹 JSON，含 ANSI/NUL 的测试轨迹
- **断言**: 无自动断言（手动截图确认）
- **证据**: `logs/checker_screenshot.png`

---

### T3.1.5
- **关联需求**: REQ-010（CLI 主命令）
- **关联契约**: 退出码映射协议（CLI EXIT_CODES vs Core returncode 语义分离）
- **风险类别**: 退出码语义正确性 / 映射覆盖完整性
- **单元测试覆盖**（表驱动参数化）:
  - `SUBMITTED → EXIT_CODES["SUCCESS"]=0`（正常）
  - `LIMIT_STEP → EXIT_CODES["AGENT_LIMIT_STEP"]=10`（正常）
  - `LIMIT_COST → EXIT_CODES["AGENT_LIMIT_COST"]=11`（正常）
  - `INTERRUPT → EXIT_CODES["AGENT_INTERRUPT"]=12`（正常）
  - `FATAL_CONFIG → EXIT_CODES["AGENT_FATAL_CONFIG"]=13`（正常）
  - `UNKNOWN_ERROR → EXIT_CODES["AGENT_UNKNOWN_ERROR"]=14`（正常）
  - 所有 6 种终态均有对应 CLI 退出码（完整性检查）
- **集成/E2E/冒烟覆盖**: 绑定 INT-S3 验证真实退出码行为
- **前置数据**: 无（纯映射函数测试）
- **断言**: 每种终态返回值等于 EXIT_CODES 字典对应值（参数化测试）
- **证据**: `tests/unit/test_exit_codes.py`

---

### T3.1.6
- **关联需求**: REQ-010（CLI 主命令）
- **关联契约**: 文档契约（ADR-002 要求 README 中启用 E2E；ADR-004 要求配置策略说明；ADR-001 要求 Python 版本）
- **风险类别**: 文档完整性 / 用户可用性
- **单元测试覆盖**: 不适用（文档任务）
- **集成/E2E/冒烟覆盖**: 不适用
- **手动验证**:
  - README 包含安装指南（`pip install -e ".[dev]"`）
  - README 包含配置优先级说明（CLI > 文件 > env > 默认值）
  - README 包含环境变量说明（`MINI_SWE_ENABLE_E2E`、`MINI_SWE_ENABLE_LIVE_API`）
  - README 包含退出码语义表（6 种终态 → CLI 退出码）
  - README 包含风险警示（Shell 执行风险）
  - README 包含快速开始示例（`mini-swe-agent run --model gpt-4o "echo hello"`）
- **前置数据**: 无
- **断言**: README 覆盖所有 ADR 文档要求的内容
- **证据**: `README.md` 文件内容

---

### INT-S3
- **关联需求**: S3 退出标准
- **关联契约**: 所有 S3 完成任务的公共契约
- **风险类别**: 系统可用性 / Sprint 关口 / 端到端完整性
- **单元测试覆盖**: 不适用
- **集成/E2E/冒烟覆盖**: 冒烟测试 + 可选 E2E（`MINI_SWE_ENABLE_E2E=1`）
- **前置数据**: S3 所有任务完成，测试用小数据集，Mock API key
- **断言**:
  - `mini-swe-agent run` 以正确退出码退出
  - `preds.json` 含正确 schema
  - TUI 正常启动（手动截图）
  - `pytest` 全量套件通过
  - 回归检查：S1/S2 核心单元测试未破坏
- **证据**: pytest 输出 / `preds.json` 内容 / TUI 截图 / 终端日志

---

## 6. Contract Coverage Overlay

> **必须存在，不可删除。**

| 契约 | 类型 | 实现承接 | 验证承接 | 状态 |
|------|------|---------|---------|:----:|
| CLI 参数语义（--config/--model/--yolo/--step-limit/--cost-limit/--output） | CLI API | T3.1.1, T3.1.2 | T3.1.2 集成测试 | ⬜ |
| --model 仅覆盖 model.name（不覆盖 api_key 等嵌套字段） | CLI API | T3.1.2 | T3.1.2 集成测试 | ⬜ |
| 配置优先级协议（CLI > 文件 > env > 默认值） | 操作契约 | T1.1.3, T1.1.5 | T1.1.3 单元测试, T1.1.5 单元测试 | ⬜ |
| 配置多源加载（YAML DebugUndefined + env + default） | 操作契约 | T1.1.2 | T1.1.2 单元测试 | ⬜ |
| 观测截断协议（>=10000 → 前5000+后5000，elided_chars） | 操作契约 | T1.1.4 | T1.1.4 单元测试（边界 9999/10000/10001） | ⬜ |
| 敏感信息脱敏协议（api_key/password/token/secret → `***`） | 安全契约 | T1.1.5 | T1.1.5 单元测试 | ⬜ |
| ConfigError 诊断文件写入（配置加载失败时） | 错误语义 | T3.1.2 | T3.1.2 集成测试 | ⬜ |
| 状态机终态协议（6 终态 + returncode 映射） | 操作契约 | T2.1.1, T2.3.1 | T2.3.1 集成测试, T3.1.5 单元测试 | ⬜ |
| 动作解析协议（tool-call/文本，0/2+/混合 → FormatError） | 操作契约 | T2.2.1 | T2.2.1 单元测试（全分支覆盖） | ⬜ |
| FormatError 防循环协议（连续 5 次 → UNKNOWN_ERROR） | 操作契约 | T2.3.1 | T2.3.1 集成测试 | ⬜ |
| 命令校验黑名单协议（破坏性命令 → CommandValidationError） | 安全契约 | T2.2.3 | T2.2.3 单元测试 | ⬜ |
| 本机执行安全协议（shlex+shell=False，stdout_original，超时不重试） | 操作契约 | T2.2.2 | T2.2.2 单元测试 | ⬜ |
| 提交标记契约（OVERALL_OUTPUT + ANSI normalize + rc==0） | 操作契约 | T2.2.4 | T2.2.4 单元测试（全边界覆盖） | ⬜ |
| 轨迹 JSON 格式（schema_version v1_jsonl，tool_call_id 关联） | 数据格式 | T2.2.6 | T2.2.6 单元测试（ADR-002 P0） | ⬜ |
| OSError 备用路径协议（save_trajectory 失败时尝试临时路径） | 错误语义 | T2.2.6 | T2.2.6 单元测试 | ⬜ |
| 模型 API 重试协议（RETRY_EXCEPTIONS 5次，FormatError 不重试） | 操作契约 | T2.2.5 | T2.2.5 单元测试（mock 验证调用次数） | ⬜ |
| 成本计费协议（cost_calculation_method：api/token_based/missing） | 操作契约 | T2.2.5 | T2.2.5 单元测试 | ⬜ |
| preds.json schema（instance_id/model_name_or_path/model_patch） | 数据格式 | T3.1.3 | T3.1.3 冒烟测试（ADR-002 P0） | ⬜ |
| 批处理轨迹命名（trajectory_{instance_id}.jsonl） | 持久化结构 | T3.1.3 | T3.1.3 单元测试 | ⬜ |
| 退出码映射协议（CLI EXIT_CODES vs Core returncode 语义分离） | 错误语义 | T3.1.5 | T3.1.5 单元测试（6 终态全覆盖） | ⬜ |

---

## 7. Testing Coverage Overlay

> **必须存在，不可删除。**

| 测试责任 | 风险类别 | 覆盖方法 | 任务承接 | 测试材料 | 状态 |
|---------|---------|---------|---------|---------|:----:|
| YAML 加载：正常/语法错误/文件不存在 | 配置 IO | 单元测试 + 代表性错误样本 | T1.1.2 | `tests/unit/test_config_loader.py` | ⬜ |
| 环境变量双下划线转嵌套 dict | 配置解析 | 单元测试 + 边界值 | T1.1.2 | `tests/unit/test_config_loader.py` | ⬜ |
| 配置合并：dict 递归/list 覆盖/None 处理 | 合并逻辑 | 单元测试 + 表驱动用例 | T1.1.3 | `tests/unit/test_config_merger.py` | ⬜ |
| 观测截断：边界 9999/10000/10001/超长 | 截断边界 | 单元测试 + 边界值 | T1.1.4 | `tests/unit/test_config_renderer.py` | ⬜ |
| Jinja2 StrictUndefined：未定义变量抛 ConfigError | 模板错误 | 单元测试 + 异常处理 | T1.1.4 | `tests/unit/test_config_renderer.py` | ⬜ |
| 敏感信息脱敏：api_key/嵌套/None 边界 | 信息安全 | 单元测试 + 边界值 | T1.1.5 | `tests/unit/test_config_manager.py` | ⬜ |
| 动作解析：0/2+动作/tool+文本混合 → FormatError | 协议正确性 | 单元测试 + 等价类划分 | T2.2.1 | `tests/unit/test_parser.py` | ⬜ |
| 动作解析：正常 tool-call/围栏/XML → 命令字符串 | 协议正确性 | 单元测试 + 正常路径 | T2.2.1 | `tests/unit/test_parser.py` | ⬜ |
| subprocess 执行：正常/超时/stderr | 执行安全 | 单元测试 + 边界值 | T2.2.2 | `tests/unit/test_executor.py` | ⬜ |
| stdout_original 原始值保留（截断前） | 数据完整性 | 单元测试 + 边界值 | T2.2.2 | `tests/unit/test_executor.py` | ⬜ |
| 命令黑名单：破坏性命令/危险标志组合/正常命令 | 安全基线 | 单元测试 + 代表性错误样本 | T2.2.3 | `tests/unit/test_validator.py` | ⬜ |
| 提交标记：成功/returncode!=0/ANSI/Unicode/截断边界 | 提交判断 | 单元测试 + 边界值 | T2.2.4 | `tests/unit/test_observer.py` | ⬜ |
| 模板降级：渲染失败不中断状态机 | 错误恢复 | 单元测试 + 异常处理 | T2.2.4 | `tests/unit/test_observer.py` | ⬜ |
| 模型重试：RETRY_EXCEPTIONS 5次；CostMissingError 不重试 | 重试策略 | 单元测试 + mock call_count | T2.2.5 | `tests/unit/test_model_adapter.py` | ⬜ |
| 成本计费三策略：warn/ignore/error | 成本计费 | 单元测试 + 等价类 | T2.2.5 | `tests/unit/test_model_adapter.py` | ⬜ |
| 轨迹写入/读取；tool_call_id 关联 | 数据完整性 | 单元测试 + ADR-002 P0 | T2.2.6 | `tests/unit/test_trajectory.py` | ⬜ |
| OSError 备用路径（磁盘满/权限不足） | 错误恢复 | 单元测试 + mock IO | T2.2.6 | `tests/unit/test_trajectory.py` | ⬜ |
| 状态机闭环：成功路径/FormatError/提交失败 | 核心业务 | 集成测试 + ADR-002 P0 | T2.3.1 | `tests/integration/test_state_machine.py` | ⬜ |
| 状态机终态：LIMIT_STEP/LIMIT_COST/INTERRUPT | 状态转换 | 集成测试 + 状态表驱动 | T2.3.1 | `tests/integration/test_state_machine.py` | ⬜ |
| CLI run：ConfigError 诊断文件；--model 覆盖语义 | CLI 契约 | 集成测试 + 代表性错误 | T3.1.2 | `tests/integration/test_cli_run.py` | ⬜ |
| BatchConfig 校验：workers cap/slice 边界 | 配置校验 | 单元测试 + 边界值 | T3.1.3 | `tests/unit/test_batch.py` | ⬜ |
| preds.json schema 冒烟 | 数据格式 | 冒烟测试 + ADR-002 P0 | T3.1.3 | `tests/integration/test_batch_smoke.py` | ⬜ |
| 退出码映射：全部 6 终态 | 错误语义 | 单元测试 + 表驱动参数化 | T3.1.5 | `tests/unit/test_exit_codes.py` | ⬜ |
| TUI 渲染：FormatError 高亮/ANSI/NUL | 界面正确性 | 手动验证 + 截图 | T3.1.4 | `logs/checker_screenshot.png` | ⬜ |

---

## 8. Verification Traceability Matrix

> **必须存在，不可删除。**

| REQ/Contract | Task | Verification | Test Material | Evidence | Status |
|---|---|---|---|---|---|
| REQ-007 配置管理 | T1.1.2, T1.1.3, T1.1.4, T1.1.5 | 单元测试 | `tests/unit/test_config_*.py` | pytest 报告 | ⬜ |
| 配置优先级协议 | T1.1.3, T1.1.5 | 单元测试 | `tests/unit/test_config_merger.py`, `test_config_manager.py` | pytest 报告 | ⬜ |
| 观测截断协议（>=10000） | T1.1.4 | 单元测试（边界值） | `tests/unit/test_config_renderer.py` | pytest 报告 | ⬜ |
| 敏感信息脱敏协议 | T1.1.5 | 单元测试 | `tests/unit/test_config_manager.py` | pytest 报告 | ⬜ |
| REQ-002 严格动作协议 | T2.2.1 | 单元测试（ADR-002 P0 全覆盖） | `tests/unit/test_parser.py` | pytest 报告 | ⬜ |
| 动作解析协议（0/2+/混合 → FormatError） | T2.2.1 | 单元测试 | `tests/unit/test_parser.py` | pytest 报告 | ⬜ |
| REQ-003 本机执行 | T2.2.2, T2.2.3 | 单元测试 | `tests/unit/test_executor.py`, `test_validator.py` | pytest 报告 | ⬜ |
| 本机执行安全协议（shlex+shell=False） | T2.2.2 | 单元测试 | `tests/unit/test_executor.py` | pytest 报告 | ⬜ |
| 命令校验黑名单协议 | T2.2.3 | 单元测试 | `tests/unit/test_validator.py` | pytest 报告 | ⬜ |
| REQ-004 提交标记契约 | T2.2.4 | 单元测试（ADR-002 P0 全覆盖） | `tests/unit/test_observer.py` | pytest 报告 | ⬜ |
| 提交标记契约（ANSI/Unicode/rc==0） | T2.2.4 | 单元测试（边界值） | `tests/unit/test_observer.py` | pytest 报告 | ⬜ |
| REQ-005 模型适配 | T2.2.5 | 单元测试 | `tests/unit/test_model_adapter.py` | pytest 报告 | ⬜ |
| 模型 API 重试协议 | T2.2.5 | 单元测试（mock call_count） | `tests/unit/test_model_adapter.py` | pytest 报告 | ⬜ |
| 成本计费协议（cost_calculation_method） | T2.2.5 | 单元测试 | `tests/unit/test_model_adapter.py` | pytest 报告 | ⬜ |
| REQ-006 轨迹记录 | T2.2.6 | 单元测试（ADR-002 P0 全覆盖） | `tests/unit/test_trajectory.py` | pytest 报告 | ⬜ |
| 轨迹 JSON 格式（schema_version + tool_call_id） | T2.2.6 | 单元测试 | `tests/unit/test_trajectory.py` | pytest 报告 | ⬜ |
| OSError 备用路径协议 | T2.2.6 | 单元测试（mock IO） | `tests/unit/test_trajectory.py` | pytest 报告 | ⬜ |
| REQ-001 核心状态机闭环 | T2.3.1 | 集成测试（ADR-002 P0 全覆盖） | `tests/integration/test_state_machine.py` | pytest 报告 | ⬜ |
| 状态机终态协议（6 终态 + returncode 映射） | T2.3.1, T3.1.5 | 集成测试 + 单元测试 | `tests/integration/test_state_machine.py`, `test_exit_codes.py` | pytest 报告 | ⬜ |
| FormatError 防循环协议（连续 5 次） | T2.3.1 | 集成测试 | `tests/integration/test_state_machine.py` | pytest 报告 | ⬜ |
| REQ-010 CLI 主命令 | T3.1.1, T3.1.2, T3.1.5 | 手动验证 + 集成测试 + 单元测试 | `logs/cli_help.txt`, `tests/integration/test_cli_run.py`, `test_exit_codes.py` | 截图 + pytest 报告 | ⬜ |
| CLI 参数语义（--model 覆盖语义） | T3.1.2 | 集成测试 | `tests/integration/test_cli_run.py` | pytest 报告 | ⬜ |
| ConfigError 诊断文件写入 | T3.1.2 | 集成测试 | `tests/integration/test_cli_run.py` | pytest 报告 | ⬜ |
| REQ-008 批处理模式 | T3.1.3 | 单元测试 + 冒烟测试（ADR-002 P0） | `tests/unit/test_batch.py`, `tests/integration/test_batch_smoke.py` | pytest 报告 | ⬜ |
| preds.json schema | T3.1.3 | 冒烟测试（ADR-002 P0） | `tests/integration/test_batch_smoke.py` | pytest 报告 | ⬜ |
| REQ-009 Textual 检查器 | T3.1.4 | 手动验证（P1） | `logs/checker_screenshot.png` | 截图 | ⬜ |
| 退出码映射协议（CLI vs Core 分离） | T3.1.5 | 单元测试（表驱动全覆盖） | `tests/unit/test_exit_codes.py` | pytest 报告 | ⬜ |
| S1 退出标准 | INT-S1 | 冒烟测试 | Sprint 冒烟检查 | pytest 输出 + lint 日志 | ⬜ |
| S2 退出标准 | INT-S2 | 冒烟测试 | Sprint 冒烟检查 | pytest 输出 + 日志截图 | ⬜ |
| S3 退出标准 | INT-S3 | 冒烟测试 + 可选 E2E | Sprint 冒烟检查 | pytest 输出 + 截图 + preds.json | ⬜ |
| 真机/火测（E2E）默认关闭 | INT-S3 | E2E（`MINI_SWE_ENABLE_E2E=1`） | `tests/e2e/`（环境变量启用） | E2E 测试报告 | ⬜ |
