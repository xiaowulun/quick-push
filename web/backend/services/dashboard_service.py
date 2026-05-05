from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

from ..models import (
    CategoryTrend,
    DashboardActivityItem,
    DashboardDecisionProject,
    DashboardDistributionItem,
    DashboardInsightsResponse,
    DashboardResponse,
    DashboardSummary,
    DashboardTimelinePoint,
    HotProject,
    LanguageTrend,
    ProjectCard,
    TrendsResponse,
)

_CATEGORY_KEYS = (
    "ai_ecosystem",
    "infra_and_tools",
    "product_and_ui",
    "knowledge_base",
)


def _parse_iso_date(value: object) -> Optional[date]:
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


def _resolve_freshness(records: List[Dict]) -> tuple[Optional[str], bool]:
    latest: Optional[date] = None
    for record in records:
        parsed = _parse_iso_date(record.get("record_date"))
        if parsed is None:
            continue
        if latest is None or parsed > latest:
            latest = parsed

    if latest is None:
        return None, False
    return latest.isoformat(), latest == date.today()


def _select_latest_repo_records(records: List[Dict]) -> Dict[str, Dict]:
    latest_map: Dict[str, Dict] = {}

    for record in records:
        repo_name = str(record.get("repo_full_name") or "").strip()
        if not repo_name:
            continue

        incoming_date = _parse_iso_date(record.get("record_date")) or date.min
        incoming_stars_today = int(record.get("stars_today") or 0)
        incoming_rank = int(record.get("rank") or 999)

        current = latest_map.get(repo_name)
        if current is None:
            latest_map[repo_name] = record
            continue

        current_date = _parse_iso_date(current.get("record_date")) or date.min
        current_stars_today = int(current.get("stars_today") or 0)
        current_rank = int(current.get("rank") or 999)

        should_replace = (
            incoming_date > current_date
            or (
                incoming_date == current_date
                and (incoming_stars_today > current_stars_today or incoming_rank < current_rank)
            )
        )
        if should_replace:
            latest_map[repo_name] = record

    return latest_map


def build_dashboard_response(
    records: List[Dict],
    *,
    analysis_lookup: Callable[[str], Optional[Dict]],
) -> DashboardResponse:
    categorized = {key: [] for key in _CATEGORY_KEYS}
    latest_repo_records = _select_latest_repo_records(records)

    for repo_name, record in latest_repo_records.items():
        category = str(record.get("category") or "infra_and_tools")
        if category not in categorized:
            category = "infra_and_tools"

        analysis = analysis_lookup(repo_name) or {}
        categorized[category].append(
            ProjectCard(
                repo_name=repo_name,
                description=str(record.get("description") or ""),
                summary=str(analysis.get("summary") or ""),
                reasons=analysis.get("reasons") if isinstance(analysis.get("reasons"), list) else [],
                keywords=analysis.get("keywords") if isinstance(analysis.get("keywords"), list) else [],
                tech_stack=analysis.get("tech_stack") if isinstance(analysis.get("tech_stack"), list) else [],
                use_cases=analysis.get("use_cases") if isinstance(analysis.get("use_cases"), list) else [],
                stars=int(record.get("stars") or 0),
                stars_today=int(record.get("stars_today") or 0),
                since_type=record.get("since_type"),
                language=str(record.get("language") or "Unknown"),
                category=category,
                url=f"https://github.com/{repo_name}",
            )
        )

    for category in categorized:
        categorized[category].sort(key=lambda row: row.stars_today, reverse=True)

    data_date, is_fresh_today = _resolve_freshness(records)
    return DashboardResponse(
        ai_ecosystem=categorized["ai_ecosystem"][:10],
        infra_and_tools=categorized["infra_and_tools"][:10],
        product_and_ui=categorized["product_and_ui"][:10],
        knowledge_base=categorized["knowledge_base"][:10],
        data_date=data_date,
        is_fresh_today=is_fresh_today,
    )


def build_dashboard_insights_response(
    *,
    days: int,
    start_date: date,
    end_date: date,
    records: List[Dict],
) -> DashboardInsightsResponse:
    day_list = _build_day_list(start_date=start_date, end_date=end_date)
    daily_repo_stats: Dict[str, Dict[str, dict]] = {day.isoformat(): {} for day in day_list}
    latest_stars_map: Dict[str, tuple[date, int]] = {}

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

        current_snapshot = latest_stars_map.get(repo_name)
        if current_snapshot is None or parsed_date >= current_snapshot[0]:
            latest_stars_map[repo_name] = (parsed_date, stars)

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
            row_rank = int(item.get("rank") or 999)
            if row_rank < 999:
                stat["rank_sum"] += row_rank
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
        latest_stars = int((latest_stars_map.get(repo_name) or (date.min, 0))[1])
        ranked_projects.append((repo_name, stat, avg_rank, latest_stars))

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
                title="趋势数据已更新",
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
                detail=f"当日 +{project.stars_today} stars · 上榜 {project.appearances} 次 · 均位 #{project.avg_rank}",
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

    data_date, is_fresh_today = _resolve_freshness(records)
    window_days = max(1, (end_date - start_date).days + 1)
    return DashboardInsightsResponse(
        period=f"最近{window_days}天",
        summary=summary,
        stars_timeline=stars_timeline,
        category_distribution=category_distribution,
        language_distribution=language_distribution,
        decision_projects=decision_projects,
        recent_activities=recent_activities[:12],
        data_date=data_date,
        is_fresh_today=is_fresh_today,
    )


def build_trends_response(
    *,
    days: int,
    records: List[Dict],
) -> TrendsResponse:
    category_counts: Dict[str, int] = {}
    language_counts: Dict[str, int] = {}
    project_appearances: Dict[str, dict] = {}

    for record in records:
        category = str(record.get("category") or "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1

        language = str(record.get("language") or "Unknown")
        language_counts[language] = language_counts.get(language, 0) + 1

        repo_name = str(record.get("repo_full_name") or "").strip()
        if not repo_name:
            continue

        entry = project_appearances.setdefault(
            repo_name,
            {
                "count": 0,
                "ranks": [],
                "last_seen": str(record.get("record_date") or ""),
                "category": category,
            },
        )
        entry["count"] += 1
        entry["ranks"].append(int(record.get("rank") or 999))

        record_date = str(record.get("record_date") or "")
        if record_date > str(entry["last_seen"]):
            entry["last_seen"] = record_date

    total = len(records)

    category_trends = [
        CategoryTrend(
            category=cat,
            count=count,
            percentage=round(count / total * 100, 1) if total > 0 else 0,
        )
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    language_trends = [
        LanguageTrend(
            language=lang,
            count=count,
            percentage=round(count / total * 100, 1) if total > 0 else 0,
        )
        for lang, count in sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    hot_projects = [
        HotProject(
            repo_name=repo,
            appearances=data["count"],
            avg_rank=round(sum(data["ranks"]) / len(data["ranks"]), 1),
            last_seen=str(data["last_seen"]),
            category=str(data["category"]),
        )
        for repo, data in sorted(
            project_appearances.items(),
            key=lambda x: (x[1]["count"], -sum(x[1]["ranks"]) / len(x[1]["ranks"])),
            reverse=True,
        )[:10]
    ]

    data_date, is_fresh_today = _resolve_freshness(records)
    return TrendsResponse(
        period=f"最近{max(1, int(days))}天",
        category_trends=category_trends,
        language_trends=language_trends,
        hot_projects=hot_projects,
        total_projects=len(project_appearances),
        total_records=total,
        data_date=data_date,
        is_fresh_today=is_fresh_today,
    )
