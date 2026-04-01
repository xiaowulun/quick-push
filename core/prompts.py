"""
路由链专家 Prompt 配置
根据项目类型分发到不同的分析视角
"""

from core.classifier import ProjectCategory

# 基础输出结构要求
OUTPUT_FORMAT = """
请分析这个项目，返回以下 JSON 格式:
{{
    "summary": "50-100字的项目简介，说明项目是做什么的、解决什么问题",
    "reasons": ["爆火原因1", "爆火原因2", "爆火原因3"]
}}

注意：
- summary 控制在 50-100 字
- 每个爆火原因最多 40 字，简洁有力
- 总共 3-5 个爆火原因即可
"""

# 🤖 AI 生态与应用
AI_ECOSYSTEM_PROMPT = """你是 AI 领域技术专家，擅长分析 AI 基础设施、大模型工具链和 AI 应用产品。

分析维度：
1. 定位判断：这是底层模型/工具，还是套壳应用？
2. 痛点解决：主要解决了 AI 落地过程中的什么痛点？
3. 技术亮点：模型能力、上下文处理、生成效率有什么创新？
4. 应用场景：适合什么类型的用户/企业使用？
5. 生态价值：对 AI 开发者社区有什么贡献？

请从技术深度、实用性和创新性角度分析这个项目。

项目名称：{repo_name}
项目描述：{description}
当前 Star 数：{stars}
README 内容：
{readme_content}

""" + OUTPUT_FORMAT

# ⚙️ 底层基建与开发者工具
INFRA_AND_TOOLS_PROMPT = """你是系统架构和开发者工具专家，擅长分析后端、云原生、数据库和开发工具。

分析维度：
1. 技术选型：用什么语言/架构重写的？有什么技术亮点？
2. 性能突破：对比同类老牌工具在性能、资源占用上有什么优势？
3. 架构创新：在系统设计、并发处理、扩展性上有什么突破？
4. 开发者体验：API 设计、文档质量、易用性如何？
5. 替代价值：相比现有方案，迁移成本和学习曲线如何？

请从工程化、性能优化和开发者体验角度分析这个项目。

项目名称：{repo_name}
项目描述：{description}
当前 Star 数：{stars}
README 内容：
{readme_content}

""" + OUTPUT_FORMAT

# 🎨 全栈应用与视觉组件
PRODUCT_AND_UI_PROMPT = """你是前端和用户体验专家，擅长分析 Web 框架、UI 组件库和开源应用系统。

分析维度：
1. 设计规范：视觉设计、交互体验、组件完整性如何？
2. 技术栈：基于什么框架？现代化程度如何？
3. 工程化：代码质量、类型安全、构建工具链如何？
4. 开箱即用：文档完善度、示例丰富度、部署便捷性如何？
5. 业务价值：能多大程度降低开发者的搭积木成本？

请从设计美学、工程规范和业务落地角度分析这个项目。

项目名称：{repo_name}
项目描述：{description}
当前 Star 数：{stars}
README 内容：
{readme_content}

""" + OUTPUT_FORMAT

# 📚 知识库与聚合资源
KNOWLEDGE_BASE_PROMPT = """你是技术学习路径规划专家，擅长分析教程、面试题、Awesome 列表等知识资源。

分析维度：
1. 系统性：内容组织结构是否清晰？覆盖范围是否全面？
2. 目标受众：适合新手入门还是老手进阶？
3. 时效性：内容是否及时更新？是否跟进最新技术趋势？
4. 实用性：是否有实战案例？是否可直接应用于工作/面试？
5. 社区价值：在开发者社区中的口碑和引用度如何？

请从学习效果、实用价值和知识完整性角度分析这个项目。

项目名称：{repo_name}
项目描述：{description}
当前 Star 数：{stars}
README 内容：
{readme_content}

""" + OUTPUT_FORMAT

# Prompt 路由映射
CATEGORY_PROMPTS = {
    ProjectCategory.AI_ECOSYSTEM: AI_ECOSYSTEM_PROMPT,
    ProjectCategory.INFRA_AND_TOOLS: INFRA_AND_TOOLS_PROMPT,
    ProjectCategory.PRODUCT_AND_UI: PRODUCT_AND_UI_PROMPT,
    ProjectCategory.KNOWLEDGE_BASE: KNOWLEDGE_BASE_PROMPT,
}


def get_prompt_by_category(category: ProjectCategory) -> str:
    """根据分类获取对应的 Prompt"""
    return CATEGORY_PROMPTS.get(category, PRODUCT_AND_UI_PROMPT)


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
