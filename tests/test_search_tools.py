import asyncio

from app.analysis.agents.tools.search_tools import SearchAggregator, SearchResult


def test_hn_queries_include_keywords_from_description():
    aggregator = SearchAggregator()
    queries = aggregator._build_hn_queries(
        repo_name="owner/mega-agent",
        description="A RAG workflow automation framework for coding assistant",
    )

    joined = " ".join(queries).lower()
    assert "owner/mega-agent" in joined or '"owner/mega-agent"' in joined
    assert "workflow" in joined or "automation" in joined


def test_search_project_merges_and_dedupes_cross_source_results():
    aggregator = SearchAggregator()

    async def fake_hn_search(query, limit=10):
        if "rag" in query.lower():
            return [
                SearchResult(
                    source="hackernews",
                    title="RAG launch",
                    url="https://hn.example/a",
                    snippet="rag",
                    score=5,
                ),
            ]
        return [
            SearchResult(
                source="hackernews",
                title="RAG launch duplicate",
                url="https://hn.example/a",
                snippet="duplicate",
                score=3,
            ),
            SearchResult(
                source="hackernews",
                title="Workflow trend",
                url="https://hn.example/b",
                snippet="workflow",
                score=4,
            ),
        ]

    async def fake_github_search(repo_name, github_token=None):
        return [
            SearchResult(
                source="github_discussions",
                title="Discussion hot topic",
                url="https://github.com/x/y/discussions/1",
                snippet="discussion",
                score=9,
            )
        ]

    aggregator.hackernews.search = fake_hn_search
    aggregator.github_discussions.search = fake_github_search

    result = asyncio.run(
        aggregator.search_project(
            repo_name="owner/mega-agent",
            description="RAG workflow automation for coding",
        )
    )

    assert result["sources"]["hackernews"] == 2
    assert result["sources"]["github_discussions"] == 1
    assert result["total_mentions"] == 3
    assert len(result["hot_discussions"]) == 3
    top_item = result["hot_discussions"][0]
    assert 0.0 <= top_item["relevance_score"] <= 1.0
    assert 0.0 <= top_item["popularity_score"] <= 1.0
    assert 0.0 <= top_item["score"] <= 0.4
    titles = {item["title"] for item in result["hot_discussions"]}
    assert "RAG launch" in titles or "RAG launch duplicate" in titles
    assert "Workflow trend" in titles
    assert "Discussion hot topic" in titles


def test_search_project_filters_low_quality_noise():
    aggregator = SearchAggregator()

    async def fake_hn_search(query, limit=10):
        return [
            SearchResult(
                source="hackernews",
                title="xxx",
                url="https://hn.example/spam",
                snippet="buy now!!! limited time giveaway",
                score=999,
            ),
            SearchResult(
                source="hackernews",
                title="Workflow automation in production",
                url="https://hn.example/good",
                snippet="A practical workflow setup for coding automation.",
                score=10,
            ),
        ]

    async def fake_github_search(repo_name, github_token=None):
        return []

    aggregator.hackernews.search = fake_hn_search
    aggregator.github_discussions.search = fake_github_search

    result = asyncio.run(
        aggregator.search_project(
            repo_name="owner/mega-agent",
            description="workflow automation",
        )
    )

    titles = [item["title"] for item in result["hot_discussions"]]
    assert "xxx" not in titles
    assert "Workflow automation in production" in titles


def test_search_project_hit_threshold_suppresses_non_matching_hot_item():
    aggregator = SearchAggregator()

    async def fake_hn_search(query, limit=10):
        return [
            SearchResult(
                source="hackernews",
                title="Unrelated market headline",
                url="https://hn.example/nohit",
                snippet="generic discussion without repo context",
                score=500,
            ),
            SearchResult(
                source="hackernews",
                title="Mega-agent workflow automation guide",
                url="https://hn.example/hit",
                snippet="workflow automation with coding pipeline",
                score=30,
            ),
        ]

    async def fake_github_search(repo_name, github_token=None):
        return []

    aggregator.hackernews.search = fake_hn_search
    aggregator.github_discussions.search = fake_github_search

    result = asyncio.run(
        aggregator.search_project(
            repo_name="owner/mega-agent",
            description="workflow automation for coding",
        )
    )

    assert result["hot_discussions"][0]["title"] == "Mega-agent workflow automation guide"
    assert result["hot_discussions"][0]["relevance_score"] > 0
