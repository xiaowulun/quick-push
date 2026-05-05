from datetime import date

from fastapi.testclient import TestClient

from web.backend.app import app
from web.backend.routers import api as api_router


class _FakeCache:
    def __init__(self):
        today = date.today().isoformat()
        self.records = [
            {
                "record_date": today,
                "repo_full_name": "alpha/agent",
                "description": "Agent framework for workflow automation",
                "language": "Python",
                "stars": 12000,
                "stars_today": 88,
                "rank": 1,
                "since_type": "daily",
                "category": "infra_and_tools",
            },
            {
                "record_date": today,
                "repo_full_name": "beta/copilot",
                "description": "Enterprise copilot with policy guardrails",
                "language": "TypeScript",
                "stars": 8400,
                "stars_today": 47,
                "rank": 2,
                "since_type": "daily",
                "category": "ai_ecosystem",
            },
        ]

    def get_trending_history(self, start_date=None, end_date=None, since_type=None, repo_name=None):
        return self.records

    def get_latest_record_date(self, since_type=None):
        return date.today()

    def get(self, repo_full_name):
        if repo_full_name == "alpha/agent":
            return {
                "summary": "High productivity multi-agent framework",
                "reasons": ["Strong ecosystem", "Fast MVP integration"],
                "keywords": ["agent", "workflow"],
                "tech_stack": ["Python", "FastAPI"],
                "use_cases": ["AI 助手"],
            }
        return {
            "summary": "Policy-aware enterprise copilot",
            "reasons": ["Security-first design"],
            "keywords": ["copilot", "enterprise"],
            "tech_stack": ["TypeScript", "Node.js"],
            "use_cases": ["开发提效"],
        }

    def get_project_detail(self, repo_full_name, history_limit=12):
        basic = next((x for x in self.records if x["repo_full_name"] == repo_full_name), None)
        if not basic:
            return None
        risk_notes = ["许可证兼容性需确认"] if repo_full_name == "beta/copilot" else []
        return {
            "basic": {
                "repo_full_name": repo_full_name,
                "description": basic["description"],
                "language": basic["language"],
                "category": basic["category"],
                "stars": basic["stars"],
                "stars_today": basic["stars_today"],
                "url": f"https://github.com/{repo_full_name}",
            },
            "summary": self.get(repo_full_name)["summary"],
            "reasons": self.get(repo_full_name)["reasons"],
            "keywords": self.get(repo_full_name)["keywords"],
            "tech_stack": self.get(repo_full_name)["tech_stack"],
            "use_cases": self.get(repo_full_name)["use_cases"],
            "risk_notes": risk_notes,
            "evidence": {"chunk_text": "README includes quickstart and deployment docs."},
            "trend_summary": {
                "total_records": 8,
                "latest_stars": basic["stars"],
                "avg_stars_today": basic["stars_today"],
            },
            "trend_history": [],
        }


def test_discover_feed_returns_scored_items(monkeypatch):
    monkeypatch.setattr(api_router, "cache", _FakeCache())
    client = TestClient(app)

    resp = client.get("/api/discover/feed", params={"days": 7, "limit": 5, "interests": "agent,workflow"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    first = body["items"][0]
    assert "overall_score" in first
    assert "dimensions" in first
    assert "risk_flags" in first


def test_compare_score_returns_ranked_rows(monkeypatch):
    monkeypatch.setattr(api_router, "cache", _FakeCache())
    client = TestClient(app)

    resp = client.post("/api/compare/score", json={"repo_names": ["alpha/agent", "beta/copilot"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["overall_score"] >= body["items"][1]["overall_score"]


def test_assistant_recommend_returns_decision(monkeypatch):
    monkeypatch.setattr(api_router, "cache", _FakeCache())
    client = TestClient(app)

    resp = client.post(
        "/api/assistant/recommend",
        json={
            "query": "我要两周上线 MVP，优先推荐哪个？",
            "repo_names": ["alpha/agent", "beta/copilot"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] in {"推荐", "谨慎推进", "观望"}
    assert isinstance(body["projects"], list) and len(body["projects"]) == 2
