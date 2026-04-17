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
from urllib.parse import quote

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    source: str
    title: str
    url: str
    snippet: str
    score: int
    created_at: Optional[datetime] = None
    comments_count: int = 0
    sentiment: str = "neutral"


class HackerNewsSearcher:
    """Hacker News 搜索"""

    API_BASE = "https://hn.algolia.com/api/v1"

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        try:
            # trust_env=True: allow using HTTP(S)_PROXY from environment (common on Windows/VPN setups)
            async with aiohttp.ClientSession(trust_env=True) as session:
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
                        score = hit.get("points", 0) + hit.get("num_comments", 0) * 2

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
                            sentiment="neutral"
                        ))

                    return sorted(results, key=lambda x: x.score, reverse=True)
        except Exception as e:
            logger.error(f"Hacker News 搜索失败: {e}")
            return []


class RedditSearcher:
    """Reddit 搜索 - 使用 Playwright 绕过 Cloudflare"""

    def __init__(self):
        from app.infrastructure.config import get_config
        config = get_config()
        self.cookie = config.reddit.cookie
        self.enabled = config.reddit.enabled
        self.timeout = config.reddit.timeout

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        if not self.enabled:
            logger.debug("Reddit 搜索已禁用")
            return []

        if not self.cookie:
            logger.warning("Reddit Cookie 未配置，跳过 Reddit 搜索")
            return []

        try:
            return await self._search_with_playwright(query, limit)
        except Exception as e:
            logger.error(f"Reddit 搜索失败: {e}")
            return []

    async def _search_with_playwright(self, query: str, limit: int) -> List[SearchResult]:
        from playwright.async_api import async_playwright

        encoded_query = quote(query, safe='')
        search_urls = [
            f"https://www.reddit.com/search/?q={encoded_query}&sort=hot&t=week",
            f"https://old.reddit.com/search/?q={encoded_query}&sort=relevance&t=week",
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            cookies = self._parse_cookie_string(self.cookie)
            if cookies:
                await context.add_cookies(cookies)

            page = await context.new_page()
            page.set_default_timeout(self.timeout * 1000)

            aggregated_results = []
            try:
                for search_url in search_urls:
                    try:
                        await page.goto(search_url, wait_until="domcontentloaded")
                        ready = await self._wait_reddit_ready(page)
                        if not ready:
                            logger.debug(f"Reddit 页面未找到预期元素: {search_url}")
                            continue
                        page_results = await self._extract_reddit_results(page, limit)
                        if page_results:
                            aggregated_results.extend(page_results)
                            break
                    except Exception as e:
                        page_title = await page.title()
                        logger.error(
                            f"Playwright 访问 Reddit 失败: url={search_url} title={page_title} "
                            f"error_type={type(e).__name__} error={e}"
                        )
            finally:
                await browser.close()

        if not aggregated_results:
            return []

        dedup = {}
        for item in aggregated_results:
            if item.url and item.url not in dedup:
                dedup[item.url] = item

        return list(dedup.values())[:limit]

    async def _wait_reddit_ready(self, page) -> bool:
        selectors = [
            '[data-testid="search-results"]',
            'article[data-testid="search-result-post"]',
            'div.search-result',
            'div.thing',
            'div[data-testid="no-search-results"]',
            'div.search-result-group',
        ]

        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=10000)
                return True
            except Exception:
                continue

        return False

    async def _extract_reddit_results(self, page, limit: int) -> List[SearchResult]:
        no_results = await page.query_selector('div[data-testid="no-search-results"]')
        if no_results:
            logger.debug("Reddit 搜索无结果")
            return []

        posts = await page.query_selector_all('article[data-testid="search-result-post"]')
        if posts:
            logger.debug(f"找到 {len(posts)} 个新 Reddit 帖子")
            return await self._parse_new_reddit_posts(posts, limit)

        posts = await page.query_selector_all('div.search-result, div.thing')
        if posts:
            logger.debug(f"找到 {len(posts)} 个旧 Reddit 帖子")
            return await self._parse_old_reddit_posts(posts, limit)

        posts = await page.query_selector_all('div[data-click-id="body"]')
        if posts:
            logger.debug(f"找到 {len(posts)} 个 Reddit 帖子 (body selector)")
            return await self._parse_new_reddit_posts(posts, limit)

        logger.debug("Reddit 页面未找到帖子元素")
        return []

    async def _parse_new_reddit_posts(self, posts, limit: int) -> List[SearchResult]:
        results = []
        for post in posts[:limit]:
            try:
                title_elem = await post.query_selector('h3')
                title = await title_elem.inner_text() if title_elem else ""

                link_elem = await post.query_selector('a[data-testid="post-title"]')
                href = await link_elem.get_attribute('href') if link_elem else ""
                if href and href.startswith('/'):
                    href = f"https://www.reddit.com{href}"

                subreddit_elem = await post.query_selector('a[data-testid="subreddit-link"]')
                subreddit = ""
                if subreddit_elem:
                    subreddit_text = await subreddit_elem.inner_text()
                    subreddit = subreddit_text.replace('r/', '').strip()

                score_elem = await post.query_selector('[data-testid="post-score"]')
                score_text = await score_elem.inner_text() if score_elem else "0"
                score = self._parse_score(score_text)

                comments_elem = await post.query_selector('a[data-click-id="comments"]')
                comments_text = await comments_elem.inner_text() if comments_elem else "0"
                comments = self._parse_comments(comments_text)

                snippet_elem = await post.query_selector('div[data-testid="post-content"] p')
                snippet = await snippet_elem.inner_text() if snippet_elem else ""
                snippet = snippet[:200] if snippet else ""

                if title and href:
                    results.append(SearchResult(
                        source=f"reddit/r/{subreddit}" if subreddit else "reddit",
                        title=title,
                        url=href,
                        snippet=snippet,
                        score=score + comments * 2,
                        created_at=None,
                        comments_count=comments,
                        sentiment="neutral"
                    ))
            except Exception as e:
                logger.debug(f"解析 Reddit 帖子失败: {e}")
                continue
        return results

    async def _parse_old_reddit_posts(self, posts, limit: int) -> List[SearchResult]:
        results = []
        for post in posts[:limit]:
            try:
                title_elem = await post.query_selector('a.search-title, a.title')
                title = await title_elem.inner_text() if title_elem else ""
                href = await title_elem.get_attribute('href') if title_elem else ""
                if href and href.startswith('/'):
                    href = f"https://old.reddit.com{href}"

                subreddit_elem = await post.query_selector('a.search-subreddit-link, a.subreddit')
                subreddit = ""
                if subreddit_elem:
                    subreddit = (await subreddit_elem.inner_text()).replace('r/', '').strip()

                snippet_elem = await post.query_selector('.search-expando, .search-result-body')
                snippet = await snippet_elem.inner_text() if snippet_elem else ""
                snippet = snippet[:200] if snippet else ""

                comments_elem = await post.query_selector('a.search-comments, a.comments')
                comments_text = await comments_elem.inner_text() if comments_elem else "0"
                comments = self._parse_comments(comments_text)

                score_elem = await post.query_selector('.search-score, .score.unvoted')
                score_text = await score_elem.inner_text() if score_elem else "0"
                score = self._parse_score(score_text)

                if title and href:
                    results.append(SearchResult(
                        source=f"reddit/r/{subreddit}" if subreddit else "reddit",
                        title=title,
                        url=href,
                        snippet=snippet,
                        score=score + comments * 2,
                        created_at=None,
                        comments_count=comments,
                        sentiment="neutral"
                    ))
            except Exception as e:
                logger.debug(f"解析 old.reddit 帖子失败: {e}")
                continue
        return results

    def _parse_cookie_string(self, cookie_string: str) -> List[Dict]:
        if not cookie_string:
            return []

        cookies = []
        for item in cookie_string.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': '.reddit.com',
                    'path': '/'
                })
        return cookies

    def _parse_score(self, text: str) -> int:
        text = text.strip().lower().replace(',', '')
        if 'k' in text:
            return int(float(text.replace('k', '')) * 1000)
        try:
            return int(text)
        except ValueError:
            return 0

    def _parse_comments(self, text: str) -> int:
        text = text.strip().lower().replace(',', '')
        text = text.replace('comments', '').replace('comment', '').strip()
        if 'k' in text:
            return int(float(text.replace('k', '')) * 1000)
        try:
            return int(text)
        except ValueError:
            return 0


class GitHubDiscussionsSearcher:
    """搜索 GitHub Discussions 和 Issues"""

    async def search(self, repo_name: str, github_token: Optional[str] = None) -> List[SearchResult]:
        """搜索项目的 Discussions"""
        try:
            # trust_env=True: allow using HTTP(S)_PROXY from environment
            async with aiohttp.ClientSession(trust_env=True) as session:
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
                            score=item.get("comments", 0) * 3,
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
        """全面搜索项目的外部讨论"""
        exact_query = f'"{repo_name}"'

        search_tasks = [
            self.hackernews.search(exact_query, limit=10),
            self.reddit.search(exact_query, limit=10),
            self.github_discussions.search(repo_name, self.github_token)
        ]

        hn_results, reddit_results, github_results = await asyncio.gather(*search_tasks)

        all_results = hn_results + reddit_results + github_results

        hot_discussions = sorted(all_results, key=lambda x: x.score, reverse=True)[:5]

        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for r in all_results:
            sentiment_counts[r.sentiment] += 1

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
