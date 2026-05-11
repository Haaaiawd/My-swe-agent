# .anws v1 - 版本清单

**创建日期**: 2026-05-10
**状态**: Active
**前序版本**: 无

## 版本目标
实现「mini SWE agent」——一个可测、可记录轨迹、可批评的 CLI 工具，用于自动化执行模型生成的 Shell 命令并形成闭环。

## 主要变更
- [ADD] 初始化版本化架构文档
- [ADD] 定义核心状态机闭环（MODEL → PARSE → EXECUTE → OBSERVE）
- [ADD] 定义严格动作协议与提交标记契约
- [ADD] 规划 CLI 能力、轨迹记录、Textual 检查器
- [ADD] 系统拆分：10 个组件合并为 3 个系统
- [ADD] 补充关键协议 ADR（动作解析、提交标记、模型适配、轨迹格式）

## 文档清单
- [x] 00_MANIFEST.md (本文件)
- [x] 01_PRD.md
- [x] 02_ARCHITECTURE_OVERVIEW.md
- [x] 03_ADR/
- [x] 04_SYSTEM_DESIGN/core-agent.md
- [x] 04_SYSTEM_DESIGN/config.md
- [x] 05A_TASKS.md (由 /blueprint 生成，2026-05-11)
- [x] 05B_VERIFICATION_PLAN.md (由 /blueprint 生成，2026-05-11)
- [x] 06_CHANGELOG.md