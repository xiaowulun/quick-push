import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.infrastructure.logging import get_logger
from app.infrastructure.config import get_config
from app.analysis.readme import clean_readme_for_multimodal
from app.infrastructure.cache import AnalysisCache
from app.analysis.agents import AgentOrchestrator

logger = get_logger(__name__)


class Summarizer:
    def __init__(self, enable_cache: bool = False):
        config = get_config()
        self.max_retries = config.behavior.max_retries
        self.cache_ttl_hours = max(0, int(getattr(config.behavior, "cache_ttl_hours", 168)))
        self.cache = AnalysisCache() if enable_cache else None
        self.agent_orchestrator = AgentOrchestrator()

    @staticmethod
    def _calc_readme_hash(readme_content: str) -> str:
        return hashlib.sha256((readme_content or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_time(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def _get_cached_if_fresh(
        self,
        repo_name: str,
        readme_content: str,
        source_updated_at: Optional[str],
    ) -> Optional[Dict]:
        if not self.cache:
            return None

        cached = self.cache.get(repo_name)
        if not cached:
            return None

        current_hash = self._calc_readme_hash(readme_content)
        cached_hash = (cached.get("readme_hash") or "").strip()

        if cached_hash:
            if cached_hash != current_hash:
                return None
        else:
            cached_readme = cached.get("readme_content") or ""
            if cached_readme and cached_readme != readme_content:
                return None

        if self.cache_ttl_hours > 0:
            analyzed_at = self._parse_time(cached.get("analyzed_at"))
            if analyzed_at is not None:
                if analyzed_at.tzinfo is not None:
                    analyzed_at = analyzed_at.astimezone().replace(tzinfo=None)
                if datetime.now() - analyzed_at > timedelta(hours=self.cache_ttl_hours):
                    return None

        current_updated = self._parse_time(source_updated_at)
        cached_updated = self._parse_time(cached.get("source_updated_at"))
        if current_updated and cached_updated:
            if current_updated.tzinfo is not None:
                current_updated = current_updated.astimezone().replace(tzinfo=None)
            if cached_updated.tzinfo is not None:
                cached_updated = cached_updated.astimezone().replace(tzinfo=None)
            if current_updated > cached_updated:
                return None

        return cached

    def summarize(
        self,
        repo_name: str,
        description: Optional[str],
        readme_content: Optional[str],
        stars: int
    ) -> dict:
        """同步方法 - 已弃用，请使用异步版本"""
        if not readme_content:
            return {
                "summary": "该项目没有README文件",
                "reasons": ["无法分析，缺少README文件"]
            }

        cached = self._get_cached_if_fresh(
            repo_name=repo_name,
            readme_content=readme_content,
            source_updated_at=None,
        )
        if cached:
            logger.info(f"使用缓存结果: {repo_name}")
            return {
                "summary": cached["summary"],
                "reasons": cached["reasons"]
            }

        return asyncio.run(self._summarize_async({
            "repo_name": repo_name,
            "description": description,
            "readme_content": readme_content,
            "stars": stars,
            "repo_data": {}
        }))

    async def _summarize_async(self, repo: Dict) -> dict:
        """异步分析项目"""
        repo_name = repo["repo_name"]
        description = repo.get("description")
        readme_content = repo.get("readme_content")
        repo_data = repo.get("repo_data", {})
        source_updated_at = repo_data.get("pushed_at")

        if not readme_content:
            return {
                "summary": "该项目没有README文件",
                "reasons": ["无法分析，缺少README文件"]
            }

        cached = self._get_cached_if_fresh(
            repo_name=repo_name,
            readme_content=readme_content,
            source_updated_at=source_updated_at,
        )
        if cached:
            logger.info(f"使用缓存结果: {repo_name}")
            return {
                "summary": cached["summary"],
                "reasons": cached["reasons"]
            }

        cleaned_content = clean_readme_for_multimodal(readme_content)

        try:
            logger.info(f"🤖 启动 Multi-Agent 分析: {repo_name}")
            agent_result = await self.agent_orchestrator.analyze_project(
                repo_name=repo_name,
                repo_data=repo_data,
                readme_content=cleaned_content,
                raw_readme_content=readme_content,
                description=description,
                category=""
            )

            if agent_result.success:
                result_data = agent_result.data
                result = {
                    "summary": result_data.get("summary", ""),
                    "reasons": result_data.get("reasons", []),
                    "multi_agent": True,
                }
                logger.info(f"✅ Multi-Agent 分析完成: {repo_name}")

                if self.cache:
                    self.cache.set(
                        repo_name,
                        result["summary"],
                        result["reasons"],
                        readme_content=readme_content,
                        readme_hash=self._calc_readme_hash(readme_content),
                        source_updated_at=source_updated_at,
                    )
                    logger.info(f"已缓存结果: {repo_name}")

                return result
            else:
                logger.error(f"Multi-Agent 分析失败: {agent_result.error}")
                return {
                    "summary": f"分析失败: {agent_result.error}",
                    "reasons": ["Multi-Agent 分析失败"]
                }

        except Exception as e:
            logger.error(f"Multi-Agent 分析异常: {e}")
            return {
                "summary": f"分析失败: {str(e)}",
                "reasons": ["Multi-Agent 分析异常"]
            }

    async def batch_summarize(
        self,
        repos: List[Dict],
        max_concurrency: int = 3
    ) -> List[dict]:
        """批量分析多个项目"""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def analyze_with_semaphore(repo: Dict, idx: int) -> tuple[int, dict]:
            async with semaphore:
                result = await self._summarize_async(repo)
                return idx, result

        tasks = [analyze_with_semaphore(repo, i) for i, repo in enumerate(repos)]
        results_with_idx = await asyncio.gather(*tasks)

        results = [None] * len(repos)
        for idx, result in results_with_idx:
            results[idx] = result

        return results
