import asyncio
from datetime import datetime
from types import SimpleNamespace

from app.knowledge.chat import RAGChatService
from app.knowledge.query_parser import QueryFilters


class _DummySession:
    def __init__(self):
        self.session_id = "tool-flow-session"
        self.last_query_time = None
        self.last_filters = None
        self.query_count = 0
        self.history = []

    def add_to_history(self, query, answer, projects):
        self.history.append({"query": query, "answer": answer, "projects": projects})


class _DummySessionManager:
    def __init__(self, session):
        self._session = session

    def get_or_create(self, session_id=None):
        return self._session


async def _collect_chunks(stream):
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return chunks


def _make_stream_with_text(text):
    async def _gen():
        yield {"type": "content_start"}
        yield {"type": "content", "content": text}
        yield {"type": "done"}

    return _gen()


def test_chat_stream_skips_parser_and_retrieval_when_not_using_rag():
    service = object.__new__(RAGChatService)
    session = _DummySession()
    service.session_manager = _DummySessionManager(session)

    service._should_use_rag = lambda _query, _session: False
    service._is_followup_query = lambda _query, _session: False
    service._sanitize_filters = lambda filters: filters if isinstance(filters, QueryFilters) else QueryFilters()

    class _MustNotCallParser:
        async def parse(self, _query):
            raise AssertionError("parser should not be called")

    service.query_parser = _MustNotCallParser()

    async def _must_not_retrieve(*_args, **_kwargs):
        raise AssertionError("retrieval should not be called")

    service._retrieve_projects_with_filter_fallback = _must_not_retrieve
    service._chat_without_retrieval = lambda _query: _make_stream_with_text("no-rag-branch")
    service._chat_no_match = lambda _query: _make_stream_with_text("no-match")
    service._stream_and_persist = lambda session, query, stream: stream

    chunks = asyncio.run(_collect_chunks(service.chat_stream("你好")))
    content = "".join(chunk.get("content", "") for chunk in chunks if chunk.get("type") == "content")

    assert content == "no-rag-branch"
    assert any(chunk.get("type") == "session" for chunk in chunks)


def test_chat_stream_uses_parser_then_retrieval_for_first_turn_rag():
    service = object.__new__(RAGChatService)
    session = _DummySession()
    service.session_manager = _DummySessionManager(session)

    parser_called = {"count": 0}
    retrieve_calls = []

    service._should_use_rag = lambda _query, _session: True
    service._is_followup_query = lambda _query, _session: False
    service._sanitize_filters = lambda filters: filters if isinstance(filters, QueryFilters) else QueryFilters()

    class _Parser:
        async def parse(self, _query):
            parser_called["count"] += 1
            return QueryFilters(language="Python", keywords=["agent"])

    service.query_parser = _Parser()

    async def _retrieve(_query, _top_k, filters=None):
        retrieve_calls.append(filters)
        return []

    service._retrieve_projects_with_filter_fallback = _retrieve
    service._chat_no_match = lambda _query: _make_stream_with_text("no-match")
    service._stream_and_persist = lambda session, query, stream: stream

    chunks = asyncio.run(_collect_chunks(service.chat_stream("推荐一个 Python agent 项目")))
    content = "".join(chunk.get("content", "") for chunk in chunks if chunk.get("type") == "content")

    assert parser_called["count"] == 1
    assert len(retrieve_calls) == 1
    assert isinstance(retrieve_calls[0], QueryFilters)
    assert retrieve_calls[0].language == "Python"
    assert "agent" in retrieve_calls[0].keywords
    assert session.last_filters is not None
    assert content == "no-match"


def test_chat_stream_reuses_session_filters_for_followup_and_skips_parser():
    service = object.__new__(RAGChatService)
    session = _DummySession()
    session.last_filters = {"language": "Go", "keywords": ["workflow"]}
    session.last_query_time = datetime.now()
    service.session_manager = _DummySessionManager(session)

    parser_called = {"count": 0}
    retrieve_calls = []

    service._should_use_rag = lambda _query, _session: True
    service._is_followup_query = lambda _query, _session: True
    service._sanitize_filters = lambda filters: QueryFilters(**filters) if isinstance(filters, dict) else (
        filters if isinstance(filters, QueryFilters) else QueryFilters()
    )

    class _Parser:
        async def parse(self, _query):
            parser_called["count"] += 1
            return QueryFilters(language="Python")

    service.query_parser = _Parser()

    async def _retrieve(_query, _top_k, filters=None):
        retrieve_calls.append(filters)
        return []

    service._retrieve_projects_with_filter_fallback = _retrieve
    service._chat_no_match = lambda _query: _make_stream_with_text("followup-no-match")
    service._stream_and_persist = lambda session, query, stream: stream

    chunks = asyncio.run(_collect_chunks(service.chat_stream("那换成 Go 的呢？")))
    content = "".join(chunk.get("content", "") for chunk in chunks if chunk.get("type") == "content")

    assert parser_called["count"] == 0
    assert len(retrieve_calls) == 1
    assert isinstance(retrieve_calls[0], QueryFilters)
    assert retrieve_calls[0].language == "Go"
    assert "workflow" in retrieve_calls[0].keywords
    assert content == "followup-no-match"

