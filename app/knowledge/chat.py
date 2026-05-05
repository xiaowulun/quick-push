"""
RAG 对话服务模块

实现基于 GitHub Trending 数据库的智能问答功能

搜索流程：1. 粗排：混合检索（向量 + BM25）→ RRF 融合 → top 20
2. 精排：Cross-Encoder 重排 → top 5
3. LLM 生成回答
"""

import asyncio
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import OpenAI

from app.infrastructure.config import get_config
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
    chunk_id: Optional[str] = None
    evidence_section: Optional[str] = None
    evidence_path: Optional[str] = None
    evidence_heading: Optional[str] = None
    evidence_chunk: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)
    match_reasons: List[str] = field(default_factory=list)


class RAGChatService:
    """RAG 对话服务"""

    SYSTEM_PROMPT = """你是专业的 GitHub 开源项目推荐助手。
请基于检索结果回答用户问题，并给出清晰、可执行的建议。
格式要求：
1) 输出纯文本分点，不使用 Markdown 标题（# / ##）和表格。
2) 首行直接开始正文，不要输出前导空行。
3) 不使用寒暄开场（如“你好”）。"""

    CHAT_SYSTEM_PROMPT = """你是友好的技术助手。
当用户寒暄时，简短回应并引导其提出具体技术需求。
格式要求：
1) 输出纯文本，不使用 Markdown 标题（# / ##）和表格。
2) 首行直接输出结论，不要空行，不要“你好”式开场。"""

    NO_MATCH_SYSTEM_PROMPT = """当检索不到合适项目时：
1) 明确说明当前数据中暂无匹配结果。
2) 给出通用方向和下一步搜索建议。
3) 不要编造不存在的项目。
格式要求：输出纯文本分点，不使用 Markdown 标题（# / ##）和表格，首行不要空行。"""

    RAG_PROMPT_TEMPLATE = """基于以下 GitHub Trending 检索结果回答用户问题。

## 用户问题
{query}

## 推荐依据
{recommendation_basis}

## 检索结果
{projects_context}

请用中文回答，并区分“基于检索结果的信息”和“补充建议”。
优先使用“推荐依据”和“检索结果”中的结构化特征（语言/类别/stars/关键词命中）来解释推荐，不要给空泛理由。
格式要求：输出纯文本分点，不使用 Markdown 标题（# / ##）和表格，首行不要空行。"""

    TECHNICAL_KEYWORDS = [
        "框架", "库", "工具", "项目", "开源", "github", "代码", "编程", "开发",
        "python", "javascript", "java", "go", "rust", "typescript", "react", "vue",
        "ai", "机器学习", "深度学习", "爬虫", "数据库", "api", "前端", "后端",
        "推荐", "有没有", "什么", "哪个", "如何", "怎么", "帮助", "找", "搜索",
        "组件", "插件", "sdk", "cli", "web", "app", "docker", "kubernetes",
        "可视化", "图表", "测试", "部署", "监控", "日志", "安全", "性能", "算法",
    ]

    PLANNING_KEYWORDS = [
        "mvp", "roadmap", "路线图", "里程碑", "排期", "优先级",
        "版本规划", "需求拆解", "功能优先级", "上线计划", "本周上线",
        "迭代计划", "交付计划", "能力规划",
    ]

    RETRIEVAL_ACTION_KEYWORDS = [
        "推荐", "有什么", "有哪些", "找", "搜索", "检索", "对比", "比较", "选型",
        "热门", "高星", "最近", "榜单", "top", "best", "列举", "列出", "几个", "哪个好",
    ]

    RETRIEVAL_OBJECT_KEYWORDS = [
        "项目", "仓库", "repo", "repository", "github", "trending", "开源", "框架", "工具",
    ]

    CONCEPTUAL_CHAT_KEYWORDS = [
        "了解", "是什么", "啥是", "介绍", "原理", "概念", "教程", "学习", "入门", "解释", "科普", "怎么理解", "区别",
        "what is", "learn", "overview", "introduction", "concept", "principle",
    ]

    GREETING_PATTERNS = [
        "你好", "您好", "hi", "hello", "嗨", "哈喽", "在吗", "在不在",
        "早上好", "下午好", "晚上好", "早安", "晚安",
    ]

    FOLLOWUP_PATTERNS = [
        "再看看", "换一个", "还有吗", "其他的", "下一个", "继续", "更多",
        "还有别的吗", "再来几个", "换一批", "重新推荐",
    ]

    EASY_TASK_HINTS = {
        "hi", "hello", "thanks", "thank you",
        "你好", "您好", "谢谢", "在吗", "嗨", "晚安",
    }
    HARD_TASK_KEYWORDS = [
        "架构", "设计", "权衡", "tradeoff", "benchmark", "性能", "优化", "并发", "分布式",
        "安全", "迁移", "故障", "调优", "复杂", "深入", "比较", "对比", "落地", "方案",
        "architecture", "design", "optimization", "security", "scalability", "migration",
    ]
    VALID_CATEGORIES = {
        "ai_ecosystem",
        "infra_and_tools",
        "product_and_ui",
        "knowledge_base",
    }

    def __init__(self):
        self.config = get_config()
        self.search_service = SearchService()
        self.session_manager = get_session_manager()
        self.request_timeout = int(getattr(self.config.openai, "request_timeout", 90))
        self.client = OpenAI(
            api_key=self.config.openai.api_key,
            base_url=self.config.openai.base_url,
            timeout=self.request_timeout,
        )
        # Keep a stable default model field for external logging compatibility.
        self.model = self.config.openai.model_medium
        self.rag_max_tokens = max(300, int(getattr(self.config.rag_chat, "max_tokens", 1200)))
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

    @staticmethod
    def _is_model_not_found_error(error: Exception) -> bool:
        msg = str(error or "").lower()
        return (
            "model does not exist" in msg
            or "invalid model" in msg
            or "code': 20012" in msg
            or '"code": 20012' in msg
        )

    def _estimate_query_difficulty(self, query: str, *, retrieval: bool) -> str:
        query_lower = str(query or "").strip().lower()
        if not query_lower:
            return "easy"

        if query_lower in self.EASY_TASK_HINTS:
            return "easy"
        if self._is_planning_query(query):
            return "hard"
        if any(keyword in query_lower for keyword in self.HARD_TASK_KEYWORDS):
            return "hard"

        if retrieval:
            if len(query_lower) >= 80:
                return "hard"
            return "medium"

        if len(query_lower) <= 12:
            return "easy"
        return "medium"

    def select_model_for_query(self, query: str, *, retrieval: bool = False) -> str:
        difficulty = self._estimate_query_difficulty(query=query, retrieval=retrieval)
        if difficulty == "easy":
            return self.config.openai.model_easy
        if difficulty == "hard":
            return self.config.openai.model_hard
        return self.config.openai.model_medium

    def preview_model_for_query(self, query: str) -> str:
        return self.select_model_for_query(query=query, retrieval=self._has_retrieval_intent(query))

    def _build_model_candidates(
        self,
        preferred_model: Optional[str] = None,
        *,
        query: str = "",
        retrieval: bool = False,
    ) -> List[str]:
        chosen_model = preferred_model or self.select_model_for_query(query=query, retrieval=retrieval)

        easy = self.config.openai.model_easy
        medium = self.config.openai.model_medium
        hard = self.config.openai.model_hard

        if chosen_model == easy:
            ordered = [easy, medium, hard]
        elif chosen_model == hard:
            ordered = [hard, medium, easy]
        else:
            ordered = [medium, hard, easy]

        candidates: List[str] = []
        for model in [chosen_model, *ordered]:
            m = str(model or "").strip()
            if m and m not in candidates:
                candidates.append(m)
        return candidates

    def _create_chat_completion_with_fallback(self, **kwargs):
        preferred_model = kwargs.pop("model", None)
        query = str(kwargs.pop("query", "") or "")
        retrieval = bool(kwargs.pop("retrieval", False))
        last_error: Optional[Exception] = None

        for model_name in self._build_model_candidates(
            preferred_model=preferred_model,
            query=query,
            retrieval=retrieval,
        ):
            try:
                return self.client.chat.completions.create(model=model_name, **kwargs)
            except Exception as error:
                last_error = error
                if self._is_model_not_found_error(error):
                    logger.warning(
                        "chat model unavailable, fallback to next model: model=%s error=%s",
                        model_name,
                        str(error),
                    )
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("No available model candidates for chat completion")

    def _has_retrieval_intent(self, query: str) -> bool:
        """Return True only when query likely asks for repo/project retrieval."""
        query_lower = (query or "").lower().strip()
        if len(query_lower) < 2:
            return False

        for pattern in self.GREETING_PATTERNS:
            p = pattern.lower()
            if query_lower == p or query_lower.startswith(p):
                return False

        has_action = any(keyword.lower() in query_lower for keyword in self.RETRIEVAL_ACTION_KEYWORDS) or bool(
            re.search(
                "(\u6709\u4ec0\u4e48|\u6709\u54ea\u4e9b|\u63a8\u8350|\u6bd4\u8f83|\u54ea\u4e2a\u597d|\u627e|\u641c\u7d22|\u68c0\u7d22)",
                query_lower,
            )
        )
        has_object = any(keyword.lower() in query_lower for keyword in self.RETRIEVAL_OBJECT_KEYWORDS) or bool(
            re.search(
                "(\u9879\u76ee|\u4ed3\u5e93|\u5f00\u6e90|\u6846\u67b6|\u5de5\u5177|github|repo|repository|trending)",
                query_lower,
            )
        )
        has_technical = any(keyword.lower() in query_lower for keyword in self.TECHNICAL_KEYWORDS)
        has_conceptual = any(keyword.lower() in query_lower for keyword in self.CONCEPTUAL_CHAT_KEYWORDS) or bool(
            re.search(
                "(\u4e86\u89e3|\u662f\u4ec0\u4e48|\u4ecb\u7ecd|\u539f\u7406|\u6982\u5ff5|\u6559\u7a0b|\u5b66\u4e60|\u5165\u95e8|\u89e3\u91ca|\u600e\u4e48\u7406\u89e3|\u533a\u522b)",
                query_lower,
            )
        )

        # Concept-learning queries should stay in plain LLM chat unless user
        # clearly asks for retrieval/recommendation.
        if has_conceptual and not has_action:
            return False

        # RAG requires explicit retrieval action + (object context or technical context).
        if has_action and (has_object or has_technical):
            return True

        # Object-only mention is not enough (e.g. "了解一个 AI agent 项目").
        return False

    def _is_technical_query(self, query: str) -> bool:
        """Backward-compatible alias: now means retrieval-intent query."""
        return self._has_retrieval_intent(query)

    def _should_use_rag(self, query: str, session: Any) -> bool:
        """Decide whether to enter RAG retrieval pipeline."""
        if self._is_followup_query(query, session) and session.last_filters:
            return True
        return self._has_retrieval_intent(query)

    def _is_planning_query(self, query: str) -> bool:
        """判断是否是规划/排期类问题。"""
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return False
        return any(keyword.lower() in query_lower for keyword in self.PLANNING_KEYWORDS)

    def _build_low_confidence_prefix(self, confidence: float) -> str:
        """Low-confidence warning prefix for soft answers."""
        return (
            f"说明：当前检索置信度较低（{confidence:.2f} < 阈值 {self.min_confidence:.2f}），"
            "以下结论更偏方向性建议，建议结合你的技术栈与目标用户做二次确认。\n\n"
        )

    def _is_followup_query(self, query: str, session) -> bool:
        """判断是否是追问。"""
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
            "还有吗", "然后呢", "继续", "再说说", "展开讲讲", "细说", "具体点", "举例", "对比下",
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
            chunk = p.chunk_id or "-"
            lines.append(f"[{sid}] {p.repo_full_name} | {heading} | chunk={chunk} | {p.url}")
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
        检索相关项目（使用混合检索 + Rerank）。

        流程：
        1. 粗排：混合检索（向量 + BM25）→ RRF 融合 → top 20
        2. 精排：Cross-Encoder 重排 → top 5

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
                    chunk_id=item.get("chunk_id"),
                    evidence_section=item.get("evidence_section"),
                    evidence_path=item.get("path") or "README.md",
                    evidence_heading=item.get("heading") or item.get("evidence_section"),
                    evidence_chunk=item.get("evidence_chunk"),
                    keywords=item.get("keywords", []) or [],
                    tech_stack=item.get("tech_stack", []) or [],
                    use_cases=item.get("use_cases", []) or [],
                    match_reasons=item.get("match_reasons", []) or [],
                )
                retrieved.append(project)

            logger.info(f"检索完成，找到 {len(retrieved)} 个相关项目")
            return retrieved

        except Exception as e:
            logger.error(f"检索项目失败：{str(e)}")
            return []

    async def _retrieve_projects_with_filter_fallback(
        self,
        query: str,
        top_k: int,
        filters: Optional[QueryFilters],
    ) -> List[RetrievedProject]:
        """
        Try retrieval with parsed filters first; if it returns empty, fallback to no filters.
        This prevents over-restrictive parser output from causing avoidable no-match answers.
        """
        projects = await self.retrieve_projects(query, top_k, filters=filters)
        if projects:
            return projects

        if not filters or not filters.has_filters():
            return projects

        logger.info("过滤条件检索为空，回退无过滤重试: query=%s filters=%s", query, filters.model_dump())
        return await self.retrieve_projects(query, top_k, filters=None)

    @staticmethod
    def _compose_project_match_reasons(project: RetrievedProject, filters: Optional[QueryFilters]) -> List[str]:
        reasons: List[str] = []
        if project.match_reasons:
            reasons.extend([str(x).strip() for x in project.match_reasons if str(x).strip()])

        if filters:
            if filters.language and project.language and project.language.lower() == filters.language.lower():
                reasons.append(f"命中语言偏好：{project.language}")
            if filters.category and project.category == filters.category:
                reasons.append(f"命中类别偏好：{project.category}")
            if filters.min_stars is not None and (project.stars or 0) >= filters.min_stars:
                reasons.append(f"满足最低 stars：{project.stars} >= {filters.min_stars}")
            if filters.keywords:
                blob = " ".join(
                    [
                        project.repo_full_name.lower(),
                        (project.summary or "").lower(),
                        " ".join([str(x) for x in project.reasons]).lower(),
                        " ".join([str(x) for x in project.keywords]).lower(),
                        " ".join([str(x) for x in project.tech_stack]).lower(),
                        " ".join([str(x) for x in project.use_cases]).lower(),
                    ]
                )
                hits = [kw for kw in filters.keywords if kw and str(kw).lower() in blob][:3]
                if hits:
                    reasons.append("命中关键词：" + "、".join(hits))

        deduped: List[str] = []
        seen = set()
        for item in reasons:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= 6:
                break
        return deduped

    def _build_recommendation_basis(
        self,
        *,
        query: str,
        filters: Optional[QueryFilters],
        projects: List[RetrievedProject],
        retrieval_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        filter_lines = filters.to_explanation_lines() if filters else []
        global_reasons: List[str] = []
        if filter_lines:
            global_reasons.append("Query Parser 识别条件：" + "；".join(filter_lines))
        else:
            global_reasons.append("Query Parser 未识别明确过滤条件，主要依据语义相关性排序。")
        if retrieval_confidence is not None:
            global_reasons.append(f"检索置信度：{retrieval_confidence:.2f}")

        project_reasons: List[Dict[str, Any]] = []
        for project in projects[:5]:
            reasons = self._compose_project_match_reasons(project, filters)
            project_reasons.append(
                {
                    "repo_full_name": project.repo_full_name,
                    "reasons": reasons[:4],
                }
            )
        return {
            "query": query,
            "filters": filters.to_active_filter_dict() if filters else {},
            "global_reasons": global_reasons,
            "project_reasons": project_reasons,
        }

    @staticmethod
    def _format_recommendation_basis_text(basis: Dict[str, Any]) -> str:
        if not basis:
            return "无"
        lines: List[str] = []
        for item in basis.get("global_reasons", []) or []:
            lines.append(f"- {item}")
        for row in basis.get("project_reasons", []) or []:
            repo = row.get("repo_full_name")
            reasons = row.get("reasons") or []
            if repo and reasons:
                lines.append(f"- {repo}: " + "；".join([str(x) for x in reasons[:3]]))
        return "\n".join(lines) if lines else "无"

    def _format_projects_context(self, projects: List[RetrievedProject], filters: Optional[QueryFilters] = None) -> str:
        """格式化项目信息为上下文。"""
        if not projects:
            return "未找到相关项目。"

        context_parts = []
        for i, project in enumerate(projects, 1):
            stars_str = f"⭐{project.stars:,}" if project.stars else ""
            lang_str = f"[{project.language}]" if project.language else ""
            source_id = project.source_id or f"S{i}"
            heading = project.evidence_heading or project.evidence_section or "README"
            snippet = (project.evidence_chunk or "").strip()
            if len(snippet) > 220:
                snippet = snippet[:220] + "..."
            match_reasons = self._compose_project_match_reasons(project, filters)[:4]
            if not match_reasons:
                match_reasons = ["semantic recall hit"]

            project_info = f"""### [{source_id}] 项目 {i}: {project.repo_full_name}
- 语言：{lang_str}
- Stars: {stars_str}
- 分类：{project.category or '未分类'}
- 项目简介：{project.summary}
- 证据位置：{project.evidence_path or 'README.md'} / {heading}
- 推荐依据：
{chr(10).join(f'  - {r}' for r in match_reasons)}
- 核心特点:
{chr(10).join(f'  - {r}' for r in project.reasons)}
- 证据片段：{snippet or '（无）'}
- GitHub: {project.url}"""
            context_parts.append(project_info)

        return "\n\n".join(context_parts)

    @staticmethod
    def _build_history_projects(projects: Optional[List[RetrievedProject]]) -> List[Dict[str, Any]]:
        if not projects:
            return []
        return [
            {
                "repo_full_name": p.repo_full_name,
                "summary": p.summary,
                "similarity": p.similarity,
            }
            for p in projects
        ]

    def _persist_session_answer(
        self,
        session: Any,
        query: str,
        answer: str,
        projects: Optional[List[RetrievedProject]] = None,
    ) -> None:
        if not answer:
            return
        session.add_to_history(query, answer, self._build_history_projects(projects))
        session.query_count += 1

    async def _stream_chat_response(
        self,
        *,
        query: str,
        retrieval: bool,
        messages: List[Dict[str, str]],
        max_tokens: int,
        status_text: str = "正在思考...",
        temperature: float = 0.7,
    ) -> AsyncGenerator[Dict, None]:
        yield {"type": "status", "content": status_text}
        yield {"type": "content_start"}

        try:
            selected_model = self.select_model_for_query(query=query, retrieval=retrieval)
            response = self._create_chat_completion_with_fallback(
                model=selected_model,
                query=query,
                retrieval=retrieval,
                messages=messages,
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.request_timeout,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {"type": "content", "content": chunk.choices[0].delta.content}
        except Exception as e:
            err = self._classify_chat_error(e)
            logger.error(f"LLM 生成失败 code={err['code']} error={str(e)}")
            yield {
                "type": "error",
                "code": err["code"],
                "content": err["message"],
            }

        yield {"type": "done"}

    async def _stream_and_persist(
        self,
        *,
        session: Any,
        query: str,
        stream: AsyncGenerator[Dict, None],
        projects: Optional[List[RetrievedProject]] = None,
    ) -> AsyncGenerator[Dict, None]:
        full_answer = ""
        async for chunk in stream:
            if chunk.get("type") == "content" and chunk.get("content"):
                full_answer += chunk["content"]
            yield chunk
        self._persist_session_answer(session, query, full_answer, projects)

    async def _chat_without_retrieval(self, query: str) -> AsyncGenerator[Dict, None]:
        """不检索项目的纯对话模式。"""
        async for chunk in self._stream_chat_response(
            query=query,
            retrieval=False,
            messages=[
                {"role": "system", "content": self.CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=500,
        ):
            yield chunk

    async def _chat_no_match(self, query: str) -> AsyncGenerator[Dict, None]:
        """数据库中没有匹配项目时的对话模式"""
        async for chunk in self._stream_chat_response(
            query=query,
            retrieval=True,
            messages=[
                {"role": "system", "content": self.NO_MATCH_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"用户问题：{query}\n\n请回答用户的问题，并告知数据库中没有找到相关 GitHub Trending 项目。",
                },
            ],
            max_tokens=800,
        ):
            yield chunk

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

        if not self._should_use_rag(query, session):
            async for chunk in self._stream_and_persist(
                session=session,
                query=query,
                stream=self._chat_without_retrieval(query),
            ):
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

        if self._is_followup_query(query, session) and session.last_filters:
            logger.info(f"检测到追问，沿用上次过滤条件：{session.last_filters}")
            filters = self._sanitize_filters(session.last_filters)
        else:
            parsed_filters = await self.query_parser.parse(query)
            filters = self._sanitize_filters(parsed_filters)
            session.last_filters = filters if filters.has_filters() else None
            session.last_query_time = datetime.now()
        
        projects = await self._retrieve_projects_with_filter_fallback(query, top_k, filters=filters)

        if not projects:
            async for chunk in self._stream_and_persist(
                session=session,
                query=query,
                stream=self._chat_no_match(query),
            ):
                yield chunk
            return

        retrieval_confidence = self._compute_retrieval_confidence(projects)
        low_confidence_hit = retrieval_confidence < self.min_confidence
        allow_soft_answer = low_confidence_hit and self._is_planning_query(query)
        basis = self._build_recommendation_basis(
            query=query,
            filters=filters,
            projects=projects,
            retrieval_confidence=retrieval_confidence,
        )
        if low_confidence_hit and not allow_soft_answer:
            low_conf_answer = self._build_low_confidence_answer(query, projects, retrieval_confidence)
            yield {
                "type": "status",
                "content": "检索证据不足，已触发低置信拒答模板。"
            }
            yield {"type": "content_start"}
            yield {"type": "content", "content": low_conf_answer}
            self._persist_session_answer(session, query, low_conf_answer, projects)
            yield {"type": "done"}
            return
        if allow_soft_answer:
            logger.info(
                "low confidence but planning query, continue with soft warning answer: confidence=%.4f threshold=%.4f",
                retrieval_confidence,
                self.min_confidence,
            )

        yield {
            "type": "status",
            "content": f"找到 {len(projects)} 个相关项目，正在生成回答..."
        }

        yield {
            "type": "recommendation_basis",
            "basis": basis,
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
                    "url": p.url,
                    "match_reasons": self._compose_project_match_reasons(p, filters)[:4],
                }
                for p in projects
            ]
        }

        projects_context = self._format_projects_context(projects, filters=filters)
        prompt = self.RAG_PROMPT_TEMPLATE.format(
            query=query,
            recommendation_basis=self._format_recommendation_basis_text(basis),
            projects_context=projects_context
        )

        yield {
            "type": "content_start"
        }

        full_answer = ""
        if allow_soft_answer:
            low_conf_prefix = self._build_low_confidence_prefix(retrieval_confidence)
            full_answer += low_conf_prefix
            yield {
                "type": "content",
                "content": low_conf_prefix
            }
        try:
            selected_model = self.select_model_for_query(query=query, retrieval=True)
            response = self._create_chat_completion_with_fallback(
                model=selected_model,
                query=query,
                retrieval=True,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=self.rag_max_tokens,
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

            self._persist_session_answer(session, query, full_answer, projects)

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

