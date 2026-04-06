"""
Multi-Agent 分析系统

包含三个核心 Agent:
1. ScoutAgent - 外部情报侦察员
2. AnalystAgent - 源码深度分析师
3. EditorAgent - 编辑审查
"""

from .base import BaseAgent, AgentResult
from .scout import ScoutAgent
from .analyst import AnalystAgent
from .editor import EditorAgent
from .orchestrator import AgentOrchestrator

__all__ = [
    "BaseAgent",
    "AgentResult",
    "ScoutAgent",
    "AnalystAgent",
    "EditorAgent",
    "AgentOrchestrator",
]
