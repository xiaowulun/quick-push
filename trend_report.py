#!/usr/bin/env python3
"""
趋势分析报表生成工具
查看 GitHub Trending 的历史趋势数据
"""

import argparse
from datetime import date, timedelta
from utils.cache import AnalysisCache
from core.prompts import get_category_emoji, get_category_name


def print_trend_report(days: int = 7):
    """打印趋势报表"""
    cache = AnalysisCache()
    report = cache.generate_trend_report(days)

    print("\n" + "=" * 60)
    print(f"📈 GitHub Trending 趋势报表 ({report['period']})")
    print("=" * 60)

    # 热门项目
    print("\n🔥 持续热门项目（上榜次数最多）")
    print("-" * 60)
    hot_repos = report['hot_repos']
    if hot_repos:
        for i, repo in enumerate(hot_repos[:10], 1):
            print(f"{i:2d}. {repo['repo_full_name']:<40} 上榜 {repo['appearances']} 次")
    else:
        print("暂无数据，需要积累至少 2 天的数据")

    # 分类趋势
    print("\n📊 分类趋势统计")
    print("-" * 60)
    category_trends = report['category_trends']
    if category_trends:
        total = sum(c['count'] for c in category_trends)
        for cat in category_trends:
            emoji = get_category_emoji(cat['category'])
            name = get_category_name(cat['category'])
            percentage = (cat['count'] / total * 100) if total > 0 else 0
            print(f"{emoji} {name:<20} {cat['count']:>3} 次 ({percentage:>5.1f}%)")
    else:
        print("暂无分类数据")

    # 新星项目
    print("\n⭐ 本周新星（首次上榜）")
    print("-" * 60)
    new_stars = report['new_stars']
    if new_stars:
        for i, repo in enumerate(new_stars[:5], 1):
            emoji = get_category_emoji(repo['category']) if repo['category'] else "📦"
            print(f"{i}. {emoji} {repo['repo_full_name']:<35} 排名 #{repo['rank']}")
    else:
        print("暂无新星数据，需要积累至少 2 天的数据")

    # 统计摘要
    print("\n📋 数据摘要")
    print("-" * 60)
    stats = cache.get_stats()
    print(f"总分析缓存: {stats['total_cached']} 条")
    print(f"趋势记录: {stats['trending_records']} 条")
    print(f"追踪项目: {stats['tracked_repos']} 个")

    print("\n" + "=" * 60)


def print_repo_history(repo_name: str, days: int = 30):
    """打印单个项目的历史记录"""
    cache = AnalysisCache()

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    history = cache.get_trending_history(
        start_date=start_date,
        end_date=end_date,
        repo_name=repo_name
    )

    print(f"\n📊 {repo_name} 的历史趋势")
    print("=" * 60)

    if not history:
        print(f"过去 {days} 天内没有该项目的记录")
        return

    print(f"\n共上榜 {len(history)} 次:\n")
    for record in history:
        date_str = record['record_date']
        rank = record['rank']
        stars = record['stars']
        stars_today = record['stars_today']
        since = record['since_type']
        print(f"  {date_str}  排名 #{rank:<2}  ⭐ {stars:,} (+{stars_today:,})  [{since}]")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="GitHub Trending 趋势分析报表")
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="统计天数 (默认: 7)"
    )
    parser.add_argument(
        "--repo", "-r",
        type=str,
        help="查看特定项目的历史趋势，如 'facebook/react'"
    )

    args = parser.parse_args()

    if args.repo:
        print_repo_history(args.repo, args.days)
    else:
        print_trend_report(args.days)


if __name__ == "__main__":
    main()
