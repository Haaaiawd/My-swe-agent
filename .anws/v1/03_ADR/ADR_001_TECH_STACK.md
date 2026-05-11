# ADR-001: 技术栈选择

**状态**: Accepted
**日期**: 2026-05-10

---

## 背景

mini SWE Agent 需要支持 subprocess 执行、模型 API 调用、YAML + Jinja2 配置、Textual TUI、批处理并发、轨迹 JSON 记录、重试机制。

需求已明确提到 Python 生态库（subprocess、tenacity、pyyaml、jinja2、textual）。

**约束条件**：
- 功能需求：核心状态机闭环、严格动作协议、提交标记契约、本机执行、模型适配、配置管理、CLI 能力、轨迹记录、Textual 检查器
- 非功能需求：性能（单步超时 120 秒）、安全（禁止硬编码密钥）、可扩展性（批处理并发）
- 技术约束：用户已明确提到 Python 生态库

---

## 决策

**选择技术栈**：Python 3.10+ + click + litellm + pyyaml+jinja2 + textual + tenacity + multiprocessing + pytest

### 编程语言
**选择**: Python 3.10+

**理由**:
- 需求已明确提到 Python 生态库
- subprocess 是 Python 标准库，满足本机执行需求
- 丰富的第三方库支持（litellm、textual、tenacity 等）
- AI/ML 首选语言，生态丰富

### CLI 框架
**选择**: click

**理由**:
- 成熟稳定，文档完善
- 装饰器风格，易于使用
- 支持子命令、参数验证、自动生成 help

**候选方案对比**:
| 方案 | 优点 | 缺点 |
|------|------|------|
| click | 成熟、文档完善、装饰器风格 | 略显冗长 |
| typer | 类型提示友好、更现代 | 相对较新 |
| argparse | 标准库、无依赖 | 冗长、易出错 |

### 模型 API
**选择**: litellm

**理由**:
- 统一接口，支持 OpenAI、Anthropic、本地模型等
- 便于切换不同模型
- 自动处理重试、速率限制等

**候选方案对比**:
| 方案 | 优点 | 缺点 |
|------|------|------|
| litellm | 统一接口、支持多模型 | 额外依赖 |
| openai SDK | 官方支持、功能完整 | 仅支持 OpenAI |

### 配置管理
**选择**: pyyaml + jinja2

**理由**:
- 需求明确要求 YAML + Jinja2
- StrictUndefined 模式避免配置错误
- 支持模板渲染，提高配置复用性

### TUI 框架
**选择**: textual

**理由**:
- 需求明确要求 textual
- 现代、功能丰富
- 对 ANSI 转义序列鲁棒

### 重试机制
**选择**: tenacity

**理由**:
- 需求明确要求 tenacity
- 装饰器风格，易于使用
- 支持指数退避、自定义停止条件

### 并发
**选择**: multiprocessing

**理由**:
- 需求明确要求 multiprocessing
- 进程级隔离，一个失败不影响其他
- 适合 CPU 密集型任务

### 测试框架
**选择**: pytest

**理由**:
- Python 生态标准
- 插件丰富（pytest-cov、pytest-mock 等）
- fixture 机制强大

### 类型检查
**选择**: mypy（可选）

**理由**:
- 静态类型检查，提高代码质量
- 可选，不强制

---

## 候选方案对比

| 候选方案 | 总分 | 优势 | 劣势 |
|---------|------|------|------|
| Python 生态（推荐） | 48/60 | 生态丰富、AI 友好、满足所有需求 | 性能不如 Go/Rust（但足够） |
| Node.js | 40/60 | 异步 I/O 强大 | subprocess 支持较弱、用户未提及 |
| Go | 42/60 | 性能优秀、并发强大 | 用户未提及、学习曲线较陡 |

---

## 权衡点

1. **Python 性能不如 Go/Rust**：但对于 CLI 工具和 subprocess 调用足够，性能不是瓶颈
2. **multiprocessing 占用更多内存**：但提供进程级隔离，一个失败不影响其他
3. **litellm 增加额外依赖**：但提供统一接口，便于切换不同模型

---

## 风险点

1. **模型 API 变化可能需要适配**：通过 litellm 统一接口降低风险
2. **批处理并发可能受系统资源限制**：通过可配置 workers 参数缓解
3. **Windows 兼容性**：subprocess 使用 shlex.split(posix=True) 在 Windows spawn 模式下可能产生错误的参数分割；建议 Windows 用户使用 WSL 或 Git Bash，或在实现层检测平台并切换 posix 参数（CH-R2-07）

---

## 后果

### 正面
- 满足所有功能需求
- 生态丰富，易于集成
- AI 友好，便于未来扩展

### 负面
- 性能不如编译型语言（但足够）
- 额外依赖（litellm）

### 需要的后续行动
- 在 pyproject.toml 中定义依赖
- 在 README 中说明 Python 版本要求
- 在 CI/CD 中配置 pytest 和 mypy