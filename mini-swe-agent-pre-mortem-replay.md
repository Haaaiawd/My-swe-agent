# Replay - mini-swe-agent-pre-mortem

- goal: 从未来回看，分析 mini SWE Agent v1 架构在进入 forge 和实际运行后可能的失败原因
- mode: explore
- totalSteps: 5
- currentStep: 5
- status: completed

## Steps

### Step 1

- shouldConverge: false
- mustConclude: false

第一步：先不要急着列问题。先理解这个系统的核心约束——它是一个 model-driven 的闭环状态机，每一步的正确性都依赖上一步的输出语义。最脆弱的地方不是某个单独组件的实现，而是组件之间的契约在真实运行时的漂移。Round 3 遗留的 CH-R3-06（观测模板渲染失败进入 UNKNOWN_ERROR 而非 FATAL_CONFIG）就是一个典型例子：当 Jinja2 StrictUndefined 触发时，状态机没有专门的错误分支，异常被泛化捕获。这意味着用户拿到的是一个模糊的终态，无法区分'配置写错了'和'程序崩了'。如果 forge 阶段不修复这个分支，它在生产环境中会消耗大量排障时间。

### Step 2

- shouldConverge: false
- mustConclude: false

第二步：从运行时角度推演。这个系统的核心循环是 MODEL→PARSE→EXECUTE→OBSERVE→(check limits)→MODEL。每个转换点都是故障注入位。我已经在文档中看到几个未完全闭合的边界：1) 步数定义虽然在 Round 3 被'钉死'了，但钉死的位置是在 challenge report 里，而不是在 PRD 或 code contract 中，实现者仍可能按直觉理解；2) 成本检查时机同样只被建议在 detail.md 中定义，但如果 estimated_next_call 的计算策略不明确，预防性检查可能形同虚设；3) FormatError 连续计数 >=5 进入 UNKNOWN_ERROR 的逻辑看起来合理，但如果模型在'tool-call 与文本混合模式'下偶尔产生歧义输出，这个阈值是否足够？更重要的是，这些边界条件在单元测试中是容易 mock 的，但在真实模型交互中，错误样本的分布是不可预测的。

### Step 3

- shouldConverge: false
- mustConclude: false

第三步：从工程实现维度审视。Sprint 划分是 S1(Config)→S2(Core)→S3(CLI)，依赖关系看起来清晰，但 TK-R3-02 指出了一个循环依赖：T1.1.1（项目骨架）的验收标准之一是  不崩溃，这需要 CLI stub，但 CLI 完整实现在 T3.1.1。这意味着 S1 的第一个任务可能被阻塞，或者验收标准需要放宽。如果实现者为了通过这个验收标准而临时写一个最小 CLI，这个临时代码在 S3 是否会被彻底替换？临时代码残留是技术债的常见来源。另一个工程风险是 batch 模式的并发写入——虽然 Round 2 修复了 trajectory 文件命名策略（instance_id），但如果 instance_id 生成不唯一，或者在 multiprocessing 中 race condition， preds.json 和 trajectory 的对应关系可能断裂。

### Step 4

- shouldConverge: true
- mustConclude: false

第四步：回看前面的判断，有一个角度被遗漏了——Config System 的 DebugUndefined vs StrictUndefined 双模式。YAML 配置加载用 DebugUndefined（未定义变量保留原样），而观测模板渲染用 StrictUndefined（未定义变量抛异常）。这个设计是有意图的：配置加载阶段应该宽容，观测渲染应该严格。但这个双模式的'模式切换点'在文档中没有显式强调。如果实现者不小心把 StrictUndefined 用到了配置加载，或者把 DebugUndefined 用到了观测渲染，Config System 的语义就会翻转。这是一个'容易用错'的设计，而且错误不会在单元测试层面立即暴露，只有在集成真实模板时才会触发。另外，README 文档缺失（TK-R3-01）看似是文档问题，但它意味着 E2E 测试的启用方式（MINI_SWE_ENABLE_E2E）没有用户可见的说明，这个环境变量的契约可能会随着时间被忘记或误用。

### Step 5

- shouldConverge: true
- mustConclude: true

第五步：收敛结论。这个架构最大的三个风险领域已经清晰：1) 状态机错误分支的完备性（CH-R3-06 是冰山一角，需要系统性地检查每个 except 分支的终态语义是否精确）；2) 计数/上限语义的文档-代码一致性（步数、成本不是实现完就稳了，需要契约测试保证 PRD→设计→代码的传递链不丢信息）；3) 并发与文件 I/O 的鲁棒性（batch 模式的 trajectory 命名、preds.json 写入、OSError 备用路径）。建议行动： forge 启动时，不要只按 TASKS 顺序写代码，而是先做一轮'危险路径识别'——把状态机中所有可能的异常传播路径画出来，确认每个异常都有精确终态。

## Final Conclusion

第五步：收敛结论。这个架构最大的三个风险领域已经清晰：1) 状态机错误分支的完备性（CH-R3-06 是冰山一角，需要系统性地检查每个 except 分支的终态语义是否精确）；2) 计数/上限语义的文档-代码一致性（步数、成本不是实现完就稳了，需要契约测试保证 PRD→设计→代码的传递链不丢信息）；3) 并发与文件 I/O 的鲁棒性（batch 模式的 trajectory 命名、preds.json 写入、OSError 备用路径）。建议行动： forge 启动时，不要只按 TASKS 顺序写代码，而是先做一轮'危险路径识别'——把状态机中所有可能的异常传播路径画出来，确认每个异常都有精确终态。
