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

from app.analysis.agents.base import BaseAgent, AgentResult
from app.analysis.agents.scout import ScoutAgent
from app.analysis.agents.analyst import AnalystAgent
from app.analysis.agents.editor import EditorAgent
from app.analysis.structured_tags import extract_structured_tags
from app.knowledge.search import SearchService

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Agent 任务调度器"""

    def __init__(self):
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.editor = EditorAgent()
        self.search_service = SearchService()
        self.logger = logging.getLogger("agents.orchestrator")

    async def analyze_project(
        self,
        repo_name: str,
        repo_data: Dict[str, Any],
        readme_content: Optional[str],
        raw_readme_content: Optional[str] = None,
        description: Optional[str] = None,
        category: str = ""
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
                result = self._create_final_result(
                    repo_name=repo_name,
                    editor_result=editor_result,
                    scout_result=scout_result,
                    analyst_result=analyst_result,
                )
            else:
                result = await self._create_fallback_result(
                    repo_name=repo_name,
                    error=editor_result.error,
                    scout_result=scout_result,
                    analyst_result=analyst_result,
                    description=description,
                    category=category,
                )

            if result.success:
                structured_tags = self._extract_structured_tags_for_result(
                    result=result,
                    repo_data=repo_data,
                    readme_content=raw_readme_content or readme_content or "",
                    scout_result=scout_result,
                )
                self._attach_structured_tags(result, structured_tags)

                # 自动生成向量并存储
                asyncio.create_task(self._index_project_async(
                    repo_name=repo_name,
                    result=result,
                    repo_data=repo_data,
                    category=category,
                    readme_content=raw_readme_content or readme_content or "",
                    structured_tags=structured_tags,
                ))

            return result

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

        final_data = {
            "summary": report.get("summary", ""),
            "reasons": report.get("reasons", []),
            "keywords": [],
            "tech_stack": [],
            "use_cases": [],
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
            },
            agent_name="AgentOrchestrator"
        )

    async def _create_fallback_result(
        self,
        repo_name: str,
        error: Optional[str],
        scout_result: AgentResult,
        analyst_result: AgentResult,
        description: Optional[str] = None,
        category: str = ""
    ) -> AgentResult:
        """Editor 失败时降级"""

        self.logger.warning(f"[Orchestrator] Editor 失败，降级使用简化报告生成: {error}")

        try:
            final_report = await self.editor._generate_report(
                repo_name=repo_name,
                description=description or "",
                category=category,
                scout_data=scout_result.data if scout_result.success else {},
                analyst_data=analyst_result.data if analyst_result.success else {}
            )

            report_dict = final_report.model_dump()

            return AgentResult(
                success=True,
                data={
                    "summary": report_dict.get("summary", ""),
                    "reasons": report_dict.get("reasons", []),
                    "keywords": [],
                    "tech_stack": [],
                    "use_cases": [],
                    "is_fallback": True,
                },
                metadata={
                    "repo_name": repo_name,
                    "fallback": True,
                    "original_error": error,
                },
                agent_name="AgentOrchestrator"
            )
        except Exception as e:
            self.logger.error(f"[Orchestrator] 降级报告生成也失败: {e}")
            return AgentResult(
                success=False,
                error=f"Editor 和降级方案均失败: {error}; 降级错误: {e}",
                agent_name="AgentOrchestrator"
            )

    def _extract_structured_tags_for_result(
        self,
        result: AgentResult,
        repo_data: Dict[str, Any],
        readme_content: str,
        scout_result: AgentResult,
    ) -> Dict[str, List[str]]:
        return extract_structured_tags(
            summary=result.data.get("summary", ""),
            reasons=result.data.get("reasons", []),
            readme_content=readme_content or "",
            repo_data=repo_data,
            scout_data=scout_result.data if scout_result.success else {},
        )

    def _attach_structured_tags(
        self,
        result: AgentResult,
        structured_tags: Dict[str, List[str]],
    ) -> None:
        result.data["keywords"] = structured_tags.get("keywords", [])
        result.data["tech_stack"] = structured_tags.get("tech_stack", [])
        result.data["use_cases"] = structured_tags.get("use_cases", [])

    async def _index_project_async(
        self,
        repo_name: str,
        result: AgentResult,
        repo_data: Dict[str, Any],
        category: str,
        readme_content: str = "",
        structured_tags: Optional[Dict[str, List[str]]] = None,
    ):
        """异步索引项目（生成向量并存储）"""
        try:
            summary = result.data.get("summary", "")
            reasons = result.data.get("reasons", [])
            language = repo_data.get("language", "")
            tags = structured_tags or {}

            success = await self.search_service.index_project(
                repo_full_name=repo_name,
                summary=summary,
                reasons=reasons,
                readme_content=readme_content,
                language=language,
                category=category,
                keywords=tags.get("keywords", []),
                tech_stack=tags.get("tech_stack", []),
                use_cases=tags.get("use_cases", []),
            )

            if success:
                self.logger.info(f"[Orchestrator] 项目 {repo_name} 向量化成功")
            else:
                self.logger.warning(f"[Orchestrator] 项目 {repo_name} 向量化失败")

        except Exception as e:
            self.logger.error(f"[Orchestrator] 项目 {repo_name} 向量化异常: {e}")
