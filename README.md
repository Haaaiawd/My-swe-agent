# mini SWE Agent

A minimal SWE agent for automated programming task evaluation.

> ⚠️ **Warning**: This tool executes shell commands automatically. Review the task description and configuration before running. Use `--yolo` with caution.

## Requirements

- Python 3.10+

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# Run a single task
mini-swe-agent run --config agent.yaml --yolo

# Batch process a dataset
mini-swe-agent batch ./dataset --config agent.yaml --workers 4 --output preds.json

# Inspect a trajectory file (Textual TUI)
mini-swe-agent check outputs/trajectory.json
```

## Configuration Priority

Configuration is resolved in the following priority (high to low):

1. **CLI arguments** (e.g. `--model`, `--step-limit`)
2. **Configuration files** (YAML, merged in order, later wins)
3. **Environment variables** (`MINI_SWE_*`, double-underscore nested, e.g. `MINI_SWE_MODEL__NAME`)
4. **Built-in defaults**

See `ADR-004` for full configuration management details.

## Exit Codes

| CLI Exit Code | Meaning |
|--------------|---------|
| 0 | Success (all tasks SUBMITTED) |
| 2 | CLI parameter error (click BadParameter) |
| 10 | Agent reached step limit |
| 11 | Agent reached cost limit |
| 12 | User interrupted (Ctrl-C) |
| 13 | Agent configuration error |
| 14 | Agent unknown error |
| 20 | Batch partial failure (some tasks failed, preds.json still written) |
| 21 | User declined to continue (yolo=False) |
| 130 | Interrupted by SIGINT |

Agent internal returncodes (mapped to CLI codes above):
| Core Returncode | State |
|-----------------|-------|
| 0 | SUBMITTED |
| 2 | LIMIT_STEP |
| 3 | LIMIT_COST |
| 4 | INTERRUPT |
| 5 | FATAL_CONFIG |
| 6 | UNKNOWN_ERROR |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `MINI_SWE_ENABLE_E2E` | Set to `1` to enable end-to-end tests (requires live API keys) |
| `MINI_SWE_ENABLE_LIVE_API` | Set to `1` to enable live API integration tests |
| `MINI_SWE_*` | Override any config field via env var (double-underscore for nesting) |

## Project Structure

```
mini-swe-agent/
├── src/
│   ├── cli/          # CLI System (run, batch, check)
│   ├── core/         # Core Agent System (state machine + internal components)
│   └── config/       # Config System (YAML + Jinja2 + multi-source merge)
├── tests/
│   ├── unit/         # Unit tests
│   ├── integration/  # Integration tests
│   └── e2e/          # End-to-end tests (disabled by default)
├── pyproject.toml
└── README.md
```

## Development

```bash
# Run tests
pytest tests/unit/ tests/integration/

# Lint
ruff check src/

# Type check
mypy src/
```

## Architecture

See `.anws/v1/` for full architecture documentation:
- `01_PRD.md` — Product Requirements
- `02_ARCHITECTURE_OVERVIEW.md` — System overview
- `03_ADR/` — Architecture Decision Records
- `04_SYSTEM_DESIGN/` — Detailed system designs
- `05A_TASKS.md` — Task list
- `05B_VERIFICATION_PLAN.md` — Verification plan
