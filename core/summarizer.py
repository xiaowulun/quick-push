import asyncio
from typing import Optional, List, Dict
from utils.logging_config import get_logger
from core.config import get_config
from core.readme_cleaner import clean_readme_for_multimodal
from utils.cache import AnalysisCache
from agents import AgentOrchestrator

logger = get_logger(__name__)


class Summarizer:
    def __init__(self, enable_cache: bool = True):
        config = get_config()
        self.max_retries = config.behavior.max_retries
        self.multimodal_config = config.multimodal
        self.cache = AnalysisCache() if enable_cache else None
        
        # Multi-Agent 编排器
        self.agent_orchestrator = AgentOrchestrator()

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

        # 检查缓存
        if self.cache and self.cache.exists(repo_name):
            cached = self.cache.get(repo_name)
            logger.info(f"使用缓存结果: {repo_name}")
            return {
                "summary": cached["summary"],
                "reasons": cached["reasons"]
            }

        # 使用异步版本
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

        if not readme_content:
            return {
                "summary": "该项目没有README文件",
                "reasons": ["无法分析，缺少README文件"]
            }

        # 检查缓存
        if self.cache and self.cache.exists(repo_name):
            cached = self.cache.get(repo_name)
            logger.info(f"使用缓存结果: {repo_name}")
            return {
                "summary": cached["summary"],
                "reasons": cached["reasons"]
            }

        cleaned_content = clean_readme_for_multimodal(readme_content)

        # Multi-Agent 分析
        try:
            logger.info(f"🤖 启动 Multi-Agent 分析: {repo_name}")
            agent_result = await self.agent_orchestrator.analyze_project(
                repo_name=repo_name,
                repo_data=repo_data,
                readme_content=cleaned_content,
                description=description,
                category=""  # 不再使用分类
            )

            if agent_result.success:
                result_data = agent_result.data
                result = {
                    "summary": result_data.get("summary", ""),
                    "reasons": result_data.get("reasons", []),
                    "multi_agent": True,
                }
                logger.info(f"✅ Multi-Agent 分析完成: {repo_name}")

                # 保存到缓存
                if self.cache:
                    self.cache.set(repo_name, result["summary"], result["reasons"])
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
