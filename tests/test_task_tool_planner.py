from app.analysis.tool_planner import (
    CODE_ANALYSIS,
    SEARCH_ENGINE,
    TaskToolPlanner,
)


def _tools(steps):
    return [step.tool for step in steps]


def test_plan_search_only_for_community_signal_task():
    planner = TaskToolPlanner()
    steps = planner.plan("帮我看这个仓库最近社区讨论和热度趋势")
    assert _tools(steps) == [SEARCH_ENGINE]


def test_plan_code_only_for_source_inspection_task():
    planner = TaskToolPlanner()
    steps = planner.plan("分析这个仓库代码结构、可运行性和潜在 bug")
    assert _tools(steps) == [CODE_ANALYSIS]


def test_plan_multi_step_search_then_code_for_mixed_task():
    planner = TaskToolPlanner()
    steps = planner.plan("评估这个项目是否值得接入：先看社区反馈，再看代码质量和架构")
    assert _tools(steps) == [SEARCH_ENGINE, CODE_ANALYSIS]


def test_plan_fallback_to_two_steps_for_evaluation_task():
    planner = TaskToolPlanner()
    steps = planner.plan("这个项目是否值得选型")
    assert _tools(steps) == [SEARCH_ENGINE, CODE_ANALYSIS]
