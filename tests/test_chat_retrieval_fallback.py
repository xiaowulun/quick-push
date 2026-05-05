import asyncio
from datetime import datetime
from types import SimpleNamespace

from app.knowledge.chat import RAGChatService, RetrievedProject
from app.knowledge.query_parser import QueryFilters


def test_retrieve_projects_fallback_to_unfiltered_when_filtered_empty():
    service = object.__new__(RAGChatService)
    calls = []

    async def fake_retrieve_projects(query, top_k=5, filters=None):
        calls.append(filters.model_dump() if filters else None)
        if filters is not None:
            return []
        return [{"repo_full_name": "owner/repo"}]

    service.retrieve_projects = fake_retrieve_projects

    projects = asyncio.run(
        service._retrieve_projects_with_filter_fallback(
            query="find python project",
            top_k=5,
            filters=QueryFilters(language="Python"),
        )
    )

    assert len(calls) == 2
    assert calls[0] is not None
    assert calls[1] is None
    assert projects == [{"repo_full_name": "owner/repo"}]


def test_retrieve_projects_no_fallback_when_no_filters():
    service = object.__new__(RAGChatService)
    calls = []

    async def fake_retrieve_projects(query, top_k=5, filters=None):
        calls.append(filters)
        return []

    service.retrieve_projects = fake_retrieve_projects

    projects = asyncio.run(
        service._retrieve_projects_with_filter_fallback(
            query="find project",
            top_k=5,
            filters=QueryFilters(),
        )
    )

    assert len(calls) == 1
    assert projects == []


class _DummyParser:
    async def parse(self, query):
        return QueryFilters()


class _DummySession:
    def __init__(self):
        self.session_id = "test-session"
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


def _build_chat_service_for_low_conf_tests(llm_answer: str, sample_similarity: float = 0.0):
    service = object.__new__(RAGChatService)
    service.min_confidence = 0.42
    service.config = SimpleNamespace(
        openai=SimpleNamespace(
            model_easy="Qwen/Qwen3-32B",
            model_medium="Pro/MiniMaxAI/MiniMax-M2.5",
            model_hard="Pro/deepseek-ai/DeepSeek-V3",
        )
    )
    service.model = "Pro/MiniMaxAI/MiniMax-M2.5"
    service.request_timeout = 5
    service.rag_max_tokens = 256
    service.SYSTEM_PROMPT = "system"
    service.RAG_PROMPT_TEMPLATE = "query={query}\ncontext={projects_context}"
    service._is_technical_query = lambda query: True
    service._should_use_rag = lambda query, session: True
    service._is_followup_query = lambda query, session: False
    service._sanitize_filters = lambda filters: filters if isinstance(filters, QueryFilters) else QueryFilters()
    service.query_parser = _DummyParser()

    session = _DummySession()
    service.session_manager = _DummySessionManager(session)

    sample = RetrievedProject(
        repo_full_name="owner/repo",
        summary="sample summary",
        reasons=["sample reason"],
        similarity=sample_similarity,
        language="Python",
        stars=123,
        url="https://github.com/owner/repo",
        source_id="S1",
        chunk_id="owner/repo#001",
        evidence_section="readme",
        evidence_path="README.md",
        evidence_heading="README",
        evidence_chunk="sample evidence",
    )

    async def fake_retrieve(query, top_k, filters=None):
        return [sample]

    service._retrieve_projects_with_filter_fallback = fake_retrieve

    response = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=llm_answer),
                )
            ]
        )
    ]
    service.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response),
        )
    )
    return service


async def _collect_stream_text(stream):
    text_parts = []
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
        if chunk.get("type") == "content":
            text_parts.append(chunk.get("content", ""))
    return "".join(text_parts), chunks




def test_chat_stream_allows_soft_answer_for_planning_query_under_low_confidence():
    service = _build_chat_service_for_low_conf_tests(llm_answer="建议先做核心闭环与监控。[S1]")

    answer, chunks = asyncio.run(
        _collect_stream_text(service.chat_stream("如果要本周上 MVP，优先做哪些能力？"))
    )

    assert any(chunk.get("type") == "done" for chunk in chunks)
    assert answer.startswith("说明：当前检索置信度较低")
    assert "当前无法给出高置信度结论" not in answer


def test_chat_stream_keeps_hard_reject_for_non_planning_query_under_low_confidence():
    service = _build_chat_service_for_low_conf_tests(llm_answer="不应该被调用")
    service.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be called"))
            )
        )
    )

    answer, chunks = asyncio.run(_collect_stream_text(service.chat_stream("推荐几个 Python 框架")))

    assert any(chunk.get("type") == "done" for chunk in chunks)
    assert "当前无法给出高置信度结论" in answer


def test_retrieval_intent_prefers_lookup_over_concept_learning():
    service = object.__new__(RAGChatService)
    retrieval_query = "\u6700\u8fd1\u6709\u4ec0\u4e48\u6bd4\u8f83\u597d\u7684AI agent\u9879\u76ee"
    conceptual_query = "\u6211\u60f3\u4e86\u89e3\u4e00\u4e0bRAG\uff0cai agent"

    assert service._has_retrieval_intent(retrieval_query) is True
    assert service._has_retrieval_intent(conceptual_query) is False


def test_should_use_rag_for_short_followup_when_session_has_filters():
    service = object.__new__(RAGChatService)
    session = SimpleNamespace(
        last_filters={"language": "Python"},
        last_query_time=datetime.now(),
    )

    assert service._should_use_rag("继续", session) is True


def test_chat_model_fallback_when_primary_model_missing():
    service = object.__new__(RAGChatService)
    service.model = "bad-model"
    service.config = SimpleNamespace(
        openai=SimpleNamespace(
            model_easy="Qwen/Qwen3-32B",
            model_medium="Pro/MiniMaxAI/MiniMax-M2.5",
            model_hard="Pro/deepseek-ai/DeepSeek-V3",
        )
    )

    class _FakeCompletions:
        def __init__(self):
            self.calls = []

        def create(self, model, **kwargs):
            self.calls.append(model)
            if model == "bad-model":
                raise RuntimeError(
                    "Error code: 400 - {'code': 20012, 'message': 'Model does not exist. Please check it carefully.', 'data': None}"
                )
            return {"used_model": model}

    fake = _FakeCompletions()
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))

    result = service._create_chat_completion_with_fallback(
        model="bad-model",
        query="hi",
        retrieval=False,
        messages=[{"role": "user", "content": "hi"}],
    )

    assert result["used_model"] == "Pro/MiniMaxAI/MiniMax-M2.5"
    assert fake.calls == ["bad-model", "Pro/MiniMaxAI/MiniMax-M2.5"]


def test_chat_stream_emits_recommendation_basis_event():
    service = _build_chat_service_for_low_conf_tests(llm_answer="[S1] 推荐这个项目", sample_similarity=0.95)

    class _ParserWithFilters:
        async def parse(self, _query):
            return QueryFilters(language="Python", keywords=["agent"])

    service.query_parser = _ParserWithFilters()

    chunks = []
    async def _collect():
        async for chunk in service.chat_stream("推荐一个 Python agent 项目"):
            chunks.append(chunk)
    asyncio.run(_collect())

    basis_chunks = [chunk for chunk in chunks if chunk.get("type") == "recommendation_basis"]
    assert len(basis_chunks) == 1
    basis = basis_chunks[0]["basis"]
    assert basis["filters"]["language"] == "Python"
    assert "agent" in basis["filters"]["keywords"]
    assert any("Query Parser" in text for text in basis["global_reasons"])
