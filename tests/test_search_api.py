from fastapi.testclient import TestClient

from web.backend.app import app
from web.backend.routers import api as api_router
from app.knowledge.query_parser import QueryFilters


class _FakeSearchService:
    async def search_projects(self, query, coarse_top_k=20, final_top_k=5, filters=None):
        return [
            {
                "repo_full_name": "owner/repo",
                "summary": "A production-ready agent framework.",
                "reasons": ["Supports multi-agent routing"],
                "rerank_score": 0.88,
                "category": "infra_and_tools",
                "language": "Python",
                "stars": 1234,
                "keywords": ["agent", "workflow"],
                "tech_stack": ["Python", "FastAPI"],
                "use_cases": ["AI Agent"],
            }
        ]


def test_search_api_returns_structured_fields(monkeypatch):
    monkeypatch.setattr(api_router, "_get_search_service", lambda: _FakeSearchService())
    class _DummyParser:
        async def parse(self, _q):
            return QueryFilters(language="Python", keywords=["agent"])

    monkeypatch.setattr(api_router, "get_query_parser", lambda: _DummyParser())
    client = TestClient(app)

    resp = client.get("/api/search", params={"q": "agent framework"})
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    result = body["results"][0]
    assert result["keywords"] == ["agent", "workflow"]
    assert result["tech_stack"] == ["Python", "FastAPI"]
    assert result["use_cases"] == ["AI Agent"]
    assert isinstance(result["match_reasons"], list)
    assert len(result["match_reasons"]) >= 1
    assert body["parsed_filters"] == {"language": "Python", "keywords": ["agent"]}
