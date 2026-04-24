from web.backend.models import SearchResult


def test_search_result_list_fields_use_default_factory():
    fields = SearchResult.model_fields
    assert fields["keywords"].default_factory is list
    assert fields["tech_stack"].default_factory is list
    assert fields["use_cases"].default_factory is list


def test_search_result_defaults_and_serialization_are_stable():
    first = SearchResult(
        repo_full_name="owner/repo-a",
        summary="summary-a",
        reasons=["reason-a"],
        similarity=0.91,
    )
    second = SearchResult(
        repo_full_name="owner/repo-b",
        summary="summary-b",
        reasons=["reason-b"],
        similarity=0.72,
    )

    first.keywords.append("agent")
    first.tech_stack.append("Python")
    first.use_cases.append("AI Agent")

    payload = first.model_dump()
    assert payload["keywords"] == ["agent"]
    assert payload["tech_stack"] == ["Python"]
    assert payload["use_cases"] == ["AI Agent"]

    # Ensure default list fields are not shared across instances.
    assert second.keywords == []
    assert second.tech_stack == []
    assert second.use_cases == []
