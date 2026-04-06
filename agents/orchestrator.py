"""
Agent Orchestrator - 任务调度器

负责协调多个 Agent 的执行：
- 管理 Agent 执行顺序
- 传递上下文信息
- 处理错误和重试
- 整合最终结果
"""

from typing import Any, Dict, List, Optional
import asyncio
import logging

from agents.base import BaseAgent, AgentResult
from agents.scout import ScoutAgent
from agents.analyst import AnalystAgent
from agents.editor import EditorAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Agent 任务调度器"""

    def __init__(self):
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.editor = EditorAgent()
        self.logger = logging.getLogger("agents.orchestrator")

    async def analyze_project(
        self,
        repo_name: str,
        repo_data: Dict[str, Any],
        readme_content: Optional[str],
        description: Optional[str],
        category: str
    ) -> AgentResult:
        """
        执行完整的 Multi-Agent 分析流程

        流程: Scout -> Analyst -> Editor

        Args:
            repo_name: 项目全名
            repo_data: GitHub API 返回的项目数据
            readme_content: README 内容
            description: 项目描述
            category: 项目分类

        Returns:
            AgentResult: 最终分析结果
        """
        self.logger.info(f"[Orchestrator] 开始分析项目: {repo_name}")

        try:
            # Step 1: Scout Agent - 趋势八卦分析
            scout_context = {
                "repo_name": repo_name,
                "repo_data": repo_data,
                "description": description,
                "readme_content": readme_content or "",
            }
            scout_result = await self.scout.execute(scout_context)
            self.logger.info(f"[Orchestrator] Scout 完成: {scout_result.success}")

            # Step 2: Analyst Agent - 技术深度分析
            analyst_context = {
                "repo_name": repo_name,
                "readme_content": readme_content or "",
                "repo_data": repo_data,
            }
            analyst_result = await self.analyst.execute(analyst_context)
            self.logger.info(f"[Orchestrator] Analyst 完成: {analyst_result.success}")

            # Step 3: Editor Agent - 整合审查
            editor_context = {
                "repo_name": repo_name,
                "description": description,
                "scout_result": scout_result.data if scout_result.success else {},
                "analyst_result": analyst_result.data if analyst_result.success else {},
                "category": category,
            }
            editor_result = await self.editor.execute(editor_context)
            self.logger.info(f"[Orchestrator] Editor 完成: {editor_result.success}")

            # 整合最终结果
            if editor_result.success:
                return self._create_final_result(
                    repo_name=repo_name,
                    editor_result=editor_result,
                    scout_result=scout_result,
                    analyst_result=analyst_result,
                )
            else:
                # Editor 失败，降级使用基础分析
                return self._create_fallback_result(
                    repo_name=repo_name,
                    error=editor_result.error,
                    scout_result=scout_result,
                    analyst_result=analyst_result,
                )

        except Exception as e:
            error_msg = f"Multi-Agent 分析失败: {str(e)}"
            self.logger.error(f"[Orchestrator] {error_msg}")
            return AgentResult(
                success=False,
                error=error_msg,
                agent_name="AgentOrchestrator"
            )

    def _create_final_result(
        self,
        repo_name: str,
        editor_result: AgentResult,
        scout_result: AgentResult,
        analyst_result: AgentResult
    ) -> AgentResult:
        """创建最终结果"""

        editor_data = editor_result.data
        report = editor_data.get("report", {})
        quality = editor_data.get("quality_assessment", {})

        # 构建最终输出格式（与现有系统兼容）
        final_data = {
            "summary": report.get("summary", ""),
            "reasons": report.get("reasons", []),
            "tech_highlights": report.get("tech_highlights", []),
            "target_users": report.get("target_users", ""),
            "quality_score": quality.get("overall_score", 0),
            "confidence": quality.get("confidence", 0),
            # 保留详细数据供后续使用
            "detailed": {
                "scout": scout_result.data if scout_result.success else None,
                "analyst": analyst_result.data if analyst_result.success else None,
                "editor": editor_data,
            }
        }

        return AgentResult(
            success=True,
            data=final_data,
            metadata={
                "repo_name": repo_name,
                "multi_agent": True,
                "quality_score": quality.get("overall_score", 0),
            },
            agent_name="AgentOrchestrator"
        )

    def _create_fallback_result(
        self,
        repo_name: str,
        error: Optional[str],
        scout_result: AgentResult,
        analyst_result: AgentResult
    ) -> AgentResult:
        """创建降级结果（Editor 失败时使用）- 基于 Scout + Analyst 数据智能生成"""

        self.logger.warning(f"[Orchestrator] Editor 失败，使用智能降级方案: {error}")

        # 提取 Scout 数据（趋势八卦）
        scout_data = scout_result.data if scout_result.success else {}
        popularity_factors = scout_data.get("popularity_factors", {})
        trend_analysis = scout_data.get("trend_analysis", {})
        competitive_edge = scout_data.get("competitive_edge", {})

        # 提取 Analyst 数据（技术深度）
        analyst_data = analyst_result.data if analyst_result.success else {}
        content_quality = analyst_data.get("content_quality", {})
        tech_analysis = analyst_data.get("tech_analysis", {})
        substance_score = analyst_data.get("substance_score", {})
        quality_metrics = analyst_data.get("quality_metrics", {})

        # 技术领域映射（内部标识符 -> 中文）
        domain_names = {
            "frontend": "前端",
            "backend": "后端",
            "database": "数据库",
            "ai_ml": "AI/ML",
            "cloud": "云原生",
            "mobile": "移动端",
            "devops": "DevOps",
        }

        # 生成智能摘要
        summary_parts = []

        # 1. 技术栈信息
        primary_lang = tech_analysis.get("primary_language", "")
        tech_domains = tech_analysis.get("tech_domains", [])

        if primary_lang:
            domain_display = [domain_names.get(d, d) for d in tech_domains[:2]]
            if domain_display:
                summary_parts.append(f"基于 {primary_lang} 的 {'/'.join(domain_display)} 项目")
            else:
                summary_parts.append(f"基于 {primary_lang} 开发")

        # 2. 核心功能（从 Scout 的 factors 提取关键词）
        factors = popularity_factors.get("factors", [])
        if factors:
            # 提取第一个因素的核心信息
            first_factor = factors[0]
            if "踩中" in first_factor and "技术热点" in first_factor:
                # 提取技术名称（支持单个或多个）
                import re
                # 尝试匹配 "踩中XXX技术" 或 "踩中多个技术热点：XXX, YYY"
                tech_match = re.search(r'踩中(\w+)技术', first_factor)
                multi_match = re.search(r'踩中多个技术热点：([^，,]+)', first_factor)
                if multi_match:
                    tech_names = multi_match.group(1).strip().upper()
                    summary_parts.append(f"，聚焦 {tech_names} 领域")
                elif tech_match:
                    tech_name = tech_match.group(1).upper()
                    summary_parts.append(f"，聚焦 {tech_name} 领域")

        # 3. 项目性质
        project_nature = substance_score.get("project_nature", "")
        if project_nature == "substantial":
            summary_parts.append("，技术实现扎实")
        elif project_nature == "moderate":
            summary_parts.append("，提供实用的开发工具")

        # 4. 热度等级
        hype_level = popularity_factors.get("hype_level", "")
        if hype_level in ["viral", "hot", "trending"]:
            summary_parts.append("，近期获得大量关注")

        # 清理摘要格式（去除开头的标点）
        fallback_summary = "".join(summary_parts) if summary_parts else f"{repo_name.split('/')[-1]} 是一个基于 {primary_lang or '现代技术栈'} 的开源项目"
        fallback_summary = fallback_summary.lstrip("，, ")  # 去除开头的逗号和空格

        # 生成爆火原因（从 Scout 的 factors 提取）
        fallback_reasons = []
        factors = popularity_factors.get("factors", [])

        # 优先使用 Scout 分析的爆火因素，但重新格式化
        for factor in factors[:3]:
            # 重新格式化因素，使其更简洁
            if "踩中" in factor and "技术热点" in factor:
                # 提取技术名称（支持单个或多个）
                tech_match = re.search(r'踩中(\w+)技术', factor)
                multi_match = re.search(r'踩中多个技术热点：([^，,]+)', factor)
                if multi_match:
                    tech_names = multi_match.group(1).strip().upper()
                    fallback_reasons.append(f"踩中 {tech_names} 技术热点，符合行业趋势")
                elif tech_match:
                    tech_name = tech_match.group(1).upper()
                    fallback_reasons.append(f"踩中 {tech_name} 技术热点，符合行业趋势")
                else:
                    fallback_reasons.append("契合当前技术发展趋势")
            elif "标签涵盖" in factor:
                # 提取标签
                tag_match = re.search(r'标签涵盖热门技术方向：(.+)', factor)
                if tag_match:
                    tags = tag_match.group(1)
                    fallback_reasons.append(f"技术标签热门：{tags}")
                else:
                    fallback_reasons.append(factor)
            else:
                # 简化其他因素
                if "，" in factor:
                    factor = factor.split("，")[0]
                if len(factor) > 40:
                    factor = factor[:37] + "..."
                fallback_reasons.append(factor)

        # 补充技术亮点
        if not fallback_reasons:
            # 从技术栈补充
            frameworks = tech_analysis.get("frameworks", [])
            if frameworks:
                fallback_reasons.append(f"采用 {frameworks[0]} 技术栈")

            # 从质量指标补充
            if quality_metrics.get("overall_quality") == "high":
                fallback_reasons.append("文档完善，维护活跃")

        # 再补充社区热度
        if len(fallback_reasons) < 3:
            buzz_signals = scout_data.get("community_buzz", {}).get("buzz_signals", [])
            if buzz_signals:
                fallback_reasons.append("社区活跃度高")

        # 保底
        if not fallback_reasons:
            fallback_reasons = ["近期获得社区关注", "技术方向符合当前趋势"]

        # 生成技术亮点
        tech_highlights = []

        # 从 Analyst 提取
        if content_quality.get("has_code_examples"):
            tech_highlights.append("提供详细代码示例")
        if content_quality.get("has_api_docs"):
            tech_highlights.append("API 文档完整")

        # 从技术栈提取
        modern_score = tech_analysis.get("modern_score", 0)
        if modern_score > 0.5:
            tech_highlights.append("采用现代化技术栈")

        # 从竞争优势提取
        edges = competitive_edge.get("competitive_edges", [])
        if edges:
            tech_highlights.append(f"具备{edges[0]}")

        # 目标用户
        target_users = ""
        if tech_domains:
            if "ai_ml" in tech_domains:
                target_users = "AI 开发者、数据科学家"
            elif "frontend" in tech_domains:
                target_users = "前端开发者"
            elif "backend" in tech_domains:
                target_users = "后端开发者"
            elif "devops" in tech_domains:
                target_users = "DevOps 工程师"
            else:
                target_users = f"{'/'.join(tech_domains[:2])} 开发者"

        # 计算质量分
        quality_score = 0.5
        if substance_score.get("substance_score", 0) > 0.7:
            quality_score += 0.2
        if quality_metrics.get("overall_quality") == "high":
            quality_score += 0.15
        if popularity_factors.get("hype_level") in ["viral", "hot"]:
            quality_score += 0.1

        return AgentResult(
            success=True,
            data={
                "summary": fallback_summary,
                "reasons": fallback_reasons[:5],
                "tech_highlights": tech_highlights[:3],
                "target_users": target_users,
                "quality_score": round(min(quality_score, 1.0), 2),
                "confidence": 0.6,  # 降级方案的置信度
                "is_fallback": True,
                "data_sources": {
                    "scout": scout_result.success,
                    "analyst": analyst_result.success,
                }
            },
            metadata={
                "repo_name": repo_name,
                "fallback": True,
                "original_error": error,
                "quality_score": round(min(quality_score, 1.0), 2),
            },
            agent_name="AgentOrchestrator"
        )

    async def analyze_projects_batch(
        self,
        projects: List[Dict[str, Any]]
    ) -> List[AgentResult]:
        """
        批量分析多个项目

        Args:
            projects: 项目列表，每个项目包含 repo_name, repo_data 等

        Returns:
            List[AgentResult]: 分析结果列表
        """
        self.logger.info(f"[Orchestrator] 批量分析 {len(projects)} 个项目")

        tasks = []
        for project in projects:
            task = self.analyze_project(
                repo_name=project["repo_name"],
                repo_data=project.get("repo_data", {}),
                readme_content=project.get("readme_content"),
                description=project.get("description"),
                category=project.get("category", "")
            )
            tasks.append(task)

        # 并发执行（限制并发数避免 API 限制）
        semaphore = asyncio.Semaphore(3)  # 最多3个并发

        async def run_with_semaphore(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*[
            run_with_semaphore(task) for task in tasks
        ], return_exceptions=True)

        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"[Orchestrator] 项目 {projects[i]['repo_name']} 分析异常: {result}")
                processed_results.append(AgentResult(
                    success=False,
                    error=str(result),
                    agent_name="AgentOrchestrator"
                ))
            else:
                processed_results.append(result)

        return