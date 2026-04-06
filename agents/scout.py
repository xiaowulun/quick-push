"""
Scout Agent - 趋势情报侦察员

负责分析项目的"八卦"和趋势：
- 为什么突然火了？（时间维度分析）
- 社区讨论热点
- 技术趋势关联
- 竞品对比优势
- 潜在爆火因素
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import re

from agents.base import BaseAgent, AgentResult
from core.config import get_config

logger = logging.getLogger(__name__)


class ScoutAgent(BaseAgent):
    """趋势情报侦察员 - 专注"八卦"和趋势分析"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__("ScoutAgent", config)

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        分析项目趋势和爆火原因

        Args:
            context: {
                "repo_name": str,
                "repo_data": Dict,  # GitHub API 数据
                "description": str,
                "readme_content": str,
                "historical_data": List[Dict],  # 历史趋势数据（可选）
            }
        """
        self.log_start(context)

        try:
            repo_name = context.get("repo_name", "")
            repo_data = context.get("repo_data", {})
            description = context.get("description", "")
            readme_content = context.get("readme_content", "")
            historical_data = context.get("historical_data", [])

            # 分析爆火因素
            popularity_factors = self._analyze_popularity_factors(repo_data, readme_content)

            # 分析技术趋势关联
            trend_analysis = self._analyze_trends(repo_name, description, readme_content)

            # 分析社区热度指标
            community_buzz = self._analyze_community_buzz(repo_data, readme_content)

            # 竞品对比分析
            competitive_edge = self._analyze_competitive_edge(repo_name, description, readme_content)

            result_data = {
                "popularity_factors": popularity_factors,
                "trend_analysis": trend_analysis,
                "community_buzz": community_buzz,
                "competitive_edge": competitive_edge,
                "collected_at": datetime.now().isoformat(),
            }

            result = self.create_success_result(
                data=result_data,
                metadata={
                    "repo_name": repo_name,
                    "focus": "trend_and_gossip",
                }
            )

            self.log_end(result)
            return result

        except Exception as e:
            error_msg = f"趋势分析失败: {str(e)}"
            logger.error(error_msg)
            return self.create_error_result(error_msg)

    def _analyze_popularity_factors(self, repo_data: Dict, readme: str) -> Dict:
        """分析爆火因素 - 为什么突然火了？"""
        factors = []
        indicators = []

        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        created_at = repo_data.get("created_at", "")
        topics = repo_data.get("topics", [])

        # 1. 新项目爆发
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_days = (datetime.now() - created.replace(tzinfo=None)).days

                if age_days < 30 and stars > 1000:
                    factors.append("新项目爆发式增长，短时间内获得大量关注")
                    indicators.append("new_star")
                elif age_days < 7:
                    factors.append("本周新项目，处于早期热度期")
                    indicators.append("brand_new")
            except:
                pass

        # 2. 技术热点关联
        hot_tech_patterns = {
            "ai": ["ai", "llm", "gpt", "claude", "openai", "machine learning", "大模型", "agent"],
            "rust": ["rust", "高性能", "内存安全"],
            "web3": ["web3", "blockchain", "crypto", "nft"],
            "devops": ["kubernetes", "docker", "devops", "ci/cd"],
        }

        readme_lower = readme.lower()
        matched_trends = []
        for trend, keywords in hot_tech_patterns.items():
            if any(kw in readme_lower or kw in str(topics).lower() for kw in keywords):
                matched_trends.append(trend)
                indicators.append(f"trend_{trend}")

        if matched_trends:
            if len(matched_trends) == 1:
                factors.append(f"踩中{matched_trends[0].upper()}技术热点，符合当前行业趋势")
            else:
                factors.append(f"同时踩中多个技术热点：{', '.join(matched_trends[:2]).upper()}，复合赛道优势")

        # 从 topics 推断技术方向
        if topics:
            tech_topics = [t for t in topics if t not in ['python', 'javascript', 'typescript', 'java', 'go', 'rust']]
            if tech_topics and len(factors) < 3:
                factors.append(f"标签涵盖热门技术方向：{', '.join(tech_topics[:3])}")
                indicators.append("hot_topics")

        # 3. 大厂/名人背书
        owner = repo_data.get("owner", {}).get("login", "")
        big_names = ["microsoft", "google", "facebook", "apple", "amazon", "openai", "anthropic"]
        if owner.lower() in big_names:
            factors.append(f"{owner}官方出品，自带流量和信任度")
            indicators.append("big_tech")

        # 4. 解决痛点
        pain_point_keywords = ["替代", "取代", "更快", "更简单", "轻量级", "零配置", "自动化"]
        for kw in pain_point_keywords:
            if kw in readme[:2000]:
                factors.append(f"精准解决开发者痛点：{kw}")
                indicators.append("pain_point")
                break

        # 5. Star/Fork 比例分析社区参与度
        if stars > 100:
            fork_ratio = forks / stars
            if fork_ratio > 0.15:
                factors.append("Fork率极高，说明开发者参与意愿强，不只是围观")
                indicators.append("high_engagement")

        return {
            "factors": factors[:5],  # 最多5个因素
            "indicators": indicators,
            "hype_level": self._calculate_hype_level(stars, factors),
        }

    def _analyze_trends(self, repo_name: str, description: str, readme: str) -> Dict:
        """分析技术趋势关联"""
        trends = []
        text = f"{repo_name} {description} {readme[:3000]}".lower()

        # 趋势关键词映射
        trend_keywords = {
            "AI 应用落地": ["agent", "rag", "fine-tune", "推理", "部署"],
            "开发者体验": ["cli", "tool", "workflow", "automation", "脚手架"],
            "性能优化": ["fast", "lightweight", "zero-cost", "高性能", "优化"],
            "云原生": ["cloud", "serverless", "container", "k8s", "微服务"],
            "前端工程化": ["bundler", "vite", "webpack", "build tool"],
        }

        for trend_name, keywords in trend_keywords.items():
            if any(kw in text for kw in keywords):
                trends.append(trend_name)

        return {
            "related_trends": trends[:3],
            "trend_fit_score": min(len(trends) * 0.3, 1.0),  # 趋势契合度
        }

    def _analyze_community_buzz(self, repo_data: Dict, readme: str) -> Dict:
        """分析社区热度"""
        buzz_signals = []

        # 从 README 检测社区活跃度信号
        if re.search(r"(?i)discord|slack|telegram", readme):
            buzz_signals.append("有活跃的社区聊天群组")

        if re.search(r"(?i)sponsor|赞助|捐赠", readme):
            buzz_signals.append("已获得社区赞助支持")

        if re.search(r"(?i)contributor|贡献者", readme[:5000]):
            buzz_signals.append("强调社区贡献，生态活跃")

        # 检测是否有媒体/博客推荐
        media_keywords = ["featured", "trending", "awesome", "推荐", "精选"]
        for kw in media_keywords:
            if kw in readme.lower():
                buzz_signals.append("被技术媒体或 Awesome 列表推荐")
                break

        return {
            "buzz_signals": buzz_signals,
            "community_health": len(buzz_signals) / 3,  # 社区健康度
        }

    def _analyze_competitive_edge(self, repo_name: str, description: str, readme: str) -> Dict:
        """分析竞争优势"""
        edges = []
        text = readme[:4000].lower()

        # 对比优势关键词
        comparison_patterns = [
            (r"(?i)faster than|比.*快|性能提升|加速", "性能优势"),
            (r"(?i)lighter|更轻量|体积小|minimal", "轻量优势"),
            (r"(?i)simpler|更简单|易用|零配置", "易用性优势"),
            (r"(?i)vs\.|versus|对比|compared to|alternative to", "对标竞品"),
            (r"(?i)unlike|不同于|区别于", "差异化优势"),
        ]

        for pattern, label in comparison_patterns:
            if re.search(pattern, text):
                edges.append(label)

        # 独特功能
        unique_features = []
        if re.search(r"(?i)first|首个|唯一|首创", text):
            unique_features.append("首创功能")
        if re.search(r"(?i)open source|开源|free", text):
            unique_features.append("开源免费")

        return {
            "competitive_edges": edges[:3],
            "unique_features": unique_features,
            "differentiation_score": min((len(edges) + len(unique_features)) * 0.25, 1.0),
        }

    def _calculate_hype_level(self, stars: int, factors: List[str]) -> str:
        """计算炒作热度等级"""
        if len(factors) >= 4 and stars > 10000:
            return "viral"  # 病毒式传播
        elif len(factors) >= 3 and stars > 5000:
            return "hot"    # 很火
        elif len(factors) >= 2 and stars > 1000:
            return "trending"  #  trending
        elif len(factors) >= 1:
            return "rising"   # 上升期
        else:
            return "stable"   # 稳定
