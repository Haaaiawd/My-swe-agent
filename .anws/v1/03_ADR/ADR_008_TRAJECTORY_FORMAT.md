# ADR-008: 轨迹记录格式

**状态**: Accepted
**日期**: 2026-05-10

---

## 背景

需求 J 部分定义了轨迹 JSON：须含 messages（role/content）及适用时的 timestamp。

Tool-call 模式：观测必须与 tool_call_id（或等价稳定键）关联。

---

## 决策

### 轨迹 JSON 结构

**必需字段**：
```json
{
  "schema_version": "v1",
  "messages": [
    {
      "role": "user|assistant|tool",
      "content": "...",
      "timestamp": "ISO 8601"
    }
  ],
  "cost_accumulator": 0.0,
  "step_counter": 0
}
```

### Tool-call 模式关联

**关联方式**：
- 观测结果与 tool_call_id 关联
- 或使用等价稳定键（如 step_index）

**实现方式**：
- 在 messages 数组中，tool 消息包含 tool_call_id
- 观测结果作为 tool 消息的 content
- 或单独存储 tool_results 字典

### Schema Version 管理

**目的**：未来兼容性

**实现**：
- 轨迹 JSON 顶层字段 `schema_version`
- 读取轨迹时检查版本兼容性
- 不兼容时抛出明确错误

**当前版本**：v1

---

## 影响范围

- Core Agent System 中的 Trajectory Manager 组件
- 所有组件（需记录到轨迹）

---

## 后续行动

- 在 Trajectory Manager 组件中实现轨迹 JSON 序列化
- 实现 tool_call_id 关联
- 实现 schema version 检查
- 编写轨迹存取的单元测试
- 编写 tool 模式下关联字段存在的单元测试