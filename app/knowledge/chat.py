"""
RAG 对话服务模块

实现基于 GitHub Trending 数据库的智能问答功能
"""

import logging
from datetime import datetime
from typing import List, Dict, AsyncGenerator, Optional
from dataclasses import dataclass
from openai import OpenAI
from app.infrastructure.config import get_config
from app.infrastructure.cache import AnalysisCache
from app.infrastructure.embedding import EmbeddingEngine
from app.knowledge.query_parser import QueryFilters, get_query_parser

logger = logging.getLogger(__name__)


@dataclass
class RetrievedProject:
    """检索到的项目"""
    repo_full_name: str
    summary: str
    reasons: List[str]
    similarity: float
    category: Optional[str] = None
    language: Optional[str] = None
    stars: Optional[int] = None
    url: str = ""


class RAGChatService:
    """RAG 对话服务"""

    SYSTEM_PROMPT = """你是一个专业的 GitHub 开源项目推荐助手。你的任务是基于 GitHub Trending 榜单数据，帮助用户找到最适合他们需求的开源项目。

## 你的能力
- 理解用户的技术需求和使用场景
- 从数据库中检索相关的热门开源项目
- 提供专业的项目推荐和分析

## 回答要求
1. 使用自然、友好的对话语气
2. 推荐项目时，说明为什么这些项目适合用户的需求
3. 对每个推荐的项目，简要介绍其核心功能和优势
4. 如果数据库中没有完全匹配的项目，诚实告知并推荐最接近的选项
5. 回答要简洁明了，重点突出

## 回答格式
- 开头简要回应问题
- 列出推荐项目（使用数字编号）
- 每个项目包含：项目名称、核心功能、为什么推荐
- 结尾可以提供使用建议或进一步的问题"""

    CHAT_SYSTEM_PROMPT = """你是一个友好的 GitHub 开源项目推荐助手。当用户与你打招呼或进行闲聊时，请友好地回应，并引导他们询问关于开源项目、技术工具、编程框架等方面的问题。

## 你的特点
- 热情友好，乐于助人
- 专注于帮助用户发现优质的开源项目
- 能够理解用户的技术需求并给出专业建议

## 回应方式
- 如果用户打招呼，热情回应并介绍你的功能
- 如果用户闲聊，友好回应并引导到技术话题
- 保持简洁，不要过于冗长"""

    NO_MATCH_SYSTEM_PROMPT = """你是一个专业的 GitHub 开源项目推荐助手。

当前情况：用户询问了一个技术问题，但数据库中没有找到足够相关的项目数据。

## 你的任务
1. 诚实告知用户数据库中没有相关的 GitHub Trending 项目
2. 基于你的专业知识，给用户一些通用的建议和方向
3. 引导用户尝试其他相关的搜索词

## 回答要求
- 诚实透明，不要编造不存在的项目
- 提供有价值的通用建议
- 保持友好和专业
- 建议用户可以尝试其他搜索词"""

    RAG_PROMPT_TEMPLATE = """基于以下检索到的 GitHub Trending 项目信息，回答用户的问题。

## 用户问题
{query}

## 检索到的相关项目（按相关度排序）

{projects_context}

---

请基于以上项目信息，用中文回答用户的问题。如果项目信息不足以完全回答问题，可以适当补充你的专业知识，但要明确说明哪些是基于数据库的信息，哪些是你的补充建议。"""

    TECHNICAL_KEYWORDS = [
        "框架", "库", "工具", "项目", "开源", "github", "代码", "编程", "开发",
        "python", "javascript", "java", "go", "rust", "typescript", "react", "vue",
        "ai", "机器学习", "深度学习", "爬虫", "数据库", "api", "前端", "后端",
        "推荐", "有没有", "什么", "哪个", "如何", "怎么", "帮助", "找", "搜索",
        "框架", "组件", "插件", "sdk", "cli", "web", "app", "docker", "kubernetes",
        "可视化", "图表", "测试", "部署", "监控", "日志", "安全", "性能", "算法"
    ]

    GREETING_PATTERNS = [
        "你好", "您好", "hi", "hello", "嗨", "哈喽", "在吗", "在不在",
        "早上好", "下午好", "晚上好", "早安", "晚安"
    ]
    
    FOLLOWUP_PATTERNS = [
        "再看看", "换一个", "还有吗", "其他的", "下一个", "继续", "更多",
        "还有别的吗", "再来几个", "换一批", "重新推荐"
    ]

    def __init__(self):
        self.config = get_config()
        self.cache = AnalysisCache()
        self.embedding_engine = EmbeddingEngine()
        self.client = OpenAI(
            api_key=self.config.openai.api_key,
            base_url=self.config.openai.base_url
        )
        self.model = self.config.openai.model_chat
        self.query_parser = get_query_parser()
        self.last_filters = None  # 记忆上次的过滤条件
        self.last_query_time = None  # 上次查询时间

    def _is_technical_query(self, query: str) -> bool:
        """判断用户问题是否与技术/项目相关"""
        query_lower = query.lower().strip()
        
        for pattern in self.GREETING_PATTERNS:
            if query_lower == pattern.lower() or query_lower.startswith(pattern.lower()):
                return False
        
        if len(query) < 3:
            return False
        
        for keyword in self.TECHNICAL_KEYWORDS:
            if keyword.lower() in query_lower:
                return True
        
        return len(query) >= 8
    
    def _is_followup_query(self, query: str) -> bool:
        """判断是否是追问（延续上下文的查询）"""
        query_lower = query.lower().strip()
        
        # 检查是否包含追问关键词（必须在 5 分钟内）
        if self.last_query_time:
            time_diff = (datetime.now() - self.last_query_time).total_seconds()
            if time_diff < 300:  # 5 分钟内
                for pattern in self.FOLLOWUP_PATTERNS:
                    if pattern in query_lower:
                        return True
        
        # 如果上次查询在 5 分钟内，且问题很短（可能是追问）
        if (self.last_query_time and 
            len(query) < 20 and 
            (datetime.now() - self.last_query_time).total_seconds() < 300):
            # 排除打招呼
            for pattern in self.GREETING_PATTERNS:
                if pattern in query_lower:
                    return False
            return True
        
        return False

    async def retrieve_projects(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.5,
        min_best_similarity: float = 0.45,
        filters: QueryFilters = None
    ) -> List[RetrievedProject]:
        """
        检索相关项目（支持宽松过滤）
        
        宽松过滤策略：
        - 不严格排除不匹配的项目
        - 匹配的项目给予相似度加权
        - 最终按加权后的相似度排序
        
        Args:
            query: 用户查询
            top_k: 返回数量
            threshold: 相似度阈值
            min_best_similarity: 最低最佳相似度
            filters: 过滤条件（可选）
        """
        try:
            all_embeddings = self.cache.get_all_embeddings()
            
            if not all_embeddings:
                logger.warning("数据库中没有已索引的项目")
                return []

            query_embedding = await self.embedding_engine.embed_text(query)
            if not query_embedding:
                logger.error("查询向量化失败")
                return []

            from app.infrastructure.embedding import EmbeddingEngine
            embeddings = [doc["embedding"] for doc in all_embeddings if doc.get("embedding")]
            similarities = EmbeddingEngine.batch_cosine_similarity(
                query_embedding,
                embeddings
            )

            results = []
            for doc, similarity in zip(all_embeddings, similarities):
                results.append({
                    "doc": doc,
                    "similarity": similarity,
                    "boosted_similarity": similarity  # 初始加权相似度=原始相似度
                })

            # 应用宽松过滤（加权策略）
            if filters and filters.has_filters():
                logger.info(f"应用宽松过滤：{filters}")
                for result in results:
                    doc = result["doc"]
                    boost = 1.0
                    
                    # 语言匹配：加权 1.3 倍
                    if filters.language:
                        if doc.get("language") == filters.language:
                            boost *= 1.3
                        elif filters.language.lower() in (doc.get("language") or "").lower():
                            boost *= 1.15  # 部分匹配（如"Python"匹配"Python3"）
                    
                    # 分类匹配：加权 1.2 倍（分类本身不太准确，权重低一些）
                    if filters.category:
                        if doc.get("category") == filters.category:
                            boost *= 1.2
                    
                    # 时间范围：7 天内的加权 1.1 倍（暂时未实现）
                    if filters.days:
                        pass
                    
                    # Star 数：超过 min_stars 的加权 1.1 倍
                    if filters.min_stars is not None:
                        if doc.get("stars", 0) >= filters.min_stars:
                            boost *= 1.1
                    
                    # 应用加权
                    result["boosted_similarity"] = result["similarity"] * boost

            # 按加权后的相似度排序
            results.sort(key=lambda x: x["boosted_similarity"], reverse=True)

            if not results or results[0]["boosted_similarity"] < min_best_similarity:
                logger.info(f"最高相似度 {results[0]['boosted_similarity'] if results else 0:.3f} 低于阈值 {min_best_similarity}，未找到相关项目")
                return []

            top_results = results[:top_k]

            retrieved = []
            for item in top_results:
                if item["boosted_similarity"] >= threshold:
                    doc = item["doc"]
                    project = RetrievedProject(
                        repo_full_name=doc["repo_full_name"],
                        summary=doc.get("summary", ""),
                        reasons=doc.get("reasons", []),
                        similarity=item["boosted_similarity"],
                        category=doc.get("category"),
                        language=doc.get("language"),
                        stars=doc.get("stars"),
                        url=f"https://github.com/{doc['repo_full_name']}"
                    )
                    retrieved.append(project)

            logger.info(f"检索完成，找到 {len(retrieved)} 个相关项目，最高相似度：{results[0]['boosted_similarity']:.3f}")
            return retrieved

        except Exception as e:
            logger.error(f"检索项目失败：{str(e)}")
            return []

    def _format_projects_context(self, projects: List[RetrievedProject]) -> str:
        """格式化项目信息为上下文"""
        if not projects:
            return "未找到相关项目"

        context_parts = []
        for i, project in enumerate(projects, 1):
            stars_str = f"⭐ {project.stars:,}" if project.stars else ""
            lang_str = f"[{project.language}]" if project.language else ""
            
            project_info = f"""### 项目 {i}: {project.repo_full_name}
- 语言：{lang_str}
- Stars: {stars_str}
- 分类：{project.category or '未分类'}
- 项目简介：{project.summary}
- 核心特点:
{chr(10).join(f'  • {r}' for r in project.reasons)}
- GitHub: {project.url}"""
            context_parts.append(project_info)

        return "\n\n".join(context_parts)

    async def _chat_without_retrieval(self, query: str) -> AsyncGenerator[Dict, None]:
        """不检索项目的纯对话模式（用于打招呼、闲聊等）"""
        yield {
            "type": "status",
            "content": "正在思考..."
        }

        yield {
            "type": "content_start"
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": query}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=500
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield {
                        "type": "content",
                        "content": content
                    }

        except Exception as e:
            logger.error(f"LLM 生成失败：{str(e)}")
            yield {
                "type": "error",
                "content": f"生成回答时出错：{str(e)}"
            }

        yield {
            "type": "done"
        }

    async def _chat_no_match(self, query: str) -> AsyncGenerator[Dict, None]:
        """数据库中没有匹配项目时的对话模式"""
        yield {
            "type": "status",
            "content": "正在思考..."
        }

        yield {
            "type": "content_start"
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.NO_MATCH_SYSTEM_PROMPT},
                    {"role": "user", "content": f"用户问题：{query}\n\n请回答用户的问题，并告知数据库中没有找到相关的 GitHub Trending 项目。"}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=800
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield {
                        "type": "content",
                        "content": content
                    }

        except Exception as e:
            logger.error(f"LLM 生成失败：{str(e)}")
            yield {
                "type": "error",
                "content": f"生成回答时出错：{str(e)}"
            }

        yield {
            "type": "done"
        }

    async def chat_stream(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.5
    ) -> AsyncGenerator[Dict, None]:
        """流式对话生成"""
        if not self._is_technical_query(query):
            async for chunk in self._chat_without_retrieval(query):
                yield chunk
            return

        yield {
            "type": "status",
            "content": "正在思考..."
        }

        yield {
            "type": "status", 
            "content": "正在检索相关项目..."
        }

        # 智能解析：判断是否是追问
        if self._is_followup_query(query) and self.last_filters:
            logger.info(f"检测到追问，沿用上次过滤条件：{self.last_filters}")
            filters = self.last_filters
        else:
            # 新查询，调用 QueryParser
            filters = await self.query_parser.parse(query)
            self.last_filters = filters if filters.has_filters() else None
            self.last_query_time = datetime.now()
        
        projects = await self.retrieve_projects(query, top_k, threshold, filters=filters)

        if not projects:
            async for chunk in self._chat_no_match(query):
                yield chunk
            return

        yield {
            "type": "status",
            "content": f"找到 {len(projects)} 个相关项目，正在生成回答..."
        }

        yield {
            "type": "projects",
            "projects": [
                {
                    "repo_full_name": p.repo_full_name,
                    "summary": p.summary,
                    "similarity": round(p.similarity * 100, 1),
                    "language": p.language,
                    "stars": p.stars,
                    "url": p.url
                }
                for p in projects
            ]
        }

        projects_context = self._format_projects_context(projects)
        prompt = self.RAG_PROMPT_TEMPLATE.format(
            query=query,
            projects_context=projects_context
        )

        yield {
            "type": "content_start"
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=2000
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield {
                        "type": "content",
                        "content": content
                    }

        except Exception as e:
            logger.error(f"LLM 生成失败：{str(e)}")
            yield {
                "type": "error",
                "content": f"生成回答时出错：{str(e)}"
            }

        yield {
            "type": "done"
        }

    async def chat(self, query: str, top_k: int = 3, threshold: float = 0.5) -> Dict:
        """非流式对话"""
        if not self._is_technical_query(query):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.CHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": query}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                return {
                    "answer": response.choices[0].message.content,
                    "projects": [],
                    "success": True
                }
            except Exception as e:
                return {
                    "answer": f"生成回答时出错：{str(e)}",
                    "projects": [],
                    "success": False
                }

        # 智能解析：判断是否是追问
        if self._is_followup_query(query) and self.last_filters:
            logger.info(f"检测到追问，沿用上次过滤条件：{self.last_filters}")
            filters = self.last_filters
        else:
            # 新查询，调用 QueryParser
            filters = await self.query_parser.parse(query)
            self.last_filters = filters if filters.has_filters() else None
            self.last_query_time = datetime.now()
        
        projects = await self.retrieve_projects(query, top_k, threshold, filters=filters)

        if not projects:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.NO_MATCH_SYSTEM_PROMPT},
                        {"role": "user", "content": f"用户问题：{query}\n\n请回答用户的问题，并告知数据库中没有找到相关的 GitHub Trending 项目。"}
                    ],
                    temperature=0.7,
                    max_tokens=800
                )
                return {
                    "answer": response.choices[0].message.content,
                    "projects": [],
                    "success": True
                }
            except Exception as e:
                return {
                    "answer": f"生成回答时出错：{str(e)}",
                    "projects": [],
                    "success": False
                }

        projects_context = self._format_projects_context(projects)
        prompt = self.RAG_PROMPT_TEMPLATE.format(
            query=query,
            projects_context=projects_context
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            answer = response.choices[0].message.content

            return {
                "answer": answer,
                "projects": [
                    {
                        "repo_full_name": p.repo_full_name,
                        "summary": p.summary,
                        "similarity": round(p.similarity * 100, 1),
                        "language": p.language,
                        "stars": p.stars,
                        "url": p.url
                    }
                    for p in projects
                ],
                "success": True
            }

        except Exception as e:
            logger.error(f"LLM 生成失败：{str(e)}")
            return {
                "answer": f"生成回答时出错：{str(e)}",
                "projects": [],
                "success": False
            }
