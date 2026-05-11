# ADR-005: 动作解析协议

**状态**: Accepted
**日期**: 2026-05-10

---

## 背景

需求 D 部分定义了严格动作协议：解析器必须在助手输出上得到恰好一个可执行动作。

Tool-call 模式：恰好一次 bash 类工具调用
文本模式：恰好一个围栏块或 XML 块

若抽取数为 0 或 >1，或两族同时命中，或 tool-call 与文本同时命中：抛 FormatError。

---

## 决策

### Tool-call 模式解析

**输入**：API 响应中的 tool_calls 数组

**解析规则**：
- 恰好 1 个 tool_call，且类型为 bash → 提取 command 字符串
- 0 个 tool_call → FormatError
- >1 个 tool_call → FormatError
- tool_call 类型不是 bash → FormatError

**输出**：命令字符串或 FormatError

### 文本模式解析

**输入**：助手消息的 content 字符串

**支持的围栏族**：
- ````mswea_bash_command ... ````
- `<mswea_bash_command>...</>`

**解析规则**：
- 恰好 1 个围栏块，且匹配已配置族 → 提取块内命令字符串
- 0 个围栏块 → FormatError
- >1 个围栏块 → FormatError
- 围栏块和 XML 块同时命中 → FormatError
- 围栏块为空 → FormatError

**输出**：命令字符串或 FormatError

### 混合模式检测

**规则**：
- 同时检测 tool-call 和文本模式
- 若两者同时命中 → FormatError
- 禁止自动选择、禁止静默合并

---

## 影响范围

- Core Agent System 中的 Parser 组件
- Model Adapter System（负责处理不同协议的 API 响应）

---

## 后续行动

- 在 Parser 组件中实现 Tool-call 模式解析
- 在 Parser 组件中实现文本模式解析
- 编写解析协议的单元测试（0 动作、2 动作、tool+文本冲突）