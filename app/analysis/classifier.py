from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.config import get_config
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProjectCategory(str, Enum):
    """项目分类枚举"""
    AI_ECOSYSTEM = "ai_ecosystem"
    INFRA_AND_TOOLS = "infra_and_tools"
    PRODUCT_AND_UI = "product_and_ui"
    KNOWLEDGE_BASE = "knowledge_base"


class ClassificationResult(BaseModel):
    """分类结果"""
    category: ProjectCategory = Field(description="项目分类")
    confidence: float = Field(description="分类置信度 0-1")
    reasoning: str = Field(description="分类理由")


def get_category_emoji(category: ProjectCategory) -> str:
    emoji_map = {
        ProjectCategory.AI_ECOSYSTEM: "🤖",
        ProjectCategory.INFRA_AND_TOOLS: "⚙️",
        ProjectCategory.PRODUCT_AND_UI: "🎨",
        ProjectCategory.KNOWLEDGE_BASE: "📚",
    }
    return emoji_map.get(category, "📦")


def get_category_name(category: ProjectCategory) -> str:
    name_map = {
        ProjectCategory.AI_ECOSYSTEM: "AI 生态与应用",
        ProjectCategory.INFRA_AND_TOOLS: "底层基建与开发者工具",
        ProjectCategory.PRODUCT_AND_UI: "全栈应用与视觉组件",
        ProjectCategory.KNOWLEDGE_BASE: "知识库与聚合资源",
    }
    return name_map.get(category, "其他")


CLASSIFIER_PROMPT = """你是一个 GitHub 项目分类专家。请根据以下信息判断项目属于哪一类：

项目名称：{repo_name}
项目描述：{description}
README 前 800 字:
{readme_preview}

可选分类:

1. 🤖 ai_ecosystem (AI 生态与应用)
   - **核心特征**: 项目本身是 AI 产品、AI 服务、或提供 AI 能力的平台
   - AI 基础设施、大模型工具链、AI 终端产品、AI Agent 平台
   - 关键词：LLM、模型、训练、推理、GPT、AI Agent、RAG、微调、Chatbot
   - **判断标准**: 如果项目的主要功能是"提供 AI 能力"或"运行 AI 模型"，选这个
   - 示例：google-ai-edge/gallery (AI 模型展示平台), HKUDS/DeepTutor (AI 学习助手)

2. ⚙️ infra_and_tools (底层基建与开发者工具)
   - **核心特征**: 项目是开发者使用的工具、配置、或技术基础设施
   - 后端/云原生/数据库、开发者工具、CLI、配置模板、技能文件
   - 关键词：数据库、缓存、RPC、网关、编译器、CLI、构建工具、配置、模板、skills、profile
   - **判断标准**: 如果项目是"给开发者用的工具"或"配置/模板文件"，选这个
   - **特别注意**: "AI 编程助手配置"、"Claude 技能文件"、"Cursor 配置"等属于开发者工具，不是 AI 产品
   - 示例：andrej-karpathy-skills (Claude 编码配置), 各种 linter、formatter、devops 工具

3. 🎨 product_and_ui (全栈应用与视觉组件)
   - **核心特征**: 项目是可直接使用的终端产品或 UI 组件
   - Web 全栈框架、UI 组件库、可部署的开源系统、SaaS 产品
   - 关键词：UI、组件、模板、Dashboard、React、Vue、Next.js、可部署、产品
   - **判断标准**: 如果项目是"最终用户直接使用的产品"或"UI 组件库"，选这个
   - 示例：openscreen (屏幕录制产品), 各种 UI 组件库

4. 📚 knowledge_base (知识库与聚合资源)
   - **核心特征**: 项目是知识聚合、学习资源、或信息整理
   - Awesome 列表、面试题、自学路线图、文档集合、教程集合
   - 关键词：Awesome、Interview、Roadmap、Tutorial、List、Guide、学习、教程
   - **判断标准**: 如果项目主要是"整理/聚合信息"而非代码工具，选这个
   - 示例：awesome-xxx 列表、面试题库、学习路线图

置信度 0.0-1.0，诚实评估。

返回：category, confidence, reasoning"""


class ProjectClassifier:
    """项目分类器"""

    def __init__(self):
        config = get_config()
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model_fast,
            temperature=0.3
        )
        self.prompt = ChatPromptTemplate.from_template(CLASSIFIER_PROMPT)
        self.chain = self.prompt | self.llm.with_structured_output(ClassificationResult)

    def classify(
        self,
        repo_name: str,
        description: Optional[str],
        readme_content: Optional[str]
    ) -> ClassificationResult:
        """同步分类项目"""
        readme_preview = (readme_content or "")[:800]

        try:
            result: ClassificationResult = self.chain.invoke({
                "repo_name": repo_name,
                "description": description or "无",
                "readme_preview": readme_preview
            })
            logger.info(f"项目 {repo_name} 分类为 {result.category.value} (置信度: {result.confidence:.2f})")
            return result
        except Exception as e:
            logger.warning(f"分类失败 {repo_name}: {e}，使用默认分类")
            return ClassificationResult(
                category=ProjectCategory.PRODUCT_AND_UI,
                confidence=0.5,
                reasoning=f"分类异常，使用默认: {str(e)}"
            )

    async def classify_async(
        self,
        repo_name: str,
        description: Optional[str],
        readme_content: Optional[str]
    ) -> ClassificationResult:
        """异步分类项目"""
        readme_preview = (readme_content or "")[:800]

        try:
            result: ClassificationResult = await self.chain.ainvoke({
                "repo_name": repo_name,
                "description": description or "无",
                "readme_preview": readme_preview
            })
            logger.info(f"项目 {repo_name} 分类为 {result.category.value} (置信度: {result.confidence:.2f})")
            return result
        except Exception as e:
            logger.warning(f"分类失败 {repo_name}: {e}，使用默认分类")
            return ClassificationResult(
                category=ProjectCategory.PRODUCT_AND_UI,
                confidence=0.5,
                reasoning=f"分类异常，使用默认: {str(e)}"
            )
