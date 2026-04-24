from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict
from datetime import date, timedelta
from time import perf_counter
import sys
import os
import json
import logging
import httpx
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.infrastructure.cache import AnalysisCache
from app.infrastructure.config import get_config
from app.knowledge.search import SearchService
from app.knowledge.search import derive_project_profile
from app.knowledge.chat import RAGChatService
from ..models import (
    DashboardResponse, ProjectCard, TrendsResponse, CategoryTrend, 
    LanguageTrend, HotProject, SearchResponse, SearchResult,
    ChatRequest, ProjectDetailResponse,
    DashboardInsightsResponse, DashboardSummary, DashboardTimelinePoint,
    DashboardDistributionItem, DashboardDecisionProject, DashboardActivityItem
)

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)

cache = AnalysisCache()
search_service: Optional[SearchService] = None
chat_service: Optional[RAGChatService] = None
search_service_init_error: Optional[str] = None
chat_service_init_error: Optional[str] = None


def warmup_runtime_services() -> None:
    """Eagerly initialize runtime services and trigger warmup tasks."""
    try:
        service = _get_chat_service()
        if getattr(service, "search_service", None):
            service.search_service.start_reranker_warmup()
            service.search_service.start_index_warmup()
        logger.info("runtime warmup triggered")
    except Exception as e:
        logger.warning("runtime warmup skipped: %s", e)


_TECH_HINTS = {
    "Python": ["python", "py", "fastapi", "flask", "django", "pytorch", "tensorflow"],
    "TypeScript": ["typescript", "ts", "next.js", "nestjs", "deno", "vue", "nuxt"],
    "JavaScript": ["javascript", "js", "node.js", "nodejs", "react", "vite"],
    "Go": ["golang", " go ", "gin", "fiber"],
    "Rust": ["rust", "cargo", "tokio"],
    "Java": ["spring", "java", "maven", "gradle"],
    "C++": ["c++", "cpp", "cmake"],
    "Docker": ["docker", "container", "k8s", "kubernetes"],
    "LLM": ["llm", "rag", "agent", "openai", "qwen", "gemma", "transformer"],
    "Data": ["pandas", "numpy", "spark", "etl", "analytics", "timeseries", "time series"],
}

_USE_CASE_HINTS = {
    "AI 助手": ["assistant", "copilot", "chatbot", "agent", "对话", "问答"],
    "数据分析": ["analytics", "analysis", "dashboard", "报表", "可视化", "预测"],
    "内容生产": ["content", "seo", "blog", "writing", "编辑", "生成"],
    "开发提效": ["developer", "ide", "coding", "devtool", "效率", "工程"],
    "自动化工作流": ["workflow", "automation", "自动化", "pipeline", "任务编排"],
    "本地化部署": ["self-host", "self host", "on-prem", "本地", "私有化", "离线"],
    "多模态创作": ["image", "video", "audio", "multimodal", "视觉", "语音"],
}


def _dedupe_tags(items: List[str], limit: int = 10) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw in items:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _infer_tags_from_text(text: str, mapping: dict, limit: int) -> List[str]:
    normalized = f" {text.lower()} "
    matched: List[str] = []
    for label, hints in mapping.items():
        if any(hint in normalized for hint in hints):
            matched.append(label)
    return _dedupe_tags(matched, limit=limit)


def _build_structured_fallback(
    *,
    summary: str,
    reasons: List[str],
    keywords: List[str],
    tech_stack: List[str],
    use_cases: List[str],
    basic: dict,
    suitable_for: List[str],
) -> tuple[List[str], List[str], List[str]]:
    description = str((basic or {}).get("description") or "")
    language = str((basic or {}).get("language") or "").strip()
    text_parts = [summary, description, *[str(r) for r in reasons], *[str(k) for k in keywords], *[str(s) for s in suitable_for]]
    corpus = " ".join(text_parts)
    corpus = re.sub(r"\s+", " ", corpus)

    normalized_keywords = _dedupe_tags(keywords, limit=10)
    if not normalized_keywords:
        normalized_keywords = _dedupe_tags(_infer_tags_from_text(corpus, _TECH_HINTS, limit=5) + _infer_tags_from_text(corpus, _USE_CASE_HINTS, limit=5), limit=10)

    normalized_tech = _dedupe_tags(tech_stack, limit=10)
    if not normalized_tech:
        inferred_tech = _infer_tags_from_text(corpus, _TECH_HINTS, limit=8)
        if language and language.lower() != "unknown":
            inferred_tech = [language, *inferred_tech]
        normalized_tech = _dedupe_tags(inferred_tech, limit=10)

    normalized_use_cases = _dedupe_tags(use_cases, limit=10)
    if not normalized_use_cases:
        inferred_cases = _infer_tags_from_text(corpus, _USE_CASE_HINTS, limit=8)
        normalized_use_cases = _dedupe_tags([*suitable_for, *inferred_cases], limit=10)

    return normalized_keywords, normalized_tech, normalized_use_cases


def _get_search_service() -> SearchService:
    global search_service, search_service_init_error
    if search_service is not None:
        return search_service
    if search_service_init_error:
        raise HTTPException(
            status_code=503,
            detail={"code": "SEARCH_SERVICE_UNAVAILABLE", "message": f"搜索服务不可用: {search_service_init_error}"},
        )
    try:
        search_service = SearchService()
        return search_service
    except Exception as e:
        search_service_init_error = str(e)
        logger.exception("搜索服务初始化失败")
        raise HTTPException(
            status_code=503,
            detail={"code": "SEARCH_SERVICE_INIT_FAILED", "message": f"搜索服务初始化失败: {search_service_init_error}"},
        )


def _get_chat_service() -> RAGChatService:
    global chat_service, chat_service_init_error
    if chat_service is not None:
        return chat_service
    if chat_service_init_error:
        raise HTTPException(
            status_code=503,
            detail={"code": "CHAT_SERVICE_UNAVAILABLE", "message": f"对话服务不可用: {chat_service_init_error}"},
        )
    try:
        chat_service = RAGChatService()
        return chat_service
    except Exception as e:
        chat_service_init_error = str(e)
        logger.exception("对话服务初始化失败")
        raise HTTPException(
            status_code=503,
            detail={"code": "CHAT_SERVICE_INIT_FAILED", "message": f"对话服务初始化失败: {chat_service_init_error}"},
        )


@router.get("/github/validate")
async def validate_github_token():
    """验证 GitHub Token 是否有效"""
    try:
        config = get_config()
        token = config.github.token
        
        if not token:
            return {
                "valid": False,
                "error": "GitHub Token 未配置",
                "message": "请在 .env 文件中设置 GITHUB_TOKEN"
            }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                "valid": True,
                "username": user_data.get("login"),
                "name": user_data.get("name"),
                "avatar_url": user_data.get("avatar_url"),
                "message": f"已登录为 {user_data.get('login')}"
            }
        elif response.status_code == 401:
            return {
                "valid": False,
                "error": "Token 无效或已过期",
                "message": "请检查 GITHUB_TOKEN 是否正确"
            }
        else:
            return {
                "valid": False,
                "error": f"验证失败: HTTP {response.status_code}",
                "message": response.text[:200]
            }
    except httpx.TimeoutException:
        return {
            "valid": False,
            "error": "请求超时",
            "message": "GitHub API 响应超时，请检查网络连接"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": "验证异常",
            "message": str(e)[:200]
        }


@router.get("/github/rate-limit")
async def get_github_rate_limit():
    """获取 GitHub API 速率限制"""
    try:
        config = get_config()
        token = config.github.token
        
        if not token:
            return {
                "error": "GitHub Token 未配置"
            }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.github.com/rate_limit",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
        
        if response.status_code == 200:
            data = response.json()
            core = data.get("resources", {}).get("core", {})
            return {
                "limit": core.get("limit"),
                "remaining": core.get("remaining"),
                "used": core.get("used"),
                "reset": core.get("reset"),
                "reset_time": date.fromtimestamp(core.get("reset", 0)) if core.get("reset") else None
            }
        else:
            return {
                "error": f"获取失败: HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "error": str(e)[:200]
        }

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(days: int = 1):
    """获取仪表盘数据，显示指定天数内的项目（默认今日）"""
    
    start_date = date.today() - timedelta(days=days-1)
    end_date = date.today()
    
    records = cache.get_trending_history(
        start_date=start_date,
        end_date=end_date
    )
    
    categorized = {
        "ai_ecosystem": [],
        "infra_and_tools": [],
        "product_and_ui": [],
        "knowledge_base": []
    }
    
    seen_repos = set()
    
    for record in records:
        repo_name = record["repo_full_name"]
        if repo_name in seen_repos:
            continue
        seen_repos.add(repo_name)
        
        category = record.get("category")
        if not category or category not in categorized:
            category = "infra_and_tools"
        
        analysis = cache.get(repo_name)
        
        project = ProjectCard(
            repo_name=repo_name,
            description=record.get("description") or "",
            summary=analysis.get("summary", "") if analysis else "",
            reasons=analysis.get("reasons", []) if analysis else [],
            keywords=analysis.get("keywords", []) if analysis else [],
            tech_stack=analysis.get("tech_stack", []) if analysis else [],
            use_cases=analysis.get("use_cases", []) if analysis else [],
            stars=record.get("stars", 0),
            stars_today=record.get("stars_today", 0),
            since_type=record.get("since_type"),
            language=record.get("language", "Unknown"),
            category=category,
            url=f"https://github.com/{repo_name}"
        )
        
        categorized[category].append(project)
    
    return DashboardResponse(
        ai_ecosystem=categorized["ai_ecosystem"][:10],
        infra_and_tools=categorized["infra_and_tools"][:10],
        product_and_ui=categorized["product_and_ui"][:10],
        knowledge_base=categorized["knowledge_base"][:10]
    )


def _parse_iso_date(value) -> Optional[date]:
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _build_day_list(start_date: date, end_date: date) -> List[date]:
    days: List[date] = []
    cursor = start_date
    while cursor <= end_date:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _build_distribution(counter: Dict[str, int], total: int) -> List[DashboardDistributionItem]:
    if total <= 0:
        return []
    return [
        DashboardDistributionItem(
            name=name,
            count=count,
            percentage=round((count / total) * 100, 1),
        )
        for name, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


@router.get("/dashboard/insights", response_model=DashboardInsightsResponse)
async def get_dashboard_insights(days: int = Query(7, ge=1, le=30)):
    """仪表盘聚合数据：总览、折线、分布、决策层、活动层。"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    records = cache.get_trending_history(start_date=start_date, end_date=end_date)

    day_list = _build_day_list(start_date=start_date, end_date=end_date)
    daily_repo_stats: Dict[str, Dict[str, dict]] = {day.isoformat(): {} for day in day_list}
    latest_stars_map: Dict[str, int] = {}

    for record in records:
        parsed_date = _parse_iso_date(record.get("record_date"))
        if parsed_date is None:
            continue
        day_key = parsed_date.isoformat()
        if day_key not in daily_repo_stats:
            continue

        repo_name = str(record.get("repo_full_name") or "").strip()
        if not repo_name:
            continue

        stars_today = int(record.get("stars_today") or 0)
        rank = int(record.get("rank") or 999)
        language = str(record.get("language") or "Unknown").strip() or "Unknown"
        category = str(record.get("category") or "infra_and_tools").strip() or "infra_and_tools"
        stars = int(record.get("stars") or 0)

        if repo_name not in latest_stars_map:
            latest_stars_map[repo_name] = stars

        current = daily_repo_stats[day_key].get(repo_name)
        if current is None:
            daily_repo_stats[day_key][repo_name] = {
                "stars_today": stars_today,
                "rank": rank,
                "language": language,
                "category": category,
            }
            continue

        current["stars_today"] = max(int(current.get("stars_today") or 0), stars_today)
        current["rank"] = min(int(current.get("rank") or 999), rank)
        if (current.get("language") or "Unknown") == "Unknown" and language != "Unknown":
            current["language"] = language
        if (current.get("category") or "infra_and_tools") == "infra_and_tools" and category != "infra_and_tools":
            current["category"] = category

    repo_stats: Dict[str, dict] = {}
    for day_key in sorted(daily_repo_stats.keys()):
        for repo_name, item in daily_repo_stats[day_key].items():
            stat = repo_stats.setdefault(
                repo_name,
                {
                    "appearances": 0,
                    "rank_sum": 0.0,
                    "rank_count": 0,
                    "last_seen": day_key,
                    "category": item.get("category") or "infra_and_tools",
                    "language": item.get("language") or "Unknown",
                    "latest_stars_today": 0,
                    "peak_stars_today": 0,
                },
            )

            stat["appearances"] += 1
            rank = int(item.get("rank") or 999)
            if rank < 999:
                stat["rank_sum"] += rank
                stat["rank_count"] += 1

            if day_key >= stat["last_seen"]:
                stat["last_seen"] = day_key
                stat["latest_stars_today"] = int(item.get("stars_today") or 0)
                stat["category"] = item.get("category") or stat["category"]
                stat["language"] = item.get("language") or stat["language"]

            stat["peak_stars_today"] = max(stat["peak_stars_today"], int(item.get("stars_today") or 0))

    today_key = end_date.isoformat()
    today_repo_stats = daily_repo_stats.get(today_key, {})

    summary = DashboardSummary(
        total_projects=len(repo_stats),
        today_projects=len(today_repo_stats),
        today_stars=sum(int(item.get("stars_today") or 0) for item in today_repo_stats.values()),
    )

    stars_timeline: List[DashboardTimelinePoint] = []
    seen_repos_timeline = set()
    for day in day_list:
        key = day.isoformat()
        repos = daily_repo_stats.get(key, {})
        stars_total = sum(int(item.get("stars_today") or 0) for item in repos.values())
        seen_repos_timeline.update(repos.keys())
        stars_timeline.append(
            DashboardTimelinePoint(
                date=key,
                label=f"{day.month}/{day.day}",
                stars_today=stars_total,
                projects=len(repos),
                total_projects=len(seen_repos_timeline),
            )
        )

    category_counts: Dict[str, int] = {}
    language_counts: Dict[str, int] = {}
    for stat in repo_stats.values():
        category = str(stat.get("category") or "infra_and_tools")
        language = str(stat.get("language") or "Unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
        language_counts[language] = language_counts.get(language, 0) + 1

    category_distribution = _build_distribution(category_counts, summary.total_projects)
    language_distribution = _build_distribution(language_counts, summary.total_projects)[:10]

    ranked_projects = []
    for repo_name, stat in repo_stats.items():
        rank_count = int(stat.get("rank_count") or 0)
        avg_rank = round(float(stat.get("rank_sum") or 0.0) / rank_count, 1) if rank_count > 0 else 999.0
        ranked_projects.append(
            (
                repo_name,
                stat,
                avg_rank,
                int(latest_stars_map.get(repo_name) or 0),
            )
        )

    ranked_projects.sort(
        key=lambda row: (
            int(row[1].get("latest_stars_today") or 0),
            int(row[1].get("appearances") or 0),
            -float(row[2]),
            int(row[3]),
        ),
        reverse=True,
    )

    decision_projects = [
        DashboardDecisionProject(
            repo_name=repo_name,
            category=str(stat.get("category") or "infra_and_tools"),
            language=str(stat.get("language") or "Unknown"),
            stars=int(latest_stars),
            stars_today=int(stat.get("latest_stars_today") or 0),
            appearances=int(stat.get("appearances") or 0),
            avg_rank=avg_rank if avg_rank < 999 else 0.0,
            last_seen=str(stat.get("last_seen") or today_key),
            url=f"https://github.com/{repo_name}",
        )
        for repo_name, stat, avg_rank, latest_stars in ranked_projects[:12]
    ]

    recent_activities: List[DashboardActivityItem] = []
    if summary.today_projects > 0:
        recent_activities.append(
            DashboardActivityItem(
                date=today_key,
                type="system",
                title="今日趋势数据已更新",
                detail=f"收录 {summary.today_projects} 个项目，累计新增 {summary.today_stars} stars",
            )
        )

    for project in decision_projects[:8]:
        activity_type = "hot" if project.stars_today >= 20 else "watch"
        recent_activities.append(
            DashboardActivityItem(
                date=project.last_seen,
                type=activity_type,
                title=project.repo_name,
                detail=f"今日 +{project.stars_today} stars · 上榜 {project.appearances} 次 · 均位 #{project.avg_rank}",
            )
        )

    if category_distribution:
        category = category_distribution[0]
        recent_activities.append(
            DashboardActivityItem(
                date=today_key,
                type="insight",
                title="分类热度",
                detail=f"{category.name} 当前占比最高（{category.percentage}%）",
            )
        )

    return DashboardInsightsResponse(
        period=f"最近 {days} 天",
        summary=summary,
        stars_timeline=stars_timeline,
        category_distribution=category_distribution,
        language_distribution=language_distribution,
        decision_projects=decision_projects,
        recent_activities=recent_activities[:12],
    )


@router.get("/projects/{repo_full_name:path}", response_model=ProjectDetailResponse)
async def get_project_detail(repo_full_name: str):
    """获取项目详情页数据（repo 基础信息 + 结构化标签 + 趋势摘要 + 证据片段）。"""
    detail = cache.get_project_detail(repo_full_name=repo_full_name, history_limit=12)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PROJECT_NOT_FOUND",
                "message": f"项目不存在: {repo_full_name}",
            },
        )

    basic = detail.get("basic") or {}
    summary = str(detail.get("summary") or "")
    reasons_raw = detail.get("reasons")
    keywords_raw = detail.get("keywords")
    tech_stack_raw = detail.get("tech_stack")
    use_cases_raw = detail.get("use_cases")
    reasons = reasons_raw if isinstance(reasons_raw, list) else []
    keywords = keywords_raw if isinstance(keywords_raw, list) else []
    tech_stack = tech_stack_raw if isinstance(tech_stack_raw, list) else []
    use_cases = use_cases_raw if isinstance(use_cases_raw, list) else []
    trend_summary = detail.get("trend_summary") or {}

    profile = derive_project_profile(
        summary=summary,
        reasons=reasons,
        keywords=keywords,
        tech_stack=tech_stack,
        use_cases=use_cases,
        trend_summary=trend_summary,
        basic=basic,
        evidence_text=((detail.get("evidence") or {}).get("chunk_text") or ""),
    )
    suitable_for = profile.get("suitable_for", [])
    keywords, tech_stack, use_cases = _build_structured_fallback(
        summary=summary,
        reasons=reasons,
        keywords=keywords,
        tech_stack=tech_stack,
        use_cases=use_cases,
        basic=basic,
        suitable_for=suitable_for if isinstance(suitable_for, list) else [],
    )

    payload = {
        "basic": {
            "repo_full_name": basic.get("repo_full_name") or repo_full_name,
            "url": basic.get("url") or f"https://github.com/{repo_full_name}",
            "description": basic.get("description") or "",
            "language": basic.get("language") or "Unknown",
            "category": basic.get("category") or "infra_and_tools",
            "stars": int(basic.get("stars") or 0),
            "stars_today": int(basic.get("stars_today") or 0),
            "rank": basic.get("rank"),
            "since_type": basic.get("since_type"),
            "repo_updated_at": basic.get("repo_updated_at"),
            "first_seen": basic.get("first_seen"),
            "last_seen": basic.get("last_seen"),
            "total_appearances": int(basic.get("total_appearances") or 0),
        },
        "summary": summary,
        "reasons": reasons,
        "keywords": keywords,
        "tech_stack": tech_stack,
        "use_cases": use_cases,
        "suitable_for": suitable_for if isinstance(suitable_for, list) else [],
        "complexity": profile.get("complexity", "unknown"),
        "maturity": profile.get("maturity", "unknown"),
        "risk_notes": profile.get("risk_notes", []),
        "evidence": {
            "chunk_id": (detail.get("evidence") or {}).get("chunk_id"),
            "chunk_text": (detail.get("evidence") or {}).get("chunk_text") or "",
            "section": (detail.get("evidence") or {}).get("section"),
            "path": (detail.get("evidence") or {}).get("path"),
            "heading": (detail.get("evidence") or {}).get("heading"),
            "updated_at": (detail.get("evidence") or {}).get("updated_at"),
        },
        "trend_summary": {
            "total_records": int(trend_summary.get("total_records") or 0),
            "first_seen": trend_summary.get("first_seen"),
            "last_seen": trend_summary.get("last_seen"),
            "best_rank": trend_summary.get("best_rank"),
            "latest_stars": int(trend_summary.get("latest_stars") or 0),
            "avg_stars_today": float(trend_summary.get("avg_stars_today") or 0.0),
        },
        "trend_history": detail.get("trend_history") or [],
    }
    return ProjectDetailResponse(**payload)

@router.get("/trends", response_model=TrendsResponse)
async def get_trends(days: int = Query(7, ge=1, le=30)):
    """获取趋势分析数据"""
    
    start_date = date.today() - timedelta(days=days)
    records = cache.get_trending_history(
        start_date=start_date,
        end_date=date.today()
    )
    
    category_counts = {}
    language_counts = {}
    project_appearances = {}
    
    for record in records:
        category = record.get("category") or "unknown"
        category_counts[category] = category_counts.get(category, 0) + 1
        
        language = record.get("language") or "Unknown"
        language_counts[language] = language_counts.get(language, 0) + 1
        
        repo_name = record["repo_full_name"]
        if repo_name not in project_appearances:
            project_appearances[repo_name] = {
                "count": 0,
                "ranks": [],
                "last_seen": record["record_date"],
                "category": category
            }
        project_appearances[repo_name]["count"] += 1
        project_appearances[repo_name]["ranks"].append(record.get("rank", 999))
        if record["record_date"] > project_appearances[repo_name]["last_seen"]:
            project_appearances[repo_name]["last_seen"] = record["record_date"]
    
    total = len(records)
    
    category_trends = [
        CategoryTrend(
            category=cat,
            count=count,
            percentage=round(count / total * 100, 1) if total > 0 else 0
        )
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    language_trends = [
        LanguageTrend(
            language=lang,
            count=count,
            percentage=round(count / total * 100, 1) if total > 0 else 0
        )
        for lang, count in sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    
    hot_projects = [
        HotProject(
            repo_name=repo,
            appearances=data["count"],
            avg_rank=round(sum(data["ranks"]) / len(data["ranks"]), 1),
            last_seen=data["last_seen"],
            category=data["category"]
        )
        for repo, data in sorted(
            project_appearances.items(),
            key=lambda x: (x[1]["count"], -sum(x[1]["ranks"]) / len(x[1]["ranks"])),
            reverse=True
        )[:10]
    ]
    
    return TrendsResponse(
        period=f"最近 {days} 天",
        category_trends=category_trends,
        language_trends=language_trends,
        hot_projects=hot_projects,
        total_projects=len(project_appearances),
        total_records=total
    )

@router.get("/search", response_model=SearchResponse)
async def search_projects(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    coarse_top_k: int = Query(20, ge=5, le=100, description="粗排数量"),
    final_top_k: int = Query(5, ge=1, le=20, description="最终返回数量")
):
    """
    智能搜索项目
    
    搜索流程：
    1. 粗排：混合检索（向量 + BM25）→ RRF 融合 → top coarse_top_k
    2. 精排：Cross-Encoder 重排序 → top final_top_k
    
    - **q**: 搜索关键词，支持自然语言查询
    - **coarse_top_k**: 粗排数量，默认20个
    - **final_top_k**: 最终返回数量，默认5个
    """
    
    service = _get_search_service()
    results = await service.search_projects(
        query=q,
        coarse_top_k=coarse_top_k,
        final_top_k=final_top_k
    )
    
    search_results = [
        SearchResult(
            repo_full_name=result.get("repo_full_name", ""),
            summary=result.get("summary", ""),
            reasons=result.get("reasons", []),
            similarity=result.get("rerank_score", 0.0),
            category=result.get("category"),
            language=result.get("language"),
            stars=result.get("stars"),
            keywords=result.get("keywords", []),
            tech_stack=result.get("tech_stack", []),
            use_cases=result.get("use_cases", [])
        )
        for result in results
    ]
    
    return SearchResponse(
        query=q,
        results=search_results,
        total=len(search_results)
    )

@router.post("/search/index")
async def index_projects():
    """重新索引所有项目（生成向量）"""
    service = _get_search_service()
    stats = await service.reindex_all_projects()
    
    return {
        "message": "索引完成",
        "stats": stats
    }

@router.get("/search/stats")
async def get_search_stats():
    """获取搜索统计信息"""
    service = _get_search_service()
    stats = service.get_search_stats()
    
    return stats


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    智能对话（流式输出）
    
    基于用户问题检索相关项目，流式生成智能回答
    使用 Server-Sent Events (SSE) 格式
    支持会话管理，传入 session_id 可保持上下文
    """
    
    started = perf_counter()
    service = _get_chat_service()
    model_name = service.preview_model_for_query(request.query)

    async def generate():
        resolved_session_id = request.session_id or "-"
        last_error_code = None
        try:
            async for chunk in service.chat_stream(
                query=request.query,
                top_k=request.top_k,
                session_id=request.session_id
            ):
                if chunk.get("type") == "session" and chunk.get("session_id"):
                    resolved_session_id = chunk.get("session_id")
                if chunk.get("type") == "error":
                    last_error_code = chunk.get("code") or "CHAT_STREAM_ERROR"
                data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {data}\n\n"
        except Exception as e:
            last_error_code = "CHAT_STREAM_INTERNAL_ERROR"
            fallback = {
                "type": "error",
                "code": last_error_code,
                "content": "流式对话异常中断，请重试。",
            }
            logger.exception("chat stream crashed: %s", str(e))
            yield f"data: {json.dumps(fallback, ensure_ascii=False)}\n\n"

        latency_ms = int((perf_counter() - started) * 1000)
        if last_error_code:
            logger.warning(
                "chat stream finished with error code=%s",
                last_error_code,
                extra={
                    "session_id": resolved_session_id,
                    "model": model_name,
                    "latency_ms": latency_ms,
                },
            )
        else:
            logger.info(
                "chat stream completed",
                extra={
                    "session_id": resolved_session_id,
                    "model": model_name,
                    "latency_ms": latency_ms,
                },
            )
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """
    获取会话信息
    
    返回会话的历史记录和状态
    """
    from app.infrastructure.session import get_session_manager
    
    session_manager = get_session_manager()
    session = session_manager.get(session_id)
    
    if not session:
        return {
            "error": "会话不存在或已过期",
            "session_id": session_id
        }
    
    return {
        "session_id": session.session_id,
        "created_at": session.created_at.isoformat(),
        "last_active": session.last_active.isoformat(),
        "query_count": session.query_count,
        "history": session.history
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话
    
    清除会话的所有状态和历史记录
    """
    from app.infrastructure.session import get_session_manager
    
    session_manager = get_session_manager()
    deleted = session_manager.delete(session_id)
    
    return {
        "success": deleted,
        "session_id": session_id
    }


@router.get("/sessions/stats")
async def get_sessions_stats():
    """
    获取会话统计信息
    
    返回当前活跃会话数量等信息
    """
    from app.infrastructure.session import get_session_manager
    
    session_manager = get_session_manager()
    
    return {
        "active_sessions": session_manager.get_active_count(),
        "total_sessions": len(session_manager.sessions)
    }
