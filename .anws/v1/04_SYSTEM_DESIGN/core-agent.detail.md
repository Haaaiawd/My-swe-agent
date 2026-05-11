# Core Agent System — 实现细节 (L1)

> **文件性质**: L1 实现层 · **对应 L0**: [`core-agent.md`](./core-agent.md)
> 本文件仅在 `/forge` 任务明确引用时加载。日常阅读和任务规划请优先看 L0。
> **孤岛检查**: 本文件各节均须在 L0 有对应超链接入口，禁止孤岛内容。

---

## 版本历史

> 所有变更记录集中于此，不再散落在代码注释里。

| 版本 | 日期         | Changelog |
| ---- | ------------ | --------- |
| v1.0 | 2026-05-10 | 初始版本  |
| v1.1 | 2026-05-10 | Challenge 审查修复：C1(subprocess安全链)、H1(tool_call_id关联)、H2(confirm_mode默认值)、H3(Parser冲突检测)、H4(FormatError类定义)、M1(成本上限检查时机)、M2(轨迹格式统一)、M3(状态转换表)、M4(观测模板接口)、M5(FATAL_CONFIG范围) |
| v1.2 | 2026-05-10 | Challenge Round 1 P0 修复：C2(终态映射)、H4(成本检查时机)、H6(CLI配置覆盖)、H7(preds.json字段) |
| v1.3 | 2026-05-10 | Challenge Round 1 P1 修复：H5(StateMachineContext)、H8(敏感信息过滤)、H9(Jinja2模式)、H12(步数定义) |
| v1.4 | 2026-05-11 | Challenge Round 4 修复：CH-R4-01(防循环计数器)、CH-R4-02(VALIDATE子步骤文档一致性) |

---

## 本文件章节索引

|   §   | 章节                                                                 |   对应 L0 入口   |
| :---: | -------------------------------------------------------------------- | :--------------: |
|  §1   | [配置常量](#1-配置常量-config-constants)                             |  L0 §7 技术选型  |
|  §2   | [完整数据结构](#2-核心数据结构完整定义-full-data-structures)         |  L0 §6 数据模型  |
|  §3   | [核心算法伪代码](#3-核心算法伪代码-non-trivial-algorithm-pseudocode) | L0 §5 操作契约表 |
|  §4   | [决策树详细逻辑](#4-决策树详细逻辑-decision-tree-details)            |   L0 §4 架构图   |
|  §5   | [边缘情况与注意事项](#5-边缘情况与注意事项-edge-cases--gotchas)      |    L0 §5 / §9    |
|  §6   | [测试辅助](#6-测试辅助-test-helpers) *(可选)*                        | L0 §11 测试策略  |

---

## §1 配置常量 (Config Constants)

> 所有硬编码配置、枚举映射、查找表集中放在此处。
> **L0 对应入口**: L0 §7 技术选型 → *配置常量详见 [L1 §1]*

```python
# ── 状态枚举 ──
class State(str, Enum):
    MODEL = "MODEL"
    PARSE = "PARSE"
    CONFIRM = "CONFIRM"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    # 终态
    SUBMITTED = "SUBMITTED"
    LIMIT_STEP = "LIMIT_STEP"
    LIMIT_COST = "LIMIT_COST"
    INTERRUPT = "INTERRUPT"
    FATAL_CONFIG = "FATAL_CONFIG"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"  # 未预期异常终态

# ── 协议枚举 ──
class Protocol(str, Enum):
    TOOL_CALL = "tool-call"
    TEXT = "text"

# ── 默认配置 ──
DEFAULT_CONFIG = {
    "step_limit": 100,
    "cost_limit": 10.0,
    "timeout": 120,
    "protocol": "tool-call",
    "confirm_mode": True,  # 默认 confirm 模式，--yolo 覆盖为 False
}

# ── 提交标记 ──
SUBMISSION_MARKER = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"

# ── 轨迹配置 ──
TRAJECTORY_SCHEMA_VERSION = "v1"
MAX_COMMAND_LENGTH = 10000

# ── 重试配置 ──
RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY = 1
RETRY_MAX_DELAY = 60
RETRY_MULTIPLIER = 2

# ── 输入验证：禁止的 shell 元字符 ──
FORBIDDEN_SHELL_CHARS = set(";|&$<>`\\")
```

---

## §2 核心数据结构完整定义 (Full Data Structures)

> 含方法体的完整类定义。L0 层只放属性声明和方法签名。
> **L0 对应入口**: L0 §6.1 末尾锚点 → *完整方法实现详见 [L1 §2]*

```python
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class ExecutionResult:
    """subprocess 执行结果"""
    returncode: int
    stdout: str  // 经过观测模板截断/渲染后的输出（用于展示和轨迹记录）
    stderr: str
    stdout_original: Optional[str] = None  // 原始 stdout（未截断，用于提交标记检测；CH-R2-05）
    exception_metadata: Optional[dict] = None

    def is_success(self) -> bool:
        """判断执行是否成功"""
        return self.returncode == 0

    def get_output(self) -> str:
        """获取完整输出（stdout + stderr）"""
        return f"{self.stdout}\n{self.stderr}" if self.stderr else self.stdout

@dataclass
class Observation:
    """观测结果"""
    content: str
    submitted: bool
    submission_text: Optional[str] = None

    def has_submission(self) -> bool:
        """判断是否有提交内容"""
        return self.submitted and self.submission_text is not None

@dataclass
class ModelResponse:
    """模型 API 响应"""
    message: dict
    cost: float

    def is_tool_call(self) -> bool:
        """判断是否为 tool-call 模式"""
        return "tool_calls" in self.message

@dataclass
class Trajectory:
    """轨迹记录"""
    schema_version: str = TRAJECTORY_SCHEMA_VERSION
    messages: list[dict] = field(default_factory=list)
    cost_accumulator: float = 0.0
    step_counter: int = 0

    def add_message(self, message: dict, tool_call_id: Optional[str] = None) -> None:
        """追加消息到轨迹"""
        if tool_call_id:
            message["tool_call_id"] = tool_call_id
        message["timestamp"] = datetime.utcnow().isoformat()
        self.messages.append(message)

    def add_cost(self, cost: float) -> None:
        """累加成本"""
        self.cost_accumulator += cost

    def increment_step(self) -> None:
        """步数计数器加一

        步数定义：每次命令执行完成（进入 OBSERVE 状态）后增加 1，
        无论 returncode 值（returncode != 0 也算一次执行）。
        仅当命令未执行时（FormatError、CommandValidationError、超时异常等）不增加步数。
        """
        self.step_counter += 1


@dataclass
class StateMachineContext:
    """状态机上下文：管理跨状态的变量"""
    response: Optional[ModelResponse] = None
    command: Optional[str] = None
    result: Optional[ExecutionResult] = None
    observation: Optional[Observation] = None
    tool_call_id: Optional[str] = None
    consecutive_format_errors: int = 0  # CH-R4-01: FormatError 防循环计数器

class FormatError(Exception):
    """格式错误"""
    def __init__(self, message: str, error_type: str):
        self.message = message
        self.error_type = error_type
        super().__init__(message)
```

---

## §3 核心算法伪代码 (Non-Trivial Algorithm Pseudocode)

> [!IMPORTANT]
> **准入门槛 — 不满足任意一条，禁止写入本节**
>
> | 准入条件 | 说明 |
> |---------|------|
> | 函数体估计 **> 15 行** | 短函数从 L0 操作契约表已可理解 |
> | 含**不明显的业务规则** | 伤害公式、状态机分支、复杂校验 |
> | 含**多步骤副作用链** | A→检查→B→更新C→触发D，顺序不可颠倒 |
> | **同事看签名猜不出实现** | 函数名+参数已能清楚表达意图则不需要 |

每个小节对应 L0 §5 操作契约表的一行，提供完整函数体。

### §3.1 parse_action

**对应契约**: L0 §5.1 — `parse_action(message, protocol)`
**准入理由**: 恰好一个动作检测逻辑复杂，包含多个分支和错误处理

```python
def parse_action(message: dict, protocol: str) -> str | FormatError:
    """
    解析助手消息，提取命令字符串

    前置条件:
    1. 消息格式正确
    2. 命令非空

    副作用:
    - 无
    """
    tool_call_count = len(message.get("tool_calls", []))
    content = message.get("content", "")

    # 先统一提取文本模式的动作块（无论是否为 tool-call 模式）
    fence_blocks = extract_fence_blocks(content)  # 提取围栏块
    xml_blocks = extract_xml_blocks(content)      # 提取 XML 块
    text_blocks = fence_blocks + xml_blocks

    # Tool-call 模式检测
    if tool_call_count > 0:
        if tool_call_count == 1:
            tool_call = message["tool_calls"][0]
            if tool_call.get("type") == "bash":
                command = tool_call.get("function", {}).get("arguments", {}).get("command", "")
                if not command:
                    return FormatError("Empty command", "empty_command")
                # 检测文本模式同时命中（基于提取结果，而非简单字符匹配）
                if text_blocks:
                    return FormatError("Tool-call and text conflict", "conflict")
                return command
        return FormatError(f"Expected exactly 1 tool_call, got {tool_call_count}", "multiple_actions")

    # 文本模式检测
    if fence_blocks and xml_blocks:
        return FormatError("Fence and XML blocks conflict", "conflict")
    if len(fence_blocks) == 1:
        return fence_blocks[0]
    if len(xml_blocks) == 1:
        return xml_blocks[0]

    return FormatError("Expected exactly 1 action block", "zero_action")
```

> **注意事项**:
> - 必须先检测 tool-call，再检测文本模式
> - tool-call 与文本同时命中时抛冲突错误
> - 命令为空时抛 FormatError

### §3.1b validate_command

**对应契约**: L0 §5.1 — `validate_command(command)`
**准入理由**: 命令安全校验包含黑名单正则匹配、危险标志组合检测

```python
class CommandValidationError(Exception):
    """命令校验失败异常"""
    def __init__(self, command: str, reason: str):
        self.command = command
        self.reason = reason
        super().__init__(f"Command validation failed: {reason}")

# CH-R4-02: 破坏性命令黑名单正则
FORBIDDEN_PATTERNS = [
    r"rm\s+-rf\s+/",                    # 删除根目录
    r"dd\s+if=/dev/zero",                # 写零到设备
    r"mkfs\b",                           # 格式化文件系统
    r"format\b",                         # 格式化
    r":(){ :|:& };:",                    # fork bomb
]

# 危险标志 + 破坏性命令组合
DESTRUCTIVE_COMMANDS = ["rm", "mv", "dd", " shred", "mkfs"]
DANGEROUS_FLAGS = ["-f", "--force", "-rf", "--recursive"]

def validate_command(command: str) -> None:
    """
    校验命令安全性

    前置条件:
    1. 命令非空

    副作用:
    - 无（纯校验函数）
    """
    if not command or not command.strip():
        raise CommandValidationError(command, "Empty command")

    # 黑名单正则匹配
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            raise CommandValidationError(command, f"Forbidden pattern matched: {pattern}")

    # 危险标志 + 破坏性命令组合
    parts = shlex.split(command)
    if parts:
        cmd_base = parts[0].lower()
        if cmd_base in DESTRUCTIVE_COMMANDS:
            for flag in DANGEROUS_FLAGS:
                if flag in parts[1:]:
                    raise CommandValidationError(command, f"Dangerous flag '{flag}' used with destructive command '{cmd_base}'")

    # 校验通过（无异常抛出）
```

> **注意事项**:
> - 校验失败时抛 `CommandValidationError`，不执行任何 Shell
> - 校验通过后返回 None，由调用方继续执行流程
> - 白名单模式（可选）: 配置 `agent.whitelist_only=True` 时，只允许白名单内命令

### §3.2 execute_command

**对应契约**: L0 §5.1 — `execute_command(command, timeout, cwd)`
**准入理由**: subprocess 执行包含超时控制、异常捕获、结果结构化

```python
def execute_command(command: str, timeout: int, cwd: str) -> ExecutionResult:
    """
    执行 Shell 命令

    前置条件:
    1. 命令非空
    2. 工作目录存在

    副作用:
    - 执行 Shell 命令
    """
    try:
        # 安全：使用 shlex.split 拆分命令字符串为列表，避免 shell=True
        # CH-R2-07: Windows 兼容——spawn 模式下使用 posix=False
        posix_mode = os.name != "nt"
        args = shlex.split(command, posix=posix_mode)
        result = subprocess.run(
            args,
            shell=False,  # 安全：禁止 shell=True
            timeout=timeout,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,  # 不抛异常，手动检查 returncode
        )
        return ExecutionResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            exception_metadata=None,
        )
    except subprocess.TimeoutExpired as e:
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
            exception_metadata={"type": "TimeoutExpired", "message": str(e)},
        )
    except Exception as e:
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr=str(e),
            exception_metadata={"type": type(e).__name__, "message": str(e)},
        )
```

> **注意事项**:
> - 必须使用 shell=False，避免命令注入
> - 超时时直接终止进程，不重试
> - 捕获所有异常，返回结构化结果

### §3.3 observe_result

**对应契约**: L0 §5.1 — `observe_result(result)`
**准入理由**: 提交标记检测逻辑包含 lstrip、行分割、首行匹配

```python
def observe_result(result: ExecutionResult) -> Observation:
    """
    观测执行结果

    前置条件:
    1. ExecutionResult 有效

    副作用:
    - 无
    """
    stdout = result.stdout
    submitted = False
    submission_text = None

    # 检测提交标记
    if result.is_success():
        lines = stdout.lstrip().splitlines()
        if lines and lines[0] == SUBMISSION_MARKER:
            submitted = True
            submission_text = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # 渲染观测内容（使用配置的模板）
    # CH-R3-06: 若观测模板渲染失败，降级为原始 stdout/stderr，不中断状态机
    try:
        content = render_observation_template(result)
    except ConfigError as e:
        logger.warning(f"Observation template render failed: {e}. "
                       f"Falling back to raw output.")
        content = result.stdout_original or result.stdout

    return Observation(
        content=content,
        submitted=submitted,
        submission_text=submission_text,
    )
```

> **注意事项**:
> - 只有 returncode==0 时才检测提交标记
> - 标记必须在首行（lstrip 后）
> - 首行之后的内容为提交正文

### §3.4 call_model

**对应契约**: L0 §5.1 — `call_model(messages, config)`
**准入理由**: 模型 API 调用包含重试逻辑、协议切换、消息扁平化

```python
@retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_BASE_DELAY, max=RETRY_MAX_DELAY),
    retry=retry_if_exception_type((TimeoutError, APIError)),
    before_sleep=lambda retry_state: logger.warning(f"Retry {retry_state.attempt_number}"),
)
def call_model(messages: list, config: dict) -> ModelResponse:
    """
    调用模型 API

    前置条件:
    1. 配置有效

    副作用:
    - 调用外部 API
    - 累加成本
    """
    client = litellm completion
    response = client(
        model=config["model_name"],
        messages=messages,
        api_key=config.get("api_key"),
        **config.get("extra_params", {}),
    )

    # 提取成本
    cost = response.get("_response", {}).get("cost", 0.0)

    # 消息扁平化（如果 API 返回无状态 response）
    if "response" in response or "output_items" in response:
        assistant_message = flatten_response(response)
    else:
        assistant_message = response.choices[0].message

    return ModelResponse(
        message=assistant_message,
        cost=cost,
    )
```

> **注意事项**:
> - 使用 tenacity 重试，指数退避 + 抖动
> - FormatError 不重试（在调用方处理）
> - 消息扁平化避免上下文丢失

### §3.5 append_to_trajectory

**对应契约**: L0 §5.1 — `append_to_trajectory(trajectory, message)`
**准入理由**: 轨迹追加包含 timestamp、tool_call_id 关联、schema version 检查

```python
def append_to_trajectory(trajectory: Trajectory, message: dict, tool_call_id: Optional[str] = None) -> None:
    """
    追加消息到轨迹

    前置条件:
    1. 轨迹已初始化

    副作用:
    - 修改轨迹对象
    """
    # 检查 schema version
    if trajectory.schema_version != TRAJECTORY_SCHEMA_VERSION:
        raise ValueError(f"Schema version mismatch: expected {TRAJECTORY_SCHEMA_VERSION}, got {trajectory.schema_version}")

    # 追加消息
    trajectory.add_message(message, tool_call_id)

    # 如果是工具调用结果，累加步数
    if message.get("role") == "tool":
        trajectory.increment_step()
```

> **注意事项**:
> - 必须检查 schema version 兼容性
> - tool_call_id 关联工具调用结果
> - 工具调用结果累加步数

### §3.6 check_submission

**对应契约**: L0 §5.1 — `check_submission(observation)`
**准入理由**: 提交检测逻辑包含多个条件判断

```python
def check_submission(observation: Observation) -> bool:
    """
    检查是否应该提交

    前置条件:
    1. Observation 有效

    副作用:
    - 无
    """
    return observation.submitted and observation.has_submission()
```

> **注意事项**:
> - 必须同时满足 submitted 和有提交内容
> - 由 observe_result 负责检测提交标记

---

## §4 决策树详细逻辑 (Decision Tree Details)

> 对应 L0 Mermaid 决策图的文字展开 + 完整伪代码。
> **L0 对应入口**: L0 §4 架构图注释 → *完整决策逻辑见 [L1 §4]*

### §4.1 状态机主循环

**对应 L0 Mermaid**: `core-agent.md §4.3`

```python
def run_state_machine(task: str, config: dict) -> str:
    """
    运行状态机主循环

    返回: 终态名称
    """
    # 初始化
    state = State.MODEL
    trajectory = Trajectory()
    trajectory.add_message({"role": "user", "content": task})
    ctx = StateMachineContext()  # 使用上下文管理跨状态变量

    # 主循环
    while state not in [State.SUBMITTED, State.LIMIT_STEP, State.LIMIT_COST, State.INTERRUPT, State.FATAL_CONFIG, State.UNKNOWN_ERROR]:
        try:
            if state == State.MODEL:
                # MODEL 状态：先检查成本上限，避免浪费模型调用
                # CH-R3-09: 预防性检查——调用模型前估算是否超限
                # estimated_next_call 基于历史平均或固定保守值（如 0.05 USD）
                estimated_next_call = config.get("cost_estimate_per_call", 0.05)
                if trajectory.cost_accumulator + estimated_next_call > config["cost_limit"]:
                    state = State.LIMIT_COST
                    continue

                ctx.response = call_model(trajectory.messages, config)
                trajectory.add_cost(ctx.response.cost)

                # 提取 tool_call_id（tool-call 模式下）
                if ctx.response.is_tool_call():
                    tool_calls = ctx.response.message.get("tool_calls", [])
                    if tool_calls:
                        ctx.tool_call_id = tool_calls[0].get("id")

                trajectory.add_message(ctx.response.message)
                state = State.PARSE

            elif state == State.PARSE:
                # PARSE 状态
                protocol = config["protocol"]
                parse_result = parse_action(ctx.response.message, protocol)

                if isinstance(parse_result, FormatError):
                    # FormatError：不执行，递增防循环计数器
                    ctx.consecutive_format_errors += 1
                    trajectory.add_message({
                        "role": "system",
                        "content": f"FormatError: {parse_result.message}"
                    }, tool_call_id=ctx.tool_call_id)  # 关联当前 tool_call_id
                    ctx.tool_call_id = None  # 重置

                    # CH-R4-01: 检查防循环阈值（默认 5 次）
                    max_format_errors = config.get("max_consecutive_format_errors", 5)
                    if ctx.consecutive_format_errors >= max_format_errors:
                        logger.error(f"Consecutive FormatError reached threshold ({max_format_errors}), entering UNKNOWN_ERROR")
                        state = State.UNKNOWN_ERROR
                    else:
                        state = State.MODEL
                else:
                    # 恰好一个动作：归零防循环计数器
                    ctx.consecutive_format_errors = 0

                    # CH-R4-02: VALIDATE 子步骤（命令安全校验）
                    ctx.command = parse_result
                    try:
                        validate_command(ctx.command)
                    except CommandValidationError as e:
                        trajectory.add_message({
                            "role": "system",
                            "content": f"CommandValidationError: {e.reason}"
                        }, tool_call_id=ctx.tool_call_id)
                        ctx.tool_call_id = None
                        state = State.MODEL
                        continue

                    if config["confirm_mode"]:
                        state = State.CONFIRM
                    else:
                        state = State.EXECUTE

            elif state == State.CONFIRM:
                # CONFIRM 状态
                user_input = input(f"Execute: {ctx.command}? [y/n] ")
                if user_input.lower() == "y":
                    state = State.EXECUTE
                else:
                    state = State.INTERRUPT

            elif state == State.EXECUTE:
                # EXECUTE 状态：命令执行前归零防循环计数器
                ctx.consecutive_format_errors = 0
                ctx.result = execute_command(ctx.command, config["timeout"], config["cwd"])
                state = State.OBSERVE

            elif state == State.OBSERVE:
                # OBSERVE 状态
                ctx.observation = observe_result(ctx.result)
                trajectory.add_message({
                    "role": "tool",
                    "content": ctx.observation.content,
                }, tool_call_id=ctx.tool_call_id)  # 关联 tool_call_id
                ctx.tool_call_id = None  # 重置，准备下一轮

                # 检查提交
                if check_submission(ctx.observation):
                    state = State.SUBMITTED
                else:
                    # 检查上限
                    if trajectory.step_counter >= config["step_limit"]:
                        state = State.LIMIT_STEP
                    elif trajectory.cost_accumulator >= config["cost_limit"]:
                        state = State.LIMIT_COST
                    else:
                        state = State.MODEL

        except KeyboardInterrupt:
            # 用户中断
            state = State.INTERRUPT
        except ConfigurationError as e:
            # 配置错误（启动时应已验证，这里是兜底）
            logger.error(f"Configuration error: {e}")
            state = State.FATAL_CONFIG
        except Exception as e:
            # 未预期的运行时异常（编程错误、外部系统故障等）
            logger.error(f"Unexpected error: {e}")
            state = State.UNKNOWN_ERROR  # 新增终态，用于未预期异常

    // 保存轨迹（CH-R2-04: 处理磁盘满/权限不足）
    trajectory_path = config.get("trajectory_path", "trajectory.json")
    try:
        save_trajectory(trajectory, trajectory_path)
    except OSError as e:
        logger.error(f"Failed to save trajectory to {trajectory_path}: {e}")
        // 尝试备用路径
        import tempfile, uuid
        backup_path = os.path.join(tempfile.gettempdir(), f"trajectory_backup_{uuid.uuid4().hex[:8]}.json")
        try:
            save_trajectory(trajectory, backup_path)
            logger.warning(f"Trajectory saved to backup: {backup_path}")
        except Exception:
            logger.critical("Failed to save trajectory to both primary and backup paths")

    # 终态 → returncode 映射（供 CLI 精确判断）
    EXITCODE_MAP = {
        State.SUBMITTED: 0,
        State.LIMIT_STEP: 2,
        State.LIMIT_COST: 3,
        State.INTERRUPT: 4,
        State.FATAL_CONFIG: 5,
        State.UNKNOWN_ERROR: 6,
    }
    returncode = EXITCODE_MAP.get(state, 6)

    return AgentResult(
        trajectory_path=config["trajectory_path"],
        final_state=state.value,
        overall_output=_extract_overall_output(trajectory) if state == State.SUBMITTED else None,
        returncode=returncode,
    )
```

> **注意事项**:
> - 主循环持续直到进入终态
> - FormatError 不执行命令，直接返回 MODEL
> - 中断时尽力保存轨迹

---

## §5 边缘情况与注意事项 (Edge Cases & Gotchas)

> 实现时必须处理的非显而易见情况。
> **L0 对应入口**: L0 §5 或 §9 安全性章节的锚点

| 场景           | 风险       | 处理方式       |
| -------------- | ---------- | -------------- |
| 命令字符串为空 | FormatError | Parser 检测并抛错误 |
| tool-call 与文本同时命中 | FormatError | Parser 检测冲突并抛错误 |
| 提交标记在 returncode!=0 时出现 | 错误提交 | Observer 检测 returncode，拒绝提交 |
| 中断时轨迹保存不完整 | 轨迹丢失 | 尽力保存，不保证完整性 |
| 轨迹文件过大 | 内存耗尽 | 使用 JSONL 流式写入 |
| 模型 API 缺少 cost 字段 | 成本计算错误 | 配置策略：忽略或报错 |

### §5.1 subprocess 安全

```python
# 错误做法
# subprocess.run(command, shell=True)  # 命令注入风险！
# subprocess.run(command, shell=False)  # 字符串传入 shell=False，命令解析失败！

# 正确做法
# args = shlex.split(command, posix=(os.name != "nt"))
# subprocess.run(args, shell=False)  # 列表形式参数
```

### §5.2 提交标记检测

```python
# 错误做法
# if SUBMISSION_MARKER in stdout:  # 可能在非首行匹配

# 正确做法
# lines = stdout.lstrip().splitlines()
# if lines and lines[0] == SUBMISSION_MARKER:  # 必须在首行
```

### §5.3 轨迹追加

```python
# 错误做法
# trajectory["messages"].append(message)  # 缺少 timestamp

# 正确做法
# trajectory.add_message(message)  # 自动添加 timestamp
```

---

## §6 测试辅助 (Test Helpers)

> 可选。单元测试中复用的工厂函数或 fixtures。
> **L0 对应入口**: L0 §11 测试策略锚点

```python
def make_test_execution_result(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> ExecutionResult:
    """创建测试用 ExecutionResult"""
    return ExecutionResult(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        exception_metadata=None,
    )

def make_test_observation(
    content: str = "",
    submitted: bool = False,
    submission_text: Optional[str] = None,
) -> Observation:
    """创建测试用 Observation"""
    return Observation(
        content=content,
        submitted=submitted,
        submission_text=submission_text,
    )

def make_test_trajectory(
    messages: Optional[list[dict]] = None,
    cost_accumulator: float = 0.0,
    step_counter: int = 0,
) -> Trajectory:
    """创建测试用 Trajectory"""
    return Trajectory(
        messages=messages or [],
        cost_accumulator=cost_accumulator,
        step_counter=step_counter,
    )

def make_test_model_response(
    message: dict,
    cost: float = 0.0,
) -> ModelResponse:
    """创建测试用 ModelResponse"""
    return ModelResponse(
        message=message,
        cost=cost,
    )
```

---

<!--  AGENT 使用指南

何时创建本文件: 触发 L0 拆分规则 R1-R5 任意一条时。
  R1 单个代码块 > 30 行
  R2 代码块总行数 > 200 行
  R3 配置常量字典条目 > 5 个
  R4 版本内联注释 > 5 处
  R5 文档总行数 > 500 行

孤岛检查: 本文件每新增一节，必须同步在 L0 对应位置添加超链接锚点。

§ 编号约定:
  §1 配置常量  — 始终第一节
  §2 数据结构  — 含方法体的完整类
  §3 算法伪代码 — 按函数顺序编号 (§3.1, §3.2 ...)
  §4 决策树    — 对应 L0 Mermaid 图的展开
  §5 边缘情况  — 从代码注释中提取的 "#  注意" 类内容
  §6 测试辅助  — 可选
-->
