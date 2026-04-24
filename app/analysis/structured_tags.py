"""Structured tag extraction for project understanding and retrieval."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Tuple


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]{1,31}")
_PHRASE_RE = re.compile(r"(multi-agent|real-time|open source|self-hosted|fine[- ]?tuning)", re.IGNORECASE)

_GENERIC_STOPWORDS = {
    "project",
    "projects",
    "github",
    "trending",
    "readme",
    "awesome",
    "open",
    "source",
    "tool",
    "tools",
    "framework",
    "application",
    "solution",
    "platform",
    "based",
    "build",
    "built",
    "using",
    "support",
    "supports",
}

_KEYWORD_ALIAS = {
    "llms": "llm",
    "large-language-model": "llm",
    "large-language-models": "llm",
    "chatgpt": "openai",
    "multiagent": "multi-agent",
    "lang-chain": "langchain",
    "vector-db": "vector-database",
    "vectordb": "vector-database",
}

_KEYWORD_CANONICAL_DISPLAY = {
    "llm": "LLM",
    "rag": "RAG",
    "api": "API",
    "sdk": "SDK",
    "cli": "CLI",
    "gpu": "GPU",
    "ocr": "OCR",
    "nlp": "NLP",
    "sql": "SQL",
    "ci/cd": "CI/CD",
    "openai": "OpenAI",
    "langchain": "LangChain",
    "chromadb": "ChromaDB",
    "fastapi": "FastAPI",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
}

# (label, regexes, base_score)
_TECH_STACK_RULES: List[Tuple[str, List[str], float]] = [
    ("Python", [r"\bpython\b"], 2.5),
    ("TypeScript", [r"\btypescript\b"], 2.3),
    ("JavaScript", [r"\bjavascript\b", r"\bnode\.?js\b"], 2.1),
    ("Go", [r"\bgolang\b", r"\bgo language\b"], 2.0),
    ("Rust", [r"\brust\b"], 2.0),
    ("Java", [r"\bjava\b"], 1.8),
    ("Vue", [r"\bvue(?:3)?\b"], 1.8),
    ("React", [r"\breact\b", r"\bnext\.?js\b"], 1.8),
    ("FastAPI", [r"\bfastapi\b"], 2.2),
    ("Django", [r"\bdjango\b"], 1.7),
    ("Flask", [r"\bflask\b"], 1.6),
    ("Docker", [r"\bdocker\b"], 1.9),
    ("Kubernetes", [r"\bkubernetes\b", r"\bk8s\b"], 2.0),
    ("PostgreSQL", [r"\bpostgres(?:ql)?\b"], 1.8),
    ("MySQL", [r"\bmysql\b"], 1.6),
    ("Redis", [r"\bredis\b"], 1.7),
    ("MongoDB", [r"\bmongodb\b"], 1.7),
    ("PyTorch", [r"\bpytorch\b"], 1.8),
    ("TensorFlow", [r"\btensorflow\b"], 1.7),
    ("LangChain", [r"\blangchain\b"], 1.9),
    ("OpenAI API", [r"\bopenai\b", r"\bgpt-?[34o5]\b"], 1.7),
    ("ChromaDB", [r"\bchroma(?:db)?\b"], 1.6),
]

# (label, regexes, base_score)
_USE_CASE_RULES: List[Tuple[str, List[str], float]] = [
    ("AI Agent", [r"\bagent\b", r"\bmulti-agent\b", r"\bautonomous\b"], 2.4),
    ("RAG Knowledge Base", [r"\brag\b", r"\bretrieval\b", r"\bvector(?: database)?\b"], 2.3),
    ("Code Assistant", [r"\bcopilot\b", r"\bcode assistant\b", r"\bcoding assistant\b"], 2.0),
    ("Data Crawling", [r"\bcrawler\b", r"\bscraper\b", r"\bweb crawl(?:ing)?\b"], 1.8),
    ("Data Visualization", [r"\bdashboard\b", r"\bvisualization\b", r"\bchart(?:s)?\b"], 1.6),
    ("Web Application", [r"\bweb app(?:lication)?\b", r"\bfrontend\b", r"\bsaas\b"], 1.5),
    ("Workflow Automation", [r"\bworkflow\b", r"\bautomation\b", r"\bpipeline\b"], 1.8),
    ("Model Serving", [r"\binference\b", r"\bserving\b", r"\bdeployment\b"], 1.7),
    ("DevOps", [r"\bdevops\b", r"\bci/cd\b", r"\bgithub actions\b"], 1.6),
    ("Education", [r"\btutorial\b", r"\bcourse\b", r"\blearn(?:ing)?\b"], 1.4),
]


def _normalize_keyword(token: str) -> str:
    text = re.sub(r"[_\s]+", "-", str(token or "").strip().lower())
    text = text.strip("-./")
    text = _KEYWORD_ALIAS.get(text, text)
    return text


def _format_keyword(token: str) -> str:
    normalized = _normalize_keyword(token)
    if normalized in _KEYWORD_CANONICAL_DISPLAY:
        return _KEYWORD_CANONICAL_DISPLAY[normalized]
    if normalized.isupper():
        return normalized
    if len(normalized) <= 4 and normalized.isalpha():
        return normalized.upper()
    return normalized


def _safe_text(raw: str, max_len: int = 12000) -> str:
    text = str(raw or "")
    return text[:max_len] if len(text) > max_len else text


def _add_score(
    score_map: DefaultDict[str, float],
    order_map: Dict[str, int],
    token: str,
    score: float,
) -> None:
    normalized = _normalize_keyword(token)
    if not normalized:
        return
    if normalized in _GENERIC_STOPWORDS:
        return
    if len(normalized) < 2:
        return
    if normalized.isnumeric():
        return
    score_map[normalized] += float(score)
    if normalized not in order_map:
        order_map[normalized] = len(order_map)


def _collect_keywords_with_scores(
    summary: str,
    reasons: List[str],
    readme_content: str,
    topics: List[str],
    sentiment_topics: List[str],
) -> List[str]:
    score_map: DefaultDict[str, float] = defaultdict(float)
    order_map: Dict[str, int] = {}

    for topic in topics:
        _add_score(score_map, order_map, topic, 4.0)

    for topic in sentiment_topics:
        _add_score(score_map, order_map, topic, 3.0)

    summary_text = _safe_text(summary, max_len=2400)
    reasons_text = _safe_text(" ".join(reasons or []), max_len=2400)
    readme_text = _safe_text(readme_content, max_len=8000)

    for token in _TOKEN_RE.findall(summary_text):
        _add_score(score_map, order_map, token, 1.8)
    for token in _TOKEN_RE.findall(reasons_text):
        _add_score(score_map, order_map, token, 1.5)
    for token in _TOKEN_RE.findall(readme_text):
        _add_score(score_map, order_map, token, 0.8)

    phrase_text = f"{summary_text} {reasons_text} {readme_text}"
    for phrase in _PHRASE_RE.findall(phrase_text):
        _add_score(score_map, order_map, phrase, 2.2)

    ranked = sorted(score_map.items(), key=lambda item: (-item[1], order_map[item[0]], item[0]))
    result: List[str] = []
    for token, score in ranked:
        if score < 1.6:
            continue
        result.append(_format_keyword(token))
        if len(result) >= 12:
            break
    return result


def _collect_rule_labels(
    text: str,
    rules: List[Tuple[str, List[str], float]],
    min_score: float,
    limit: int,
    topic_text: str = "",
) -> List[str]:
    lowered = (text or "").lower()
    topic_lower = (topic_text or "").lower()
    score_map: DefaultDict[str, float] = defaultdict(float)
    order_map: Dict[str, int] = {}

    for label, regex_list, base_score in rules:
        hits = 0
        for rx in regex_list:
            hits += len(re.findall(rx, lowered))
        if hits > 0:
            score_map[label] += base_score + min(2.0, 0.25 * hits)
            if label not in order_map:
                order_map[label] = len(order_map)
        if topic_lower and any(re.search(rx, topic_lower) for rx in regex_list):
            score_map[label] += 1.2
            if label not in order_map:
                order_map[label] = len(order_map)

    ranked = sorted(score_map.items(), key=lambda item: (-item[1], order_map[item[0]], item[0]))
    return [label for label, score in ranked if score >= min_score][:limit]


def _normalize_language(language: str) -> str:
    text = str(language or "").strip()
    if not text:
        return ""
    low = text.lower()
    if low == "python":
        return "Python"
    if low == "typescript":
        return "TypeScript"
    if low == "javascript":
        return "JavaScript"
    if low == "go":
        return "Go"
    if low == "rust":
        return "Rust"
    if low == "java":
        return "Java"
    return text


def _unique_keep_order(values: List[str], limit: int) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def extract_structured_tags(
    summary: str,
    reasons: List[str],
    readme_content: str,
    repo_data: Optional[Dict] = None,
    scout_data: Optional[Dict] = None,
) -> Dict[str, List[str]]:
    repo_data = repo_data or {}
    scout_data = scout_data or {}

    topics = [str(t).strip() for t in (repo_data.get("topics") or []) if str(t).strip()]
    language = _normalize_language(str(repo_data.get("language") or ""))

    sentiment_topics: List[str] = []
    community = scout_data.get("community_sentiment") or {}
    if isinstance(community, dict):
        sentiment_topics = [str(t).strip() for t in (community.get("key_topics") or []) if str(t).strip()]

    full_text = " ".join(
        [
            _safe_text(summary, 2400),
            _safe_text(" ".join(reasons or []), 2400),
            _safe_text(readme_content, 9000),
            " ".join(topics),
            " ".join(sentiment_topics),
            language,
        ]
    )
    topic_text = " ".join(topics + sentiment_topics)

    keywords = _collect_keywords_with_scores(
        summary=summary or "",
        reasons=reasons or [],
        readme_content=readme_content or "",
        topics=topics,
        sentiment_topics=sentiment_topics,
    )

    tech_stack: List[str] = []
    if language:
        tech_stack.append(language)
    tech_stack.extend(_collect_rule_labels(full_text, _TECH_STACK_RULES, min_score=1.8, limit=10, topic_text=topic_text))

    use_cases = _collect_rule_labels(full_text, _USE_CASE_RULES, min_score=1.7, limit=8, topic_text=topic_text)

    return {
        "keywords": _unique_keep_order(keywords, limit=12),
        "tech_stack": _unique_keep_order(tech_stack, limit=10),
        "use_cases": _unique_keep_order(use_cases, limit=8),
    }
