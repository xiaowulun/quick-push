"""
Editor Agent - 编辑审查

负责整合 Scout（趋势八卦）和 Analyst（技术深度）的结果：
- 去重合并信息
- 质量评估
- 生成结构化报告
- 输出质量评分
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from agents.base import BaseAgent, AgentResult
from core.config import get_config
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FinalReport(BaseModel):
    """最终分析报告"""
    summary: str = Field(description="50-100字的项目简介")
    reasons: List[str] = Field(description="3-5个爆火原因，每个最多40字")
    tech_highlights: List[str] = Field(description="技术亮点，2-3点")
    target_users: str = Field(description="目标用户群体")
    quality_score: float = Field(description="报告质量评分 0-1")
    confidence: float = Field(description="整体置信度 0-1")


class EditorAgent(BaseAgent):
    """编辑审查 Agent"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__("EditorAgent", config)
        self.config = get_config()
        self.llm = ChatOpenAI(
            api_key=self.config.openai.api_key,
            base_url=self.config.openai.base_url,
            model_name=self.config.openai.model,
            temperature=0.3
        )

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        整合审查并生成最终报告

        Args:
            context: {
                "repo_name": str,
                "description": str,
                "scout_result": AgentResult,  # 趋势八卦
                "analyst_result": AgentResult,  # 技术深度
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
            scout_data = scout_result.get("data", {}) if scout_result.get("success") else {}
            analyst_data = analyst_result.get("data", {}) if analyst_result.get("success") else {}

            # 2. 使用 LLM 生成最终报告
            final_report = await self._generate_report(
                repo_name=repo_name,
                description=description,
                category=category,
                scout_data=scout_data,
                analyst_data=analyst_data
            )

            # 3. 质量评估
            quality_assessment = self._assess_quality(
                final_report,
                scout_result,
                analyst_result
            )

            result_data = {
                "report": final_report.dict(),
                "quality_assessment": quality_assessment,
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
                    "quality_score": quality_assessment["overall_score"],
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
        """使用 LLM 生成最终报告"""

        # 提取 Scout 的关键信息（趋势八卦）
        popularity_factors = scout_data.get("popularity_factors", {})
        trend_analysis = scout_data.get("trend_analysis", {})
        community_buzz = scout_data.get("community_buzz", {})
        competitive_edge = scout_data.get("competitive_edge", {})

        # 提取 Analyst 的关键信息（技术深度）
        content_quality = analyst_data.get("content_quality", {})
        tech_analysis = analyst_data.get("tech_analysis", {})
        substance_score = analyst_data.get("substance_score", {})
        quality_metrics = analyst_data.get("quality_metrics", {})

        # 构建 Prompt
        prompt_template = """你是一位资深技术编辑，负责整合趋势情报和技术分析，生成高质量的项目分析报告。

## 项目信息
- 名称: {repo_name}
- 描述: {description}
- 分类: {category}

## 趋势情报 (Scout)
**爆火因素:**
{popularity_factors}

**技术趋势关联:**
{trend_analysis}

**社区热度:**
{community_buzz}

**竞争优势:**
{competitive_edge}

## 技术深度 (Analyst)
**内容质量:**
{content_quality}

**技术栈:**
{tech_analysis}

**项目实质:**
{substance_score}

**质量指标:**
{quality_metrics}

## 任务
基于以上信息，生成一份专业的项目分析报告：
1. 用 50-100 字概括项目核心（结合技术实质和趋势热点）
2. 列出 3-5 个爆火原因（优先使用 Scout 的爆火因素，结合技术亮点）
3. 提炼 2-3 个技术亮点（从 Analyst 的技术分析中提取）
4. 描述目标用户群体（结合技术栈和使用场景）
5. 评估整体置信度（0-1，基于数据完整度）

注意：
- 去重合并，避免重复信息
- 突出最值得关注的特点
- 如果 Analyst 显示项目"水货"嫌疑，要在报告中委婉体现
- 语言简洁有力，每个爆火原因最多40字
"""

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm.with_structured_output(FinalReport)

        result = await chain.ainvoke({
            "repo_name": repo_name,
            "description": description or "暂无描述",
            "category": category,
            "popularity_factors": self._format_dict(popularity_factors),
            "trend_analysis": self._format_dict(trend_analysis),
            "community_buzz": self._format_dict(community_buzz),
            "competitive_edge": self._format_dict(competitive_edge),
            "content_quality": self._format_dict(content_quality),
            "tech_analysis": self._format_dict(tech_analysis),
            "substance_score": self._format_dict(substance_score),
            "quality_metrics": self._format_dict(quality_metrics),
        })

        return result

    def _format_dict(self, data: Dict) -> str:
        """格式化字典为字符串"""
        if not data:
            return "暂无数据"
        lines = []
        for k, v in data.items():
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v[:5])
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def _assess_quality(
        self,
        report: FinalReport,
        scout_result: Dict,
        analyst_result: Dict
    ) -> Dict:
        """评估报告质量"""

        # 数据完整度
        data_completeness = 0
        if scout_result.get("success"):
            data_completeness += 0.4
        if analyst_result.get("success"):
            data_completeness += 0.4
        if report.summary and len(report.summary) >= 20:
            data_completeness += 0.2

        # 内容丰富度
        content_richness = min(len(report.reasons) / 3, 1.0) * 0.5
        content_richness += min(len(report.tech_highlights) / 2, 1.0) * 0.3
        content_richness += (0.2 if report.target_users else 0)

        # 整体评分
        overall_score = (data_completeness * 0.4 + content_richness * 0.4 +
                        report.quality_score * 0.2)

        return {
            "overall_score": round(overall_score, 2),
            "data_completeness": round(data_completeness, 2),
            "content_richness": round(content_richness, 2),
            "llm_quality_score": round(report.quality_score, 2),
            "confidence": round(report.confidence, 2),
        }
