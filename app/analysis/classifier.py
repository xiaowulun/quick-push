from enum import Enum
import json
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.infrastructure.config import get_config
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProjectCategory(str, Enum):
    """Project category enum."""

    AI_ECOSYSTEM = "ai_ecosystem"
    INFRA_AND_TOOLS = "infra_and_tools"
    PRODUCT_AND_UI = "product_and_ui"
    KNOWLEDGE_BASE = "knowledge_base"


class ClassificationResult(BaseModel):
    """Classification output model."""

    category: ProjectCategory = Field(description="Project category")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in [0, 1]")
    reasoning: str = Field(description="Short reason")

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value):
        try:
            num = float(value)
        except (TypeError, ValueError):
            return 0.5
        if num < 0.0:
            return 0.0
        if num > 1.0:
            return 1.0
        return num


def get_category_emoji(category: ProjectCategory) -> str:
    emoji_map = {
        ProjectCategory.AI_ECOSYSTEM: "🤖",
        ProjectCategory.INFRA_AND_TOOLS: "🛠️",
        ProjectCategory.PRODUCT_AND_UI: "🎨",
        ProjectCategory.KNOWLEDGE_BASE: "📚",
    }
    return emoji_map.get(category, "📝")


def get_category_name(category: ProjectCategory) -> str:
    name_map = {
        ProjectCategory.AI_ECOSYSTEM: "AI 生态与 Agent",
        ProjectCategory.INFRA_AND_TOOLS: "基础设施与工具链",
        ProjectCategory.PRODUCT_AND_UI: "产品与界面体验",
        ProjectCategory.KNOWLEDGE_BASE: "知识库与教程资料",
    }
    return name_map.get(category, "未分类")


CLASSIFIER_PROMPT = """你是 GitHub 项目分类助手，请根据项目信息给出分类。

仓库: {repo_name}
描述: {description}
README 摘要:
{readme_preview}

可选分类:
- ai_ecosystem
- infra_and_tools
- product_and_ui
- knowledge_base

要求:
1) 只输出 JSON，字段: category, confidence, reasoning
2) category 必须是四个枚举之一
3) confidence 在 0 到 1 之间
4) reasoning 控制在 20 字以内
"""


FALLBACK_PROMPT = """只输出一行紧凑 JSON，不要解释。
repo={repo_name}
desc={description}
readme={readme_preview}
category 只能是: ai_ecosystem, infra_and_tools, product_and_ui, knowledge_base
输出样例: {"category":"product_and_ui","confidence":0.62,"reasoning":"偏向产品界面"}
"""


class ProjectClassifier:
    """Classify projects into 4 categories."""

    def __init__(self):
        config = get_config()
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_fast,
            temperature=0.2,
            max_tokens=180,
        )
        self.fallback_llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_fast,
            temperature=0.0,
            max_tokens=100,
        )
        self.prompt = ChatPromptTemplate.from_template(CLASSIFIER_PROMPT)
        self.chain = self.prompt | self.llm.with_structured_output(ClassificationResult)
        self.fallback_prompt = ChatPromptTemplate.from_template(FALLBACK_PROMPT)
        self.fallback_chain = self.fallback_prompt | self.fallback_llm

    @staticmethod
    def _build_readme_preview(readme_content: Optional[str]) -> str:
        return (readme_content or "").strip()[:300]

    @staticmethod
    def _extract_json_blob(text: str) -> Optional[dict]:
        if not text:
            return None
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _to_result(data: Optional[dict]) -> Optional[ClassificationResult]:
        if not isinstance(data, dict):
            return None
        category = str(data.get("category", "")).strip()
        if category not in {c.value for c in ProjectCategory}:
            return None
        return ClassificationResult(
            category=ProjectCategory(category),
            confidence=data.get("confidence", 0.5),
            reasoning=(str(data.get("reasoning", "")).strip() or "简版分类结果")[:40],
        )

    @staticmethod
    def _is_truncation_error(error: Exception) -> bool:
        message = str(error)
        return "length limit was reached" in message or "Could not parse response content" in message

    @staticmethod
    def _estimate_confidence(
        category: ProjectCategory,
        description: Optional[str],
        readme_preview: str,
        reasoning: str,
    ) -> float:
        text = f"{description or ''} {readme_preview or ''}".lower()
        score = 0.1

        desc_len = len((description or "").strip())
        readme_len = len((readme_preview or "").strip())

        if desc_len >= 40:
            score += 0.15
        elif desc_len >= 15:
            score += 0.08

        if readme_len >= 180:
            score += 0.2
        elif readme_len >= 80:
            score += 0.12
        elif readme_len >= 20:
            score += 0.06

        keyword_map = {
            ProjectCategory.AI_ECOSYSTEM: ["llm", "agent", "ai", "rag", "inference", "chatbot", "prompt"],
            ProjectCategory.INFRA_AND_TOOLS: ["cli", "sdk", "framework", "pipeline", "devops", "toolchain", "library"],
            ProjectCategory.PRODUCT_AND_UI: ["ui", "ux", "frontend", "dashboard", "app", "react", "vue", "next.js"],
            ProjectCategory.KNOWLEDGE_BASE: ["tutorial", "guide", "awesome", "roadmap", "docs", "course", "learn"],
        }
        hits = sum(1 for keyword in keyword_map.get(category, []) if keyword in text)
        score += min(hits, 3) * 0.12

        if len((reasoning or "").strip()) >= 8:
            score += 0.08

        if desc_len < 10 and readme_len < 20:
            score = min(score, 0.22)

        return max(0.1, min(0.9, score))

    @classmethod
    def _calibrate_confidence(
        cls,
        result: ClassificationResult,
        description: Optional[str],
        readme_preview: str,
    ) -> ClassificationResult:
        if result.confidence <= 0.0:
            result.confidence = cls._estimate_confidence(
                category=result.category,
                description=description,
                readme_preview=readme_preview,
                reasoning=result.reasoning,
            )
        return result

    def _default_result(
        self,
        error: Exception,
        description: Optional[str],
        readme_preview: str,
    ) -> ClassificationResult:
        result = ClassificationResult(
            category=ProjectCategory.PRODUCT_AND_UI,
            confidence=0.0,
            reasoning=f"分类异常，默认分类: {error}",
        )
        return self._calibrate_confidence(result, description, readme_preview)

    def _fallback_classify(
        self,
        repo_name: str,
        description: Optional[str],
        readme_preview: str,
    ) -> Optional[ClassificationResult]:
        try:
            message = self.fallback_chain.invoke(
                {
                    "repo_name": repo_name,
                    "description": description or "无",
                    "readme_preview": readme_preview,
                }
            )
            parsed = self._extract_json_blob(getattr(message, "content", ""))
            return self._to_result(parsed)
        except Exception:
            return None

    async def _fallback_classify_async(
        self,
        repo_name: str,
        description: Optional[str],
        readme_preview: str,
    ) -> Optional[ClassificationResult]:
        try:
            message = await self.fallback_chain.ainvoke(
                {
                    "repo_name": repo_name,
                    "description": description or "无",
                    "readme_preview": readme_preview,
                }
            )
            parsed = self._extract_json_blob(getattr(message, "content", ""))
            return self._to_result(parsed)
        except Exception:
            return None

    def classify(
        self,
        repo_name: str,
        description: Optional[str],
        readme_content: Optional[str],
    ) -> ClassificationResult:
        readme_preview = self._build_readme_preview(readme_content)
        try:
            result: ClassificationResult = self.chain.invoke(
                {
                    "repo_name": repo_name,
                    "description": description or "无",
                    "readme_preview": readme_preview,
                }
            )
            result = self._calibrate_confidence(result, description, readme_preview)
            logger.info(
                f"项目 {repo_name} 分类为 {result.category.value} (置信度: {result.confidence:.2f})"
            )
            return result
        except Exception as error:
            if self._is_truncation_error(error):
                recovered = self._fallback_classify(repo_name, description, readme_preview)
                if recovered:
                    recovered = self._calibrate_confidence(recovered, description, readme_preview)
                    logger.info(
                        f"分类截断恢复成功 {repo_name}: {recovered.category.value} ({recovered.confidence:.2f})"
                    )
                    return recovered
            logger.warning(f"分类失败 {repo_name}: {error}，使用默认分类")
            return self._default_result(error, description, readme_preview)

    async def classify_async(
        self,
        repo_name: str,
        description: Optional[str],
        readme_content: Optional[str],
    ) -> ClassificationResult:
        readme_preview = self._build_readme_preview(readme_content)
        try:
            result: ClassificationResult = await self.chain.ainvoke(
                {
                    "repo_name": repo_name,
                    "description": description or "无",
                    "readme_preview": readme_preview,
                }
            )
            result = self._calibrate_confidence(result, description, readme_preview)
            logger.info(
                f"项目 {repo_name} 分类为 {result.category.value} (置信度: {result.confidence:.2f})"
            )
            return result
        except Exception as error:
            if self._is_truncation_error(error):
                recovered = await self._fallback_classify_async(repo_name, description, readme_preview)
                if recovered:
                    recovered = self._calibrate_confidence(recovered, description, readme_preview)
                    logger.info(
                        f"分类截断恢复成功 {repo_name}: {recovered.category.value} ({recovered.confidence:.2f})"
                    )
                    return recovered
            logger.warning(f"分类失败 {repo_name}: {error}，使用默认分类")
            return self._default_result(error, description, readme_preview)
