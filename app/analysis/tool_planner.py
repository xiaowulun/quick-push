"""
Task-level tool planner for multi-step execution.

Goal:
- Decide which tool to use for each step from a high-level task.
- Keep decisions deterministic and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


SEARCH_ENGINE = "search_engine"
CODE_ANALYSIS = "code_analysis"


@dataclass(frozen=True)
class ToolStep:
    name: str
    tool: str
    reason: str


class TaskToolPlanner:
    """Heuristic planner for selecting tools per step."""

    _SEARCH_HINTS = (
        "搜索",
        "查",
        "社区",
        "讨论",
        "热度",
        "趋势",
        "对比",
        "竞品",
        "舆情",
        "新闻",
        "hackernews",
        "github discussion",
        "github discussions",
    )

    _CODE_HINTS = (
        "代码",
        "架构",
        "目录",
        "可运行",
        "运行",
        "工程",
        "依赖",
        "质量",
        "测试",
        "issue",
        "bug",
        "性能",
        "安全",
        "review",
        "分析源码",
    )

    def plan(self, task: str) -> List[ToolStep]:
        text = (task or "").strip().lower()
        if not text:
            return []

        need_search = any(k in text for k in self._SEARCH_HINTS)
        need_code = any(k in text for k in self._CODE_HINTS)

        steps: List[ToolStep] = []

        if need_search:
            steps.append(
                ToolStep(
                    name="collect_external_context",
                    tool=SEARCH_ENGINE,
                    reason="task mentions external signals (community/trend/discussion/search)",
                )
            )
        if need_code:
            steps.append(
                ToolStep(
                    name="inspect_repository_code",
                    tool=CODE_ANALYSIS,
                    reason="task mentions source-level analysis (code/architecture/runnability/issues)",
                )
            )

        if not steps and any(k in text for k in ("评估", "是否值得", "决策", "选型", "可行性")):
            steps = [
                ToolStep(
                    name="collect_external_context",
                    tool=SEARCH_ENGINE,
                    reason="evaluation task defaults to collecting external evidence first",
                ),
                ToolStep(
                    name="inspect_repository_code",
                    tool=CODE_ANALYSIS,
                    reason="evaluation task also needs code-level verification",
                ),
            ]

        if not steps:
            steps = [
                ToolStep(
                    name="collect_external_context",
                    tool=SEARCH_ENGINE,
                    reason="default fallback when no clear code-analysis intent is found",
                )
            ]

        return steps

