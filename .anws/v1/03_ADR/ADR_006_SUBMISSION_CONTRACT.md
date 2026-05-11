# ADR-006: 提交标记契约

**状态**: Accepted
**日期**: 2026-05-10

---

## 背景

需求 E 部分定义了提交标记契约：在文档与测试中钉死 OVERALL_OUTPUT 的定义（PIN）。

若 OVERALL_OUTPUT.lstrip() 后首行恰为 COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT 且 returncode == 0：进入 SUBMITTED。

若 returncode != 0：即使出现标记文本也不得提交。

---

## 决策

### OVERALL_OUTPUT 定义

**定义**：OVERALL_OUTPUT 是命令执行后的 stdout 内容

**处理流程**：
1. 获取 stdout 字符串
2. 执行 lstrip() 去除左侧空白
3. 按行分割，取第一行

### 提交标记

**标记字符串**：`COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`

**匹配规则**（增强鲁棒性）：
1. 获取 stdout 字符串。
2. 去除 ANSI 转义序列：`re.sub(r'\x1b\[[0-9;]*m', '', stdout)`。
3. 去除 Unicode 空白符（含 BOM、零宽空格、不换行空格等）：`re.sub(r'[\ufeff\u200b\u00a0]+', '', stdout)`。
4. 执行 `lstrip()` 去除左侧 ASCII 空白。
5. 按行分割（`splitlines()`），取第一行。
6. 第一行恰好等于标记字符串，且 returncode == 0。

**边界场景处理**：
- 标记被 ANSI 颜色码包裹 → strip ANSI 后匹配
- 标记前含 Unicode 空白 → normalize 后匹配
- 标记出现在截断边界（观测模板截断后）→ 提交检测基于**原始 stdout**（ExecutionResult.stdout_original），不受截断影响；但用户看到的观测内容可能与提交内容不一致（已知限制）。若 stdout_original 为 None，则回退到 stdout（CH-R2-05）
- 标记与其他文本混合（如 `MARKER: extra`）→ 不提交（精确匹配）
- 标记在 stderr 中 → 不检测（仅检测 stdout）

**提交行为**：
- 进入 SUBMITTED 终态
- 首行之后余下内容为最终提交正文
- 停止状态机，不再继续循环

### 拒绝提交

**拒绝条件**：
- returncode != 0（即使出现标记也拒绝）
- 标记字符串不匹配
- 标记字符串不在首行
- 标记字符串前后有多余字符

**拒绝行为**：
- 不进入 SUBMITTED 终态
- 继续状态机循环（或达到其他终态）

---

## 影响范围

- Core Agent System 中的 Observer 组件
- 终态处理逻辑

---

## 后续行动

- 在 Observer 组件中实现提交标记检测
- 编写提交契约的单元测试（成功路径、returncode!=0 且含标记）
- 在文档和测试中钉死 OVERALL_OUTPUT 的定义