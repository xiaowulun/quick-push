from fastapi import APIRouter, Query
from typing import Optional
from datetime import date, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from utils.cache import AnalysisCache
from ..models import DashboardResponse, ProjectCard, TrendsResponse, CategoryTrend, LanguageTrend, HotProject

router = APIRouter(prefix="/api", tags=["api"])

cache = AnalysisCache()

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """获取仪表盘数据，按分类展示项目"""
    
    today = date.today()
    records = cache.get_trending_history(
        start_date=today - timedelta(days=7),
        end_date=today
    )
    
    categorized = {
        "ai_ecosystem": [],
        "dev_tools": [],
        "infrastructure": [],
        "product_and_ui": []
    }
    
    seen_repos = set()
    
    for record in records:
        repo_name = record["repo_full_name"]
        if repo_name in seen_repos:
            continue
        seen_repos.add(repo_name)
        
        category = record.get("category")
        if not category or category not in categorized:
            category = "dev_tools"
        
        analysis = cache.get(repo_name)
        
        project = ProjectCard(
            repo_name=repo_name,
            description=record.get("language", ""),
            summary=analysis.get("summary", "") if analysis else "",
            reasons=analysis.get("reasons", []) if analysis else [],
            stars=record.get("stars", 0),
            stars_today=record.get("stars_today", 0),
            language=record.get("language", "Unknown"),
            category=category,
            url=f"https://github.com/{repo_name}"
        )
        
        categorized[category].append(project)
        
        if len(categorized[category]) >= 5:
            continue
    
    return DashboardResponse(
        ai_ecosystem=categorized["ai_ecosystem"][:5],
        dev_tools=categorized["dev_tools"][:5],
        infrastructure=categorized["infrastructure"][:5],
        product_and_ui=categorized["product_and_ui"][:5]
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
