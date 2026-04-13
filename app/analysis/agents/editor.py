"""
Editor Agent - 编辑审查

负责整合 Scout（趋势情报）和 Analyst（技术深度）的结果，生成最终推送报告。
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.analysis.agents.base import BaseAgent, AgentResult
from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


class FinalReport(BaseModel):
    """最终分析报告"""
    summary: str = Field(description="项目分析：深层次探究项目的用处、价值、可行性，100-150字")
    reasons: List[str] = Field(description="爆火原因：结合当下热点评估，3-5条，每条最多40字")


class EditorAgent(BaseAgent):
    """编辑审查 Agent"""

    def __init__(self):
        super().__init__("EditorAgent", "编辑审查 Agent")
        config = get_config()
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_pro,
            temperature=0.3
        )

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        整合 Scout 和 Analyst 的结果，生成最终报告

        Args:
            context: {
                "repo_name": str,
                "description": str,
                "scout_result": AgentResult,
                "analyst_result": AgentResult,
                "category": str,
            }
        """
        self.log_start(context)

        try:
            repo_name = context.get("repo_name", "")
            description = context.get("description", "")
            scout_result = context.get("scout_result", {})
            analyst_result = context.get("analyst_result", {})
            category = context.get("category", "")

            # 1. 数据预处理
            scout_data = scout_result if scout_result else {}
            analyst_data = analyst_result if analyst_result else {}

            # 2. 使用 LLM 生成最终报告
            final_report = await self._generate_report(
                repo_name=repo_name,
                description=description,
                category=category,
                scout_data=scout_data,
                analyst_data=analyst_data
            )

            result_data = {
                "report": final_report.model_dump(),
                "data_sources": {
                    "scout_success": scout_result.get("success", False),
                    "analyst_success": analyst_result.get("success", False),
                },
                "generated_at": datetime.now().isoformat(),
            }

            result = self.create_success_result(
                data=result_data,
                metadata={
                    "repo_name": repo_name,
                }
            )

            self.log_end(result)
            return result

        except Exception as e:
            error_msg = f"编辑审查失败: {str(e)}"
            logger.error(error_msg)
            return self.create_error_result(error_msg)

    async def _generate_report(
        self,
        repo_name: str,
        description: str,
        category: str,
        scout_data: Dict,
        analyst_data: Dict
    ) -> FinalReport:
        """使用 LLM 整合 Scout 和 Analyst 的分析结果"""

        materials = self._build_analysis_materials(scout_data, analyst_data)

        prompt_template = """你是一位资深技术编辑，需要整合以下调研资料，生成面向用户的简洁报告。

项目: {repo_name}
描述: {description}

{materials}

直接返回 JSON，不要其他内容：
{{"summary": "项目分析（100-150字，深层次探究项目的用处、价值、可行性）", "reasons": ["爆火原因1", "爆火原因2", "爆火原因3"]}}

注意：
- summary 要深入分析项目的核心价值、解决什么问题、技术可行性如何
- reasons 每条≤40字，结合当下技术热点，写具体事实（如"免费替代XX工具"、"踩中AI编程趋势"）
- 不要写套话，要有实质性内容
"""

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm.with_structured_output(FinalReport)

        result = await chain.ainvoke({
            "repo_name": repo_name,
            "description": description or "暂无描述",
            "materials": materials,
        })

        return result

    def _build_analysis_materials(self, scout_data: Dict, analyst_data: Dict) -> str:
        """整合 Scout 和 Analyst 的信息，生成完整的调研资料"""

        sections = []

        if scout_data:
            parts = ["【市场分析】"]

            popularity = scout_data.get("popularity_analysis", [])
            if popularity:
                parts.append("爆火因素:")
                for p in popularity[:5]:
                    parts.append(f"  • {p}")

            trend = scout_data.get("trend_alignment", "")
            if trend:
                parts.append(f"技术趋势: {trend}")

            advantage = scout_data.get("competitive_advantage", "")
            if advantage:
                parts.append(f"竞争优势: {advantage}")

            sentiment = scout_data.get("community_sentiment", {})
            if sentiment:
                heat = sentiment.get("heat_level", "")
                atmosphere = sentiment.get("atmosphere", "")
                topics = sentiment.get("key_topics", [])
                if heat and heat != "unknown":
                    parts.append(f"社区热度: {heat} ({atmosphere})")
                if topics:
                    parts.append(f"讨论话题: {', '.join(topics)}")

            concerns = scout_data.get("potential_concerns", [])
            if concerns:
                parts.append(f"潜在风险: {'; '.join(concerns)}")

            sections.append("\n".join(parts))

        if analyst_data:
            tech_review = analyst_data.get("tech_review", analyst_data)
            if tech_review:
                parts = ["【技术分析】"]

                runnability = tech_review.get("runnability", {})
                if runnability:
                    diff = runnability.get("difficulty", "")
                    assessment = runnability.get("assessment", "")
                    missing = runnability.get("missing_configs", [])
                    parts.append(f"部署难度: {diff}")
                    if assessment:
                        parts.append(f"  评价: {assessment}")
                    if missing:
                        parts.append(f"  缺失配置: {', '.join(missing[:3])}")

                structure = tech_review.get("code_structure", {})
                if structure:
                    level = structure.get("engineering_level", "")
                    assessment = structure.get("assessment", "")
                    parts.append(f"工程水平: {level}")
                    if assessment:
                        parts.append(f"  评价: {assessment}")

                issues = tech_review.get("issue_analysis", {})
                if issues:
                    bug_density = issues.get("bug_density", "")
                    warning = issues.get("critical_warning", "")
                    active = issues.get("author_active", None)
                    parts.append(f"Bug密度: {bug_density}")
                    if warning and warning != "无":
                        parts.append(f"  严重警告: {warning}")
                    if active is not None:
                        parts.append(f"作者活跃: {'是' if active else '否'}")

                sections.append("\n".join(parts))

        if not sections:
            return "（仅有项目描述可用）"

        result = "\n\n".join(sections)
        if len(result) > 800:
            result = result[:797] + "..."
        return result
