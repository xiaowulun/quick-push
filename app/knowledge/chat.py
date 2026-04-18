"""
RAG 对话服务模块

实现基于 GitHub Trending 数据库的智能问答功能

搜索流程：
1. 粗排：混合检索（向量 + BM25）→ RRF 融合 → top 20
2. 精排：Cross-Encoder 重排序 → top 5
3. LLM 生成回答
"""

import asyncio
import logging
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import OpenAI

from app.infrastructure.config import get_config
from app.infrastructure.cache import AnalysisCache
from app.infrastructure.session import get_session_manager
from app.knowledge.search import SearchService
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
    source_id: Optional[str] = None
    evidence_section: Optional[str] = None
    evidence_path: Optional[str] = None
    evidence_heading: Optional[str] = None
    evidence_chunk: Optional[str] = None


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

    VALID_CATEGORIES = {
        "ai_ecosystem",
        "infra_and_tools",
        "product_and_ui",
        "knowledge_base",
    }

    def __init__(self):
        self.config = get_config()
        self.cache = AnalysisCache()
        self.search_service = SearchService()
        self.session_manager = get_session_manager()
        self.request_timeout = int(getattr(self.config.openai, "request_timeout", 90))
        self.client = OpenAI(
            api_key=self.config.openai.api_key,
            base_url=self.config.openai.base_url,
            timeout=self.request_timeout,
        )
        self.model = self.config.openai.model_chat
        self.min_confidence = float(os.getenv("CHAT_MIN_CONFIDENCE", "0.42"))
        self.query_parser = get_query_parser()

    def _classify_chat_error(self, error: Exception) -> Dict[str, Any]:
        name = error.__class__.__name__
        status_code = getattr(error, "status_code", None)

        if isinstance(error, (TimeoutError, asyncio.TimeoutError)) or name in {"APITimeoutError", "ReadTimeout"}:
            return {
                "code": "CHAT_TIMEOUT",
                "message": "请求超时，请稍后重试。",
                "status_code": 504,
            }
        if name == "RateLimitError":
            return {
                "code": "CHAT_RATE_LIMIT",
                "message": "请求过于频繁，请稍后再试。",
                "status_code": 429,
            }
        if name in {"APIConnectionError", "ConnectTimeout", "ConnectionError"}:
            return {
                "code": "CHAT_UPSTREAM_UNAVAILABLE",
                "message": "上游服务暂时不可用，请稍后重试。",
                "status_code": 503,
            }
        if name == "APIStatusError":
            mapped_status = status_code if isinstance(status_code, int) and status_code >= 400 else 502
            return {
                "code": "CHAT_UPSTREAM_ERROR",
                "message": f"上游服务异常（{mapped_status}），请稍后重试。",
                "status_code": mapped_status,
            }
        return {
            "code": "CHAT_INTERNAL_ERROR",
            "message": "服务内部异常，请稍后重试。",
            "status_code": 500,
        }

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
    
    def _is_followup_query(self, query: str, session) -> bool:
        """判断是否是追问"""
        query_lower = query.lower().strip()
        
        if not session.last_query_time:
            return False

        # Keep follow-up reuse only in a short context window.
        time_diff = (datetime.now() - session.last_query_time).total_seconds()
        if time_diff >= 300:
            return False

        for pattern in self.FOLLOWUP_PATTERNS:
            if pattern in query_lower:
                return True

        # Only explicit short ellipsis prompts are treated as follow-up.
        terse_followup = {
            "还有呢", "然后呢", "继续", "再说说", "展开讲讲", "细说", "具体点", "举例", "对比下",
            "what else", "go on", "continue", "more",
        }
        if query_lower in terse_followup:
            return True

        return False

    def _sanitize_filters(self, filters: Any) -> QueryFilters:
        """Normalize parser/session filters and drop malformed values."""
        if isinstance(filters, QueryFilters):
            data = filters.model_dump()
        elif isinstance(filters, dict):
            data = dict(filters)
        else:
            return QueryFilters()

        raw_category = str(data.get("category") or "").strip().lower()
        normalized_category = None
        if raw_category:
            compact = raw_category.replace("-", "_").replace(" ", "")
            for cat in self.VALID_CATEGORIES:
                if cat in compact:
                    normalized_category = cat
                    break

        raw_language = str(data.get("language") or "").strip()
        normalized_language = None
        if raw_language:
            normalized_language = re.sub(r"\s+", " ", raw_language)
            if len(normalized_language) > 32:
                normalized_language = normalized_language[:32]

        raw_keywords = data.get("keywords") or []
        normalized_keywords: List[str] = []
        for kw in raw_keywords:
            text = re.sub(r"\s+", " ", str(kw or "").strip())
            if not text:
                continue
            normalized_keywords.append(text[:32])
            if len(normalized_keywords) >= 8:
                break

        days = data.get("days")
        if not isinstance(days, int) or days <= 0 or days > 365:
            days = None

        min_stars = data.get("min_stars")
        if not isinstance(min_stars, int) or min_stars < 0:
            min_stars = None

        return QueryFilters(
            language=normalized_language,
            category=normalized_category,
            days=days,
            min_stars=min_stars,
            keywords=normalized_keywords,
        )

    @staticmethod
    def _normalize_similarity(score: float) -> float:
        """Map arbitrary rerank score to [0, 1]."""
        try:
            s = float(score)
        except (TypeError, ValueError):
            return 0.0
        if 0.0 <= s <= 1.0:
            return s
        if s >= 20:
            return 1.0
        if s <= -20:
            return 0.0
        return 1.0 / (1.0 + math.exp(-s))

    def _compute_retrieval_confidence(self, projects: List[RetrievedProject]) -> float:
        if not projects:
            return 0.0
        scores = [self._normalize_similarity(p.similarity) for p in projects]
        scores.sort(reverse=True)
        top1 = scores[0]
        avg_top = sum(scores[: min(3, len(scores))]) / min(3, len(scores))
        top2 = scores[1] if len(scores) > 1 else 0.0
        margin = max(0.0, min(1.0, top1 - top2))
        confidence = 0.6 * top1 + 0.3 * avg_top + 0.1 * margin
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _has_citations(answer: str) -> bool:
        return bool(re.search(r"\[S\d+\]", answer or ""))

    @staticmethod
    def _build_source_appendix(projects: List[RetrievedProject]) -> str:
        if not projects:
            return "\n\n参考来源：当前检索未命中可引用项目。"
        lines = ["", "", "参考来源："]
        for p in projects[:5]:
            sid = p.source_id or "-"
            heading = p.evidence_heading or p.evidence_section or "README"
            lines.append(f"[{sid}] {p.repo_full_name} | {heading} | {p.url}")
        return "\n".join(lines)

    def _build_low_confidence_answer(
        self,
        query: str,
        projects: List[RetrievedProject],
        confidence: float,
    ) -> str:
        head = (
            f"当前无法给出高置信度结论（置信度 {confidence:.2f} < 阈值 {self.min_confidence:.2f}）。"
            " 我先不直接下结论，建议你缩小问题范围后重试。"
        )
        suggestions = [
            "建议重试方式：",
            f"1. 增加技术关键词，例如：`{query} + 语言/框架名`",
            "2. 指定范围，例如：最近 7 天、某一语言、某一类别",
            "3. 如果你要对比，请明确对比维度（性能/易用性/部署成本）",
        ]
        return "\n".join([head, *suggestions, self._build_source_appendix(projects)])

    async def retrieve_projects(
        self,
        query: str,
        top_k: int = 5,
        filters: QueryFilters = None
    ) -> List[RetrievedProject]:
        """
        检索相关项目（使用混合检索 + Rerank）
        
        流程：
        1. 粗排：混合检索（向量 + BM25）→ RRF 融合 → top 20
        2. 精排：Cross-Encoder 重排序 → top 5
        
        Args:
            query: 用户查询
            top_k: 最终返回数量
            filters: 过滤条件（暂未实现）
        """
        try:
            results = await self.search_service.search_projects(
                query=query,
                coarse_top_k=20,
                final_top_k=top_k,
                filters=filters
            )

            if not results:
                logger.info(f"未找到相关项目: {query}")
                return []

            retrieved = []
            for idx, item in enumerate(results, 1):
                project = RetrievedProject(
                    repo_full_name=item.get("repo_full_name", ""),
                    summary=item.get("summary", ""),
                    reasons=item.get("reasons", []),
                    similarity=item.get("rerank_score", 0),
                    category=item.get("category"),
                    language=item.get("language"),
                    stars=item.get("stars"),
                    url=f"https://github.com/{item.get('repo_full_name', '')}",
                    source_id=f"S{idx}",
                    evidence_section=item.get("evidence_section"),
                    evidence_path=item.get("path") or "README.md",
                    evidence_heading=item.get("heading") or item.get("evidence_section"),
                    evidence_chunk=item.get("evidence_chunk"),
                )
                retrieved.append(project)

            logger.info(f"检索完成，找到 {len(retrieved)} 个相关项目")
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
            source_id = project.source_id or f"S{i}"
            heading = project.evidence_heading or project.evidence_section or "README"
            snippet = (project.evidence_chunk or "").strip()
            if len(snippet) > 220:
                snippet = snippet[:220] + "..."

            project_info = f"""### [{source_id}] 项目 {i}: {project.repo_full_name}
- 语言：{lang_str}
- Stars: {stars_str}
- 分类：{project.category or '未分类'}
- 项目简介：{project.summary}
- 证据位置：{project.evidence_path or 'README.md'} / {heading}
- 核心特点:
{chr(10).join(f'  • {r}' for r in project.reasons)}
- 证据片段：{snippet or '（无）'}
- GitHub: {project.url}"""
            context_parts.append(project_info)

        return "\n\n".join(context_parts)

    async def _chat_without_retrieval(self, query: str) -> AsyncGenerator[Dict, None]:
        """不检索项目的纯对话模式"""
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
                max_tokens=500,
                timeout=self.request_timeout,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield {
                        "type": "content",
                        "content": content
                    }

        except Exception as e:
            err = self._classify_chat_error(e)
            logger.error(f"LLM 生成失败 code={err['code']} error={str(e)}")
            yield {
                "type": "error",
                "code": err["code"],
                "content": err["message"],
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
                max_tokens=800,
                timeout=self.request_timeout,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield {
                        "type": "content",
                        "content": content
                    }

        except Exception as e:
            err = self._classify_chat_error(e)
            logger.error(f"LLM 生成失败 code={err['code']} error={str(e)}")
            yield {
                "type": "error",
                "code": err["code"],
                "content": err["message"],
            }

        yield {
            "type": "done"
        }

    async def chat_stream(
        self,
        query: str,
        top_k: int = 5,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """流式对话生成"""
        session = self.session_manager.get_or_create(session_id)
        
        yield {
            "type": "session",
            "session_id": session.session_id
        }

        if not self._is_technical_query(query):
            full_answer = ""
            async for chunk in self._chat_without_retrieval(query):
                if chunk.get("type") == "content" and chunk.get("content"):
                    full_answer += chunk["content"]
                yield chunk

            if full_answer:
                session.add_to_history(query, full_answer, [])
                session.query_count += 1
            return

        yield {
            "type": "status",
            "content": "正在思考..."
        }

        yield {
            "type": "status", 
            "content": "正在检索相关项目..."
        }

        if self._is_followup_query(query, session) and session.last_filters:
            logger.info(f"检测到追问，沿用上次过滤条件：{session.last_filters}")
            filters = self._sanitize_filters(session.last_filters)
        else:
            parsed_filters = await self.query_parser.parse(query)
            filters = self._sanitize_filters(parsed_filters)
            session.last_filters = filters if filters.has_filters() else None
            session.last_query_time = datetime.now()
        
        projects = await self.retrieve_projects(query, top_k, filters=filters)

        if not projects:
            full_answer = ""
            async for chunk in self._chat_no_match(query):
                if chunk.get("type") == "content" and chunk.get("content"):
                    full_answer += chunk["content"]
                yield chunk

            if full_answer:
                session.add_to_history(query, full_answer, [])
                session.query_count += 1
            return

        retrieval_confidence = self._compute_retrieval_confidence(projects)
        if retrieval_confidence < self.min_confidence:
            low_conf_answer = self._build_low_confidence_answer(query, projects, retrieval_confidence)
            yield {
                "type": "status",
                "content": "检索证据不足，已触发低置信拒答模板。"
            }
            yield {"type": "content_start"}
            yield {"type": "content", "content": low_conf_answer}
            session.add_to_history(query, low_conf_answer, [
                {
                    "repo_full_name": p.repo_full_name,
                    "summary": p.summary,
                    "similarity": p.similarity
                }
                for p in projects
            ])
            session.query_count += 1
            yield {"type": "done"}
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

        full_answer = ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=2000,
                timeout=self.request_timeout,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    yield {
                        "type": "content",
                        "content": content
                    }

            if not self._has_citations(full_answer):
                appendix = self._build_source_appendix(projects)
                full_answer += appendix
                yield {
                    "type": "content",
                    "content": appendix
                }

            session.add_to_history(query, full_answer, [
                {
                    "repo_full_name": p.repo_full_name,
                    "summary": p.summary,
                    "similarity": p.similarity
                }
                for p in projects
            ])
            session.query_count += 1

        except Exception as e:
            err = self._classify_chat_error(e)
            logger.error(f"LLM 生成失败 code={err['code']} error={str(e)}")
            yield {
                "type": "error",
                "code": err["code"],
                "content": err["message"],
            }

        yield {
            "type": "done"
        }

    async def chat(self, query: str, top_k: int = 5, session_id: Optional[str] = None) -> Dict:
        """非流式对话"""
        session = self.session_manager.get_or_create(session_id)

        if not self._is_technical_query(query):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.CHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": query}
                    ],
                    temperature=0.7,
                    max_tokens=500,
                    timeout=self.request_timeout,
                )
                return {
                    "answer": response.choices[0].message.content,
                    "projects": [],
                    "success": True,
                    "session_id": session.session_id
                }
            except Exception as e:
                err = self._classify_chat_error(e)
                return {
                    "answer": err["message"],
                    "projects": [],
                    "success": False,
                    "session_id": session.session_id,
                    "error_code": err["code"],
                    "error_message": err["message"],
                    "status_code": err["status_code"],
                }

        if self._is_followup_query(query, session) and session.last_filters:
            logger.info(f"检测到追问，沿用上次过滤条件：{session.last_filters}")
            filters = self._sanitize_filters(session.last_filters)
        else:
            parsed_filters = await self.query_parser.parse(query)
            filters = self._sanitize_filters(parsed_filters)
            session.last_filters = filters if filters.has_filters() else None
            session.last_query_time = datetime.now()
        
        projects = await self.retrieve_projects(query, top_k, filters=filters)

        if not projects:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.NO_MATCH_SYSTEM_PROMPT},
                        {"role": "user", "content": f"用户问题：{query}\n\n请回答用户的问题，并告知数据库中没有找到相关的 GitHub Trending 项目。"}
                    ],
                    temperature=0.7,
                    max_tokens=800,
                    timeout=self.request_timeout,
                )
                return {
                    "answer": response.choices[0].message.content,
                    "projects": [],
                    "success": True,
                    "session_id": session.session_id
                }
            except Exception as e:
                err = self._classify_chat_error(e)
                return {
                    "answer": err["message"],
                    "projects": [],
                    "success": False,
                    "session_id": session.session_id,
                    "error_code": err["code"],
                    "error_message": err["message"],
                    "status_code": err["status_code"],
                }

        retrieval_confidence = self._compute_retrieval_confidence(projects)
        if retrieval_confidence < self.min_confidence:
            answer = self._build_low_confidence_answer(query, projects, retrieval_confidence)
            session.add_to_history(query, answer, [
                {
                    "repo_full_name": p.repo_full_name,
                    "summary": p.summary,
                    "similarity": p.similarity
                }
                for p in projects
            ])
            session.query_count += 1
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
                "success": True,
                "session_id": session.session_id
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
                max_tokens=2000,
                timeout=self.request_timeout,
            )

            answer = response.choices[0].message.content
            if not self._has_citations(answer):
                answer += self._build_source_appendix(projects)

            session.add_to_history(query, answer, [
                {
                    "repo_full_name": p.repo_full_name,
                    "summary": p.summary,
                    "similarity": p.similarity
                }
                for p in projects
            ])
            session.query_count += 1

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
                "success": True,
                "session_id": session.session_id
            }

        except Exception as e:
            err = self._classify_chat_error(e)
            logger.error(f"LLM 生成失败 code={err['code']} error={str(e)}")
            return {
                "answer": err["message"],
                "projects": [],
                "success": False,
                "session_id": session.session_id,
                "error_code": err["code"],
                "error_message": err["message"],
                "status_code": err["status_code"],
            }
