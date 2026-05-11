# ADR-004: 配置管理策略

**状态**: Accepted
**日期**: 2026-05-10

---

## 背景

需求 H 部分明确：YAML + Jinja2，StrictUndefined。多源配置递归合并；须文档化优先级（PIN：CLI vs 文件 vs key=value）。

观测模板强制截断：渲染后 output 长度 >= 10000 时：warning + 前 5000 + 后 5000 + elided_chars = 原长 - 10000；否则全文。

---

## 决策

### 配置优先级

从高到低：CLI 参数 > 配置文件 > 环境变量 > 默认值

**PIN**：CLI vs 文件 vs key=value

### 配置格式

- **主格式**：YAML
- **模板引擎**：Jinja2（StrictUndefined 模式）
- **递归合并**：字典递归合并，列表覆盖

### 配置源

| 配置源 | 格式 | 优先级 | 说明 |
|-------|------|--------|------|
| CLI 参数 | `--key value` | 最高 | 命令行直接指定 |
| 配置文件 | YAML | 高 | 可重复 `--config file.yaml` |
| 环境变量 | `KEY=value` | 中 | 用于密钥 |
| 默认值 | 硬编码 | 低 | 代码中定义 |

### 观测模板截断

**可配置参数**：`truncate_observation_threshold`（默认 10000 字符），可通过配置文件或 CLI 参数覆盖。

```python
def truncate_observation(output: str, max_length: int = 10000) -> str:
    if len(output) >= max_length:
        half = max_length // 2
        elided = len(output) - max_length
        truncated = output[:half] + output[-half:]
        logger.warning(f"Output truncated, elided {elided} chars")
        return truncated
    return output
```

### 安全约束

- **禁止硬编码密钥**：仅允许环境变量与配置文件
- **StrictUndefined**：模板变量未定义时抛出错误（仅用于观测模板渲染；YAML 配置文件加载使用 DebugUndefined 以支持可选变量）
- **敏感信息过滤**：
  - ConfigManager 实现 `_redact()` 递归脱敏，敏感字段（`api_key`, `password`, `token`, `secret`）的值在 `__repr__`/日志/轨迹/错误信息中替换为 `***`
  - 脱敏范围覆盖：配置字典、错误信息、轨迹 JSON 的 messages.content、命令日志的 stdout/stderr
  - 敏感模式检测（正则）：`r'api[_-]?key\s*=\s*[^\s]+'`, `r'sk-[A-Za-z0-9]{20,}'` 等

### ConfigError 异常定义

```python
class ConfigError(RuntimeError):
    """配置管理相关错误的基类。

    Attributes:
        file_path: 触发错误的文件路径（如有）
        line: 模板渲染失败的行号（如有）
        variable: 未定义的变量名（如是 UndefinedError）
        message: 用户友好的错误描述
    """
    def __init__(self, message: str, *, file_path: str | None = None,
                 line: int | None = None, variable: str | None = None):
        super().__init__(message)
        self.file_path = file_path
        self.line = line
        self.variable = variable
```

### 模板缓存策略

- YAML 配置文件和观测模板均使用独立的 jinja2.Template 缓存（`hash(content)` 为 key）
- 缓存随 `ConfigManager.clear_cache()` 清除
- 观测模板使用 StrictUndefined（ADR-004 §安全约束）；YAML 配置文件使用 DebugUndefined（允许 `{{ var | default('x') }}`）

---

## 影响范围

- 配置管理组件必须实现多源合并
- 观测模板必须实现截断逻辑
- CLI 必须支持 `--config` 参数
- README 必须文档化配置优先级

---

## 后续行动

- 实现配置管理组件
- 实现观测模板截断
- 在 CLI 中添加 `--config` 参数
- 在 README 中文档化配置策略