"""
查询解析器 - 从用户问题中提取过滤条件

使用 LLM 理解用户意图，提取语言、分类、时间等过滤条件
"""

import logging
from typing import Optional, List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


class QueryFilters(BaseModel):
    """查询过滤条件"""
    
    language: Optional[str] = Field(
        default=None, 
        description="编程语言，如 Python, JavaScript, Rust, Go, TypeScript, Java 等"
    )
    
    category: Optional[str] = Field(
        default=None, 
        description="项目分类：ai_ecosystem, infra_and_tools, product_and_ui, knowledge_base"
    )
    
    days: Optional[int] = Field(
        default=None, 
        description="时间范围（天数），如 7, 14, 30"
    )
    
    min_stars: Optional[int] = Field(
        default=None, 
        description="最小 Star 数，如 100, 1000"
    )
    
    keywords: List[str] = Field(
        default_factory=list, 
        description="技术关键词列表，如 ['AI', '框架', '工具']"
    )
    
    def has_filters(self) -> bool:
        """检查是否有任何过滤条件"""
        return any([
            self.language,
            self.category,
            self.days,
            self.min_stars is not None,
            len(self.keywords) > 0
        ])
    
    def to_boost_dict(self) -> dict:
        """
        转换为加权配置（宽松过滤）
        
        返回的权重用于调整相似度分数，而不是严格过滤
        """
        boost = {}
        
        if self.language:
            boost['language'] = self.language
        
        if self.category:
            boost['category'] = self.category
        
        if self.days:
            boost['days'] = self.days
        
        if self.min_stars is not None:
            boost['min_stars'] = self.min_stars
        
        return boost


class QueryParser:
    """查询解析器"""
    
    SYSTEM_PROMPT = """你是一个查询意图分析助手。你的任务是从用户的问题中提取过滤条件。

## 可提取的过滤条件

1. **language** (编程语言)
   - 示例："Python 项目" → language="Python"
   - 常见值：Python, JavaScript, TypeScript, Rust, Go, Java, C++, Ruby, PHP, Swift
   - 注意：如果用户说"Python 相关的"、"用 Python 写的"，也提取为 Python

2. **category** (项目分类)
   - 示例："AI 项目" → category="ai_ecosystem"
   - 可选值：
     * ai_ecosystem: AI 生态与应用（LLM、模型、AI Agent、RAG 等）
     * infra_and_tools: 底层基建与开发者工具（数据库、CLI、框架、配置等）
     * product_and_ui: 全栈应用与视觉组件（Web 应用、UI 组件库、SaaS 产品等）
     * knowledge_base: 知识库与聚合资源（Awesome 列表、面试题、学习路线图等）

3. **days** (时间范围)
   - 示例："最近的"、"本周" → days=7
   - 示例："本月的"、"最近一个月" → days=30
   - 示例："今天的" → days=1
   - 默认：如果没有明确时间，不设置此字段

4. **min_stars** (最小 Star 数)
   - 示例："过千 Star" → min_stars=1000
   - 示例："100 star 以上" → min_stars=100
   - 示例："比较火的" → min_stars=500（估算）

5. **keywords** (技术关键词)
   - 示例："用于深度学习的" → keywords=["深度学习"]
   - 示例："Web 开发框架" → keywords=["Web", "框架"]
   - 提取用户描述中涉及的技术领域、功能特点等

## 注意事项

1. **不要过度推断**：如果用户没有明确提到某个条件，不要设置
2. **诚实原则**：如果不确定某个字段，留空（null）
3. **自然语言理解**：理解"最近"、"热门的"、"好用的"等模糊表达
4. **多条件组合**：用户可能同时提到多个条件，都要提取

## 返回格式

直接返回 JSON 对象，不要其他内容。没有提到的字段设为 null。
"""

    def __init__(self):
        config = get_config()
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_fast,  # 使用快速模型，节省成本
            temperature=0.0  # 低温保证输出稳定性
        )

    async def parse(self, query: str) -> QueryFilters:
        """
        从用户问题中提取过滤条件
        
        Args:
            query: 用户问题，如"帮我找最近的 Python AI 项目"
        
        Returns:
            QueryFilters: 提取的过滤条件
        """
        try:
            from langchain_core.prompts import ChatPromptTemplate
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", self.SYSTEM_PROMPT),
                ("user", "用户问题：{query}\n\n请提取过滤条件（没有提到的字段设为 null）：")
            ])
            
            chain = prompt_template | self.llm.with_structured_output(QueryFilters)
            result: QueryFilters = await chain.ainvoke({"query": query})
            
            logger.info(f"查询解析完成：{query} → {result}")
            return result
            
        except Exception as e:
            logger.warning(f"查询解析失败：{e}，返回空过滤条件")
            return QueryFilters()
    
    def parse_sync(self, query: str) -> QueryFilters:
        """同步版本的解析（用于测试）"""
        import asyncio
        return asyncio.run(self.parse(query))


# 全局解析器实例
_parser: Optional[QueryParser] = None


def get_query_parser() -> QueryParser:
    """获取查询解析器单例"""
    global _parser
    if _parser is None:
        _parser = QueryParser()
    return _parser
