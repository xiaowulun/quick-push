"""
Scout Agent - 趋势情报侦察员

基于外部搜索数据 + LLM 推理，提供主观的趋势分析。
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.analysis.agents.base import BaseAgent, AgentResult
from app.analysis.agents.tools.search_tools import SearchAggregator
from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


class CommunitySentiment(BaseModel):
    """社区热度评估"""
    heat_level: str = Field(description="热度等级：high/medium/low/unknown")
    atmosphere: str = Field(description="氛围：positive/neutral/mixed/unknown")
    key_topics: List[str] = Field(description="讨论最多的话题，2-3个")


class ScoutAnalysis(BaseModel):
    """Scout 分析结果"""
    popularity_analysis: List[str] = Field(description="3-5条爆火原因分析，每条简洁有力")
    trend_alignment: str = Field(description="契合的技术趋势，1-2句话")
    community_sentiment: CommunitySentiment
    competitive_advantage: str = Field(description="竞争优势，1-2句话")
    potential_concerns: List[str] = Field(description="潜在风险，1-2条，如无则留空")


class ScoutAgent(BaseAgent):
    """
    趋势情报侦察员 - 智能分析版本
    """

    def __init__(self):
        super().__init__("ScoutAgent", "趋势情报侦察员 - 基于外部搜索数据 + LLM 推理，提供主观的趋势分析")
        config = get_config()
        self.searcher = SearchAggregator(github_token=config.github.token)
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_standard,
            temperature=0.7
        )

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        执行智能趋势分析

        Args:
            context: {
                "repo_name": "owner/repo",
                "repo_data": {...},
                "description": "...",
                "readme_content": "..."
            }
        """
        self.log_start(context)

        try:
            repo_name = context.get("repo_name", "")
            repo_data = context.get("repo_data", {})
            description = context.get("description", "")
            readme = context.get("readme_content", "")

            # Step 1: 搜索外部讨论
            logger.info(f"[Scout] 搜索 {repo_name} 的外部讨论...")
            search_results = await self.searcher.search_project(repo_name, description)

            # Step 2: 使用 LLM 进行智能分析（Pydantic 结构化输出）
            analysis = await self._analyze_with_llm(
                repo_name=repo_name,
                description=description,
                readme=readme,
                repo_data=repo_data,
                search_results=search_results
            )

            # 添加元数据
            result = {
                **analysis,
                "search_metadata": {
                    "has_external_data": search_results.get("has_external_discussion", False),
                    "total_mentions": search_results.get("total_mentions", 0),
                    "analyzed_at": datetime.now().isoformat()
                }
            }

            self.log_end(AgentResult(success=True, data=result))
            return self.create_success_result(result)

        except Exception as e:
            logger.error(f"[Scout] 分析失败: {e}")
            return self.create_error_result(str(e))

    async def _analyze_with_llm(
        self,
        repo_name: str,
        description: str,
        readme: str,
        repo_data: Dict,
        search_results: Dict
    ) -> Dict:
        """
        使用 LLM + Pydantic 结构化输出进行分析
        """
        prompt_template = """你是一位敏锐的技术趋势分析师。

## 项目信息
- 名称: {repo_name}
- 描述: {description}
- ⭐ Stars: {stars}
- 语言: {language}
- Topics: {topics}

## README 摘要
```
{readme_summary}
```

## 外部讨论（最近7天）
{external_discussions}

## 讨论统计
- 总提及: {total_mentions}
- HN: {hn_count} | Reddit: {reddit_count} | GitHub: {github_count}
- 情感: 正面{positive} 中性{neutral} 负面{negative}

---

## 你的任务
分析这个项目为什么登上 Trending，提供：

1. **爆火原因** (3-5条): 为什么受关注？解决了什么痛点？踩中了什么趋势？
   - 要结合 README 功能亮点
   - 要有主观判断，说出"为什么"
   - **外部讨论可能为空，这是正常的！基于 GitHub Stars、Topics 和 README 分析即可**

2. **技术趋势关联**: 契合哪些当前趋势？

3. **社区热度**: 基于 Stars 和讨论，评估热度等级和氛围

4. **竞争优势**: 相比同类项目的独特之处

5. **潜在风险**: 有无质疑或担忧？

**⚠️ 极度重要**:
- 该项目已有 {stars} Stars，是热门项目
- 外部讨论为空不代表没数据，GitHub Stars 和 README 就是数据
- **必须给出具体分析，禁止返回"数据缺失"类表述**
- 基于已有信息做出合理推断
"""

        # 截断 README
        readme_summary = readme[:1500] if readme else "README 内容较少"

        # 格式化外部讨论
        discussions_text = search_results.get("raw_text", "暂无外部讨论数据")
        sentiment = search_results.get("sentiment_summary", {})

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm.with_structured_output(ScoutAnalysis)

        result = await chain.ainvoke({
            "repo_name": repo_name,
            "description": description or "暂无描述",
            "stars": repo_data.get("stars", 0),
            "language": repo_data.get("language", "Unknown"),
            "topics": ", ".join(repo_data.get("topics", [])),
            "readme_summary": readme_summary,
            "external_discussions": discussions_text,
            "total_mentions": search_results.get("total_mentions", 0),
            "hn_count": search_results.get("sources", {}).get("hackernews", 0),
            "reddit_count": search_results.get("sources", {}).get("reddit", 0),
            "github_count": search_results.get("sources", {}).get("github_discussions", 0),
            "positive": sentiment.get("positive", 0),
            "neutral": sentiment.get("neutral", 0),
            "negative": sentiment.get("negative", 0),
        })

        return result.model_dump()
