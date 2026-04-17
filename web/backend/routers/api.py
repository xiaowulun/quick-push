from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import date, timedelta
from time import perf_counter
import sys
import os
import json
import logging
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.infrastructure.cache import AnalysisCache
from app.infrastructure.config import get_config
from app.infrastructure.logging import get_request_id
from app.knowledge.search import SearchService
from app.knowledge.chat import RAGChatService
from ..models import (
    DashboardResponse, ProjectCard, TrendsResponse, CategoryTrend, 
    LanguageTrend, HotProject, SearchResponse, SearchResult,
    ChatRequest, ChatResponse, ChatProject
)

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)

cache = AnalysisCache()
search_service: Optional[SearchService] = None
chat_service: Optional[RAGChatService] = None
search_service_init_error: Optional[str] = None
chat_service_init_error: Optional[str] = None


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
            stars=record.get("stars", 0),
            stars_today=record.get("stars_today", 0),
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


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    智能对话（非流式）
    
    基于用户问题检索相关项目，生成智能回答
    支持会话管理，传入 session_id 可保持上下文
    """
    
    started = perf_counter()
    service = _get_chat_service()
    model_name = getattr(service, "model", "-")
    req_session_id = request.session_id or "-"

    result = await service.chat(
        query=request.query,
        top_k=request.top_k,
        session_id=request.session_id
    )

    latency_ms = int((perf_counter() - started) * 1000)
    resolved_session_id = result.get("session_id") or req_session_id
    request_id = get_request_id()

    if not result.get("success", False):
        status_code = int(result.get("status_code") or 500)
        error_code = result.get("error_code") or "CHAT_INTERNAL_ERROR"
        error_message = result.get("error_message") or result.get("answer") or "对话请求失败"
        logger.warning(
            "chat request failed code=%s status=%s",
            error_code,
            status_code,
            extra={
                "session_id": resolved_session_id,
                "model": model_name,
                "latency_ms": latency_ms,
            },
        )
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": error_code,
                "message": error_message,
                "request_id": request_id,
                "session_id": resolved_session_id,
            },
        )

    logger.info(
        "chat request completed",
        extra={
            "session_id": resolved_session_id,
            "model": model_name,
            "latency_ms": latency_ms,
        },
    )
    
    return ChatResponse(
        answer=result["answer"],
        projects=[
            ChatProject(
                repo_full_name=p["repo_full_name"],
                summary=p["summary"],
                similarity=p["similarity"],
                language=p.get("language"),
                stars=p.get("stars"),
                url=p["url"]
            )
            for p in result["projects"]
        ],
        success=result["success"],
        session_id=result["session_id"]
    )


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
    model_name = getattr(service, "model", "-")

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
