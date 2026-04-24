from app.knowledge import search as search_module


def _base_payload():
    return {
        "summary": "A production-grade multi-agent framework.",
        "reasons": ["Growing community", "Clear deployment path"],
        "keywords": ["LLM", "RAG", "agent"],
        "tech_stack": ["Python", "FastAPI", "Docker"],
        "use_cases": ["AI Agent", "RAG Knowledge Base"],
        "trend_summary": {"total_records": 6, "best_rank": 3, "latest_stars": 3200},
        "basic": {"repo_full_name": "owner/repo", "language": "Python", "category": "infra_and_tools", "stars": 3200, "total_appearances": 6},
        "evidence_text": "This section explains architecture and deployment.",
    }


def test_derive_project_profile_fallbacks_to_rule_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(search_module, "_derive_profile_with_llm", lambda **kwargs: None)
    payload = _base_payload()
    profile = search_module.derive_project_profile(**payload)

    assert profile["complexity"] in {"low", "medium", "high"}
    assert profile["maturity"] in {"early", "medium", "high"}
    assert len(profile["suitable_for"]) > 0
    assert len(profile["risk_notes"]) > 0


def test_derive_project_profile_uses_llm_when_available(monkeypatch):
    monkeypatch.setattr(
        search_module,
        "_derive_profile_with_llm",
        lambda **kwargs: {
            "suitable_for": ["适合做企业知识库智能问答平台"],
            "complexity": "high",
            "maturity": "medium",
            "risk_notes": ["依赖链较长，建议先做最小化部署验证。"],
        },
    )
    payload = _base_payload()
    profile = search_module.derive_project_profile(**payload)

    assert profile["complexity"] == "high"
    assert profile["maturity"] == "medium"
    assert profile["suitable_for"] == ["适合做企业知识库智能问答平台"]
    assert profile["risk_notes"] == ["依赖链较长，建议先做最小化部署验证。"]


def test_derive_project_profile_keeps_rule_when_llm_values_invalid(monkeypatch):
    monkeypatch.setattr(
        search_module,
        "_derive_profile_with_llm",
        lambda **kwargs: {
            "suitable_for": [],
            "complexity": "unknown",
            "maturity": "unknown",
            "risk_notes": [],
        },
    )
    payload = _base_payload()
    profile = search_module.derive_project_profile(**payload)

    assert profile["complexity"] in {"low", "medium", "high"}
    assert profile["maturity"] in {"early", "medium", "high"}
    assert len(profile["suitable_for"]) > 0
    assert len(profile["risk_notes"]) > 0
