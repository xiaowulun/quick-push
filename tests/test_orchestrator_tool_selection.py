import asyncio

from app.analysis.agents.base import AgentResult
from app.analysis.agents.orchestrator import AgentOrchestrator
from app.analysis.tool_planner import CODE_ANALYSIS, SEARCH_ENGINE, ToolStep
from app.analysis.tool_registry import CODE_ANALYSIS_TOOL, SEARCH_TOOL


class _FakePlanner:
    def __init__(self, tools):
        self.tools = tools

    def plan(self, _task_text):
        return [
            ToolStep(name=f"step_{idx}", tool=tool, reason="test")
            for idx, tool in enumerate(self.tools)
        ]


class _CounterAgent:
    def __init__(self, result, *, start_event=None, release_event=None):
        self.calls = 0
        self.last_context = None
        self._result = result
        self._start_event = start_event
        self._release_event = release_event

    async def execute(self, context):
        self.calls += 1
        self.last_context = context
        if self._start_event is not None:
            self._start_event.set()
        if self._release_event is not None:
            await self._release_event.wait()
        return self._result


class _FakeSearchService:
    async def index_project(self, **_kwargs):
        return True


def _make_orchestrator_with_plan(tools):
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator.logger = type(
        "_L",
        (),
        {"info": lambda *a, **k: None, "warning": lambda *a, **k: None, "error": lambda *a, **k: None},
    )()
    orchestrator.tool_planner = _FakePlanner(tools)
    orchestrator.search_service = _FakeSearchService()

    scout_result = AgentResult(success=True, data={"scout": "ok"}, agent_name="ScoutAgent")
    analyst_result = AgentResult(success=True, data={"analyst": "ok"}, agent_name="AnalystAgent")
    editor_result = AgentResult(
        success=True,
        data={"report": {"summary": "done", "reasons": ["r1"]}},
        agent_name="EditorAgent",
    )

    orchestrator.scout = _CounterAgent(scout_result)
    orchestrator.analyst = _CounterAgent(analyst_result)
    orchestrator.editor = _CounterAgent(editor_result)
    return orchestrator


def test_orchestrator_only_calls_scout_when_plan_is_search_only(monkeypatch):
    orchestrator = _make_orchestrator_with_plan([SEARCH_ENGINE])
    monkeypatch.setattr(asyncio, "create_task", lambda _coro: _coro.close())

    result = asyncio.run(
        orchestrator.analyze_project(
            repo_name="owner/repo",
            repo_data={},
            readme_content="",
            description="看社区反馈",
            category="infra_and_tools",
        )
    )

    assert result.success is True
    assert orchestrator.scout.calls == 1
    assert orchestrator.analyst.calls == 0
    assert orchestrator.editor.calls == 1
    assert result.metadata["tool_plan"][0]["tool"] == SEARCH_ENGINE
    assert result.metadata["selected_tools"] == [SEARCH_TOOL]
    assert orchestrator.editor.last_context["scout_success"] is True
    assert orchestrator.editor.last_context["analyst_success"] is False
    assert orchestrator.editor.last_context["analyst_result"] == {}


def test_orchestrator_only_calls_analyst_when_plan_is_code_only(monkeypatch):
    orchestrator = _make_orchestrator_with_plan([CODE_ANALYSIS])
    monkeypatch.setattr(asyncio, "create_task", lambda _coro: _coro.close())

    result = asyncio.run(
        orchestrator.analyze_project(
            repo_name="owner/repo",
            repo_data={},
            readme_content="",
            description="分析代码质量",
            category="infra_and_tools",
        )
    )

    assert result.success is True
    assert orchestrator.scout.calls == 0
    assert orchestrator.analyst.calls == 1
    assert orchestrator.editor.calls == 1
    assert result.metadata["tool_plan"][0]["tool"] == CODE_ANALYSIS
    assert result.metadata["selected_tools"] == [CODE_ANALYSIS_TOOL]
    assert orchestrator.editor.last_context["scout_success"] is False
    assert orchestrator.editor.last_context["analyst_success"] is True
    assert orchestrator.editor.last_context["scout_result"] == {}


def test_orchestrator_runs_scout_and_analyst_in_parallel_when_both_selected():
    async def _scenario():
        orchestrator = _make_orchestrator_with_plan([SEARCH_ENGINE, CODE_ANALYSIS])
        release_event = asyncio.Event()
        scout_started = asyncio.Event()
        analyst_started = asyncio.Event()

        orchestrator.scout = _CounterAgent(
            AgentResult(success=True, data={"scout": "ok"}, agent_name="ScoutAgent"),
            start_event=scout_started,
            release_event=release_event,
        )
        orchestrator.analyst = _CounterAgent(
            AgentResult(success=True, data={"analyst": "ok"}, agent_name="AnalystAgent"),
            start_event=analyst_started,
            release_event=release_event,
        )

        task = asyncio.create_task(
            orchestrator.analyze_project(
                repo_name="owner/repo",
                repo_data={},
                readme_content="",
                description="先看社区，再看代码",
                category="infra_and_tools",
            )
        )

        await asyncio.wait_for(
            asyncio.gather(scout_started.wait(), analyst_started.wait()),
            timeout=0.2,
        )
        release_event.set()
        result = await asyncio.wait_for(task, timeout=0.2)
        return orchestrator, result

    orchestrator, result = asyncio.run(_scenario())
    assert result.success is True
    assert orchestrator.scout.calls == 1
    assert orchestrator.analyst.calls == 1
    assert result.metadata["selected_tools"] == sorted([SEARCH_TOOL, CODE_ANALYSIS_TOOL])
    assert orchestrator.editor.last_context["scout_success"] is True
    assert orchestrator.editor.last_context["analyst_success"] is True
