from app.analysis.tool_planner import CODE_ANALYSIS, SEARCH_ENGINE
from app.analysis.tool_registry import CODE_ANALYSIS_TOOL, SEARCH_TOOL, ToolRegistry


def test_registry_has_two_top_level_tools():
    registry = ToolRegistry()

    assert registry.get(SEARCH_TOOL) is not None
    assert registry.get(CODE_ANALYSIS_TOOL) is not None


def test_registry_maps_planner_keys_to_tool_names():
    registry = ToolRegistry()

    assert registry.resolve_tool_name(SEARCH_ENGINE) == SEARCH_TOOL
    assert registry.resolve_tool_name(CODE_ANALYSIS) == CODE_ANALYSIS_TOOL


def test_registry_resolves_multiple_tool_names():
    registry = ToolRegistry()
    resolved = registry.resolve_tool_names([SEARCH_ENGINE, CODE_ANALYSIS, "unknown"])

    assert resolved == {SEARCH_TOOL, CODE_ANALYSIS_TOOL}


def test_registry_resolves_agents_from_planner_keys():
    registry = ToolRegistry()
    agents = registry.resolve_agent_names([SEARCH_ENGINE, CODE_ANALYSIS])

    assert agents == {"ScoutAgent", "AnalystAgent"}
