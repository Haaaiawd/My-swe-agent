# mini SWE Agent

一个极简的自动化编程任务执行 Agent。给它一段任务描述，它就能调用大模型，自动分析、编码、验证，直到任务完成。

> [!] **Warning**: This tool executes shell commands automatically. Review the task description and configuration before running. Use `--yolo` with caution.

---

## Demo

给 Agent 一段任务（创建 3 个 HTML 文件），它自动完成：

```
mini-swe-agent run --config agent.yaml --yolo
```

```
╭──────────────────────────────────────────────────────────────────╮
│   mini-swe-agent  ● SUBMITTED   model: deepseek-v4-flash         │
│   Step  17 / 80  [████░░░░░░░░░░░░░░░░░░]  Cost $0.0051          │
│   ❯  echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT                  │
╰──────────────────────────────────────────────────────────────────╯
✓  SUBMITTED  17 steps  $0.0051  0:46
```

Agent 自动生成了 `clock.html`（实时数字时钟）、`matrix.html`（Matrix 雨动画）、`dashboard.html`（系统监控面板）。

---

## Features

- **🤖 模型无关**: 支持 OpenAI、DeepSeek、OpenRouter 等任何 litellm 兼容的模型
- **🖥️ 实时面板**: 运行中显示进度条、步骤、成本、耗时、当前命令、模型输出流
- **🔧 双协议解析**: 原生 Tool-call 模式 + 文本 Fence/XML 模式，自动切换
- **📝 轨迹记录**: 每一步的输入输出、成本、token 数都写入 `trajectory.json`，可追溯可审计
- **💰 成本控制**: 实时估算每步成本，超预算自动停止
- **🧪 测试完备**: 155 个测试（unit + integration），全部通过

---

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Configure

复制 `agent.yaml`，填入你的 API key：

```yaml
model:
  name: "deepseek/deepseek-v4-flash"
  protocol: "text"
  api_key: "${MINI_SWE_MODEL__API_KEY}"   # 从环境变量读取
  stream: true

agent:
  step_limit: 80
  cost_limit: 0.5

output:
  trajectory_path: "./outputs/trajectory.json"
```

设置环境变量（Windows PowerShell）:
```powershell
$env:MINI_SWE_MODEL__API_KEY = "sk-your-key-here"
```

### 3. Run

```bash
mini-swe-agent run --config agent.yaml --yolo
```

| 参数 | 说明 |
|------|------|
| `--config` | YAML 配置文件路径（必填） |
| `--yolo` | 跳过确认提示，直接运行 |
| `--model` | 覆盖模型名称 |
| `--step-limit` | 覆盖步数限制 |
| `--cost-limit` | 覆盖成本上限（USD） |
| `--output` | 轨迹输出目录 |

### 4. Check trajectory

```bash
mini-swe-agent check outputs/trajectory.json
```

启动 Textual TUI，浏览每一步的输入输出、成本、状态。

---

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   Config    │────▶│  Agent   │────▶│  State   │────▶│  Model   │
│   System    │     │  Core    │     │ Machine  │     │ Adapter  │
└─────────────┘     └────┬─────┘     └──────────┘     └────┬─────┘
                         │                                    │
                    ┌────┴────┐                         ┌────┴────┐
                    │ Parser  │                         │ Executor│
                    │ Executor│                         │ Observer│
                    │ Observer│                         └─────────┘
                    └─────────┘
```

- **Config System**: YAML + Jinja2 + 环境变量，多层合并
- **State Machine**: 严格的步进循环，每步恰好一个动作
- **Parser**: 支持 Tool-call / Fence block / XML / Bare text 四种动作格式
- **Executor**: subprocess 执行命令，捕获 stdout/stderr/returncode
- **Observer**: 检测提交标记，判断任务完成状态
- **Model Adapter**: litellm 统一封装，流式输出，成本估算

完整架构文档见 `.anws/v1/`:
- `01_PRD.md` — 产品需求
- `02_ARCHITECTURE_OVERVIEW.md` — 系统总览
- `03_ADR/` — 架构决策记录
- `04_SYSTEM_DESIGN/` — 子系统设计
- `05A_TASKS.md` — 任务清单
- `05B_VERIFICATION_PLAN.md` — 验证计划

---

## Configuration

优先级（高 → 低）:

1. CLI 参数 (`--model`, `--step-limit`)
2. YAML 配置文件
3. 环境变量 (`MINI_SWE_MODEL__NAME`, `MINI_SWE_AGENT__STEP_LIMIT`)
4. 内置默认值

环境变量使用双下划线表示嵌套: `MINI_SWE_MODEL__API_KEY` → `model.api_key`

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | 任务成功提交 |
| 2 | CLI 参数错误 |
| 10 | 达到步数上限 |
| 11 | 达到成本上限 |
| 12 | 用户中断 (Ctrl-C) |
| 13 | 配置错误 |
| 14 | 未知错误 |
| 20 | 批量任务部分失败 |
| 21 | 用户拒绝继续 |
| 130 | SIGINT 中断 |

---

## Development

```bash
# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Lint
ruff check src/
ruff format src/

# Type check
mypy src/
```

---

## Project Structure

```
mini-swe-agent/
├── src/
│   ├── cli/              # CLI 入口 (run / batch / check)
│   │   ├── main.py
│   │   ├── live_display.py   # 实时进度面板
│   │   ├── batch.py
│   │   └── checker.py        # Textual TUI 检查器
│   ├── core/             # Agent 核心
│   │   ├── agent.py          # 主循环
│   │   ├── state_machine.py  # 状态机
│   │   ├── parser.py         # 动作解析
│   │   ├── executor.py       # 命令执行
│   │   ├── observer.py       # 结果观测
│   │   ├── model_adapter.py  # 模型调用
│   │   ├── models.py         # 数据模型
│   │   └── trajectory.py     # 轨迹记录
│   └── config/           # 配置系统
│       ├── config_manager.py
│       ├── loader.py
│       └── renderer.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/              # 默认关闭
├── agent.yaml            # 示例配置
├── requirements.md       # 示例任务
├── pyproject.toml
└── README.md
```

---

## License

MIT
