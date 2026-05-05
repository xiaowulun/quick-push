import asyncio

from app.knowledge.query_parser import QueryFilters, QueryParser


def _build_parser_for_unit_test() -> QueryParser:
    parser = object.__new__(QueryParser)
    parser.request_timeout = 0.1
    parser.retry_backoff_seconds = 0.0
    parser.primary_max_retries = 3
    parser.fallback_max_retries = 2
    return parser


def test_parse_stars_from_text_supports_units():
    assert QueryParser._parse_stars_from_text("top 1.2k stars") == 1200
    assert QueryParser._parse_stars_from_text("top 2w star") == 20000
    assert QueryParser._parse_stars_from_text("top 3q stars") == 3000


def test_invoke_chain_with_retry_retries_timeout_then_success():
    parser = _build_parser_for_unit_test()

    class DummyChain:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, payload):
            self.calls += 1
            if self.calls < 3:
                raise TimeoutError("Request timed out.")
            return payload["query"]

    chain = DummyChain()
    result = asyncio.run(
        parser._invoke_chain_with_retry(
            chain=chain,
            payload={"query": "ok"},
            stage="unit-test",
            retries=3,
        )
    )

    assert result == "ok"
    assert chain.calls == 3


def test_parse_uses_fallback_after_primary_timeout():
    parser = _build_parser_for_unit_test()

    async def _primary_parse(_query: str):
        raise TimeoutError("Request timed out.")

    async def _fallback_parse(_query: str):
        return QueryFilters(language="Python")

    parser._primary_parse = _primary_parse
    parser._fallback_parse = _fallback_parse
    parser._heuristic_parse = lambda _query: QueryFilters()

    result = asyncio.run(parser.parse("recommend Python projects"))
    assert result.language == "Python"


def test_parse_uses_heuristic_when_fallback_has_no_filters():
    parser = _build_parser_for_unit_test()

    async def _primary_parse(_query: str):
        raise TimeoutError("Request timed out.")

    async def _fallback_parse(_query: str):
        return QueryFilters()

    parser._primary_parse = _primary_parse
    parser._fallback_parse = _fallback_parse
    parser._heuristic_parse = lambda _query: QueryFilters(category="knowledge_base")

    result = asyncio.run(parser.parse("recommend docs projects"))
    assert result.category == "knowledge_base"


def test_query_filters_explanation_lines():
    filters = QueryFilters(
        language="Python",
        category="ai_ecosystem",
        days=7,
        min_stars=500,
        keywords=["agent", "workflow"],
    )

    lines = filters.to_explanation_lines()

    assert any("Python" in line for line in lines)
    assert any("ai_ecosystem" in line for line in lines)
    assert any("7" in line for line in lines)
    assert any("500" in line for line in lines)
    assert any("agent" in line and "workflow" in line for line in lines)


def test_extract_keywords_reuses_heuristic_rules():
    parser = _build_parser_for_unit_test()
    keywords = parser.extract_keywords("owner/mega-agent RAG workflow automation Python", limit=4)

    lowered = {k.lower() for k in keywords}
    assert "workflow" in lowered or "automation" in lowered
    assert "python" not in lowered
