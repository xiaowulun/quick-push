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
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.infrastructure.cache import AnalysisCache
from app.infrastructure.config import get_config
from app.infrastructure.session import get_session_manager
from app.knowledge.search import SearchService
from app.knowledge.search import derive_project_profile
from app.knowledge.chat import RAGChatService
from app.knowledge.query_parser import QueryFilters, get_query_parser
from ..models import (
    DashboardResponse,
    TrendsResponse,
    SearchResponse,
    SearchResult,
    ChatRequest,
    ProjectDetailResponse,
    DashboardInsightsResponse,
)
from ..services.dashboard_service import (
    build_dashboard_insights_response,
    build_dashboard_response,
    build_trends_response,
)

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)

cache = AnalysisCache()
search_service: Optional[SearchService] = None
chat_service: Optional[RAGChatService] = None
search_service_init_error: Optional[str] = None
chat_service_init_error: Optional[str] = None


class CompareScoreRequest(BaseModel):
    repo_names: List[str] = Field(default_factory=list)


class AssistantRecommendRequest(BaseModel):
    query: str = ""
    repo_names: List[str] = Field(default_factory=list)


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
    "AI Assistant": ["assistant", "copilot", "chatbot", "agent"],
    "Data Analytics": ["analytics", "analysis", "dashboard", "report", "forecast"],
    "Content Generation": ["content", "seo", "blog", "writing"],
    "Developer Tooling": ["developer", "ide", "coding", "devtool"],
    "Workflow Automation": ["workflow", "automation", "pipeline"],
    "Self Hosting": ["self-host", "self host", "on-prem"],
    "Multimodal": ["image", "video", "audio", "multimodal"],
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


def _score_clamp(value: float) -> float:
    return round(max(1.0, min(5.0, float(value))), 1)


def _safe_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _build_match_reasons_from_result(
    *,
    query: str,
    filters: Optional[QueryFilters],
    result: Dict[str, object],
) -> List[str]:
    reasons: List[str] = []
    if isinstance(result.get("match_reasons"), list):
        reasons.extend([str(x).strip() for x in result.get("match_reasons", []) if str(x or "").strip()])

    score = float(result.get("rerank_score") or result.get("similarity") or 0.0)
    if score:
        reasons.append(f"semantic relevance high (score={score:.3f})")

    language = str(result.get("language") or "").strip()
    category = str(result.get("category") or "").strip()
    stars = int(result.get("stars") or 0)
    if language:
        reasons.append(f"language match: {language}")
    if category:
        reasons.append(f"category match: {category}")

    if filters:
        if filters.language and language.lower() == filters.language.lower():
            reasons.append(f"hits language filter: {language}")
        if filters.category and category == filters.category:
            reasons.append(f"hits category filter: {category}")
        if filters.min_stars is not None and stars >= filters.min_stars:
            reasons.append(f"meets stars threshold: {stars} >= {filters.min_stars}")
        if filters.keywords:
            content = " ".join(
                [
                    str(result.get("repo_full_name") or "").lower(),
                    str(result.get("summary") or "").lower(),
                    " ".join([str(x) for x in _safe_list(result.get("reasons"))]).lower(),
                    " ".join([str(x) for x in _safe_list(result.get("keywords"))]).lower(),
                    " ".join([str(x) for x in _safe_list(result.get("tech_stack"))]).lower(),
                    " ".join([str(x) for x in _safe_list(result.get("use_cases"))]).lower(),
                ]
            )
            hits = [kw for kw in filters.keywords if kw and str(kw).lower() in content][:3]
            if hits:
                reasons.append("hits keywords: " + ", ".join(hits))

    for src in _safe_list(result.get("reasons"))[:2]:
        reasons.append(f"retrieval evidence: {src}")

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

def _extract_risk_flags(risk_notes: List[str], stars_today: int) -> List[Dict[str, str]]:
    flags: List[Dict[str, str]] = []
    for note in risk_notes[:3]:
        text = str(note or "").strip()
        if not text:
            continue
        lowered = text.lower()
        risk_type = "general"
        level = "medium"
        if "license" in lowered:
            risk_type = "license"
        elif "maint" in lowered or "stale" in lowered:
            risk_type = "maintenance"
        elif "security" in lowered or "cve" in lowered:
            risk_type = "security"
            level = "high"
        elif "dependency" in lowered:
            risk_type = "dependency"

        if any(word in lowered for word in ("high", "critical")):
            level = "high"
        elif any(word in lowered for word in ("low",)):
            level = "low"

        flags.append({"type": risk_type, "level": level, "text": text})

    if not flags and stars_today <= 2:
        flags.append({"type": "maintenance", "level": "low", "text": "Recent activity is low; watch maintainer responsiveness."})
    return flags

def _compute_project_score(
    *,
    card: Dict[str, object],
    detail: Optional[Dict[str, object]],
    keywords: List[str],
    tech_stack: List[str],
    use_cases: List[str],
) -> Dict[str, object]:
    stars = int(card.get("stars") or 0)
    stars_today = int(card.get("stars_today") or 0)
    reasons_count = len(_safe_list(card.get("reasons")))
    summary_len = len(str(card.get("summary") or ""))
    description_len = len(str(card.get("description") or ""))

    detail_obj = detail or {}
    trend_summary = detail_obj.get("trend_summary") if isinstance(detail_obj.get("trend_summary"), dict) else {}
    total_records = int((trend_summary or {}).get("total_records") or 0)
    evidence = detail_obj.get("evidence") if isinstance(detail_obj.get("evidence"), dict) else {}
    evidence_len = len(str((evidence or {}).get("chunk_text") or ""))
    risk_notes = _safe_list(detail_obj.get("risk_notes"))

    activity = _score_clamp(2.0 + min(2.0, stars_today / 30.0) + min(1.0, total_records / 14.0))
    community = _score_clamp(
        1.8 + min(1.6, stars / 60000.0) + min(1.0, reasons_count / 4.0) + min(0.6, len(keywords) / 6.0)
    )
    docs = _score_clamp(
        1.8 + min(1.2, summary_len / 280.0) + min(0.7, description_len / 160.0) + min(1.3, evidence_len / 650.0)
    )

    security_penalty = min(2.2, len(risk_notes) * 0.7)
    security = _score_clamp(4.6 - security_penalty)
    if not risk_notes and stars_today >= 20:
        security = _score_clamp(security + 0.2)

    usability = _score_clamp(
        2.0 + min(1.2, len(use_cases) / 4.0) + min(1.0, len(tech_stack) / 6.0) + (0.4 if reasons_count else 0.0)
    )

    overall = round((activity + community + docs + security + usability) / 5.0, 2)
    return {
        "overall_score": overall,
        "dimensions": {
            "activity": activity,
            "community": community,
            "docs": docs,
            "security": security,
            "usability": usability,
        },
        "risk_flags": _extract_risk_flags(risk_notes=risk_notes, stars_today=stars_today),
    }


def _collect_discover_projects(days: int, interests: List[str], limit: int) -> Dict[str, object]:
    _, _, records = _load_records_for_days(days)
    dashboard = build_dashboard_response(records, analysis_lookup=cache.get)

    cards: List[Dict[str, object]] = []
    for section in (
        dashboard.ai_ecosystem,
        dashboard.infra_and_tools,
        dashboard.product_and_ui,
        dashboard.knowledge_base,
    ):
        for row in section:
            cards.append(row.model_dump())

    cards.sort(key=lambda item: (int(item.get("stars_today") or 0), int(item.get("stars") or 0)), reverse=True)

    interest_terms = [str(term or "").strip().lower() for term in interests if str(term or "").strip()]
    selected: List[Dict[str, object]] = []
    for card in cards:
        searchable = " ".join(
            [
                str(card.get("repo_name") or ""),
                str(card.get("description") or ""),
                str(card.get("summary") or ""),
                " ".join(_safe_list(card.get("reasons"))),
                " ".join(_safe_list(card.get("keywords"))),
                " ".join(_safe_list(card.get("tech_stack"))),
                " ".join(_safe_list(card.get("use_cases"))),
            ]
        ).lower()
        if interest_terms and not any(term in searchable for term in interest_terms):
            continue

        repo_name = str(card.get("repo_name") or "").strip()
        if not repo_name:
            continue

        try:
            detail = cache.get_project_detail(repo_full_name=repo_name, history_limit=12) or {}
            profile = derive_project_profile(
                summary=str(card.get("summary") or ""),
                reasons=_safe_list(card.get("reasons")),
                keywords=_safe_list(card.get("keywords")),
                tech_stack=_safe_list(card.get("tech_stack")),
                use_cases=_safe_list(card.get("use_cases")),
                trend_summary=(detail.get("trend_summary") or {}) if isinstance(detail, dict) else {},
                basic=(detail.get("basic") or {}) if isinstance(detail, dict) else {},
                evidence_text=((detail.get("evidence") or {}).get("chunk_text") or "") if isinstance(detail, dict) else "",
                allow_llm=False,
            )
            keywords, tech_stack, use_cases = _build_structured_fallback(
                summary=str(card.get("summary") or ""),
                reasons=_safe_list(card.get("reasons")),
                keywords=_safe_list(card.get("keywords")),
                tech_stack=_safe_list(card.get("tech_stack")),
                use_cases=_safe_list(card.get("use_cases")),
                basic=(detail.get("basic") or {}) if isinstance(detail, dict) else {},
                suitable_for=_safe_list(profile.get("suitable_for")),
            )
            detail_basic = (detail.get("basic") or {}) if isinstance(detail, dict) else {}
            score = _compute_project_score(card=card, detail=detail, keywords=keywords, tech_stack=tech_stack, use_cases=use_cases)

            selected.append(
                {
                    **card,
                    "keywords": keywords,
                    "tech_stack": tech_stack,
                    "use_cases": use_cases,
                    "suitable_for": _safe_list(profile.get("suitable_for")),
                    "complexity": str(profile.get("complexity") or "unknown"),
                    "maturity": str(profile.get("maturity") or "unknown"),
                    "risk_notes": _safe_list(profile.get("risk_notes")),
                    **score,
                }
            )
        except Exception as exc:
            logger.warning("discover feed item fallback for %s: %s", repo_name, exc)
            selected.append(
                {
                    **card,
                    "keywords": _safe_list(card.get("keywords")),
                    "tech_stack": _safe_list(card.get("tech_stack")),
                    "use_cases": _safe_list(card.get("use_cases")),
                    "suitable_for": [],
                    "complexity": "unknown",
                    "maturity": "unknown",
                    "risk_notes": [],
                    "overall_score": 3.0,
                    "dimensions": {
                        "activity": 3.0,
                        "community": 3.0,
                        "docs": 3.0,
                        "security": 3.0,
                        "usability": 3.0,
                    },
                    "risk_flags": [],
                }
            )

        if len(selected) >= limit:
            break

    return {
        "items": selected,
        "total": len(selected),
        "data_date": dashboard.data_date,
        "is_fresh_today": dashboard.is_fresh_today,
    }


def _resolve_compare_item(repo_name: str) -> Optional[Dict[str, object]]:
    detail = cache.get_project_detail(repo_full_name=repo_name, history_limit=12)
    if not detail:
        return None

    basic = detail.get("basic") if isinstance(detail.get("basic"), dict) else {}
    summary = str(detail.get("summary") or "")
    reasons = _safe_list(detail.get("reasons"))
    keywords = _safe_list(detail.get("keywords"))
    tech_stack = _safe_list(detail.get("tech_stack"))
    use_cases = _safe_list(detail.get("use_cases"))

    profile = derive_project_profile(
        summary=summary,
        reasons=reasons,
        keywords=keywords,
        tech_stack=tech_stack,
        use_cases=use_cases,
        trend_summary=(detail.get("trend_summary") or {}) if isinstance(detail, dict) else {},
        basic=basic,
        evidence_text=((detail.get("evidence") or {}).get("chunk_text") or ""),
        allow_llm=False,
    )
    keywords, tech_stack, use_cases = _build_structured_fallback(
        summary=summary,
        reasons=reasons,
        keywords=keywords,
        tech_stack=tech_stack,
        use_cases=use_cases,
        basic=basic,
        suitable_for=_safe_list(profile.get("suitable_for")),
    )

    card = {
        "repo_name": repo_name,
        "description": str(basic.get("description") or ""),
        "summary": summary,
        "reasons": reasons,
        "stars": int(basic.get("stars") or 0),
        "stars_today": int(basic.get("stars_today") or 0),
        "language": str(basic.get("language") or "Unknown"),
        "category": str(basic.get("category") or "infra_and_tools"),
        "url": str(basic.get("url") or f"https://github.com/{repo_name}"),
    }
    score = _compute_project_score(card=card, detail=detail, keywords=keywords, tech_stack=tech_stack, use_cases=use_cases)

    return {
        **card,
        "keywords": keywords,
        "tech_stack": tech_stack,
        "use_cases": use_cases,
        "risk_notes": _safe_list(profile.get("risk_notes")),
        **score,
    }


def _build_recommendation(profile_query: str, items: List[Dict[str, object]]) -> Dict[str, object]:
    query = str(profile_query or "").lower()
    weights = {"activity": 0.2, "community": 0.2, "docs": 0.2, "security": 0.2, "usability": 0.2}

    if any(word in query for word in ("mvp", "launch", "pilot", "fast")):
        weights = {"activity": 0.3, "community": 0.15, "docs": 0.2, "security": 0.1, "usability": 0.25}
    elif any(word in query for word in ("security", "compliance", "enterprise")):
        weights = {"activity": 0.15, "community": 0.15, "docs": 0.2, "security": 0.35, "usability": 0.15}
    elif any(word in query for word in ("community", "ecosystem", "active", "star")):
        weights = {"activity": 0.25, "community": 0.35, "docs": 0.15, "security": 0.1, "usability": 0.15}

    ranked: List[Dict[str, object]] = []
    for item in items:
        dimensions = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else {}
        weighted = 0.0
        for key, w in weights.items():
            weighted += float(dimensions.get(key) or 0.0) * w
        ranked.append({**item, "weighted_score": round(weighted, 2)})

    ranked.sort(key=lambda row: float(row.get("weighted_score") or 0.0), reverse=True)
    if not ranked:
        return {
            "decision": "hold",
            "reason": "No valid project candidates found for recommendation.",
            "weights": weights,
            "projects": [],
            "followups": [],
        }

    best = ranked[0]
    best_weighted = float(best.get("weighted_score") or 0.0)
    best_security = float(((best.get("dimensions") or {}).get("security")) or 0.0)
    best_risk_count = len(_safe_list((best.get("risk_notes") or [])))

    if best_weighted >= 4.2 and best_security >= 3.8 and best_risk_count <= 1:
        decision = "go"
    elif best_weighted >= 3.5:
        decision = "go_with_guardrails"
    else:
        decision = "hold"

    reason = (
        f"Top candidate: {best.get('repo_name', 'unknown')} with weighted score {best_weighted:.2f}. "
        f"Security={best_security:.1f}, risk_notes={best_risk_count}."
    )
    followups = [
        "Review dependency and license risk before rollout.",
        "Prepare a small pilot scope and success metrics.",
        "Set rollback and fallback options in advance.",
    ]
    return {
        "decision": decision,
        "reason": reason,
        "weights": weights,
        "projects": ranked,
        "followups": followups,
    }
def _get_search_service() -> SearchService:
    global search_service, search_service_init_error
    if search_service is not None:
        return search_service
    if search_service_init_error:
        raise HTTPException(
            status_code=503,
            detail={"code": "SEARCH_SERVICE_UNAVAILABLE", "message": f"Search service unavailable: {search_service_init_error}"},
        )
    try:
        search_service = SearchService()
        return search_service
    except Exception as e:
        search_service_init_error = str(e)
        logger.exception("search service init failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "SEARCH_SERVICE_INIT_FAILED", "message": f"Search service init failed: {search_service_init_error}"},
        )


def _get_chat_service() -> RAGChatService:
    global chat_service, chat_service_init_error
    if chat_service is not None:
        return chat_service
    if chat_service_init_error:
        raise HTTPException(
            status_code=503,
            detail={"code": "CHAT_SERVICE_UNAVAILABLE", "message": f"Chat service unavailable: {chat_service_init_error}"},
        )
    try:
        chat_service = RAGChatService()
        return chat_service
    except Exception as e:
        chat_service_init_error = str(e)
        logger.exception("chat service init failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "CHAT_SERVICE_INIT_FAILED", "message": f"Chat service init failed: {chat_service_init_error}"},
        )
@router.get("/github/validate")
async def validate_github_token():
    """Validate configured GitHub token."""
    try:
        config = get_config()
        token = config.github.token

        if not token:
            return {
                "valid": False,
                "error": "GitHub token is missing.",
                "message": "璇峰湪 .env 鏂囦欢涓缃?GITHUB_TOKEN",
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

        if response.status_code == 200:
            user_data = response.json()
            return {
                "valid": True,
                "username": user_data.get("login"),
                "name": user_data.get("name"),
                "avatar_url": user_data.get("avatar_url"),
                "message": f"宸茬櫥褰曚负 {user_data.get('login')}",
            }
        if response.status_code == 401:
            return {
                "valid": False,
                "error": "Token 鏃犳晥鎴栧凡杩囨湡",
                "message": "璇锋鏌?GITHUB_TOKEN 鏄惁姝ｇ‘",
            }
        return {
            "valid": False,
            "error": f"楠岃瘉澶辫触: HTTP {response.status_code}",
            "message": response.text[:200],
        }
    except httpx.TimeoutException:
        return {
            "valid": False,
            "error": "璇锋眰瓒呮椂",
            "message": "GitHub API request timed out.",
        }
    except Exception as e:
        return {
            "valid": False,
            "error": "楠岃瘉寮傚父",
            "message": str(e)[:200],
        }


@router.get("/github/rate-limit")
async def get_github_rate_limit():
    """Get GitHub API rate-limit status."""
    try:
        config = get_config()
        token = config.github.token

        if not token:
            return {"error": "GitHub token is not configured."}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.github.com/rate_limit",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

        if response.status_code == 200:
            data = response.json()
            core = data.get("resources", {}).get("core", {})
            return {
                "limit": core.get("limit"),
                "remaining": core.get("remaining"),
                "used": core.get("used"),
                "reset": core.get("reset"),
                "reset_time": date.fromtimestamp(core.get("reset", 0)) if core.get("reset") else None,
            }
        return {"error": f"鑾峰彇澶辫触: HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)[:200]}


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(days: int = 1):
    """Get dashboard summary cards."""
    _, _, records = _load_records_for_days(days)
    return build_dashboard_response(records, analysis_lookup=cache.get)



def _resolve_date_window(days: int) -> tuple[date, date]:
    """Resolve date window with lightweight fallback."""
    safe_days = max(1, int(days))
    end_date = date.today()
    start_date = end_date - timedelta(days=safe_days - 1)

    records = cache.get_trending_history(start_date=start_date, end_date=end_date)
    if records:
        return start_date, end_date

    # 鏃ヨ鍥捐姹備弗鏍煎綋澶╋紝涓嶅厑璁歌嚜鍔ㄥ洖閫€鍒板巻鍙叉棩鏈燂紝閬垮厤璇銆?
    if safe_days == 1:
        return start_date, end_date

    latest_date = cache.get_latest_record_date()
    if latest_date is None:
        return start_date, end_date

    fallback_end = latest_date
    fallback_start = fallback_end - timedelta(days=safe_days - 1)
    return fallback_start, fallback_end


def _load_records_for_days(days: int) -> tuple[date, date, List[Dict]]:
    start_date, end_date = _resolve_date_window(days)
    records = cache.get_trending_history(start_date=start_date, end_date=end_date)
    return start_date, end_date, records


@router.get("/dashboard/insights", response_model=DashboardInsightsResponse)
async def get_dashboard_insights(days: int = Query(7, ge=1, le=30)):
    """Resolve discover payload from cached trending records."""
    start_date, end_date, records = _load_records_for_days(days)
    return build_dashboard_insights_response(
        days=days,
        start_date=start_date,
        end_date=end_date,
        records=records,
    )


@router.get("/discover/feed")
async def get_discover_feed(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(12, ge=3, le=36),
    interests: str = Query("", description="閫楀彿鍒嗛殧鐨勫叴瓒ｆ爣绛撅紝濡?python,agent,workflow"),
):
    """Discover feed endpoint for recommendation cards."""
    interest_terms = [segment.strip() for segment in str(interests or "").split(",") if segment.strip()]
    payload = _collect_discover_projects(days=days, interests=interest_terms, limit=limit)
    return {
        "days": days,
        "interests": interest_terms,
        "total": int(payload.get("total") or 0),
        "data_date": payload.get("data_date"),
        "is_fresh_today": bool(payload.get("is_fresh_today")),
        "items": payload.get("items") or [],
    }


@router.post("/compare/score")
async def compare_project_score(request: CompareScoreRequest):
    """Compare project score cards (2-5 repos)."""
    names = _dedupe_tags(request.repo_names, limit=5)
    if len(names) < 2:
        raise HTTPException(status_code=400, detail={"code": "COMPARE_REPO_COUNT_INVALID", "message": "At least 2 repositories are required."})

    results: List[Dict[str, object]] = []
    missing: List[str] = []
    for repo_name in names:
        row = _resolve_compare_item(repo_name)
        if not row:
            missing.append(repo_name)
            continue
        results.append(row)

    if len(results) < 2:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COMPARE_PROJECTS_NOT_FOUND",
                "message": "Not enough comparable projects found in current dataset.",
                "missing": missing,
            },
        )

    results.sort(key=lambda item: float(item.get("overall_score") or 0.0), reverse=True)
    return {
        "total": len(results),
        "missing": missing,
        "items": results,
    }


@router.post("/assistant/recommend")
async def assistant_recommend(request: AssistantRecommendRequest):
    """Assistant recommendation endpoint."""
    names = _dedupe_tags(request.repo_names, limit=5)
    if not names:
        raise HTTPException(status_code=400, detail={"code": "ASSISTANT_REPO_REQUIRED", "message": "At least one repository is required."})

    projects: List[Dict[str, object]] = []
    missing: List[str] = []
    for repo_name in names:
        row = _resolve_compare_item(repo_name)
        if not row:
            missing.append(repo_name)
            continue
        projects.append(row)

    if not projects:
        raise HTTPException(status_code=404, detail={"code": "ASSISTANT_PROJECTS_NOT_FOUND", "message": "No candidate projects found in current dataset."})

    recommendation = _build_recommendation(profile_query=request.query, items=projects)
    return {
        "query": request.query,
        "missing": missing,
        "decision": recommendation.get("decision"),
        "reason": recommendation.get("reason"),
        "weights": recommendation.get("weights"),
        "projects": recommendation.get("projects"),
        "followups": recommendation.get("followups"),
    }


@router.get("/projects/{repo_full_name:path}", response_model=ProjectDetailResponse)
async def get_project_detail(repo_full_name: str):
    """Get project detail with profile and analysis summary."""
    detail = cache.get_project_detail(repo_full_name=repo_full_name, history_limit=12)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PROJECT_NOT_FOUND",
                "message": f"椤圭洰涓嶅瓨鍦? {repo_full_name}",
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
    """Get trend charts data."""
    _, _, records = _load_records_for_days(days)
    return build_trends_response(days=days, records=records)


@router.get("/search", response_model=SearchResponse)
async def search_projects(
    q: str = Query(..., min_length=1, description="search query"),
    coarse_top_k: int = Query(20, ge=5, le=100, description="绮楁帓鏁伴噺"),
    final_top_k: int = Query(5, ge=1, le=20, description="final result count"),
):
    """Search projects endpoint."""
    service = _get_search_service()
    try:
        parser = get_query_parser()
        parsed_filters = await parser.parse(q)
    except Exception as exc:
        logger.warning("query parser unavailable in /search, fallback to no filters: %s", exc)
        parsed_filters = QueryFilters()
    active_filters = parsed_filters if parsed_filters.has_filters() else None
    try:
        results = await service.search_projects(
            query=q,
            coarse_top_k=coarse_top_k,
            final_top_k=final_top_k,
            filters=active_filters,
        )
    except TypeError:
        # Backward compatibility for test stubs with old signature.
        results = await service.search_projects(
            query=q,
            coarse_top_k=coarse_top_k,
            final_top_k=final_top_k,
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
            use_cases=result.get("use_cases", []),
            match_reasons=_build_match_reasons_from_result(
                query=q,
                filters=active_filters,
                result=result,
            ),
        )
        for result in results
    ]

    return SearchResponse(
        query=q,
        results=search_results,
        total=len(search_results),
        parsed_filters=parsed_filters.to_active_filter_dict() if parsed_filters.has_filters() else None,
    )


@router.post("/search/index")
async def index_projects():
    """Rebuild search index."""
    service = _get_search_service()
    stats = await service.reindex_all_projects()
    
    return {
        "message": "绱㈠紩瀹屾垚",
        "stats": stats
    }

@router.get("/search/stats")
async def get_search_stats():
    """Get search backend stats."""
    service = _get_search_service()
    stats = service.get_search_stats()
    
    return stats


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    鏅鸿兘瀵硅瘽锛堟祦寮忚緭鍑猴級銆?

    鍩轰簬鐢ㄦ埛闂妫€绱㈢浉鍏抽」鐩紝浣跨敤 SSE 鎸佺画杩斿洖鐢熸垚鍐呭銆?
    鏀寔浼氳瘽绠＄悊锛屼紶鍏?session_id 鍙繚鐣欎笂涓嬫枃銆?
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
                "content": "Chat stream interrupted unexpectedly, please retry.",
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
    鑾峰彇浼氳瘽淇℃伅銆?
    
    杩斿洖浼氳瘽鍘嗗彶璁板綍鍜岀姸鎬併€?
    """
    session_manager = get_session_manager()
    session = session_manager.get(session_id)
    
    if not session:
        return {
            "error": "Session not found or expired.",
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
    鍒犻櫎浼氳瘽銆?
    
    娓呴櫎浼氳瘽鐘舵€佸拰鍘嗗彶璁板綍銆?
    """
    session_manager = get_session_manager()
    deleted = session_manager.delete(session_id)
    
    return {
        "success": deleted,
        "session_id": session_id
    }


@router.get("/sessions/stats")
async def get_sessions_stats():
    """
    鑾峰彇浼氳瘽缁熻淇℃伅銆?
    
    杩斿洖褰撳墠娲昏穬浼氳瘽鏁伴噺绛変俊鎭€?
    """
    session_manager = get_session_manager()
    
    return {
        "active_sessions": session_manager.get_active_count(),
        "total_sessions": len(session_manager.sessions)
    }






