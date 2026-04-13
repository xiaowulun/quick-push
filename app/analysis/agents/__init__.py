"""
Multi-Agent 分析系统

包含三个核心 Agent:
1. ScoutAgent - 外部情报侦察员
2. AnalystAgent - 源码深度分析师
3. EditorAgent - 编辑审查
"""

from app.analysis.agents.base import BaseAgent, AgentResult
from app.analysis.agents.scout import ScoutAgent
from app.analysis.agents.analyst import AnalystAgent
from app.analysis.agents.editor import EditorAgent
from app.analysis.agents.orchestrator import AgentOrchestrator

__all__ = [
    "BaseAgent",
    "AgentResult",
    "ScoutAgent",
    "AnalystAgent",
    "EditorAgent",
    "AgentOrchestrator",
]
