"""
搜索服务模块

整合向量检索、BM25 与重排序，提供项目索引和搜索能力。
默认使用 chunk 级召回，再聚合为 repo 级结果。
"""

import logging
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.infrastructure.cache import AnalysisCache
from app.infrastructure.chroma_store import ChromaVectorStore
from app.infrastructure.embedding import EmbeddingEngine
from app.infrastructure.hybrid_search import HybridSearchEngine
from app.infrastructure.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


class SearchService:
    """搜索服务：chunk 召回 -> chunk 重排 -> repo 聚合。"""

    def __init__(self):
        self.cache = AnalysisCache()
        self.embedding_engine = EmbeddingEngine()
        self.chroma_store = ChromaVectorStore()
        self.hybrid_engine = HybridSearchEngine(rrf_k=60)
        self.reranker = CrossEncoderReranker(model_name="BAAI/bge-reranker-base")
        self._initialized = False

    def _ensure_index(self) -> None:
        """确保检索索引已构建。"""
        if self._initialized:
            return

        all_chunks = self.cache.get_all_chunks()
        if not all_chunks:
            all_chunks = self._build_legacy_chunks()

        if all_chunks:
            self.hybrid_engine.build_index(all_chunks)
            self._initialized = True
            logger.info(f"搜索索引初始化完成，共 {len(all_chunks)} 个 chunk")

    def _build_legacy_chunks(self) -> List[Dict]:
        """兼容旧数据：从 repo 级 embedding 构造单 chunk 文档。"""
        legacy_docs = self.cache.get_all_embeddings()
        chunks: List[Dict] = []
        for doc in legacy_docs:
            text = (doc.get("search_text") or doc.get("summary") or "").strip()
            if not text:
                continue

            chunks.append({
                "chunk_id": f"{doc.get('repo_full_name', '')}#legacy",
                "repo_full_name": doc.get("repo_full_name", ""),
                "chunk_index": 0,
                "chunk_text": text,
                "section": "legacy",
                "embedding": doc.get("embedding"),
                "keywords": doc.get("keywords", []),
                "tech_stack": doc.get("tech_stack", []),
                "use_cases": doc.get("use_cases", []),
                "summary": doc.get("summary", ""),
                "reasons": doc.get("reasons", []),
                "category": doc.get("category"),
                "language": doc.get("language"),
                "stars": doc.get("stars"),
                "record_date": doc.get("record_date"),
            })

        return chunks

    async def index_project(
        self,
        repo_full_name: str,
        summary: str,
        reasons: List[str],
        language: str = "",
        category: str = "",
        keywords: List[str] = None,
        tech_stack: List[str] = None,
        use_cases: List[str] = None
    ) -> bool:
        """索引项目：保存 repo 级 embedding，并生成 chunk 索引。"""
        try:
            keywords = keywords or []
            tech_stack = tech_stack or []
            use_cases = use_cases or []

            search_text = self.cache.build_search_text(
                repo_full_name=repo_full_name,
                summary=summary,
                reasons=reasons,
                language=language,
                category=category,
            )

            # 保留 repo 级缓存，兼容已有逻辑和统计。
            embedding = await self.embedding_engine.embed_text(search_text)
            if not embedding:
                logger.error(f"项目 {repo_full_name} 向量化失败")
                return False

            self.cache.set_with_embedding(
                repo_full_name=repo_full_name,
                summary=summary,
                reasons=reasons,
                search_text=search_text,
                embedding=embedding,
                keywords=keywords,
                tech_stack=tech_stack,
                use_cases=use_cases,
            )

            chunks = self._build_project_chunks(
                repo_full_name=repo_full_name,
                summary=summary,
                reasons=reasons,
                language=language,
                category=category,
                keywords=keywords,
                tech_stack=tech_stack,
                use_cases=use_cases,
                search_text=search_text,
            )
            if not chunks:
                logger.warning(f"项目 {repo_full_name} 没有可索引 chunk")
                return False

            chunk_embeddings = await self.embedding_engine.embed_batch([c["chunk_text"] for c in chunks])
            valid_chunks = []
            for chunk, chunk_embedding in zip(chunks, chunk_embeddings):
                if chunk_embedding:
                    chunk["embedding"] = chunk_embedding
                    valid_chunks.append(chunk)

            if not valid_chunks:
                logger.error(f"项目 {repo_full_name} 的 chunk 向量化全部失败")
                return False

            self.cache.replace_chunks(repo_full_name=repo_full_name, chunks=valid_chunks)

            self.chroma_store.batch_upsert(
                ids=[c["chunk_id"] for c in valid_chunks],
                embeddings=[c["embedding"] for c in valid_chunks],
                metadatas=[
                    {
                        "chunk_id": c["chunk_id"],
                        "repo_full_name": c["repo_full_name"],
                        "chunk_index": c["chunk_index"],
                        "section": c.get("section", ""),
                        "summary": c.get("summary", ""),
                        "language": c.get("language", ""),
                        "category": c.get("category", ""),
                        "keywords": ",".join(c.get("keywords", [])),
                        "tech_stack": ",".join(c.get("tech_stack", [])),
                        "use_cases": ",".join(c.get("use_cases", [])),
                    }
                    for c in valid_chunks
                ],
            )

            self._initialized = False
            logger.info(f"项目 {repo_full_name} 索引成功，chunk 数: {len(valid_chunks)}")
            return True

        except Exception as e:
            logger.error(f"索引项目失败: {str(e)}")
            return False

    def _build_project_chunks(
        self,
        repo_full_name: str,
        summary: str,
        reasons: List[str],
        language: str,
        category: str,
        keywords: List[str],
        tech_stack: List[str],
        use_cases: List[str],
        search_text: str,
    ) -> List[Dict]:
        """把项目内容切分为多个可检索 chunk。"""
        sections: List[Tuple[str, str]] = []

        if summary:
            sections.append(("summary", summary.strip()))

        for reason in reasons or []:
            reason = (reason or "").strip()
            if reason:
                sections.append(("reason", reason))

        if keywords:
            sections.append(("keywords", "关键词: " + "、".join(keywords)))

        if tech_stack:
            sections.append(("tech_stack", "技术栈: " + "、".join(tech_stack)))

        if use_cases:
            sections.append(("use_cases", "使用场景: " + "、".join(use_cases)))

        # 加一段结构化文本，保证通用召回效果。
        if search_text:
            sections.append(("overview", search_text.strip()))

        chunks: List[Dict] = []
        idx = 0
        for section_name, section_text in sections:
            piece_texts = self._split_text_to_chunks(section_text, max_chars=380, overlap_chars=60)
            for piece in piece_texts:
                if not piece.strip():
                    continue

                chunk_text = (
                    f"项目: {repo_full_name}\n"
                    f"语言: {language or 'unknown'}\n"
                    f"分类: {category or 'unknown'}\n"
                    f"{piece.strip()}"
                )

                chunks.append({
                    "chunk_id": f"{repo_full_name}#{idx:03d}",
                    "repo_full_name": repo_full_name,
                    "chunk_index": idx,
                    "chunk_text": chunk_text,
                    "section": section_name,
                    "summary": summary or "",
                    "reasons": reasons or [],
                    "keywords": keywords or [],
                    "tech_stack": tech_stack or [],
                    "use_cases": use_cases or [],
                    "language": language,
                    "category": category,
                })
                idx += 1

        return chunks

    def _split_text_to_chunks(self, text: str, max_chars: int = 380, overlap_chars: int = 60) -> List[str]:
        """按语义边界优先的轻量切块（句子优先，超长回退按字符切分）。"""
        text = (text or "").strip()
        if not text:
            return []

        sentences = re.split(r"(?<=[。！？!?；;\n])", text)
        sentences = [s.strip() for s in sentences if s and s.strip()]
        if not sentences:
            sentences = [text]

        chunks: List[str] = []
        current = ""

        for sentence in sentences:
            if len(sentence) > max_chars:
                if current:
                    chunks.append(current)
                    current = ""

                start = 0
                while start < len(sentence):
                    end = min(len(sentence), start + max_chars)
                    chunks.append(sentence[start:end])
                    if end >= len(sentence):
                        break
                    start = max(0, end - overlap_chars)
                continue

            if not current:
                current = sentence
                continue

            if len(current) + 1 + len(sentence) <= max_chars:
                current = f"{current} {sentence}"
            else:
                chunks.append(current)
                tail = current[-overlap_chars:] if overlap_chars > 0 and len(current) > overlap_chars else ""
                current = (tail + " " + sentence).strip() if tail else sentence

        if current:
            chunks.append(current)

        return chunks

    async def batch_index_projects(self, projects: List[Dict]) -> Dict[str, bool]:
        """批量索引项目"""
        results = {}
        for project in projects:
            repo_name = project.get("repo_full_name")
            if not repo_name:
                continue

            success = await self.index_project(
                repo_full_name=repo_name,
                summary=project.get("summary", ""),
                reasons=project.get("reasons", []),
                language=project.get("language", ""),
                category=project.get("category", ""),
                keywords=project.get("keywords", []),
                tech_stack=project.get("tech_stack", []),
                use_cases=project.get("use_cases", []),
            )
            results[repo_name] = success

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"批量索引完成，成功 {success_count}/{len(results)} 个项目")
        return results

    async def search_projects(
        self,
        query: str,
        coarse_top_k: int = 20,
        final_top_k: int = 5,
        filters: Optional[Any] = None,
    ) -> List[Dict]:
        """搜索项目：chunk 召回+重排，最后聚合为 repo 结果。"""
        try:
            self._ensure_index()

            if not self._initialized:
                logger.warning("索引未初始化")
                return []

            coarse_k = max(coarse_top_k, final_top_k * 6)
            coarse_results = await self.hybrid_engine.search(query=query, top_k=coarse_k)
            if not coarse_results:
                return []

            filtered_results = self._apply_filters(coarse_results, filters)
            if not filtered_results:
                return []

            rerank_k = min(len(filtered_results), max(final_top_k * 8, 20))
            reranked_chunks = await self.reranker.rerank(
                query=query,
                results=filtered_results,
                top_k=rerank_k,
            )

            repo_results = self._aggregate_chunks_to_repos(
                chunk_results=reranked_chunks,
                top_k=final_top_k,
            )

            for result in repo_results:
                result.pop("embedding", None)
                result.pop("vector_score", None)
                result.pop("bm25_score", None)

            return repo_results

        except Exception as e:
            logger.error(f"搜索项目失败: {str(e)}")
            return []

    def _aggregate_chunks_to_repos(self, chunk_results: List[Dict], top_k: int) -> List[Dict]:
        """把 chunk 结果聚合为 repo，并做去重和多样性控制。"""
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for chunk in chunk_results:
            repo = chunk.get("repo_full_name")
            if not repo:
                continue
            grouped[repo].append(chunk)

        candidates = []
        for repo_name, chunks in grouped.items():
            chunks.sort(key=lambda x: x.get("rerank_score", x.get("rrf_score", 0.0)), reverse=True)

            deduped_chunks = []
            seen_text = set()
            for chunk in chunks:
                text_key = " ".join((chunk.get("chunk_text") or "").lower().split())
                if text_key in seen_text:
                    continue
                seen_text.add(text_key)
                deduped_chunks.append(chunk)
                if len(deduped_chunks) >= 2:
                    break

            if not deduped_chunks:
                continue

            top1 = deduped_chunks[0].get("rerank_score", deduped_chunks[0].get("rrf_score", 0.0))
            top2 = deduped_chunks[1].get("rerank_score", deduped_chunks[1].get("rrf_score", 0.0)) if len(deduped_chunks) > 1 else 0.0
            repo_score = float(top1 * 0.75 + top2 * 0.25)

            primary = deduped_chunks[0]
            reasons = primary.get("reasons", []) or []
            if not reasons and primary.get("chunk_text"):
                reasons = [primary["chunk_text"][:120]]

            candidates.append({
                "repo_full_name": repo_name,
                "summary": primary.get("summary", ""),
                "reasons": reasons[:3],
                "rerank_score": repo_score,
                "similarity": repo_score,
                "category": primary.get("category"),
                "language": primary.get("language"),
                "stars": primary.get("stars"),
                "evidence_chunk": primary.get("chunk_text", ""),
                "evidence_section": primary.get("section"),
            })

        if not candidates:
            return []

        return self._select_with_diversity(candidates, top_k)

    def _select_with_diversity(self, candidates: List[Dict], top_k: int) -> List[Dict]:
        """基于 repo 分数做贪心选择，抑制同类别/同语言过度重复。"""
        remaining = candidates[:]
        selected: List[Dict] = []
        category_count: Dict[str, int] = defaultdict(int)
        language_count: Dict[str, int] = defaultdict(int)

        while remaining and len(selected) < top_k:
            best_idx = 0
            best_score = float("-inf")

            for i, item in enumerate(remaining):
                category = item.get("category") or ""
                language = item.get("language") or ""
                base = item.get("rerank_score", 0.0)
                penalty = 1.0 + 0.18 * category_count[category] + 0.12 * language_count[language]
                score = base / penalty

                if score > best_score:
                    best_score = score
                    best_idx = i

            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            category_count[chosen.get("category") or ""] += 1
            language_count[chosen.get("language") or ""] += 1

        return selected

    def _apply_filters(self, results: List[Dict], filters: Optional[Any]) -> List[Dict]:
        """Apply query filters to coarse retrieval results before rerank."""
        if not filters:
            return results

        language = getattr(filters, "language", None)
        category = getattr(filters, "category", None)
        min_stars = getattr(filters, "min_stars", None)
        keywords = getattr(filters, "keywords", None) or []
        days = getattr(filters, "days", None)

        filtered = []
        cutoff_date = None
        if days and days > 0:
            cutoff_date = date.today() - timedelta(days=days)

        for item in results:
            item_language = (item.get("language") or "").lower()
            item_category = item.get("category")
            item_stars = item.get("stars", 0) or 0
            summary = (item.get("summary") or "").lower()
            reason_text = " ".join(item.get("reasons", [])).lower()
            chunk_text = (item.get("chunk_text") or "").lower()
            repo_name = (item.get("repo_full_name") or "").lower()

            if language:
                lang = str(language).lower()
                if lang != item_language and lang not in item_language:
                    continue

            if category and item_category != category:
                continue

            if min_stars is not None and item_stars < min_stars:
                continue

            if keywords:
                keyword_hit = False
                for kw in keywords:
                    k = str(kw).lower().strip()
                    if not k:
                        continue
                    if k in summary or k in reason_text or k in repo_name or k in chunk_text:
                        keyword_hit = True
                        break
                if not keyword_hit:
                    continue

            if cutoff_date:
                record_date_str = item.get("record_date")
                if record_date_str:
                    try:
                        from datetime import datetime as dt

                        if isinstance(record_date_str, str):
                            record_date = dt.strptime(record_date_str, "%Y-%m-%d").date()
                        elif isinstance(record_date_str, date):
                            record_date = record_date_str
                        else:
                            record_date = None

                        if record_date and record_date < cutoff_date:
                            continue
                    except (ValueError, TypeError):
                        pass

            filtered.append(item)

        return filtered

    async def reindex_all_projects(self) -> Dict[str, int]:
        """重新索引所有项目"""
        try:
            today = date.today()
            records = self.cache.get_trending_history(
                start_date=today - timedelta(days=30),
                end_date=today,
            )

            stats = {
                "total": len(records),
                "success": 0,
                "failed": 0,
                "skipped": 0,
            }

            seen_repos = set()
            for record in records:
                repo_name = record["repo_full_name"]
                if repo_name in seen_repos:
                    stats["skipped"] += 1
                    continue

                seen_repos.add(repo_name)

                analysis = self.cache.get(repo_name)
                if not analysis:
                    stats["skipped"] += 1
                    continue

                success = await self.index_project(
                    repo_full_name=repo_name,
                    summary=analysis.get("summary", ""),
                    reasons=analysis.get("reasons", []),
                    language=record.get("language", ""),
                    category=record.get("category", ""),
                )

                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

            logger.info(f"重新索引完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"重新索引失败: {str(e)}")
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    def get_search_stats(self) -> Dict:
        """获取搜索统计信息"""
        try:
            all_chunks = self.cache.get_all_chunks()
            repo_set = {doc.get("repo_full_name") for doc in all_chunks if doc.get("repo_full_name")}

            return {
                "indexed_projects": len(repo_set),
                "indexed_chunks": len(all_chunks),
                "chroma_count": self.chroma_store.count(),
                "categories": list(set(doc.get("category") for doc in all_chunks if doc.get("category"))),
                "languages": list(set(doc.get("language") for doc in all_chunks if doc.get("language"))),
            }

        except Exception as e:
            logger.error(f"获取搜索统计失败: {str(e)}")
            return {
                "indexed_projects": 0,
                "indexed_chunks": 0,
                "chroma_count": 0,
                "categories": [],
                "languages": [],
            }
