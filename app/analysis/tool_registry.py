"""
Tool registry for agent orchestration.

Minimal scope:
- Two tools only: search_tool / code_analysis_tool
- No action-level decomposition yet
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set, Tuple

from app.analysis.tool_planner import CODE_ANALYSIS, SEARCH_ENGINE


SEARCH_TOOL = "search_tool"
CODE_ANALYSIS_TOOL = "code_analysis_tool"


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    planner_keys: Tuple[str, ...]
    default_agent: str


class ToolRegistry:
    """Map planner outputs to concrete tool identifiers."""

    def __init__(self):
        self._tools: Dict[str, ToolDef] = {
            SEARCH_TOOL: ToolDef(
                name=SEARCH_TOOL,
                description="External/community signal retrieval for repository.",
                planner_keys=(SEARCH_ENGINE,),
                default_agent="ScoutAgent",
            ),
            CODE_ANALYSIS_TOOL: ToolDef(
                name=CODE_ANALYSIS_TOOL,
                description="Repository code and issue inspection.",
                planner_keys=(CODE_ANALYSIS,),
                default_agent="AnalystAgent",
            ),
        }

        self._planner_key_to_tool: Dict[str, str] = {}
        for tool_name, tool in self._tools.items():
            for key in tool.planner_keys:
                self._planner_key_to_tool[key] = tool_name

    def get(self, tool_name: str) -> Optional[ToolDef]:
        return self._tools.get(tool_name)

    def resolve_tool_name(self, planner_key: str) -> Optional[str]:
        return self._planner_key_to_tool.get(planner_key)

    def resolve_tool_names(self, planner_keys: Iterable[str]) -> Set[str]:
        names: Set[str] = set()
        for key in planner_keys:
            tool_name = self.resolve_tool_name(key)
            if tool_name:
                names.add(tool_name)
        return names

    def resolve_agent_names(self, planner_keys: Iterable[str]) -> Set[str]:
        tool_names = self.resolve_tool_names(planner_keys)
        return self.resolve_agent_names_from_tool_names(tool_names)

    def resolve_agent_names_from_tool_names(self, tool_names: Iterable[str]) -> Set[str]:
        agents: Set[str] = set()
        for tool_name in tool_names:
            tool = self.get(tool_name)
            if tool and tool.default_agent:
                agents.add(tool.default_agent)
        return agents
