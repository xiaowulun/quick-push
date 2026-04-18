import os
import time
import asyncio
import aiohttp
import requests
from dataclasses import dataclass
from typing import Optional, Literal, List
from bs4 import BeautifulSoup
from app.infrastructure.logging import get_logger
from app.infrastructure.config import get_config

logger = get_logger(__name__)


@dataclass
class Repo:
    name: str
    full_name: str
    description: Optional[str]
    url: str
    stars: int
    language: Optional[str]
    forks: int
    stars_today: int
    readme: Optional[str] = None
    topics: List[str] = None
    has_pages: bool = False
    license_key: Optional[str] = None
    pushed_at: Optional[str] = None


class GitHubFetcher:
    def __init__(self):
        config = get_config()
        self.max_retries = config.github.max_retries
        self.timeout = config.github.timeout
        self.api_base = config.github.api_base
        self.token = config.github.token

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def fetch_trending(
        self,
        language: str = "",
        since: Literal["daily", "weekly", "monthly"] = "daily",
        limit: int = 10
    ) -> List[Repo]:
        repos = self._fetch_from_trending_page(language, since, limit)
        if repos:
            asyncio.run(self._enrich_repos_async(repos))
        return repos

    def fetch_trending_repos(
        self,
        language: Optional[str] = None,
        date_range: str = "daily",
        limit: int = 50
    ) -> List[Repo]:
        """获取 Trending 仓库"""
        return self.fetch_trending(language or "", since=date_range, limit=limit)

    async def _enrich_repos_async(self, repos: List[Repo]) -> None:
        """并发获取 README 和补充字段"""
        await asyncio.gather(
            self._fetch_readmes_async(repos),
            self._fetch_repo_details_async(repos)
        )

    async def _fetch_repo_details_async(self, repos: List[Repo], max_concurrency: int = 10) -> None:
        """调用 GitHub API 获取项目详情（topics, has_pages, license）"""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_single(session: aiohttp.ClientSession, repo: Repo) -> None:
            async with semaphore:
                url = f"{self.api_base}/repos/{repo.full_name}"
                try:
                    async with session.get(url, headers=self.headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            repo.topics = data.get("topics", [])
                            repo.has_pages = data.get("has_pages", False)
                            repo.license_key = data.get("license", {}).get("key") if data.get("license") else None
                            repo.pushed_at = data.get("pushed_at")
                            logger.debug(f"获取项目详情成功: {repo.full_name}, topics={repo.topics}")
                        else:
                            logger.warning(f"获取项目详情失败: {repo.full_name}, status={resp.status}")
                except Exception as e:
                    logger.error(f"获取项目详情异常: {repo.full_name}, error={e}")

        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [fetch_single(session, repo) for repo in repos]
            await asyncio.gather(*tasks)

    async def _fetch_readmes_async(self, repos: List[Repo], max_concurrency: int = 10) -> None:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_single(session: aiohttp.ClientSession, repo: Repo) -> tuple:
            async with semaphore:
                return repo.full_name, await self._fetch_readme_with_retry(session, repo.full_name)

        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [fetch_single(session, repo) for repo in repos]
            results = await asyncio.gather(*tasks)

        for full_name, readme in results:
            for repo in repos:
                if repo.full_name == full_name:
                    repo.readme = readme
                    break

    async def _fetch_readme_with_retry(
        self,
        session: aiohttp.ClientSession,
        full_name: str,
        retry_count: int = 0
    ) -> Optional[str]:
        try:
            result = await self._fetch_readme_async(session, full_name)
            return result
        except RateLimitError as e:
            if retry_count < self.max_retries:
                base_delay = 10
                wait_time = e.retry_after if e.retry_after else min(base_delay * (2 ** retry_count), 120)
                logger.warning(f"GitHub API 速率限制触发，等待 {wait_time} 秒后重试 ({retry_count + 1}/{self.max_retries})...")
                await asyncio.sleep(wait_time)
                return await self._fetch_readme_with_retry(session, full_name, retry_count + 1)
            else:
                logger.error(f"GitHub API 速率限制，重试次数耗尽，跳过 {full_name}")
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if retry_count < self.max_retries:
                base_delay = 2
                wait_time = min(base_delay * (2 ** retry_count), 30)
                logger.warning(f"获取 {full_name} README 失败 ({e})，{wait_time}秒后重试 ({retry_count + 1}/{self.max_retries})...")
                await asyncio.sleep(wait_time)
                return await self._fetch_readme_with_retry(session, full_name, retry_count + 1)
            else:
                logger.error(f"获取 {full_name} README 失败次数耗尽，跳过")
                return None

    async def _fetch_readme_async(self, session: aiohttp.ClientSession, full_name: str) -> Optional[str]:
        url = f"{self.api_base}/repos/{full_name}/readme"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
            if response.status == 200:
                return await response.text()
            elif response.status == 404:
                return None
            elif response.status == 403:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError(f"Rate limit exceeded", retry_after=int(retry_after) if retry_after else None)
            elif response.status == 451:
                logger.warning(f"{full_name} 因法律原因无法访问")
                return None
            else:
                raise aiohttp.ClientError(f"Unexpected status: {response.status}")

    def _fetch_from_trending_page(
        self,
        language: str,
        since: str,
        limit: int
    ) -> List[Repo]:
        if language:
            url = f"https://github.com/trending/{language}?since={since}"
        else:
            url = f"https://github.com/trending?since={since}"

        response = None
        for retry in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                break
            except requests.RequestException as e:
                if retry == self.max_retries - 1:
                    logger.error(f"获取 GitHub Trending 页面失败，已达最大重试次数: {e}")
                    return []
                base_delay = 2
                wait_time = min(base_delay * (2 ** retry), 30)
                logger.warning(f"获取 GitHub Trending 页面失败 ({e})，{wait_time}秒后重试 ({retry + 1}/{self.max_retries})...")
                time.sleep(wait_time)

        if not response:
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        article_tags = soup.select("article.Box-row")

        if not article_tags:
            logger.warning(f"未能解析到 Trending 项目，可能页面结构已更新")
            return []

        repos = []
        for article in article_tags[:limit]:
            repo = self._parse_article(article)
            if repo:
                repos.append(repo)

        return repos

    def _parse_article(self, article) -> Optional[Repo]:
        try:
            repo_link = article.select_one("h2 a")
            if not repo_link:
                return None

            href = repo_link.get("href")
            if not href or "/" not in href:
                return None

            full_name = href.lstrip("/")
            name = full_name.split("/")[1]

            url = "https://github.com" + href

            description_elem = article.select_one("p")
            description = description_elem.get_text(strip=True) if description_elem else None

            stars_str = article.select_one("a[href*='/stargazers']")
            stars = self._parse_number(stars_str.get_text(strip=True)) if stars_str else 0

            forks_str = article.select_one("a[href*='/forks']")
            forks = self._parse_number(forks_str.get_text(strip=True)) if forks_str else 0

            language_elem = article.select_one("span[itemprop='programmingLanguage']")
            language = language_elem.get_text(strip=True) if language_elem else None

            stars_today_str = article.select_one(".float-sm-right")
            stars_today = 0
            if stars_today_str:
                text = stars_today_str.get_text(strip=True)
                if "today" in text.lower():
                    stars_today = self._parse_number(text.replace(",", "").split()[0])

            return Repo(
                name=name,
                full_name=full_name,
                description=description,
                url=url,
                stars=stars,
                language=language,
                forks=forks,
                stars_today=stars_today
            )
        except Exception:
            return None

    def _parse_number(self, text: str) -> int:
        text = text.replace(",", "").strip()
        if text.endswith("k"):
            return int(float(text[:-1]) * 1000)
        elif text.endswith("M"):
            return int(float(text[:-1]) * 1000000)
        try:
            return int(text)
        except ValueError:
            return 0


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after
