import re
from dataclasses import dataclass
from typing import List


@dataclass
class QueryVariant:
    text: str
    weight: float
    reason: str


class QueryRewriter:
    """Rule-based query rewriter for bilingual terms / acronyms / synonyms."""

    _RULES = [
        {
            "triggers": ["rag", "检索增强", "检索增强生成"],
            "expansions": ["retrieval augmented generation", "向量检索"],
        },
        {
            "triggers": ["向量数据库", "vector db", "vectordb", "vector database"],
            "expansions": ["chroma", "faiss", "milvus", "pgvector"],
        },
        {
            "triggers": ["代理", "agent", "智能体"],
            "expansions": ["autonomous agent", "multi-agent"],
        },
        {
            "triggers": ["工作流", "workflow", "自动化"],
            "expansions": ["orchestration", "pipeline", "n8n", "zapier"],
        },
        {
            "triggers": ["前端", "frontend", "ui", "界面"],
            "expansions": ["react", "vue", "next.js"],
        },
        {
            "triggers": ["后端", "backend", "服务端"],
            "expansions": ["api", "fastapi", "spring", "go"],
        },
        {
            "triggers": ["llm", "大模型", "语言模型"],
            "expansions": ["large language model", "inference", "prompt"],
        },
        {
            "triggers": ["爬虫", "crawler", "scraper"],
            "expansions": ["web scraping", "playwright", "selenium"],
        },
    ]

    def rewrite(self, query: str, max_variants: int = 3) -> List[QueryVariant]:
        base = self._normalize_spaces(query)
        if not base:
            return [QueryVariant(text=query, weight=1.0, reason="original")]

        variants: List[QueryVariant] = [QueryVariant(text=base, weight=1.0, reason="original")]
        lowered = base.lower()
        used = {lowered}

        expansion_terms: List[str] = []
        for rule in self._RULES:
            if any(trigger in lowered for trigger in rule["triggers"]):
                for term in rule["expansions"]:
                    term_norm = term.lower().strip()
                    if term_norm and term_norm not in lowered:
                        expansion_terms.append(term)

        if expansion_terms:
            # Variant A: append compact high-signal terms.
            compact_terms = self._dedupe_keep_order(expansion_terms)[:4]
            v1 = self._normalize_spaces(f"{base} {' '.join(compact_terms)}")
            if v1.lower() not in used:
                variants.append(QueryVariant(text=v1, weight=0.75, reason="term_expansion"))
                used.add(v1.lower())

            # Variant B: emphasize English technical aliases.
            english_terms = [t for t in compact_terms if re.search(r"[a-zA-Z]", t)]
            if english_terms:
                v2 = self._normalize_spaces(f"{base} {' '.join(english_terms)}")
                if v2.lower() not in used:
                    variants.append(QueryVariant(text=v2, weight=0.65, reason="english_alias"))
                    used.add(v2.lower())

        return variants[: max(1, max_variants)]

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip())

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            key = item.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
