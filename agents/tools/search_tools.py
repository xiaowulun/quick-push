"""
搜索工具 - 获取项目的外部讨论和趋势信息

用于 Scout Agent 收集项目的"八卦"和社区热度
"""

import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    source: str  # 来源：hackernews, reddit, github_discussions, etc.
    title: str
    url: str
    snippet: str
    score: int  # 热度分数
    created_at: Optional[datetime] = None
    comments_count: int = 0
    sentiment: str = "neutral"  # positive, neutral, negative


class HackerNewsSearcher:
    """Hacker News 搜索"""

    API_BASE = "https://hn.algolia.com/api/v1"

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.API_BASE}/search"
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": "created_at_i>" + str(int((datetime.now() - timedelta(days=7)).timestamp())),
                    "hitsPerPage": limit
                }

                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    results = []

                    for hit in data.get("hits", []):
                        # 计算热度分数：积分 + 评论数 * 2
                        score = hit.get("points", 0) + hit.get("num_comments", 0) * 2
                        
                        # 处理空文本：如果没正文，用一句提示词代替，引导 LLM 关注热度
                        raw_snippet = hit.get("story_text")
                        snippet = raw_snippet[:200] if raw_snippet else f"[外部链接帖] 引发了 {hit.get('num_comments', 0)} 条社区讨论。"

                        results.append(SearchResult(
                            source="hackernews",
                            title=hit.get("title", ""),
                            url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                            snippet=snippet,
                            score=score,
                            created_at=datetime.fromtimestamp(hit.get("created_at_i", 0)),
                            comments_count=hit.get("num_comments", 0),
                            sentiment="neutral" # 废弃本地极性判断，交给 LLM
                        ))

                    return sorted(results, key=lambda x: x.score, reverse=True)
        except Exception as e:
            logger.error(f"Hacker News 搜索失败: {e}")
            return []


class RedditSearcher:
    """Reddit 搜索（全局搜索优化版）"""

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        try:
            async with aiohttp.ClientSession() as session:
                # 直接调用全站搜索，搜索范围为最近一周
                url = "https://www.reddit.com/search.json"
                params = {
                    "q": query,
                    "sort": "hot",
                    "t": "week",
                    "limit": limit
                }
                # User-Agent 必须稍微伪装一下，否则很容易被 Reddit 429 拦截
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

                async with session.get(url, params=params, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        logger.warning(f"Reddit API 返回 {response.status}")
                        return []

                    data = await response.json()
                    posts = data.get("data", {}).get("children", [])
                    results = []

                    for post in posts:
                        post_data = post.get("data", {})
                        score = post_data.get("score", 0) + post_data.get("num_comments", 0) * 2

                        results.append(SearchResult(
                            source=f"reddit/r/{post_data.get('subreddit', 'unknown')}",
                            title=post_data.get("title", ""),
                            url=f"https://reddit.com{post_data.get('permalink', '')}",
                            # 保证内容不为 None
                            snippet=(post_data.get("selftext") or "")[:200],
                            score=score,
                            created_at=datetime.fromtimestamp(post_data.get("created_utc", 0)),
                            comments_count=post_data.get("num_comments", 0),
                            sentiment="neutral" # 交给后续 LLM 分析
                        ))

                    return results
        except Exception as e:
            logger.error(f"Reddit 搜索失败: {e}")
            return []


class GitHubDiscussionsSearcher:
    """搜索 GitHub Discussions 和 Issues"""

    async def search(self, repo_name: str, github_token: Optional[str] = None) -> List[SearchResult]:
        """搜索项目的 Discussions"""
        try:
            async with aiohttp.ClientSession() as session:
                # 搜索项目的 discussions
                url = f"https://api.github.com/search/issues"
                params = {
                    "q": f"repo:{repo_name} is:discussion sort:created-desc",
                    "per_page": 10
                }
                headers = {"Accept": "application/vnd.github.v3+json"}
                if github_token:
                    headers["Authorization"] = f"token {github_token}"

                async with session.get(url, params=params, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    results = []

                    for item in data.get("items", []):
                        results.append(SearchResult(
                            source="github_discussions",
                            title=item.get("title", ""),
                            url=item.get("html_url", ""),
                            snippet=item.get("body", "")[:200],
                            score=item.get("comments", 0) * 3,  # Discussions 权重更高
                            created_at=datetime.fromisoformat(item.get("created_at", "").replace("Z", "+00:00")),
                            comments_count=item.get("comments", 0)
                        ))

                    return results

        except Exception as e:
            logger.error(f"GitHub Discussions 搜索失败: {e}")
            return []


class SearchAggregator:
    """搜索聚合器 - 整合多个搜索源"""

    def __init__(self, github_token: Optional[str] = None):
        self.hackernews = HackerNewsSearcher()
        self.reddit = RedditSearcher()
        self.github_discussions = GitHubDiscussionsSearcher()
        self.github_token = github_token

    async def search_project(self, repo_name: str, description: str = "") -> Dict:
        """
        全面搜索项目的外部讨论

        Returns:
            {
                "total_mentions": 总提及数,
                "sources": {
                    "hackernews": 数量,
                    "reddit": 数量,
                    "github_discussions": 数量
                },
                "hot_discussions": [最热门的讨论, ...],
                "sentiment_summary": {
                    "positive": 正面讨论数,
                    "neutral": 中性讨论数,
                    "negative": 负面讨论数
                },
                "raw_text": "所有讨论文本拼接，用于 LLM 分析",
                "has_external_discussion": bool
            }
        """
        # 提取项目名（去掉 owner）
        exact_query = f'"{repo_name}"'

        # 并行搜索多个源
        search_tasks = [
            self.hackernews.search(exact_query, limit=10),
            self.reddit.search(exact_query, limit=10),
            # GitHub 自己的搜索不需要加引号，它本身就是搜 repo
            self.github_discussions.search(repo_name, self.github_token)
        ]

        hn_results, reddit_results, github_results = await asyncio.gather(*search_tasks)

        # 整合结果
        all_results = hn_results + reddit_results + github_results

        # 按热度排序
        hot_discussions = sorted(all_results, key=lambda x: x.score, reverse=True)[:5]

        # 情感统计
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for r in all_results:
            sentiment_counts[r.sentiment] += 1

        # 生成原始文本（用于 LLM 分析）
        raw_text_parts = []
        for r in hot_discussions:
            raw_text_parts.append(f"[{r.source}] {r.title}\n{r.snippet}\n")

        return {
            "total_mentions": len(all_results),
            "sources": {
                "hackernews": len(hn_results),
                "reddit": len(reddit_results),
                "github_discussions": len(github_results)
            },
            "hot_discussions": [
                {
                    "source": r.source,
                    "title": r.title,
                    "url": r.url,
                    "score": r.score,
                    "sentiment": r.sentiment,
                    "comments": r.comments_count
                }
                for r in hot_discussions
            ],
            "sentiment_summary": sentiment_counts,
            "raw_text": "\n".join(raw_text_parts),
            "has_external_discussion": len(all_results) > 0
        }
