"""
Query parser: extract soft filter conditions from user query.

Parsing strategy:
1) Structured LLM parsing (primary)
2) Compact JSON parsing (fallback)
3) Heuristic parsing (final safeguard)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


class QueryFilters(BaseModel):
    """Parsed query filters."""

    language: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    days: Optional[int] = Field(default=None)
    min_stars: Optional[int] = Field(default=None)
    keywords: List[str] = Field(default_factory=list)

    def has_filters(self) -> bool:
        return any(
            [
                self.language,
                self.category,
                self.days,
                self.min_stars is not None,
                len(self.keywords) > 0,
            ]
        )

    def to_boost_dict(self) -> dict:
        boost = {}
        if self.language:
            boost["language"] = self.language
        if self.category:
            boost["category"] = self.category
        if self.days:
            boost["days"] = self.days
        if self.min_stars is not None:
            boost["min_stars"] = self.min_stars
        return boost


class QueryParser:
    """Parse user query into structured retrieval filters."""

    SYSTEM_PROMPT = """
You are a query parser for GitHub trending project retrieval.
Return ONLY a JSON object with these keys:
- language: string or null
- category: one of ["ai_ecosystem","infra_and_tools","product_and_ui","knowledge_base"] or null
- days: integer or null
- min_stars: integer or null
- keywords: array of strings

Rules:
1) Do not over-infer. If uncertain, use null / empty array.
2) Keep keywords concise (0-6 items).
3) If user mentions relative time:
   - today / 今天 / 今日 -> 1
   - this week / recent week / 本周 / 最近一周 -> 7
   - this month / recent month / 本月 / 最近一个月 -> 30
4) If user asks "popular/hot/high-star" or "热门/高星", min_stars can be estimated as 500.
""".strip()

    FALLBACK_PROMPT = """
Output one-line minified JSON only.
keys: language, category, days, min_stars, keywords
query: {query}
""".strip()

    VALID_CATEGORIES = {
        "ai_ecosystem",
        "infra_and_tools",
        "product_and_ui",
        "knowledge_base",
    }

    CATEGORY_ALIAS = {
        "ai": "ai_ecosystem",
        "llm": "ai_ecosystem",
        "agent": "ai_ecosystem",
        "rag": "ai_ecosystem",
        "智能体": "ai_ecosystem",
        "大模型": "ai_ecosystem",
        "infra": "infra_and_tools",
        "tool": "infra_and_tools",
        "tools": "infra_and_tools",
        "devops": "infra_and_tools",
        "cli": "infra_and_tools",
        "framework": "infra_and_tools",
        "产品": "product_and_ui",
        "前端": "product_and_ui",
        "product": "product_and_ui",
        "ui": "product_and_ui",
        "frontend": "product_and_ui",
        "webapp": "product_and_ui",
        "知识库": "knowledge_base",
        "教程": "knowledge_base",
        "学习路线": "knowledge_base",
        "awesome": "knowledge_base",
        "tutorial": "knowledge_base",
        "guide": "knowledge_base",
        "docs": "knowledge_base",
        "course": "knowledge_base",
        "knowledge": "knowledge_base",
    }

    LANGUAGE_MAP = {
        "python": "Python",
        "py": "Python",
        "javascript": "JavaScript",
        "js": "JavaScript",
        "typescript": "TypeScript",
        "ts": "TypeScript",
        "rust": "Rust",
        "go": "Go",
        "golang": "Go",
        "java": "Java",
        "c++": "C++",
        "cpp": "C++",
        "c#": "C#",
        "csharp": "C#",
        "swift": "Swift",
        "php": "PHP",
        "ruby": "Ruby",
        "kotlin": "Kotlin",
    }

    FILTER_INTENT_HINTS = (
        "language",
        "lang",
        "category",
        "分类",
        "语言",
        "最近",
        "近",
        "today",
        "week",
        "month",
        "top",
        "热门",
        "高星",
        "stars",
        "star",
        "最热",
    )

    def __init__(self):
        config = get_config()
        timeout = float(config.openai.request_timeout)
        # 解析器属于前置步骤，超时预算应明显小于主对话预算。
        self.request_timeout = max(4.0, min(timeout, 12.0))
        self.primary_max_retries = max(1, min(int(getattr(config.behavior, "max_retries", 2)), 2))
        self.fallback_max_retries = 1
        self.retry_backoff_seconds = 0.4

        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_fast,
            temperature=0.0,
            max_tokens=220,
            timeout=self.request_timeout,
        )
        self.fallback_llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_fast,
            temperature=0.0,
            max_tokens=120,
            timeout=self.request_timeout,
        )

    @staticmethod
    def _is_truncation_error(error: Exception) -> bool:
        message = str(error)
        return "length limit was reached" in message or "Could not parse response content" in message

    @staticmethod
    def _is_timeout_error(error: Exception) -> bool:
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return True
        message = str(error).lower()
        timeout_tokens = [
            "request timed out",
            "read timeout",
            "connect timeout",
            "timed out",
            "timeout",
            "deadline exceeded",
            "apitimeouterror",
        ]
        return any(token in message for token in timeout_tokens)

    async def _invoke_chain_with_retry(self, chain: Any, payload: dict, stage: str, retries: int):
        retries = max(1, int(retries))
        delay = float(self.retry_backoff_seconds)
        for attempt in range(1, retries + 1):
            try:
                return await asyncio.wait_for(
                    chain.ainvoke(payload),
                    timeout=self.request_timeout + 2.0,
                )
            except Exception as error:
                is_timeout = self._is_timeout_error(error)
                is_last_attempt = attempt >= retries
                if (not is_timeout) or is_last_attempt:
                    raise
                logger.warning(
                    "查询解析%s超时，第 %s/%s 次重试，%.1f 秒后继续：%s",
                    stage,
                    attempt,
                    retries,
                    delay,
                    error,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 2.5)

    @staticmethod
    def _extract_json_blob(text: str) -> Optional[dict]:
        if not text:
            return None
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @classmethod
    def _normalize_category(cls, category: Optional[str]) -> Optional[str]:
        if not category:
            return None
        raw = str(category).strip().lower().replace("-", "_").replace(" ", "")
        if raw in cls.VALID_CATEGORIES:
            return raw
        if any(token in raw for token in ["ai", "llm", "agent", "rag", "智能体", "大模型"]):
            return "ai_ecosystem"
        if any(token in raw for token in ["ui", "frontend", "product", "webapp", "前端", "产品"]):
            return "product_and_ui"
        if any(token in raw for token in ["knowledge", "awesome", "tutorial", "guide", "docs", "course", "知识库", "教程"]):
            return "knowledge_base"
        if any(token in raw for token in ["infra", "tool", "tools", "devops", "cli", "framework"]):
            return "infra_and_tools"
        for key, normalized in cls.CATEGORY_ALIAS.items():
            if key in raw:
                return normalized
        return None

    @classmethod
    def _normalize_language(cls, language: Optional[str]) -> Optional[str]:
        if not language:
            return None
        raw_text = str(language).strip()
        raw = raw_text.lower()
        if raw in cls.LANGUAGE_MAP:
            return cls.LANGUAGE_MAP[raw]

        # Handle composite output such as "Python, TypeScript".
        candidates = []
        for key, normalized in cls.LANGUAGE_MAP.items():
            if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", raw):
                candidates.append((raw.find(key), normalized))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        return raw_text

    @staticmethod
    def _normalize_days(days: Any) -> Optional[int]:
        if days is None:
            return None
        try:
            value = int(days)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        return min(value, 365)

    @staticmethod
    def _normalize_min_stars(stars: Any) -> Optional[int]:
        if stars is None:
            return None
        try:
            value = int(stars)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        if value < 10:
            return None
        return value

    @staticmethod
    def _normalize_keywords(keywords: Any) -> List[str]:
        generic_tokens = {
            "project",
            "projects",
            "github",
            "trending",
            "star",
            "stars",
            "popular",
            "hot",
            "ai",
            "llm",
            "agent",
            "rag",
            "项目",
            "热门",
            "高星",
        }
        if not keywords:
            return []
        if not isinstance(keywords, list):
            keywords = [keywords]
        out: List[str] = []
        seen = set()
        for kw in keywords:
            text = re.sub(r"\s+", " ", str(kw).strip())
            if not text:
                continue
            key = text.lower()
            normalized = re.sub(r"[^a-z0-9+#\u4e00-\u9fff]+", " ", key).strip()
            tokens = [t for t in normalized.split() if t]
            if tokens and all(t in generic_tokens for t in tokens):
                continue
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
            if len(out) >= 8:
                break
        return out

    @classmethod
    def _from_dict(cls, data: Optional[dict]) -> QueryFilters:
        if not isinstance(data, dict):
            return QueryFilters()
        language = cls._normalize_language(data.get("language"))
        keywords = cls._normalize_keywords(data.get("keywords"))
        if language:
            lang_norm = str(language).strip().lower()
            keywords = [kw for kw in keywords if str(kw).strip().lower() != lang_norm]
        return QueryFilters(
            language=language,
            category=cls._normalize_category(data.get("category")),
            days=cls._normalize_days(data.get("days")),
            min_stars=cls._normalize_min_stars(data.get("min_stars")),
            keywords=keywords,
        )

    @staticmethod
    def _parse_stars_from_text(text: str) -> Optional[int]:
        raw = (text or "").lower()
        patterns = [
            r"(\d+(?:\.\d+)?)\s*[kK]\s*stars?",
            r"(\d+(?:\.\d+)?)\s*[kK]",
            r"(\d+(?:\.\d+)?)\s*万\s*stars?",
            r"(\d+(?:\.\d+)?)\s*万",
            r"(\d+(?:\.\d+)?)\s*千\s*stars?",
            r"(\d+(?:\.\d+)?)\s*千",
            r"(\d+)\s*stars?",
            r"(\d+)\s*star",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw)
            if not match:
                continue
            value = float(match.group(1))
            if "k" in pattern.lower():
                return int(value * 1000)
            if "万" in pattern:
                return int(value * 10000)
            if "千" in pattern:
                return int(value * 1000)
            return int(value)
        if any(token in raw for token in ["热门", "很火", "高星", "popular", "hot"]):
            return 500
        return None

    def _heuristic_parse(self, query: str) -> QueryFilters:
        q = (query or "").strip()
        if not q:
            return QueryFilters()
        lower = q.lower()

        language = None
        for k, v in self.LANGUAGE_MAP.items():
            if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", lower):
                language = v
                break

        category = None
        for k, v in self.CATEGORY_ALIAS.items():
            if k in lower or k in q:
                category = v
                break
        if category is None:
            if any(x in q for x in ["AI", "大模型", "智能体", "RAG"]):
                category = "ai_ecosystem"
            elif any(x in q for x in ["知识库", "教程", "学习路线", "awesome"]):
                category = "knowledge_base"
            elif any(x in q for x in ["前端", "UI", "产品", "SaaS"]):
                category = "product_and_ui"

        days = None
        if any(x in q for x in ["今天", "今日", "today"]):
            days = 1
        elif any(x in q for x in ["本周", "最近一周", "近一周", "this week", "last week"]):
            days = 7
        elif any(x in q for x in ["本月", "最近一个月", "近一个月", "this month", "last month"]):
            days = 30

        min_stars = self._parse_stars_from_text(q)

        # Keep heuristic keywords conservative to avoid over-filtering.
        keywords: List[str] = []
        generic_tokens = {
            "find",
            "show",
            "best",
            "good",
            "project",
            "projects",
            "github",
            "trending",
            "star",
            "stars",
            "popular",
            "hot",
            "ai",
            "llm",
            "agent",
            "rag",
        }
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_+\-]{1,20}", q):
            if token.lower() in generic_tokens:
                continue
            if token.lower() in {k.lower() for k in self.LANGUAGE_MAP}:
                continue
            keywords.append(token)
        keywords = self._normalize_keywords(keywords)[:4]

        return QueryFilters(
            language=language,
            category=category,
            days=days,
            min_stars=min_stars,
            keywords=keywords,
        )

    def _has_filter_intent(self, query: str) -> bool:
        q = (query or "").strip()
        if not q:
            return False
        lower = q.lower()

        if any(token in lower for token in self.FILTER_INTENT_HINTS):
            return True

        if re.search(r"\b(python|java|javascript|typescript|go|rust|c\+\+|c#|cpp)\b", lower):
            return True

        if re.search(r"\b\d+\s*(stars?|star|k)\b", lower):
            return True

        return False

    async def _primary_parse(self, query: str) -> QueryFilters:
        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", self.SYSTEM_PROMPT),
                ("user", "query: {query}\nReturn JSON only."),
            ]
        )
        chain = prompt_template | self.llm.with_structured_output(QueryFilters)
        result = await self._invoke_chain_with_retry(
            chain=chain,
            payload={"query": query},
            stage="主链路",
            retries=self.primary_max_retries,
        )

        if isinstance(result, QueryFilters):
            data = result.model_dump()
        else:
            dump_fn = getattr(result, "model_dump", None)
            data = dump_fn() if callable(dump_fn) else {}
        return self._from_dict(data)

    async def _fallback_parse(self, query: str) -> QueryFilters:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.SYSTEM_PROMPT),
                ("user", self.FALLBACK_PROMPT),
            ]
        )
        chain = prompt | self.fallback_llm
        message = await self._invoke_chain_with_retry(
            chain=chain,
            payload={"query": query},
            stage="回退链路",
            retries=self.fallback_max_retries,
        )
        parsed = self._extract_json_blob(getattr(message, "content", ""))
        return self._from_dict(parsed)

    async def parse(self, query: str) -> QueryFilters:
        """Parse filters from user query."""
        heuristic = self._heuristic_parse(query)
        if heuristic.has_filters():
            logger.info("查询解析规则命中: %s -> %s", query, heuristic.model_dump())
            return heuristic

        if not self._has_filter_intent(query):
            logger.info("查询解析跳过 LLM（无过滤意图）: %s", query)
            return QueryFilters()

        try:
            normalized = await self._primary_parse(query)
            if normalized.has_filters():
                logger.info("查询解析LLM命中: %s -> %s", query, normalized.model_dump())
                return normalized
            return heuristic
        except Exception as e:
            if self._is_truncation_error(e):
                logger.warning("查询解析截断，尝试回退解析: %s", e)
            elif self._is_timeout_error(e):
                logger.warning("查询解析超时，尝试回退解析: %s", e)
            else:
                logger.warning("查询解析失败，尝试回退解析: %s", e)

            try:
                recovered = await self._fallback_parse(query)
                if recovered.has_filters():
                    logger.info("查询解析回退成功: %s -> %s", query, recovered.model_dump())
                    return recovered
            except Exception as fallback_error:
                logger.warning("查询解析回退失败: %s", fallback_error)

            if heuristic.has_filters():
                logger.info("查询解析启发式成功: %s -> %s", query, heuristic.model_dump())
                return heuristic

            logger.warning("查询解析失败：%s，返回空过滤条件", e)
            return QueryFilters()

    def parse_sync(self, query: str) -> QueryFilters:
        """Sync wrapper for tests and scripts."""
        return asyncio.run(self.parse(query))


_parser: Optional[QueryParser] = None


def get_query_parser() -> QueryParser:
    """Get singleton query parser."""
    global _parser
    if _parser is None:
        _parser = QueryParser()
    return _parser
