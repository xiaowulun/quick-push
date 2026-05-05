from datetime import date, timedelta

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


class _FallbackCache:
    def __init__(self):
        self.latest = date.today() - timedelta(days=2)
        self.calls = []

    def get_trending_history(self, start_date=None, end_date=None, since_type=None):
        self.calls.append((start_date, end_date, since_type))

        # Today window has no data.
        if start_date == date.today() and end_date == date.today():
            return []

        # Fallback window returns data.
        if end_date == self.latest:
            return [
                {
                    "record_date": self.latest.isoformat(),
                    "repo_full_name": "owner/repo",
                    "description": "fallback repo",
                    "language": "Python",
                    "stars": 200,
                    "stars_today": 8,
                    "rank": 1,
                    "since_type": "daily",
                    "category": "infra_and_tools",
                }
            ]
        return []

    def get_latest_record_date(self, since_type=None):
        return self.latest

    def get(self, repo_full_name):
        return {"summary": "Summary text", "reasons": ["Reason A"]}


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
    assert body["data_date"] == date.today().isoformat()
    assert body["is_fresh_today"] is True


def test_dashboard_day_filter_does_not_fallback(monkeypatch):
    cache = _FallbackCache()
    monkeypatch.setattr(api_router, "cache", cache)
    client = TestClient(app)

    resp = client.get("/api/dashboard?days=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_ecosystem"] == []
    assert body["infra_and_tools"] == []
    assert body["product_and_ui"] == []
    assert body["knowledge_base"] == []
    assert body["data_date"] is None
    assert body["is_fresh_today"] is False
    assert len(cache.calls) >= 1
    assert all(call[0] == date.today() and call[1] == date.today() for call in cache.calls)


def test_dashboard_multi_day_filter_fallbacks_to_latest(monkeypatch):
    cache = _FallbackCache()
    monkeypatch.setattr(api_router, "cache", cache)
    client = TestClient(app)

    resp = client.get("/api/dashboard?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["infra_and_tools"]) == 1
    assert body["infra_and_tools"][0]["repo_name"] == "owner/repo"
    assert body["data_date"] == cache.latest.isoformat()
    assert body["is_fresh_today"] is False
    # First call checks today window; second call uses fallback latest date window.
    assert len(cache.calls) >= 2


def test_dashboard_insights_marks_stale_when_fallback(monkeypatch):
    cache = _FallbackCache()
    monkeypatch.setattr(api_router, "cache", cache)
    client = TestClient(app)

    resp = client.get("/api/dashboard/insights?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_date"] == cache.latest.isoformat()
    assert body["is_fresh_today"] is False


def test_trends_marks_stale_when_fallback(monkeypatch):
    cache = _FallbackCache()
    monkeypatch.setattr(api_router, "cache", cache)
    client = TestClient(app)

    resp = client.get("/api/trends?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_date"] == cache.latest.isoformat()
    assert body["is_fresh_today"] is False
