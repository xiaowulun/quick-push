from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from core.config import get_config
from utils.logging_config import get_logger

logger = get_logger(__name__)


class ProjectCategory(str, Enum):
    """项目分类枚举"""
    AI_ECOSYSTEM = "ai_ecosystem"           # 🤖 AI 生态与应用
    INFRA_AND_TOOLS = "infra_and_tools"     # ⚙️ 底层基建与开发者工具
    PRODUCT_AND_UI = "product_and_ui"       # 🎨 全栈应用与视觉组件
    KNOWLEDGE_BASE = "knowledge_base"       # 📚 知识库与聚合资源


class ClassificationResult(BaseModel):
    """分类结果"""
    category: ProjectCategory = Field(description="项目分类")
    confidence: float = Field(description="分类置信度 0-1")
    reasoning: str = Field(description="分类理由")


def get_category_emoji(category: ProjectCategory) -> str:
    """获取分类对应的 emoji"""
    emoji_map = {
        ProjectCategory.AI_ECOSYSTEM: "🤖",
        ProjectCategory.INFRA_AND_TOOLS: "⚙️",
        ProjectCategory.PRODUCT_AND_UI: "🎨",
        ProjectCategory.KNOWLEDGE_BASE: "📚",
    }
    return emoji_map.get(category, "📦")


def get_category_name(category: ProjectCategory) -> str:
    """获取分类的中文名称"""
    name_map = {
        ProjectCategory.AI_ECOSYSTEM: "AI 生态与应用",
        ProjectCategory.INFRA_AND_TOOLS: "底层基建与开发者工具",
        ProjectCategory.PRODUCT_AND_UI: "全栈应用与视觉组件",
        ProjectCategory.KNOWLEDGE_BASE: "知识库与聚合资源",
    }
    return name_map.get(category, "其他")


# 分类 Prompt
CLASSIFIER_PROMPT = """你是一个 GitHub 项目分类专家。请根据以下信息判断项目属于哪一类：

项目名称: {repo_name}
项目描述: {description}
README 前 800 字:
{readme_preview}

可选分类:

1. 🤖 ai_ecosystem (AI 生态与应用)
   - AI 基础设施、大模型工具链、AI 终端产品
   - 关键词: LLM、模型、训练、推理、GPT、AI Agent、RAG、微调
   - 判断: 是否涉及 AI/ML 核心技术或应用

2. ⚙️ infra_and_tools (底层基建与开发者工具)
   - 后端/云原生/数据库、开发者工具 (CLI, 打包工具)
   - 关键词: 数据库、缓存、RPC、网关、编译器、CLI、构建工具
   - 判断: 是否面向开发者提供底层能力或工具链

3. 🎨 product_and_ui (全栈应用与视觉组件)
   - Web 全栈框架、UI 组件库、可部署的开源系统
   - 关键词: UI、组件、模板、Dashboard、React、Vue、前端
   - 判断: 是否提供可视化界面或完整的应用系统

4. 📚 knowledge_base (知识库与聚合资源)
   - Awesome 列表、面试题、自学路线图、文档集合
   - 关键词: Awesome、Interview、Roadmap、Tutorial、List、合集
   - 判断: 是否以资源整理、知识汇总为主，代码量少

置信度判断标准：
- 0.9-1.0: 非常确定，项目名称或描述明确包含分类关键词
- 0.7-0.89: 比较确定，README 内容明显符合某类特征
- 0.5-0.69: 一般确定，需要更多信息才能准确判断
- 0.3-0.49: 不太确定，项目特征模糊，可能跨多个类别
- 0.0-0.29: 很不确定，信息不足或无法归类

请根据以上标准，诚实评估你的分类置信度。

返回格式要求：
- category: 从四个选项中选择一个最匹配的
- confidence: 0.0-1.0 之间的浮点数，根据上述标准
- reasoning: 简要说明分类理由（1-2句话）
"""


class ProjectClassifier:
    """项目分类器"""

    def __init__(self):
        config = get_config()
        self.llm = ChatOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            model_name=config.openai.model,
            temperature=0.3  # 确定性输出
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
