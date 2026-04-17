import os
import asyncio
import argparse
import uuid
from datetime import datetime, date
from time import perf_counter
from dotenv import load_dotenv
from app.github.fetcher import GitHubFetcher
from app.analysis.summarizer import Summarizer
from app.analysis.classifier import ProjectClassifier
from app.infrastructure.notifier import Notifier, TrendingMessage
from app.infrastructure.logging import (
    get_logger,
    reset_request_id,
    set_request_id,
    setup_logging,
)
from app.infrastructure.cache import AnalysisCache
from app.infrastructure.config import get_config

load_dotenv()

logger = get_logger(__name__)


def run(language: str = "", since: str = "daily", limit: int = 10, notify: bool = True):
    logger.info(f"开始获取 GitHub 趋势榜单 (语言: {language or '全部'}, 时间: {since})")

    fetcher = GitHubFetcher()
    repos = fetcher.fetch_trending_repos(language=language, date_range=since, limit=limit)
    logger.info(f"获取到 {len(repos)} 个热门项目")

    # Cache is keyed by repo_full_name (not by date). Use --no-cache to force a fresh run.
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
    summarize_started = perf_counter()
    analyses = asyncio.run(summarizer.batch_summarize(
        repo_dicts,
        max_concurrency=config.behavior.max_concurrency
    ))
    summarize_elapsed = perf_counter() - summarize_started
    logger.info(f"批量分析完成，耗时 {summarize_elapsed:.2f}s，并发={config.behavior.max_concurrency}")

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

    classification_started = perf_counter()
    _save_trending_data(repos, since)
    classification_elapsed = perf_counter() - classification_started
    logger.info(f"分类与趋势入库完成，耗时 {classification_elapsed:.2f}s")

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
    """保存趋势数据到数据库（分类阶段受控并发）"""
    try:
        cache = AnalysisCache()
        classifier = ProjectClassifier()
        config = get_config()
        today = date.today()
        max_concurrency = max(1, int(config.behavior.max_concurrency))

        async def classify_all():
            semaphore = asyncio.Semaphore(max_concurrency)

            async def classify_one(repo):
                async with semaphore:
                    return await classifier.classify_async(
                        repo.full_name,
                        repo.description,
                        repo.readme
                    )

            tasks = [classify_one(repo) for repo in repos]
            return await asyncio.gather(*tasks, return_exceptions=True)

        classifications = asyncio.run(classify_all())

        for i, (repo, classification) in enumerate(zip(repos, classifications), 1):
            category = None
            if isinstance(classification, Exception):
                logger.warning(f"分类失败 {repo.full_name}: {classification}")
            elif classification is not None:
                category = classification.category.value

            cache.save_trending_record(
                record_date=today,
                repo_full_name=repo.full_name,
                description=repo.description or "",
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
    parser.add_argument("--no-cache", action="store_true", help="禁用分析缓存（强制重新分析）")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="日志级别")

    args = parser.parse_args()

    setup_logging(level=args.log_level, include_context=False)
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    req_token = set_request_id(run_id)
    logger.info("离线任务开始", extra={"latency_ms": 0})

    try:
        get_config()
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        reset_request_id(req_token)
        return

    notify = not args.no_notify

    # Wire cache toggle into Summarizer by monkey-patching via env-like flag.
    # Keep behavior identical unless user explicitly disables cache.
    if args.no_cache:
        # Recreate Summarizer inside run() with cache disabled.
        # We keep the run() signature unchanged to avoid touching other callers.
        global Summarizer
        _Summarizer = Summarizer

        class Summarizer(_Summarizer):
            def __init__(self, enable_cache: bool = False):
                super().__init__(enable_cache=False)

        logger.info("已禁用分析缓存：本次运行将强制重新分析所有项目")

    started = perf_counter()
    try:
        run(language=args.language, since=args.since, limit=args.limit, notify=notify)
        elapsed_ms = int((perf_counter() - started) * 1000)
        logger.info("离线任务结束", extra={"latency_ms": elapsed_ms})
    finally:
        reset_request_id(req_token)


if __name__ == "__main__":
    main()
