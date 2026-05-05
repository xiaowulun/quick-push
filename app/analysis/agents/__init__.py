"""Agent package exports with lazy loading to avoid heavy import side effects."""

from app.analysis.agents.base import BaseAgent, AgentResult

__all__ = [
    "BaseAgent",
    "AgentResult",
    "ScoutAgent",
    "AnalystAgent",
    "EditorAgent",
    "AgentOrchestrator",
]


def __getattr__(name):
    if name == "ScoutAgent":
        from app.analysis.agents.scout import ScoutAgent

        return ScoutAgent
    if name == "AnalystAgent":
        from app.analysis.agents.analyst import AnalystAgent

        return AnalystAgent
    if name == "EditorAgent":
        from app.analysis.agents.editor import EditorAgent

        return EditorAgent
    if name == "AgentOrchestrator":
        from app.analysis.agents.orchestrator import AgentOrchestrator

        return AgentOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

