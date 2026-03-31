import asyncio
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from utils.logging_config import get_logger
from core.config import get_config
from core.readme_cleaner import clean_readme_for_multimodal
from utils.multimodal_builder import build_multimodal_payload, payload_to_string
from utils.cache import AnalysisCache

logger = get_logger(__name__)


class ProjectAnalysis(BaseModel):
    summary: str = Field(description="50-100字的项目简介，说明项目是做什么的、解决什么问题")
    reasons: List[str] = Field(description="3-5个爆火原因，每个原因20-40字")


PROMPT_TEMPLATE = """你是一个专业的技术分析师，擅长从技术趋势、社区活跃度、项目质量等角度分析开源项目。

请分析以下GitHub热门项目：

项目名称：{repo_name}
项目描述：{description}
当前Star数：{stars}

README内容：
{readme_content}

## 输出要求

请严格按以下JSON格式返回，不要添加任何其他内容：
{{
    "summary": "50-100字的项目简介，说明项目是做什么的、解决什么问题",
    "reasons": ["20-40字的原因1", "20-40字的原因2", "20-40字的原因3"]
}}

## 示例

输入：
- 项目名称：microsoft/TypeScript
- 项目描述：A language for application-scale JavaScript development
- 当前Star数：100000

输出：
{{
    "summary": "TypeScript是微软推出的编程语言，为JavaScript添加了静态类型检查和面向对象特性，提升大型项目的可维护性和开发效率。",
    "reasons": [
        "微软背书，品质有保证，社区信任度高",
        "完美兼容JavaScript，现有项目迁移成本低",
        "类型系统大幅提升代码质量和IDE支持",
        "Vue、React等主流框架纷纷采用，增加曝光度"
    ]
}}"""


class Summarizer:
    def __init__(self, enable_cache: bool = True):
        config = get_config()
        self.max_retries = config.behavior.max_retries
        self.multimodal_config = config.multimodal
        self.cache = AnalysisCache() if enable_cache else None
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model,
            temperature=0.7
        )
        self.prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        self.chain = self.prompt | self.llm.with_structured_output(ProjectAnalysis)

    def summarize(
        self,
        repo_name: str,
        description: Optional[str],
        readme_content: Optional[str],
        stars: int
    ) -> dict:
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

        # 构建多模态 payload（智能分块）
        payload = build_multimodal_payload(
            cleaned_content,
            repo_name,
            max_chars=self.multimodal_config.max_chars,
            max_images=self.multimodal_config.max_images
        )

        # 根据配置决定是否启用多模态
        if self.multimodal_config.enable_multimodal:
            result = self._invoke_multimodal(repo_name, description, stars, payload)
        else:
            # 转换为纯文本格式
            readme_preview = payload_to_string(payload)
            result: ProjectAnalysis = self.chain.invoke({
                "repo_name": repo_name,
                "description": description or "无",
                "stars": stars,
                "readme_content": readme_preview
            })

        # 保存到缓存
        if self.cache:
            self.cache.set(repo_name, result.summary, result.reasons)
            logger.info(f"已缓存结果: {repo_name}")

        return result.model_dump()

    async def _summarize_async(self, repo: Dict) -> dict:
        repo_name = repo["repo_name"]
        description = repo.get("description")
        readme_content = repo.get("readme_content")
        stars = repo.get("stars", 0)

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

        # 构建多模态 payload（智能分块）
        payload = build_multimodal_payload(
            cleaned_content,
            repo_name,
            max_chars=self.multimodal_config.max_chars,
            max_images=self.multimodal_config.max_images
        )

        # 根据配置决定是否启用多模态
        if self.multimodal_config.enable_multimodal:
            result = await self._summarize_multimodal_with_retry(repo_name, description, stars, payload)
        else:
            # 转换为纯文本格式
            readme_preview = payload_to_string(payload)
            result = await self._summarize_with_retry(repo_name, description, stars, readme_preview)

        # 保存到缓存
        if self.cache and "summary" in result:
            self.cache.set(repo_name, result["summary"], result["reasons"])
            logger.info(f"已缓存结果: {repo_name}")

        return result

    async def _summarize_with_retry(
        self,
        repo_name: str,
        description: Optional[str],
        stars: int,
        readme_preview: str,
        retry_count: int = 0
    ) -> dict:
        try:
            loop = asyncio.get_event_loop()
            result: ProjectAnalysis = await loop.run_in_executor(
                None,
                lambda: self.chain.invoke({
                    "repo_name": repo_name,
                    "description": description or "无",
                    "stars": stars,
                    "readme_content": readme_preview
                })
            )
            return result.model_dump()
        except Exception as e:
            if retry_count < self.max_retries:
                wait_time = (2 ** retry_count) * 5
                logger.warning(f"分析 {repo_name} 失败 ({e})，{wait_time}秒后重试 ({retry_count + 1}/{self.max_retries})...")
                await asyncio.sleep(wait_time)
                return await self._summarize_with_retry(
                    repo_name, description, stars, readme_preview, retry_count + 1
                )
            else:
                logger.error(f"分析 {repo_name} 失败，已达最大重试次数: {e}")
                return {
                    "summary": f"分析失败: {str(e)}",
                    "reasons": ["LLM 调用异常，已达最大重试次数"]
                }

    def _invoke_multimodal(
        self,
        repo_name: str,
        description: Optional[str],
        stars: int,
        payload: List[Dict]
    ) -> ProjectAnalysis:
        """使用多模态格式调用 LLM"""
        from langchain_core.messages import HumanMessage

        # 构建多模态消息
        content_parts = [
            {"type": "text", "text": f"请分析以下GitHub热门项目：\n\n项目名称：{repo_name}\n项目描述：{description or '无'}\n当前Star数：{stars}\n\nREADME内容：\n"}
        ]
        content_parts.extend(payload)
        content_parts.append({"type": "text", "text": "\n\n请分析这个项目，返回JSON格式：{\"summary\": \"...\", \"reasons\": [\"...\", \"...\"]}"})

        message = HumanMessage(content=content_parts)
        result: ProjectAnalysis = self.llm.with_structured_output(ProjectAnalysis).invoke([message])
        return result

    async def _summarize_multimodal_with_retry(
        self,
        repo_name: str,
        description: Optional[str],
        stars: int,
        payload: List[Dict],
        retry_count: int = 0
    ) -> dict:
        """多模态调用的重试逻辑"""
        try:
            loop = asyncio.get_event_loop()
            result: ProjectAnalysis = await loop.run_in_executor(
                None,
                lambda: self._invoke_multimodal(repo_name, description, stars, payload)
            )
            return result.model_dump()
        except Exception as e:
            if retry_count < self.max_retries:
                wait_time = (2 ** retry_count) * 5
                logger.warning(f"多模态分析 {repo_name} 失败 ({e})，{wait_time}秒后重试 ({retry_count + 1}/{self.max_retries})...")
                await asyncio.sleep(wait_time)
                return await self._summarize_multimodal_with_retry(
                    repo_name, description, stars, payload, retry_count + 1
                )
            else:
                logger.error(f"多模态分析 {repo_name} 失败，已达最大重试次数: {e}")
                # 降级为纯文本模式
                readme_preview = payload_to_string(payload)
                return await self._summarize_with_retry(repo_name, description, stars, readme_preview)

    async def batch_summarize(
        self,
        repos: List[Dict],
        max_concurrency: int = 3
    ) -> List[dict]:
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