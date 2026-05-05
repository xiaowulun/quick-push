"""
Agent orchestrator for project analysis.

Execution model:
- Agents are fixed (Scout / Analyst / Editor)
- Tool usage is dynamic via task-level planning
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

from app.analysis.agents.base import AgentResult
from app.analysis.structured_tags import extract_structured_tags
from app.analysis.tool_planner import TaskToolPlanner, ToolStep
from app.analysis.tool_registry import ToolRegistry
from app.knowledge.search import SearchService

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self):
        # Lazy import keeps module import lightweight for unit tests/evaluation tooling.
        from app.analysis.agents.scout import ScoutAgent
        from app.analysis.agents.analyst import AnalystAgent
        from app.analysis.agents.editor import EditorAgent

        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.editor = EditorAgent()
        self.tool_planner = TaskToolPlanner()
        self.tool_registry = ToolRegistry()
        self.search_service = SearchService()
        self.logger = logging.getLogger("agents.orchestrator")

    async def analyze_project(
        self,
        repo_name: str,
        repo_data: Dict[str, Any],
        readme_content: Optional[str],
        raw_readme_content: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "",
    ) -> AgentResult:
        self.logger.info("[Orchestrator] start analysis: %s", repo_name)

        try:
            task_text = self._build_task_text(
                repo_name=repo_name,
                description=description,
                category=category,
                readme_content=readme_content,
            )
            tool_plan = self.tool_planner.plan(task_text)
            selected_tools = {step.tool for step in tool_plan}
            tool_registry = getattr(self, "tool_registry", None) or ToolRegistry()
            selected_tool_names = tool_registry.resolve_tool_names(selected_tools)
            self.logger.info(
                "[Orchestrator] tool plan: %s",
                [f"{s.name}:{s.tool}" for s in tool_plan],
            )

            scout_context = {
                "repo_name": repo_name,
                "repo_data": repo_data,
                "description": description,
                "readme_content": readme_content or "",
            }
            analyst_context = {
                "repo_name": repo_name,
                "readme_content": readme_content or "",
                "repo_data": repo_data,
            }

            agent_contexts = {
                "ScoutAgent": scout_context,
                "AnalystAgent": analyst_context,
            }
            agent_runners = {
                "ScoutAgent": self.scout.execute,
                "AnalystAgent": self.analyst.execute,
            }

            selected_agent_names = tool_registry.resolve_agent_names_from_tool_names(selected_tool_names)

            agent_results: Dict[str, AgentResult] = {
                "ScoutAgent": self._create_skipped_agent_result(
                    agent_name="ScoutAgent",
                    reason="no selected tool mapped to this agent",
                ),
                "AnalystAgent": self._create_skipped_agent_result(
                    agent_name="AnalystAgent",
                    reason="no selected tool mapped to this agent",
                ),
            }

            active_calls: Dict[str, Any] = {}
            for agent_name in selected_agent_names:
                runner = agent_runners.get(agent_name)
                context = agent_contexts.get(agent_name)
                if not runner or context is None:
                    agent_results[agent_name] = AgentResult(
                        success=False,
                        error=f"no executor/context found for {agent_name}",
                        agent_name=agent_name,
                    )
                    continue
                active_calls[agent_name] = runner(context)

            if active_calls:
                outputs = await asyncio.gather(*active_calls.values(), return_exceptions=True)
                for agent_name, output in zip(active_calls.keys(), outputs):
                    agent_results[agent_name] = self._coerce_agent_result(agent_name, output)

            scout_result = agent_results["ScoutAgent"]
            analyst_result = agent_results["AnalystAgent"]

            scout_success = self._is_agent_effectively_successful(scout_result)
            analyst_success = self._is_agent_effectively_successful(analyst_result)

            editor_result = await self.editor.execute(
                {
                    "repo_name": repo_name,
                    "description": description,
                    "scout_result": scout_result.data if scout_success else {},
                    "analyst_result": analyst_result.data if analyst_success else {},
                    "scout_success": scout_success,
                    "analyst_success": analyst_success,
                    "category": category,
                }
            )

            if editor_result.success:
                result = self._create_final_result(
                    repo_name=repo_name,
                    editor_result=editor_result,
                    scout_result=scout_result,
                    analyst_result=analyst_result,
                    tool_plan=tool_plan,
                    selected_tool_names=selected_tool_names,
                )
            else:
                result = await self._create_fallback_result(
                    repo_name=repo_name,
                    error=editor_result.error,
                    scout_result=scout_result,
                    analyst_result=analyst_result,
                    description=description,
                    category=category,
                    tool_plan=tool_plan,
                    selected_tool_names=selected_tool_names,
                )

            if result.success:
                structured_tags = self._extract_structured_tags_for_result(
                    result=result,
                    repo_data=repo_data,
                    readme_content=raw_readme_content or readme_content or "",
                    scout_result=scout_result,
                )
                self._attach_structured_tags(result, structured_tags)

                asyncio.create_task(
                    self._index_project_async(
                        repo_name=repo_name,
                        result=result,
                        repo_data=repo_data,
                        category=category,
                        readme_content=raw_readme_content or readme_content or "",
                        structured_tags=structured_tags,
                    )
                )

            return result

        except Exception as e:
            error_msg = f"Multi-Agent execution failed: {str(e)}"
            self.logger.error("[Orchestrator] %s", error_msg)
            return AgentResult(
                success=False,
                error=error_msg,
                agent_name="AgentOrchestrator",
            )

    def _create_final_result(
        self,
        repo_name: str,
        editor_result: AgentResult,
        scout_result: AgentResult,
        analyst_result: AgentResult,
        tool_plan: Optional[List[ToolStep]] = None,
        selected_tool_names: Optional[Set[str]] = None,
    ) -> AgentResult:
        editor_data = editor_result.data or {}
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
            },
        }

        return AgentResult(
            success=True,
            data=final_data,
            metadata={
                "repo_name": repo_name,
                "multi_agent": True,
                "tool_plan": [
                    {"name": step.name, "tool": step.tool, "reason": step.reason}
                    for step in (tool_plan or [])
                ],
                "selected_tools": sorted(list(selected_tool_names or set())),
            },
            agent_name="AgentOrchestrator",
        )

    async def _create_fallback_result(
        self,
        repo_name: str,
        error: Optional[str],
        scout_result: AgentResult,
        analyst_result: AgentResult,
        description: Optional[str] = None,
        category: str = "",
        tool_plan: Optional[List[ToolStep]] = None,
        selected_tool_names: Optional[Set[str]] = None,
    ) -> AgentResult:
        self.logger.warning("[Orchestrator] editor failed, entering fallback: %s", error)

        try:
            final_report = await self.editor._generate_report(
                repo_name=repo_name,
                description=description or "",
                category=category,
                scout_data=scout_result.data if scout_result.success else {},
                analyst_data=analyst_result.data if analyst_result.success else {},
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
                    "tool_plan": [
                        {"name": step.name, "tool": step.tool, "reason": step.reason}
                        for step in (tool_plan or [])
                    ],
                    "selected_tools": sorted(list(selected_tool_names or set())),
                },
                agent_name="AgentOrchestrator",
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Editor fallback failed: {error}; fallback_error: {e}",
                agent_name="AgentOrchestrator",
            )

    @staticmethod
    def _create_skipped_agent_result(agent_name: str, reason: str) -> AgentResult:
        return AgentResult(
            success=True,
            data={"skipped": True, "reason": reason},
            metadata={"skipped": True, "reason": reason},
            agent_name=agent_name,
        )

    @staticmethod
    def _coerce_agent_result(agent_name: str, output: Any) -> AgentResult:
        if isinstance(output, AgentResult):
            return output
        if isinstance(output, Exception):
            return AgentResult(
                success=False,
                error=f"{agent_name} execution failed: {output}",
                agent_name=agent_name,
            )
        return AgentResult(
            success=False,
            error=f"{agent_name} returned invalid output type: {type(output).__name__}",
            agent_name=agent_name,
        )

    @staticmethod
    def _is_agent_effectively_successful(result: AgentResult) -> bool:
        if not result.success:
            return False
        metadata = result.metadata or {}
        return not bool(metadata.get("skipped"))

    @staticmethod
    def _build_task_text(
        repo_name: str,
        description: Optional[str],
        category: str,
        readme_content: Optional[str],
    ) -> str:
        parts = [
            str(repo_name or ""),
            str(description or ""),
            str(category or ""),
            str(readme_content or "")[:600],
        ]
        return " ".join(p for p in parts if p).strip()

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
                self.logger.info("[Orchestrator] indexed project %s", repo_name)
            else:
                self.logger.warning("[Orchestrator] index failed for %s", repo_name)

        except Exception as e:
            self.logger.error("[Orchestrator] indexing crashed for %s: %s", repo_name, e)
