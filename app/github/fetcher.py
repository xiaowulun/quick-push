import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import List, Literal, Optional

import aiohttp
import requests
from bs4 import BeautifulSoup

from app.infrastructure.config import get_config
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Repo:
    name: str
    full_name: str
    description: Optional[str]
    url: str
    stars: int
    language: Optional[str]
    stars_today: int
    readme: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    pushed_at: Optional[str] = None


class GitHubFetcher:
    def __init__(self):
        config = get_config()
        self.max_retries = config.github.max_retries
        self.timeout = config.github.timeout
        self.api_base = config.github.api_base
        self.token = config.github.token

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def fetch_trending(
        self,
        language: str = "",
        since: Literal["daily", "weekly", "monthly"] = "daily",
        limit: int = 10,
    ) -> List[Repo]:
        repos = self._fetch_from_trending_page(language, since, limit)
        if repos:
            asyncio.run(self._enrich_repos_async(repos))
        return repos

    def fetch_trending_repos(
        self,
        language: Optional[str] = None,
        date_range: str = "daily",
        limit: int = 50,
    ) -> List[Repo]:
        return self.fetch_trending(language or "", since=date_range, limit=limit)

    async def _enrich_repos_async(self, repos: List[Repo]) -> None:
        # Keep enrichment in parallel to reduce total runtime.
        await asyncio.gather(
            self._fetch_readmes_async(repos),
            self._fetch_repo_details_async(repos),
        )

    async def _fetch_repo_details_async(self, repos: List[Repo], max_concurrency: int = 10) -> None:
        # Repo details are only used for downstream analysis quality.
        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_single(session: aiohttp.ClientSession, repo: Repo) -> None:
            async with semaphore:
                url = f"{self.api_base}/repos/{repo.full_name}"
                try:
                    async with session.get(
                        url,
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as resp:
                        if resp.status != 200:
                            logger.warning("fetch repo details failed: %s status=%s", repo.full_name, resp.status)
                            return

                        data = await resp.json()
                        repo.topics = data.get("topics", []) or []
                        repo.pushed_at = data.get("pushed_at")
                        logger.debug("fetch repo details success: %s topics=%s", repo.full_name, repo.topics)
                except Exception as error:  # noqa: BLE001
                    logger.error("fetch repo details error: %s error=%s", repo.full_name, error)

        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [fetch_single(session, repo) for repo in repos]
            await asyncio.gather(*tasks)

    async def _fetch_readmes_async(self, repos: List[Repo], max_concurrency: int = 10) -> None:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_single(session: aiohttp.ClientSession, repo: Repo) -> tuple[str, Optional[str]]:
            async with semaphore:
                return repo.full_name, await self._fetch_readme_with_retry(session, repo.full_name)

        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [fetch_single(session, repo) for repo in repos]
            results = await asyncio.gather(*tasks)

        readme_map = {full_name: readme for full_name, readme in results}
        for repo in repos:
            repo.readme = readme_map.get(repo.full_name)

    async def _fetch_readme_with_retry(
        self,
        session: aiohttp.ClientSession,
        full_name: str,
        retry_count: int = 0,
    ) -> Optional[str]:
        try:
            return await self._fetch_readme_async(session, full_name)
        except RateLimitError as error:
            if retry_count >= self.max_retries:
                logger.error("readme rate limited and retries exhausted, skip %s", full_name)
                return None

            base_delay = 10
            wait_time = error.retry_after if error.retry_after else min(base_delay * (2**retry_count), 120)
            logger.warning(
                "readme rate limited: %s, retry after %ss (%s/%s)",
                full_name,
                wait_time,
                retry_count + 1,
                self.max_retries,
            )
            await asyncio.sleep(wait_time)
            return await self._fetch_readme_with_retry(session, full_name, retry_count + 1)
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            if retry_count >= self.max_retries:
                logger.error("readme fetch retries exhausted, skip %s error=%s", full_name, error)
                return None

            base_delay = 2
            wait_time = min(base_delay * (2**retry_count), 30)
            logger.warning(
                "readme fetch failed: %s retry in %ss (%s/%s), error=%s",
                full_name,
                wait_time,
                retry_count + 1,
                self.max_retries,
                error,
            )
            await asyncio.sleep(wait_time)
            return await self._fetch_readme_with_retry(session, full_name, retry_count + 1)

    async def _fetch_readme_async(self, session: aiohttp.ClientSession, full_name: str) -> Optional[str]:
        url = f"{self.api_base}/repos/{full_name}/readme"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
            if response.status == 200:
                return await response.text()
            if response.status == 404:
                return None
            if response.status == 403:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError("Rate limit exceeded", retry_after=int(retry_after) if retry_after else None)
            if response.status == 451:
                logger.warning("readme blocked by legal reasons: %s", full_name)
                return None
            raise aiohttp.ClientError(f"Unexpected status: {response.status}")

    def _fetch_from_trending_page(self, language: str, since: str, limit: int) -> List[Repo]:
        url = f"https://github.com/trending/{language}?since={since}" if language else f"https://github.com/trending?since={since}"

        response = None
        for retry in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                break
            except requests.RequestException as error:
                if retry == self.max_retries - 1:
                    logger.error("fetch GitHub trending failed after retries: %s", error)
                    return []
                wait_time = min(2 * (2**retry), 30)
                logger.warning("fetch GitHub trending failed, retry in %ss (%s/%s): %s", wait_time, retry + 1, self.max_retries, error)
                time.sleep(wait_time)

        if not response:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        article_tags = soup.select("article.Box-row")
        if not article_tags:
            logger.warning("parse trending page returned 0 repos, page structure may have changed")
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

            stars_elem = article.select_one("a[href*='/stargazers']")
            stars = self._parse_number(stars_elem.get_text(strip=True)) if stars_elem else 0

            language_elem = article.select_one("span[itemprop='programmingLanguage']")
            language = language_elem.get_text(strip=True) if language_elem else None

            gain_elem = article.select_one(".float-sm-right")
            stars_today = 0
            if gain_elem:
                stars_today = self._parse_trending_stars_gain(gain_elem.get_text(" ", strip=True))

            return Repo(
                name=name,
                full_name=full_name,
                description=description,
                url=url,
                stars=stars,
                language=language,
                stars_today=stars_today,
            )
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _parse_trending_stars_gain(text: str) -> int:
        if not text:
            return 0

        normalized = " ".join(text.lower().split())
        if not any(token in normalized for token in ("today", "this week", "this month")):
            return 0

        # Typical formats:
        # - "1,234 stars today"
        # - "2,345 stars this week"
        # - "987 stars this month"
        match = re.search(r"([0-9][0-9,]*(?:\.\d+)?[kKmM]?)\s+stars?\s+(today|this week|this month)", normalized)
        if match:
            return GitHubFetcher._parse_number(match.group(1))

        # Fallback: if period token exists, parse first numeric token.
        first_number = re.search(r"([0-9][0-9,]*(?:\.\d+)?[kKmM]?)", normalized)
        return GitHubFetcher._parse_number(first_number.group(1)) if first_number else 0

    @staticmethod
    def _parse_number(text: str) -> int:
        value = (text or "").replace(",", "").strip()
        if not value:
            return 0
        suffix = value[-1]
        try:
            if suffix in {"k", "K"}:
                return int(float(value[:-1]) * 1000)
            if suffix in {"m", "M"}:
                return int(float(value[:-1]) * 1000000)
            return int(float(value))
        except ValueError:
            return 0


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after
