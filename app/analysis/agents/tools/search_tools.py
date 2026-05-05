"""
Search tools for external/community signals.

Used by ScoutAgent to collect cross-source evidence.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency fallback
    aiohttp = None  # type: ignore

from app.knowledge.query_parser import QueryParser

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    source: str
    title: str
    url: str
    snippet: str
    score: int
    created_at: Optional[datetime] = None
    comments_count: int = 0
    sentiment: str = "neutral"


class HackerNewsSearcher:
    """Search recent HN stories through Algolia."""

    API_BASE = "https://hn.algolia.com/api/v1"

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        if aiohttp is None:
            logger.warning("aiohttp is unavailable, skip HackerNews search")
            return []
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                url = f"{self.API_BASE}/search"
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": "created_at_i>"
                    + str(int((datetime.now() - timedelta(days=7)).timestamp())),
                    "hitsPerPage": limit,
                }

                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    results: List[SearchResult] = []

                    for hit in data.get("hits", []):
                        score = int(hit.get("points", 0)) + int(hit.get("num_comments", 0)) * 2
                        raw_snippet = hit.get("story_text") or ""
                        snippet = (
                            raw_snippet[:200]
                            if raw_snippet
                            else f"[external-link] {int(hit.get('num_comments', 0))} comments"
                        )
                        results.append(
                            SearchResult(
                                source="hackernews",
                                title=hit.get("title", "") or "",
                                url=hit.get("url")
                                or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                                snippet=snippet,
                                score=score,
                                created_at=datetime.fromtimestamp(int(hit.get("created_at_i", 0) or 0)),
                                comments_count=int(hit.get("num_comments", 0) or 0),
                                sentiment="neutral",
                            )
                        )

                    return sorted(results, key=lambda x: x.score, reverse=True)
        except Exception as e:
            logger.error("HackerNews search failed: %s", e)
            return []


class GitHubDiscussionsSearcher:
    """Search GitHub discussions via search/issues API."""

    async def search(self, repo_name: str, github_token: Optional[str] = None) -> List[SearchResult]:
        if aiohttp is None:
            logger.warning("aiohttp is unavailable, skip GitHub discussions search")
            return []
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                url = "https://api.github.com/search/issues"
                params = {
                    "q": f"repo:{repo_name} is:discussion sort:created-desc",
                    "per_page": 10,
                }
                headers = {"Accept": "application/vnd.github.v3+json"}
                if github_token:
                    headers["Authorization"] = f"token {github_token}"

                async with session.get(url, params=params, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    results: List[SearchResult] = []
                    for item in data.get("items", []):
                        created_raw = item.get("created_at", "") or ""
                        created_at = None
                        if created_raw:
                            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                        results.append(
                            SearchResult(
                                source="github_discussions",
                                title=item.get("title", "") or "",
                                url=item.get("html_url", "") or "",
                                snippet=(item.get("body", "") or "")[:200],
                                score=int(item.get("comments", 0) or 0) * 3,
                                created_at=created_at,
                                comments_count=int(item.get("comments", 0) or 0),
                            )
                        )

                    return results
        except Exception as e:
            logger.error("GitHub discussions search failed: %s", e)
            return []


class SearchAggregator:
    """Aggregate multi-source external discussions."""

    SPAM_HINTS = (
        "buy now",
        "limited time",
        "subscribe",
        "click here",
        "free money",
        "giveaway",
        "casino",
        "xxx",
    )

    def __init__(self, github_token: Optional[str] = None):
        self.hackernews = HackerNewsSearcher()
        self.github_discussions = GitHubDiscussionsSearcher()
        self.github_token = github_token

    @staticmethod
    def _normalize_term(term: str) -> str:
        return re.sub(r"\s+", " ", (term or "").strip().lower())

    def _build_relevance_terms(self, repo_name: str, description: str = "") -> List[str]:
        repo_name = (repo_name or "").strip()
        repo_short = repo_name.split("/")[-1] if "/" in repo_name else repo_name
        keyword_source = f"{repo_name} {description}".strip()
        keywords = QueryParser.extract_keywords(keyword_source, limit=6)

        raw_terms = [repo_name, repo_short] + keywords
        terms: List[str] = []
        seen = set()
        for raw in raw_terms:
            normalized = self._normalize_term(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            terms.append(normalized)

            for token in re.findall(r"[a-z0-9+#][a-z0-9_+\-]{1,24}", normalized):
                token_norm = self._normalize_term(token)
                if len(token_norm) < 3 or token_norm in seen:
                    continue
                seen.add(token_norm)
                terms.append(token_norm)

        return terms[:12]

    def _compute_relevance_score(self, result: SearchResult, terms: List[str]) -> float:
        if not terms:
            return 0.0

        title = self._normalize_term(result.title)
        snippet = self._normalize_term(result.snippet)
        weighted_hits = 0.0
        term_hits = 0
        max_hits = float(len(terms))

        for term in terms:
            if term and term in title:
                weighted_hits += 1.0
                term_hits += 1
            elif term and term in snippet:
                weighted_hits += 0.6
                term_hits += 1

        min_term_hits = 2 if len(terms) >= 4 else 1
        if term_hits < min_term_hits:
            return 0.0
        return min(1.0, weighted_hits / max_hits)

    def _passes_quality_gate(self, result: SearchResult) -> bool:
        title = (result.title or "").strip()
        snippet = (result.snippet or "").strip()
        url = (result.url or "").strip()

        if len(title) < 5:
            return False
        if not url:
            return False
        if len(title) + len(snippet) < 20:
            return False

        normalized_title = self._normalize_term(title)
        normalized_body = self._normalize_term(f"{title} {snippet}")
        if len(set(normalized_title)) <= 2:
            return False

        if not re.search(r"[a-z0-9\u4e00-\u9fff]", normalized_body):
            return False
        if any(hint in normalized_body for hint in self.SPAM_HINTS):
            return False
        return True

    @staticmethod
    def _normalize_popularity_by_source(results: List[SearchResult]) -> Dict[int, float]:
        by_source: Dict[str, List[SearchResult]] = {}
        for item in results:
            by_source.setdefault(item.source, []).append(item)

        popularity: Dict[int, float] = {}
        for source_results in by_source.values():
            scores = [float(max(0, r.score)) for r in source_results]
            min_score = min(scores)
            max_score = max(scores)

            if max_score == min_score:
                value = 1.0 if max_score > 0 else 0.0
                for r in source_results:
                    popularity[id(r)] = value
                continue

            span = max_score - min_score
            for r in source_results:
                popularity[id(r)] = (float(max(0, r.score)) - min_score) / span

        return popularity

    def _rank_results(
        self,
        results: List[SearchResult],
        repo_name: str,
        description: str,
    ) -> List[Tuple[SearchResult, float, float, float]]:
        if not results:
            return []

        quality_filtered = [item for item in results if self._passes_quality_gate(item)]
        candidate_results = quality_filtered if quality_filtered else results
        terms = self._build_relevance_terms(repo_name, description)
        popularity_map = self._normalize_popularity_by_source(candidate_results)

        ranked: List[Tuple[SearchResult, float, float, float]] = []
        for item in candidate_results:
            relevance = self._compute_relevance_score(item, terms)
            popularity = popularity_map.get(id(item), 0.0)
            final_score = relevance * 0.6 + popularity * 0.4
            if relevance <= 0.0:
                final_score = min(final_score, popularity * 0.1)
            ranked.append((item, relevance, popularity, final_score))

        ranked.sort(
            key=lambda x: (
                x[3],  # final score
                x[1],  # relevance
                x[2],  # normalized popularity
                x[0].score,  # raw source score
            ),
            reverse=True,
        )
        return ranked

    @staticmethod
    def _dedupe_results(results: List[SearchResult]) -> List[SearchResult]:
        kept: Dict[str, SearchResult] = {}
        for item in results:
            key = (item.url or f"{item.source}:{item.title}").strip().lower()
            if not key:
                key = f"{item.source}:{item.title}".strip().lower()
            existed = kept.get(key)
            if existed is None or item.score > existed.score:
                kept[key] = item
        return sorted(kept.values(), key=lambda x: x.score, reverse=True)

    def _build_hn_queries(self, repo_name: str, description: str = "") -> List[str]:
        repo_name = (repo_name or "").strip()
        repo_short = repo_name.split("/")[-1] if "/" in repo_name else repo_name
        keyword_source = f"{repo_name} {description}".strip()
        keywords = QueryParser.extract_keywords(keyword_source, limit=4)

        candidates = [
            f'"{repo_name}"' if repo_name else "",
            f'"{repo_short}"' if repo_short and repo_short != repo_name else "",
            " ".join(keywords) if keywords else "",
            f'{repo_short} {" ".join(keywords[:2])}'.strip() if repo_short and keywords else "",
        ]

        deduped: List[str] = []
        seen = set()
        for q in candidates:
            q = q.strip()
            if not q or q in seen:
                continue
            seen.add(q)
            deduped.append(q)
        return deduped[:4]

    async def search_project(self, repo_name: str, description: str = "") -> Dict:
        hn_queries = self._build_hn_queries(repo_name, description)

        tasks = [self.hackernews.search(q, limit=8 if idx == 0 else 6) for idx, q in enumerate(hn_queries)]
        tasks.append(self.github_discussions.search(repo_name, self.github_token))
        outputs = await asyncio.gather(*tasks)

        github_results = outputs[-1] if outputs else []
        hn_merged_raw: List[SearchResult] = []
        for bucket in outputs[:-1]:
            hn_merged_raw.extend(bucket)

        hn_results = self._dedupe_results(hn_merged_raw)
        all_results = self._dedupe_results(hn_results + github_results)
        ranked_results = self._rank_results(all_results, repo_name=repo_name, description=description)
        hot_discussions = ranked_results[:5]

        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for r in all_results:
            sentiment_counts[r.sentiment] = sentiment_counts.get(r.sentiment, 0) + 1

        raw_text_parts = []
        for r, relevance, popularity, final_score in hot_discussions:
            raw_text_parts.append(
                f"[{r.source}] {r.title}\n{r.snippet}\n"
                f"(final={final_score:.3f}, relevance={relevance:.3f}, popularity={popularity:.3f})\n"
            )

        return {
            "queries": {
                "hn": hn_queries,
                "github_discussions": f"repo:{repo_name} is:discussion sort:created-desc",
            },
            "total_mentions": len(all_results),
            "sources": {
                "hackernews": len(hn_results),
                "github_discussions": len(github_results),
            },
            "hot_discussions": [
                {
                    "source": r.source,
                    "title": r.title,
                    "url": r.url,
                    "score": round(final_score, 4),
                    "relevance_score": round(relevance, 4),
                    "popularity_score": round(popularity, 4),
                    "raw_score": r.score,
                    "sentiment": r.sentiment,
                    "comments": r.comments_count,
                }
                for r, relevance, popularity, final_score in hot_discussions
            ],
            "sentiment_summary": sentiment_counts,
            "raw_text": "\n".join(raw_text_parts),
            "has_external_discussion": len(all_results) > 0,
        }
