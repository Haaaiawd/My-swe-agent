# AGENTS.md - AI 协作协议

> **"如果你正在阅读此文档，你就是那个智能体 (The Intelligence)。"**
>
> 这个文件是你的**锚点 (Anchor)**。它定义了项目的法则、领地的地图，以及记忆协议。
> 当你唤醒（开始新会话）时，**请首先阅读此文件**。

---

## 30秒恢复协议 (Quick Recovery)

**当你开始新会话或感到"迷失"时，立即执行**:

1. **读取根目录的 AGENTS.md** → 获取项目地图
2. **查看下方"当前状态"** → 找到最新架构版本
3. **读取 `.anws/v{N}/05A_TASKS.md` 与 `05B_VERIFICATION_PLAN.md`** → 了解执行与验证待办
4. **开始工作**

---

## 地图 (领地感知)

以下是这个项目的组织方式：


| 路径                                    | 描述                                  | 访问协议                                             |
| ------------------------------------- | ----------------------------------- | ------------------------------------------------ |
| `src/`                                | **实现层**。实际的代码库。                     | 通过 Task 读/写。                                     |
| `.anws/`                              | **统一架构根目录**。包含版本化架构状态与升级记录。         | **只读**(旧版) / **写一次**(新版) / `changelog` 由 CLI 维护。 |
| `.anws/v{N}/`                         | **当前真理**。最新的架构定义。                   | 永远寻找最大的 `v{N}`。                                  |
| `.anws/changelog/`                    | **升级记录**。`anws update` 生成的变更记录。     | 由 CLI 自动维护，请勿删除。                                 |
| `target-specific workflow projection` | **工作流**。`/genesis`, `/blueprint` 等。 | 读取当前 target 对应的原生投影文件。                           |
| `target-specific skill projection`    | **技能库**。原子能力。                       | 调用当前 target 对应的原生投影文件。                           |
| `.nexus-map/`                         | **知识库**。代码库结构映射。                    | 由 nexus-mapper 生成。                               |


## 工作流注册表

> [!IMPORTANT]
> **工作流优先原则**：当任务匹配某个工作流，或你判断当前任务**明显符合、基本符合、甚至只是疑似符合**某个工作流的适用场景时，**都必须先读取相应文件**，并严格遵循其中的步骤执行。工作流是经过精心设计的协议，而非可选参考。
>
> **触发流程**：
>
> 1. 用户提及工作流名称，或你判断当前任务明显符合、基本符合、甚至只是疑似符合某个工作流的适用场景时，都必须先读取相应文件
> 2. **立即读取** 相应工作流文件
> 3. **严格遵循**工作流中的步骤执行
> 4. 在检查点暂停等待用户确认


| 工作流              | 触发时机                 | 产出                                           |
| ---------------- | -------------------- | -------------------------------------------- |
| `/quickstart`    | 新用户入口 / 不知道从哪开始      | 编排其他工作流                                      |
| `/genesis`       | 新项目 / 重大重构           | PRD, Architecture, ADRs                      |
| `/probe`         | 变更前 / 接手项目           | `.anws/v{N}/00_PROBE_REPORT.md`              |
| `/design-system` | genesis 后            | 04_SYSTEM_DESIGN/*.md                        |
| `/blueprint`     | genesis 后            | 05A_TASKS.md + 05B_VERIFICATION_PLAN.md + AGENTS.md 初始 Wave |
| `/change`        | 进入 forge 编码后的任务局部修订  | 更新 TASKS + SYSTEM_DESIGN (仅修改) + CHANGELOG   |
| `/explore`       | 调研时                  | 探索报告                                         |
| `/challenge`     | 决策前质疑                | 07_CHALLENGE_REPORT.md (含问题总览目录)             |
| `/forge`         | 编码执行                 | 代码 + 更新 AGENTS.md Wave 块                     |
| `/craft`         | 创建工作流/技能/提示词         | Workflow / Skill / Prompt 文档                 |
| `/upgrade`       | `anws update` 后做升级编排 | 判断 Minor / Major，并路由到 `/change` 或 `/genesis` |


---

## 宪法 (The Constitution)

1. **版本即法律**: 不"修补"架构文档，只"演进"。变更必须创建新版本。
2. **显式上下文**: 决策写入 ADR，不留在"聊天记忆"里。
3. **交叉验证**: 编码前对照 `05A_TASKS.md` 与 `05B_VERIFICATION_PLAN.md`。我在做计划好的事吗？
4. **美学**: 文档应该是美的。善用 Markdown 与清晰的层次结构。

---

## 项目状态保留区

<!-- AUTO:BEGIN — 项目状态保留区（升级时唯一保留的部分，请勿手动修改区块边界） -->

## 当前状态 (由 Workflow 自动更新)

> **注意**: 这是项目文件中的保留部分，由 `/genesis`、`/blueprint` 和 `/forge` 自动维护。

- **最新架构版本**: `.anws/v1`
- **活动任务清单: `05A_TASKS.md` + `05B_VERIFICATION_PLAN.md` (blueprint 已生成))
- **待办任务数: 19 个开发任务 + 3 个 INT 里程碑（分 3 个 Sprint）
- **最近一次更新: `2026-05-11` (Challenge Round 4 双重审查 + /change 修复完成；CH-R4-01 Critical 防循环计数器已补充；CH-R4-02 VALIDATE 文档一致性已修复；CH-R4-03 cost_estimate_per_call 默认值已定义；TK-R4-01 T3.1.6 验证计划已补充；门禁 APPROVED，可进入 /forge)

### 🌊 Wave 1 ✅ — S1 Foundation: 项目骨架初始化
T1.1.1
签名: AUTO

### 🌊 Wave 2 ✅ — S1 Foundation: Config 内部组件
T1.1.2, T1.1.3, T1.1.4
签名: AUTO

### 🌊 Wave 3 ✅ — S1 Foundation: ConfigManager 组合 + 脱敏
T1.1.5
签名: AUTO

### 🌊 Wave 4 ✅ — S1 Foundation: S1 集成验证
INT-S1
签名: AUTO



---

## 项目结构 (Project Tree)

> **注意**: 此部分由 `/genesis` 维护。

```text
mini-swe-agent/
├── src/
│   ├── cli/                 # CLI System
│   │   ├── main.py          # 主命令入口
│   │   ├── batch.py         # 批处理扩展
│   │   └── checker.py       # Textual 检查器扩展
│   ├── core/                # Core Agent System
│   │   ├── agent.py         # 核心状态机
│   │   ├── state_machine.py # 状态机实现
│   │   ├── parser.py        # 动作解析（内部组件）
│   │   ├── executor.py      # subprocess 执行（内部组件）
│   │   ├── observer.py      # 结果观测（内部组件）
│   │   ├── model.py         # 模型适配（内部组件）
│   │   └── trajectory.py    # 轨迹记录（内部组件）
│   └── config/              # Config System
│       └── config_manager.py
├── tests/
│   ├── unit/                # 单元测试
│   ├── integration/         # 集成测试
│   └── e2e/                 # E2E 测试（默认关闭）
├── pyproject.toml
├── README.md
└── .anws/
    ├── changelog/         (升级记录)
    └── v1/                # 当前架构文档
        ├── 00_MANIFEST.md
        ├── 01_PRD.md
        ├── 02_ARCHITECTURE_OVERVIEW.md
        ├── 03_ADR/
        ├── 04_SYSTEM_DESIGN/
        ├── 05A_TASKS.md         # 任务清单 (blueprint 产出)
        ├── 05B_VERIFICATION_PLAN.md  # 验证计划 (blueprint 产出)
        ├── 06_CHANGELOG.md
        └── 07_CHALLENGE_REPORT.md
```

---

## 导航指南 (Navigation Guide)

> **注意**: 此部分由 `/genesis` 维护。

- **在新架构就绪前**: 请勿大规模修改代码。
- **架构总览**: `.anws/v1/02_ARCHITECTURE_OVERVIEW.md`
- **ADR**: 架构决策见 `.anws/v1/03_ADR/` (跨系统决策的唯一记录源)
- **详细设计**: 
  - Core Agent System: `.anws/v1/04_SYSTEM_DESIGN/core-agent.md`
  - Config System: `.anws/v1/04_SYSTEM_DESIGN/config.md`
  - CLI System: `.anws/v1/04_SYSTEM_DESIGN/cli-system.md`
- **任务清单**: 待 `/blueprint` 执行后更新 (将生成 `.anws/v1/05A_TASKS.md` 与 `.anws/v1/05B_VERIFICATION_PLAN.md`)

### ADR ↔ SYSTEM_DESIGN 关系
- **ADR** 记录跨系统决策 (如技术栈、认证方式)
- **SYSTEM_DESIGN** §8 Trade-offs 引用 ADR，不复制决策内容
- 修改 ADR 时，检查"影响范围"章节，确认引用该 ADR 的系统

---

### 技术栈决策

- 语言: Python 3.10+
- 框架: click (CLI), litellm (模型 API), textual (TUI)
- 构建工具: pyproject.toml

### 系统边界

- Core Agent System: 核心状态机闭环，包含 Parser、Executor、Observer、Model Adapter、Trajectory Manager（内部组件）
- CLI System: CLI 入口、批处理、Textual 检查器 — 详细设计见 `.anws/v1/04_SYSTEM_DESIGN/cli-system.md`
- Config System: 配置管理，YAML + Jinja2，多源合并

### 活跃 ADR

- ADR-001: 技术栈选择 — Python 3.10+ + click + litellm + textual
- ADR-002: 测试策略与质量门禁 — 单元/集成/E2E 分层，PR/提交前/发布前门禁
- ADR-003: 错误处理与重试策略 — 明确 litellm 异常类型重试范围（Timeout/APIError/RateLimit/ServiceUnavailable/APIConnection），CostMissingError/AuthError/BadRequestError 不重试
- ADR-004: 配置管理策略 — YAML + Jinja2，CLI > 文件 > 环境变量 > 默认值；YAML 加载用 DebugUndefined，观测模板用 StrictUndefined；敏感信息 `_redact()` 脱敏
- ADR-005: 动作解析协议 — Tool-call/文本模式，恰好一个动作
- ADR-006: 提交标记契约 — OVERALL_OUTPUT 定义，returncode==0 才提交
- ADR-007: 模型适配协议 — 协议切换、消息扁平化、成本计费；新增 `cost_missing_strategy` 配置项（ignore/warn/error）
- ADR-008: 轨迹记录格式 — schema version、tool_call_id 关联

### 当前任务状态

- [由 blueprint/forge 自动更新]

<!-- AUTO:END -->

---

> **状态自检**: 准备好了？提醒用户运行 `/quickstart` 开始吧。

