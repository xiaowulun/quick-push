"""
Analyst Agent - 技术审查员

职责：作为资深架构师，接收 GitHub 原始数据，通过 Pydantic 结构化输出专业的尽调报告。
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.analysis.agents.base import BaseAgent, AgentResult
from app.analysis.agents.tools.code_analysis_tools import GitHubRepoInspector
from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


class RunnabilityEval(BaseModel):
    difficulty: str = Field(description="部署难度，必须严格从以下选择其一：easy / medium / hard")
    missing_configs: List[str] = Field(description="如果要投入生产环境，目前缺失的关键配置文件或文档说明")
    assessment: str = Field(description="用1-2句话精炼评价部署这套代码的坑点在哪里，或者夸奖它的部署体验")

class CodeStructureEval(BaseModel):
    engineering_level: str = Field(description="工程化成熟度：high / medium / low")
    assessment: str = Field(description="架构评价，指出目录分层是否合理、是否有测试用例和CI/CD流程")

class IssueEval(BaseModel):
    bug_density: str = Field(description="Bug 密度：high / medium / low")
    critical_warning: str = Field(description="从当前的 Issue 列表中提取出的最严重的一个警告，如果没有严重问题则填 '无'")
    author_active: bool = Field(description="根据 Issue 的回复情况，判断作者是否仍在积极维护")

class TechReviewReport(BaseModel):
    runnability: RunnabilityEval
    code_structure: CodeStructureEval
    issue_analysis: IssueEval


class AnalystAgent(BaseAgent):
    """
    技术审查员 - 基于原始数据，LLM 进行专业架构审查
    """

    def __init__(self):
        super().__init__("AnalystAgent", "技术审查员 - 基于原始数据，LLM 进行专业架构审查")
        config = get_config()
        self.inspector = GitHubRepoInspector(config.github.token)

        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_standard,
            temperature=0.1,
            max_tokens=1200,
        )

    @staticmethod
    def _clip_text(text: Optional[str], limit: int) -> str:
        raw = (text or "").strip()
        if not raw:
            return ""
        if len(raw) <= limit:
            return raw
        return raw[:limit] + f"\n...[TRUNCATED {len(raw) - limit} chars]"

    def _build_key_files_context(self, key_files_dict: Dict[str, str], *, compact: bool) -> str:
        if not key_files_dict:
            return "无任何常见配置文件。"

        if compact:
            max_files = 6
            per_file_limit = 900
            total_limit = 4200
        else:
            max_files = 10
            per_file_limit = 1800
            total_limit = 9000

        key_files_blocks: List[str] = []
        total = 0
        for file_name, content in key_files_dict.items():
            if not content:
                continue
            clipped = self._clip_text(content, per_file_limit)
            block = f"### {file_name}\n```text\n{clipped}\n```"
            next_total = total + len(block)
            if key_files_blocks and next_total > total_limit:
                break
            key_files_blocks.append(block)
            total = next_total
            if len(key_files_blocks) >= max_files:
                break

        if not key_files_blocks:
            return "无任何常见配置文件。"
        return "\n\n".join(key_files_blocks)

    def _build_analysis_messages(
        self,
        repo_name: str,
        raw_data: Dict,
        repo_data: Dict,
        *,
        compact: bool,
    ) -> Dict[str, str]:
        if compact:
            directory_limit = 2600
            issues_limit = 2200
        else:
            directory_limit = 7000
            issues_limit = 4500

        return {
            "repo_name": repo_name,
            "language": repo_data.get("language", "Unknown"),
            "directory_tree": self._clip_text(raw_data.get("directory_tree", "无目录结构"), directory_limit) or "无目录结构",
            "key_files": self._build_key_files_context(raw_data.get("key_files", {}), compact=compact),
            "issues_text": self._clip_text(raw_data.get("issues_text", "无 Issue 数据"), issues_limit) or "无 Issue 数据",
        }

    @staticmethod
    def _is_output_length_error(error: Exception) -> bool:
        msg = str(error or "").lower()
        return (
            "length limit was reached" in msg
            or "maximum context length" in msg
            or "max output tokens" in msg
            or "finish_reason:length" in msg
        )

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """执行技术审查"""
        self.log_start(context)

        try:
            repo_name = context.get("repo_name", "")
            repo_data = context.get("repo_data", {})

            if not repo_name:
                raise ValueError("缺少必须参数: repo_name")

            logger.info(f"[Analyst] 开始尽职调查: {repo_name}")

            # Step 1: 召唤探针，获取纯净的原始数据
            raw_data = await self.inspector.inspect(repo_name)

            # Step 2: 让架构师 (LLM) 进行深度审查
            analysis_dict = await self._analyze(
                repo_name=repo_name,
                raw_data=raw_data,
                repo_data=repo_data
            )

            # Step 3: 组装最终报告
            result = {
                "repo_name": repo_name,
                "tech_review": analysis_dict,
                "analyzed_at": datetime.now().isoformat()
            }

            self.log_end(AgentResult(success=True, data=result))
            return self.create_success_result(result)

        except Exception as e:
            logger.error(f"[Analyst] 技术审查失败: {e}")
            return self.create_error_result(str(e))

    async def _analyze(
        self,
        repo_name: str,
        raw_data: Dict,
        repo_data: Dict
    ) -> Dict:
        """将数据喂给 LLM，并通过 Pydantic 获取结构化 JSON"""

        prompt_template = """你是一位极其严苛且专业的开源技术架构师。
你需要对以下 GitHub 开源项目进行"尽职调查（Due Diligence）"，判断其真实可用性。

# 项目基本信息
- 仓库名称：{repo_name}
- 主要语言：{language}

---
# 1. 目录骨架
{directory_tree}

---
# 2. 核心配置文件
{key_files}

---
# 3. 近期 Issue 反馈 (Top 20)
{issues_text}

---
# 任务要求
请像资深技术总监一样，直接指出该项目的部署痛点、架构设计水平以及社区隐藏的致命Bug。
请严格遵循预期的 JSON 数据结构进行输出。切勿使用客套话，务必直击痛点。
输出约束（非常重要）：
- 严格仅输出结构化 JSON（不要输出 Markdown、解释、前后缀）
- `runnability.assessment`、`code_structure.assessment` 各 <= 120 字
- `missing_configs` 最多 8 项，每项 <= 40 字
- `critical_warning` <= 80 字；若无则填 "无"
"""

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm.with_structured_output(TechReviewReport)

        messages = self._build_analysis_messages(
            repo_name=repo_name,
            raw_data=raw_data,
            repo_data=repo_data,
            compact=False,
        )

        try:
            logger.info(f"[Analyst] 正在等待 LLM 思考架构评估结果...")
            result_obj: TechReviewReport = await chain.ainvoke(messages)
            return result_obj.model_dump()

        except Exception as e:
            if self._is_output_length_error(e):
                logger.warning("[Analyst] 检测到输出长度截断，使用紧凑上下文重试一次。")
                compact_messages = self._build_analysis_messages(
                    repo_name=repo_name,
                    raw_data=raw_data,
                    repo_data=repo_data,
                    compact=True,
                )
                try:
                    result_obj: TechReviewReport = await chain.ainvoke(compact_messages)
                    return result_obj.model_dump()
                except Exception as retry_error:
                    logger.error(f"[Analyst] 紧凑重试后仍失败: {retry_error}")
                    raise RuntimeError(f"结构化输出解析失败（已重试紧凑上下文）: {retry_error}")

            logger.error(f"[Analyst] LLM 解析结构化输出失败: {e}")
            raise RuntimeError(f"结构化输出解析失败，可能是 LLM 拒答或模型能力不足: {e}")
