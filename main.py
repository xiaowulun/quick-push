import os
import asyncio
import argparse
from datetime import datetime, date
from dotenv import load_dotenv
from app.github.fetcher import GitHubFetcher
from app.analysis.summarizer import Summarizer
from app.analysis.classifier import ProjectClassifier
from app.infrastructure.notifier import Notifier, TrendingMessage
from app.infrastructure.logging import setup_logging, get_logger
from app.infrastructure.cache import AnalysisCache
from app.infrastructure.config import get_config

load_dotenv()

logger = get_logger(__name__)


def run(language: str = "", since: str = "daily", limit: int = 10, notify: bool = True):
    logger.info(f"开始获取 GitHub 趋势榜单 (语言: {language or '全部'}, 时间: {since})")

    fetcher = GitHubFetcher()
    repos = fetcher.fetch_trending_repos(language=language, date_range=since, limit=limit)
    logger.info(f"获取到 {len(repos)} 个热门项目")

    summarizer = Summarizer(enable_cache=True)
    logger.info(f"开始并行分析 {len(repos)} 个项目")

    config = get_config()
    repo_dicts = [
        {
            "repo_name": repo.full_name,
            "description": repo.description,
            "readme_content": repo.readme,
            "repo_data": {
                "stars": repo.stars,
                "language": repo.language,
                "description": repo.description,
                "topics": repo.topics if repo.topics else [],
                "has_pages": repo.has_pages,
                "license": repo.license_key,
            }
        }
        for repo in repos
    ]
    analyses = asyncio.run(summarizer.batch_summarize(
        repo_dicts,
        max_concurrency=config.behavior.max_concurrency
    ))

    success_messages = []
    failure_repos = []

    for repo, analysis in zip(repos, analyses):
        if _is_failure_analysis(analysis):
            failure_repos.append((repo, analysis))
        else:
            msg = TrendingMessage(
                repo_name=repo.full_name,
                description=repo.description or "无",
                url=repo.url,
                stars=repo.stars,
                stars_today=repo.stars_today,
                language=repo.language or "N/A",
                summary=analysis["summary"],
                reasons=analysis["reasons"]
            )
            success_messages.append(msg)

    logger.info(f"分析完成，成功 {len(success_messages)} 个，失败 {len(failure_repos)} 个")

    _save_trending_data(repos, since)

    mode = "feishu" if notify else "print"
    notifier = Notifier(mode=mode)
    today = datetime.now().strftime("%Y-%m-%d")

    if success_messages:
        title = f"GitHub 热门项目日报 ({today})"
        notifier.send(success_messages, title)

    if failure_repos:
        notifier.send_failure_report(failure_repos, title if success_messages else f"GitHub 热门项目日报 ({today})")

    logger.info(f"任务完成")
    return success_messages


def _save_trending_data(repos, since_type: str):
    """保存趋势数据到数据库"""
    try:
        cache = AnalysisCache()
        classifier = ProjectClassifier()
        today = date.today()

        for i, repo in enumerate(repos, 1):
            try:
                classification = classifier.classify(
                    repo.full_name,
                    repo.description,
                    repo.readme
                )
                category = classification.category.value
            except Exception as e:
                logger.warning(f"分类失败 {repo.full_name}: {e}")
                category = None

            cache.save_trending_record(
                record_date=today,
                repo_full_name=repo.full_name,
                language=repo.language or "Unknown",
                stars=repo.stars,
                stars_today=repo.stars_today,
                rank=i,
                since_type=since_type,
                category=category
            )

        logger.info(f"已保存 {len(repos)} 条趋势记录")
    except Exception as e:
        logger.error(f"保存趋势数据失败: {e}")


def _is_failure_analysis(analysis: dict) -> bool:
    reasons = analysis.get("reasons", [])
    if not reasons:
        return False
    failure_keywords = ["异常", "失败", "错误", "异常"]
    return any(keyword in reasons[0] for keyword in failure_keywords)


def main():
    parser = argparse.ArgumentParser(description="GitHub 热门项目分析推送工具")
    parser.add_argument("--language", "-l", default="", help="编程语言筛选，如 python, javascript")
    parser.add_argument("--since", "-s", default="weekly",
                        choices=["daily", "weekly", "monthly"],
                        help="时间范围")
    parser.add_argument("--limit", "-n", type=int, default=10, help="获取数量")
    parser.add_argument("--no-notify", action="store_true", help="禁用飞书推送，仅打印")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="日志级别")

    args = parser.parse_args()

    setup_logging(level=args.log_level)

    try:
        get_config()
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        return

    notify = not args.no_notify
    run(language=args.language, since=args.since, limit=args.limit, notify=notify)


if __name__ == "__main__":
    main()
