from app.analysis.agents.base import AgentResult
from app.analysis.agents.orchestrator import AgentOrchestrator


def test_create_final_result_contains_structured_fields_defaults():
    orchestrator = object.__new__(AgentOrchestrator)
    editor_result = AgentResult(
        success=True,
        data={"report": {"summary": "summary", "reasons": ["reason"]}},
    )
    scout_result = AgentResult(success=True, data={"foo": "bar"})
    analyst_result = AgentResult(success=True, data={"baz": "qux"})

    result = AgentOrchestrator._create_final_result(
        orchestrator,
        repo_name="owner/repo",
        editor_result=editor_result,
        scout_result=scout_result,
        analyst_result=analyst_result,
    )

    assert result.success is True
    assert result.data["keywords"] == []
    assert result.data["tech_stack"] == []
    assert result.data["use_cases"] == []


def test_attach_structured_tags_overrides_defaults():
    orchestrator = object.__new__(AgentOrchestrator)
    result = AgentResult(success=True, data={"summary": "s", "reasons": ["r"]})

    AgentOrchestrator._attach_structured_tags(
        orchestrator,
        result,
        {
            "keywords": ["agent"],
            "tech_stack": ["Python"],
            "use_cases": ["AI Agent"],
        },
    )

    assert result.data["keywords"] == ["agent"]
    assert result.data["tech_stack"] == ["Python"]
    assert result.data["use_cases"] == ["AI Agent"]
