"""
搜索服务模块

整合向量化和数据库操作，提供完整的搜索功能
"""

import logging
from typing import List, Dict, Optional
from datetime import date, timedelta

from app.infrastructure.cache import AnalysisCache
from app.infrastructure.embedding import EmbeddingEngine, VectorSearchEngine

logger = logging.getLogger(__name__)


class SearchService:
    """搜索服务"""

    def __init__(self):
        self.cache = AnalysisCache()
        self.embedding_engine = EmbeddingEngine()
        self.vector_search_engine = VectorSearchEngine()

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
        """索引项目（生成向量并存储）"""
        try:
            search_text = self.cache.build_search_text(
                repo_full_name=repo_full_name,
                summary=summary,
                reasons=reasons,
                language=language,
                category=category
            )

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
                keywords=keywords or [],
                tech_stack=tech_stack or [],
                use_cases=use_cases or []
            )

            logger.info(f"项目 {repo_full_name} 索引成功")
            return True

        except Exception as e:
            logger.error(f"索引项目失败: {str(e)}")
            return False

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
                use_cases=project.get("use_cases", [])
            )
            results[repo_name] = success

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"批量索引完成，成功 {success_count}/{len(results)} 个项目")
        return results

    async def search_projects(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.5,
        use_hybrid: bool = True
    ) -> List[Dict]:
        """搜索项目"""
        try:
            all_embeddings = self.cache.get_all_embeddings()

            if not all_embeddings:
                logger.warning("数据库中没有已索引的项目")
                return []

            if use_hybrid:
                results = await self.vector_search_engine.hybrid_search(
                    query=query,
                    documents=all_embeddings,
                    top_k=top_k
                )
            else:
                results = await self.vector_search_engine.search(
                    query=query,
                    documents=all_embeddings,
                    top_k=top_k,
                    threshold=threshold
                )

            for result in results:
                if "embedding" in result:
                    del result["embedding"]

            return results

        except Exception as e:
            logger.error(f"搜索项目失败: {str(e)}")
            return []

    async def reindex_all_projects(self) -> Dict[str, int]:
        """重新索引所有项目"""
        try:
            today = date.today()
            records = self.cache.get_trending_history(
                start_date=today - timedelta(days=30),
                end_date=today
            )

            stats = {
                "total": len(records),
                "success": 0,
                "failed": 0,
                "skipped": 0
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
                    category=record.get("category", "")
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
            all_embeddings = self.cache.get_all_embeddings()

            return {
                "indexed_projects": len(all_embeddings),
                "categories": list(set(doc.get("category") for doc in all_embeddings if doc.get("category"))),
                "languages": list(set(doc.get("language") for doc in all_embeddings if doc.get("language")))
            }

        except Exception as e:
            logger.error(f"获取搜索统计失败: {str(e)}")
            return {
                "indexed_projects": 0,
                "categories": [],
                "languages": []
            }
