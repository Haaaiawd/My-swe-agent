# ADR-003: 错误处理与重试策略

**状态**: Accepted
**日期**: 2026-05-10

---

## 背景

需求 G 部分明确：瞬态失败用 tenacity；不得把 FormatError 当成功重试。

通过需求澄清，已确定：
- 网络/API 错误重试 5 次
- 执行超时直接终止该步并记录错误，不重试
- 成本计费：使用 API 返回的原始 cost（如有），否则基于 tokens 计算

---

## 决策

### 重试策略

| 错误类型 | 重试策略 | 理由 |
|---------|---------|------|
| 网络超时 | 重试 5 次（tenacity） | 瞬态失败，可能恢复 |
| API 错误（429/500/503） | 重试 5 次（tenacity） | 瞬态失败，可能恢复 |
| RateLimitError (429) | 重试 5 次（tenacity） | 限流，指数退避后可恢复 |
| APIConnectionError | 重试 5 次（tenacity） | 连接问题，可能恢复 |
| FormatError | 不重试 | 协议错误，重试无意义。状态机返回 MODEL，继续循环 |
| 执行超时 | 不重试 | 命令本身的问题，重试无意义。捕获 TimeoutExpired 后进入 OBSERVE，记录 error_type="TIMEOUT"，继续循环 |
| 配置错误 | 不重试 | 配置问题，重试无意义 |
| CostMissingError | 不重试 | 计费信息缺失，非瞬态问题 |
| 命令校验失败 | 不重试 | 安全校验不通过（见下），进入 OBSERVE 记录拒绝原因，继续循环 |

### 重试配置

```python
from tenacity import retry, stop_after_attempt, wait_exponential

# 重试的异常类型（来自 litellm 异常体系）
RETRY_EXCEPTIONS = (
    litellm.Timeout,           # 网络超时
    litellm.APIError,          # 5xx 服务端错误
    litellm.RateLimitError,    # 429 限流
    litellm.ServiceUnavailableError,  # 503 服务不可用
    litellm.APIConnectionError,  # 连接失败
)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RETRY_EXCEPTIONS),
)
def call_model_api():
    ...
```

**不重试的异常**：
- `FormatError`（模型输出格式错误）
- `CostMissingError`（API 响应缺 cost 字段且策略为 error，见 ADR-007）
- `AuthenticationError`（401/403，密钥问题，重试无意义）
- `BadRequestError`（400，请求参数错误）
- `CommandValidationError`（命令内容未通过安全校验，见下）

### 命令校验策略（安全基线）

**目的**：防止模型生成破坏性命令直接执行。

**校验层级**：在 PARSE 之后、EXECUTE 之前增加 VALIDATE 子步骤。

**校验规则**：
1. **黑名单**：禁止 `rm -rf /`、`dd if=/dev/zero`、`mkfs`、`format` 等破坏性命令（正则匹配）。
2. **危险标志检查**：禁止 `-f`/`--force` 与破坏性命令组合；禁止 `--no-confirm`。
3. **白名单模式（可选）**：配置 `command.whitelist` 后，仅允许白名单中的命令通过。

**失败处理**：
- 校验失败 → 抛 `CommandValidationError` → 进入 OBSERVE → 向模型提供拒绝反馈（含拒绝原因）→ 继续循环。
- 不重试（命令本身问题，重试无意义）。

### FormatError 防循环机制

**风险**：FormatError 不增加步数，模型持续输出格式错误时，步数上限无法触发，可能导致无限循环。

**防护措施**：
- 在状态机中维护 `consecutive_format_errors` 计数器。
- 连续 FormatError 达到 `max_consecutive_format_errors`（默认 5）时，强制进入 `UNKNOWN_ERROR` 终态并保存轨迹。
- 每次进入 OBSERVE（成功执行）时重置计数器。

### 错误恢复

- **中断处理**：尽力保存轨迹 JSON，进入 INTERRUPT 终态
- **FATAL_CONFIG**：配置错误时立即终止，不执行任何操作
- **LIMIT_STEP**：达到步数上限时保存轨迹，进入 LIMIT_STEP 终态
- **LIMIT_COST**：达到成本上限时保存轨迹，进入 LIMIT_COST 终态

---

## 影响范围

- 模型适配器必须实现重试逻辑
- 执行器必须实现超时控制
- 核心状态机必须处理各种终态
- 轨迹管理器必须在各种终态下尽力保存

---

## 后续行动

- 在模型适配器中实现 tenacity 重试
- 在执行器中实现超时控制
- 在核心状态机中实现终态处理
- 编写重试策略的单元测试