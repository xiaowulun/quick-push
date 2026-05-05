"""Editor Agent - merge scout and analyst outputs into a final report."""

from datetime import datetime
from typing import Any, Dict, List, Tuple
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.analysis.agents.base import AgentResult, BaseAgent
from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


class FinalReport(BaseModel):
    """Final concise report returned by Editor."""

    summary: str = Field(
        description=(
            "Deep project summary in about 100-150 Chinese characters, "
            "covering value, problem fit, and feasibility."
        )
    )
    reasons: List[str] = Field(
        description=(
            "3-5 concrete reasons for popularity/adoption, each <= 40 Chinese characters."
        )
    )


class EditorAgent(BaseAgent):
    """Editor review agent."""

    def __init__(self):
        super().__init__("EditorAgent", "Editor review agent")
        config = get_config()
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_pro,
            temperature=0.3,
        )

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Merge scout and analyst results and generate final report."""
        self.log_start(context)

        try:
            repo_name = context.get("repo_name", "")
            description = context.get("description", "")
            scout_result = context.get("scout_result", {})
            analyst_result = context.get("analyst_result", {})
            category = context.get("category", "")

            # Normalize payload shapes for backward compatibility.
            scout_data, inferred_scout_success = self._normalize_agent_payload(scout_result)
            analyst_data, inferred_analyst_success = self._normalize_agent_payload(analyst_result)
            scout_success = bool(context.get("scout_success", inferred_scout_success))
            analyst_success = bool(context.get("analyst_success", inferred_analyst_success))

            final_report = await self._generate_report(
                repo_name=repo_name,
                description=description,
                category=category,
                scout_data=scout_data,
                analyst_data=analyst_data,
            )

            result_data = {
                "report": final_report.model_dump(),
                "data_sources": {
                    "scout_success": scout_success,
                    "analyst_success": analyst_success,
                },
                "generated_at": datetime.now().isoformat(),
            }

            result = self.create_success_result(
                data=result_data,
                metadata={"repo_name": repo_name},
            )
            self.log_end(result)
            return result

        except Exception as e:
            error_msg = f"editor review failed: {e}"
            logger.error(error_msg)
            return self.create_error_result(error_msg)

    @staticmethod
    def _normalize_agent_payload(payload: Any) -> Tuple[Dict[str, Any], bool]:
        # New path: payload is raw data dict, success comes from explicit flags.
        # Legacy path: payload may look like {"success": bool, "data": {...}}.
        if isinstance(payload, dict) and "data" in payload and isinstance(payload.get("data"), dict):
            success = bool(payload.get("success", False))
            data = payload.get("data") or {}
            return (data if success else {}), success

        if isinstance(payload, dict):
            return payload, bool(payload)

        return {}, False

    async def _generate_report(
        self,
        repo_name: str,
        description: str,
        category: str,
        scout_data: Dict,
        analyst_data: Dict,
    ) -> FinalReport:
        """Use LLM to synthesize scout + analyst outputs."""

        materials = self._build_analysis_materials(scout_data, analyst_data)

        prompt_template = """You are a senior technical editor.
You need to integrate the following research materials and produce a concise user-facing report.

Project: {repo_name}
Description: {description}
Category: {category}

{materials}

Return JSON only:
{{"summary": "...", "reasons": ["...", "...", "..."]}}

Requirements:
- summary: about 100-150 Chinese characters, include value, problem fit, feasibility.
- reasons: 3-5 items, each <= 40 Chinese characters, concrete and specific.
- avoid generic filler text.
"""

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm.with_structured_output(FinalReport)

        result = await chain.ainvoke(
            {
                "repo_name": repo_name,
                "description": description or "no description",
                "category": category or "",
                "materials": materials,
            }
        )
        return result

    def _build_analysis_materials(self, scout_data: Dict, analyst_data: Dict) -> str:
        """Build compact text materials from scout and analyst outputs."""

        sections: List[str] = []

        if scout_data:
            parts = ["[Market Analysis]"]

            popularity = scout_data.get("popularity_analysis", [])
            if popularity:
                parts.append("Popularity Drivers:")
                for item in popularity[:5]:
                    parts.append(f"- {item}")

            trend = scout_data.get("trend_alignment", "")
            if trend:
                parts.append(f"Trend Alignment: {trend}")

            advantage = scout_data.get("competitive_advantage", "")
            if advantage:
                parts.append(f"Competitive Advantage: {advantage}")

            sentiment = scout_data.get("community_sentiment", {})
            if sentiment:
                heat = sentiment.get("heat_level", "")
                atmosphere = sentiment.get("atmosphere", "")
                topics = sentiment.get("key_topics", [])
                if heat and heat != "unknown":
                    parts.append(f"Community Heat: {heat} ({atmosphere})")
                if topics:
                    parts.append(f"Discussion Topics: {', '.join(topics)}")

            concerns = scout_data.get("potential_concerns", [])
            if concerns:
                parts.append(f"Potential Risks: {'; '.join(concerns)}")

            sections.append("\n".join(parts))

        if analyst_data:
            tech_review = analyst_data.get("tech_review", analyst_data)
            if tech_review:
                parts = ["[Technical Analysis]"]

                runnability = tech_review.get("runnability", {})
                if runnability:
                    diff = runnability.get("difficulty", "")
                    assessment = runnability.get("assessment", "")
                    missing = runnability.get("missing_configs", [])
                    parts.append(f"Deployment Difficulty: {diff}")
                    if assessment:
                        parts.append(f"Assessment: {assessment}")
                    if missing:
                        parts.append(f"Missing Configs: {', '.join(missing[:3])}")

                structure = tech_review.get("code_structure", {})
                if structure:
                    level = structure.get("engineering_level", "")
                    assessment = structure.get("assessment", "")
                    parts.append(f"Engineering Level: {level}")
                    if assessment:
                        parts.append(f"Assessment: {assessment}")

                issues = tech_review.get("issue_analysis", {})
                if issues:
                    bug_density = issues.get("bug_density", "")
                    warning = issues.get("critical_warning", "")
                    active = issues.get("author_active", None)
                    parts.append(f"Bug Density: {bug_density}")
                    if warning and warning != "none":
                        parts.append(f"Critical Warning: {warning}")
                    if active is not None:
                        parts.append(f"Maintainer Active: {'yes' if active else 'no'}")

                sections.append("\n".join(parts))

        if not sections:
            return "(Only repository description available)"

        result = "\n\n".join(sections)
        if len(result) > 800:
            result = result[:797] + "..."
        return result
