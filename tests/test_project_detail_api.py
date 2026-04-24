from fastapi.testclient import TestClient

from web.backend.app import app
from web.backend.routers import api as api_router


class _FakeProjectDetailCache:
    def get_project_detail(self, repo_full_name, history_limit=12):
        if repo_full_name != "owner/repo":
            return None
        return {
            "basic": {
                "repo_full_name": "owner/repo",
                "url": "https://github.com/owner/repo",
                "description": "Useful open-source project",
                "language": "Python",
                "category": "infra_and_tools",
                "stars": 3200,
                "stars_today": 45,
                "rank": 2,
                "since_type": "daily",
                "repo_updated_at": "2026-04-20T10:00:00Z",
                "first_seen": "2026-04-10",
                "last_seen": "2026-04-20",
                "total_appearances": 7,
            },
            "summary": "A production-grade multi-agent framework.",
            "reasons": ["Growing community", "Clear deployment path"],
            "keywords": ["LLM", "RAG", "agent"],
            "tech_stack": ["Python", "FastAPI", "Docker"],
            "use_cases": ["AI Agent", "RAG Knowledge Base"],
            "evidence": {
                "chunk_id": "owner/repo#000",
                "chunk_text": "This section explains architecture and deployment.",
                "section": "readme:Architecture",
                "path": "README.md",
                "heading": "Architecture",
                "updated_at": "2026-04-20T10:00:00Z",
            },
            "trend_summary": {
                "total_records": 5,
                "first_seen": "2026-04-10",
                "last_seen": "2026-04-20",
                "best_rank": 2,
                "latest_stars": 3200,
                "avg_stars_today": 38.4,
            },
            "trend_history": [
                {
                    "record_date": "2026-04-20",
                    "stars": 3200,
                    "stars_today": 45,
                    "rank": 2,
                    "since_type": "daily",
                    "language": "Python",
                    "category": "infra_and_tools",
                }
            ],
        }


class _FakeNotFoundCache:
    def get_project_detail(self, repo_full_name, history_limit=12):
        return None


def test_project_detail_success(monkeypatch):
    monkeypatch.setattr(api_router, "cache", _FakeProjectDetailCache())
    client = TestClient(app)

    resp = client.get("/api/projects/owner/repo")
    assert resp.status_code == 200

    body = resp.json()
    assert body["basic"]["repo_full_name"] == "owner/repo"
    assert body["summary"] == "A production-grade multi-agent framework."
    assert body["reasons"] == ["Growing community", "Clear deployment path"]
    assert body["keywords"] == ["LLM", "RAG", "agent"]
    assert body["tech_stack"] == ["Python", "FastAPI", "Docker"]
    assert body["use_cases"] == ["AI Agent", "RAG Knowledge Base"]
    assert len(body["suitable_for"]) > 0
    assert body["complexity"] in {"low", "medium", "high"}
    assert body["maturity"] in {"early", "medium", "high"}
    assert len(body["risk_notes"]) > 0
    assert body["evidence"]["section"] == "readme:Architecture"
    assert body["trend_summary"]["total_records"] == 5
    assert len(body["trend_history"]) == 1


def test_project_detail_404(monkeypatch):
    monkeypatch.setattr(api_router, "cache", _FakeNotFoundCache())
    client = TestClient(app)

    resp = client.get("/api/projects/owner/missing")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["code"] == "PROJECT_NOT_FOUND"
