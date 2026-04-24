from datetime import date

from fastapi.testclient import TestClient

from web.backend.app import app
from web.backend.routers import api as api_router


class _FakeCache:
    def get_trending_history(self, start_date=None, end_date=None):
        return [
            {
                "record_date": date.today().isoformat(),
                "repo_full_name": "owner/repo",
                "description": "A real repo description",
                "language": "Python",
                "stars": 123,
                "stars_today": 10,
                "rank": 1,
                "since_type": "weekly",
                "category": "infra_and_tools",
            }
        ]

    def get(self, repo_full_name):
        return {"summary": "Summary text", "reasons": ["Reason A", "Reason B"]}


def test_dashboard_uses_stored_description(monkeypatch):
    monkeypatch.setattr(api_router, "cache", _FakeCache())
    client = TestClient(app)

    resp = client.get("/api/dashboard")
    assert resp.status_code == 200

    body = resp.json()
    card = body["infra_and_tools"][0]
    assert card["description"] == "A real repo description"
    assert card["language"] == "Python"
    assert card["keywords"] == []
    assert card["tech_stack"] == []
    assert card["use_cases"] == []
