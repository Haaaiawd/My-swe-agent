import re

path = 'D:/PROJECTALL/My-swe-agent/.anws/v1/04_SYSTEM_DESIGN/core-agent.detail.md'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# CH-R2-05: ExecutionResult add stdout_original
old1 = '''@dataclass
class ExecutionResult:
    """subprocess 执行结果"""
    returncode: int
    stdout: str
    stderr: str
    exception_metadata: Optional[dict] = None'''

new1 = '''@dataclass
class ExecutionResult:
    """subprocess 执行结果"""
    returncode: int
    stdout: str  # 经过观测模板截断/渲染后的输出（用于展示和轨迹记录）
    stderr: str
    stdout_original: Optional[str] = None  # 原始 stdout（未截断，用于提交标记检测；CH-R2-05）
    exception_metadata: Optional[dict] = None'''

text = text.replace(old1, new1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Done')
