# ADR-007: 模型适配协议

**状态**: Accepted
**日期**: 2026-05-10

---

## 背景

需求 G 部分定义了模型适配：同时支持 tool-call 与文本协议（均可切换；默认可配置）。

若 API 返回无状态 response/output_items：下一轮调用前须扁平化为对话消息，避免工具结果与上下文丢失。

每次调用计费 cost（可为 0）；全局累计与上限。

---

## 决策

### 协议切换

**支持协议**：
- Tool-call 模式（OpenAI、Anthropic 等原生支持）
- 文本模式（纯文本输出）

**切换方式**：
- 配置文件中指定默认协议
- CLI 参数 `--protocol` 覆盖默认值

**检测逻辑**：
- API 响应包含 tool_calls → Tool-call 模式
- API 响应只有 content → 文本模式

### 消息扁平化

**触发条件**：API 返回无状态 response/output_items

**扁平化算法**：
1. 将 response/output_items 转换为对话消息格式
2. 保留 role（assistant/user/tool）
3. 保留 content
4. tool_call 结果与 tool_call_id 关联
5. 追加到消息历史

**目的**：避免工具结果与上下文丢失

### 成本计费

**成本来源**：
- API 返回的 cost 字段（优先）
- 基于 tokens 计算（备选）

**计费策略**：
- 每次调用计费（可为 0）
- 全局累计
- 达到上限时进入 LIMIT_COST 终态

**配置选项**：
- 响应缺 cost 时策略（`cost_missing_strategy`）：
  - `"warn"`（默认）：记录警告，cost 记为 0，继续执行
  - `"ignore"`：cost 记为 0，继续执行（静默）
  - `"error"`：抛出 `CostMissingError`（自定义异常，继承 `RuntimeError`），**不重试**（见 ADR-003）
- 配置项位置：`model.cost_missing_strategy`，默认 `"warn"`

**Token-based 成本估算（当 API 不返回 cost 时）**：
```python
def estimate_cost(input_tokens: int, output_tokens: int, model_name: str) -> float:
    """基于 model 定价表估算成本（USD）。"""
    pricing = PRICING_TABLE.get(model_name, {"input": 0.0, "output": 0.0})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
```
- `PRICING_TABLE` 为内置定价字典（覆盖常见模型），用户可通过配置覆盖。
- 若 model 不在定价表中，cost 记为 0，同时记录 `warn`（当策略为 warn 时）。

**轨迹审计字段**：
- 轨迹 JSON 每条 message 追加 `cost_calculation_method` 字段，值为 `"api" | "token_based" | "missing"`。
- 便于事后审计成本来源。

**缺 cost 异常定义**：
```python
class CostMissingError(RuntimeError):
    """API 响应中缺少 cost 字段且策略为 error 时抛出。"""
    pass
```

---

## 影响范围

- Core Agent System 中的 Model Adapter 组件
- Trajectory Manager 组件（记录成本）

---

## 后续行动

- 在 Model Adapter 组件中实现协议切换
- 在 Model Adapter 组件中实现消息扁平化
- 在 Model Adapter 组件中实现成本计费
- 编写消息扁平化的单元测试（用 fixture 覆盖）