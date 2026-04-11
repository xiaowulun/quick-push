"""
GitHub 数据抓取器

负责从 GitHub API 获取 Trending 数据
"""

import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import httpx
from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class RepoInfo:
    """仓库基本信息"""
    repo_full_name: str
    description: Optional[str]
    stars: int
    forks: int
    language: Optional[str]
    open_issues: int
    repo_url: str
    owner: str
    name: str


class GitHubFetcher:
    """GitHub Trending 数据抓取器"""

    def __init__(self, token: Optional[str] = None):
        config = get_config()
        self.token = token or config.github.token
        self.base_url = "https://api.github.com"
        self.timeout = 30.0

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "QuickPush/1.0"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    async def fetch_trending_repos(
        self,
        language: Optional[str] = None,
        date_range: str = "daily",
        limit: int = 50
    ) -> List[RepoInfo]:
        """获取 Trending 仓库"""
        try:
            if date_range == "daily":
                date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            elif date_range == "weekly":
                date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            elif date_range == "monthly":
                date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            else:
                date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

            query = f"created:>{date_from}"
            if language:
                query += f" language:{language}"

            url = f"{self.base_url}/search/repositories"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(limit, 100)
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                data = response.json()

            repos = []
            for item in data.get("items", []):
                repos.append(RepoInfo(
                    repo_full_name=item["full_name"],
                    description=item.get("description"),
                    stars=item.get("stargazers_count", 0),
                    forks=item.get("forks_count", 0),
                    language=item.get("language"),
                    open_issues=item.get("open_issues_count", 0),
                    repo_url=item["html_url"],
                    owner=item["owner"]["login"],
                    name=item["name"]
                ))

            logger.info(f"获取到 {len(repos)} 个 Trending 仓库")
            return repos

        except httpx.HTTPError as e:
            logger.error(f"HTTP 错误: {e}")
            return []
        except Exception as e:
            logger.error(f"获取 Trending 失败: {e}")
            return []

    async def fetch_readme(self, owner: str, repo: str) -> Optional[str]:
        """获取仓库 README"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/readme"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()

                import base64
                content = data.get("content", "")
                encoding = data.get("encoding", "utf-8")

                if encoding == "base64":
                    content = base64.b64decode(content).decode("utf-8", errors="ignore")

                return content

        except Exception as e:
            logger.error(f"获取 README 失败 {owner}/{repo}: {e}")
            return None

    async def fetch_repo_details(self, owner: str, repo: str) -> Optional[Dict]:
        """获取仓库详细信息"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"获取仓库详情失败 {owner}/{repo}: {e}")
            return None

    @staticmethod
    def parse_repo_full_name(full_name: str) -> tuple:
        """解析仓库全名"""
        parts = full_name.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", ""
