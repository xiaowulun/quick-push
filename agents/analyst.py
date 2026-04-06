"""
Analyst Agent - 技术深度分析师

负责深度技术分析，判断项目是不是"水货"：
- README 实质内容评估（不是空话）
- 技术栈先进性和合理性
- 项目成熟度指标
- 内容质量评分（有没有干货）
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import re
import logging

from agents.base import BaseAgent, AgentResult

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """技术深度分析师 - 专注判断项目质量"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__("AnalystAgent", config)

    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        深度技术分析

        Args:
            context: {
                "repo_name": str,
                "readme_content": str,
                "repo_data": Dict,
            }
        """
        self.log_start(context)

        try:
            repo_name = context.get("repo_name", "")
            readme_content = context.get("readme_content", "")
            repo_data = context.get("repo_data", {})

            # 1. README 实质内容评估
            content_quality = self._assess_content_quality(readme_content)

            # 2. 技术栈分析
            tech_analysis = self._analyze_tech_stack(readme_content, repo_data)

            # 3. 项目实质内容评估（是不是水货）
            substance_score = self._evaluate_substance(readme_content, repo_data)

            # 4. 代码/文档质量指标
            quality_metrics = self._assess_quality_metrics(readme_content, repo_data)

            result_data = {
                "content_quality": content_quality,
                "tech_analysis": tech_analysis,
                "substance_score": substance_score,
                "quality_metrics": quality_metrics,
                "analyzed_at": datetime.now().isoformat(),
            }

            result = self.create_success_result(
                data=result_data,
                metadata={
                    "repo_name": repo_name,
                    "focus": "technical_depth",
                }
            )

            self.log_end(result)
            return result

        except Exception as e:
            error_msg = f"技术分析失败: {str(e)}"
            logger.error(error_msg)
            return self.create_error_result(error_msg)

    def _assess_content_quality(self, readme: str) -> Dict:
        """评估 README 实质内容质量（不是空话）"""
        if not readme or len(readme) < 100:
            return {
                "substance_level": "poor",
                "has_real_content": False,
                "fluff_ratio": 1.0,
                "issues": ["README 内容过少或缺失"],
            }

        issues = []

        # 1. 检测空话/套话
        fluff_patterns = [
            r"(?i)world.?class|世界级",
            r"(?i)cutting.?edge|前沿",
            r"(?i)revolutionary|革命性",
            r"(?i)next.?generation|下一代",
            r"(?i)powerful|强大.*解决方案",
            r"(?i)innovative|创新",
        ]
        fluff_count = sum(1 for p in fluff_patterns if re.search(p, readme))
        fluff_ratio = min(fluff_count / len(fluff_patterns), 1.0)

        if fluff_ratio > 0.5:
            issues.append("营销话术过多，缺乏实质内容")

        # 2. 检测是否有具体技术细节
        # 检测代码块（支持 ``` 和缩进代码）
        has_code_block = bool(re.search(r'`{3}', readme))  # 三个反引号
        has_indented_code = bool(re.search(r'(?:^|\n)(?:    |\t)', readme))  # 缩进代码
        has_code_examples = has_code_block or has_indented_code

        has_api_docs = bool(re.search(r'(?i)api|接口|方法|function|usage|使用', readme))
        has_install_guide = bool(re.search(r'(?i)install|pip|npm|yarn|安装|getting started', readme))

        if not has_code_examples:
            issues.append("缺少代码示例")
        if not has_api_docs:
            issues.append("缺少 API 文档")
        if not has_install_guide:
            issues.append("缺少安装指南")

        # 3. 内容密度分析
        total_lines = len(readme.split('\n'))
        code_lines = len(re.findall(r'^    |^\t|^```', readme, re.MULTILINE))
        code_density = code_lines / total_lines if total_lines > 0 else 0

        # 4. 判断实质程度
        substance_indicators = sum([
            has_code_examples,
            has_api_docs,
            has_install_guide,
            code_density > 0.1,
            fluff_ratio < 0.3,
        ])

        if substance_indicators >= 4:
            substance_level = "excellent"
        elif substance_indicators >= 3:
            substance_level = "good"
        elif substance_indicators >= 2:
            substance_level = "fair"
        else:
            substance_level = "poor"

        return {
            "substance_level": substance_level,
            "has_real_content": substance_indicators >= 2,
            "fluff_ratio": round(fluff_ratio, 2),
            "code_density": round(code_density, 2),
            "has_code_examples": has_code_examples,
            "has_api_docs": has_api_docs,
            "has_install_guide": has_install_guide,
            "issues": issues[:3],
        }

    def _analyze_tech_stack(self, readme: str, repo_data: Dict) -> Dict:
        """分析技术栈"""
        text = readme.lower()
        language = repo_data.get("language", "")
        topics = repo_data.get("topics", [])
        description = repo_data.get("description", "").lower()

        # 合并所有文本用于检测
        all_text = f"{text} {description} {' '.join(topics)}"

        # 检测主要技术
        tech_indicators = {
            "frontend": ["react", "vue", "angular", "svelte", "html", "css", "webpack", "vite", "ui", "component"],
            "backend": ["django", "flask", "fastapi", "spring", "express", "nestjs", "server", "api"],
            "database": ["mysql", "postgresql", "mongodb", "redis", "sqlite", "elasticsearch", "database", "orm"],
            "ai_ml": ["pytorch", "tensorflow", "scikit-learn", "huggingface", "openai", "llm", "ai", "agent", "model", "gpt", "claude"],
            "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "cloud"],
            "mobile": ["react native", "flutter", "ios", "android", "swift", "mobile", "app"],
            "devops": ["ci/cd", "github actions", "jenkins", "gitlab", "deployment"],
        }

        detected_domains = []
        for domain, keywords in tech_indicators.items():
            if any(kw in all_text for kw in keywords):
                detected_domains.append(domain)

        # 从编程语言推断领域
        lang_to_domain = {
            "JavaScript": ["frontend", "backend"],
            "TypeScript": ["frontend", "backend"],
            "Python": ["backend", "ai_ml"],
            "Go": ["backend", "cloud"],
            "Rust": ["backend", "cloud"],
            "Java": ["backend"],
            "Swift": ["mobile"],
            "Kotlin": ["mobile"],
            "Dart": ["mobile"],
        }
        if language in lang_to_domain:
            for domain in lang_to_domain[language]:
                if domain not in detected_domains:
                    detected_domains.append(domain)

        # 评估技术先进性
        modern_tech = ["rust", "go", "typescript", "webassembly", "graphql"]
        modern_score = sum(1 for tech in modern_tech if tech in text) / len(modern_tech)

        # 技术栈复杂度
        complexity = "simple" if len(detected_domains) <= 1 else \
                     "moderate" if len(detected_domains) <= 3 else "complex"

        return {
            "primary_language": language,
            "tech_domains": detected_domains,
            "modern_score": round(modern_score, 2),
            "complexity": complexity,
            "is_fullstack": "frontend" in detected_domains and "backend" in detected_domains,
        }

    def _evaluate_substance(self, readme: str, repo_data: Dict) -> Dict:
        """评估项目是不是水货"""
        red_flags = []
        green_flags = []

        # 红旗指标（可能是水货）
        if len(readme) < 500:
            red_flags.append("README 过短，缺乏介绍")

        if not re.search(r'`{3}', readme) and not re.search(r'(?:^|\n)(?:    |\t)', readme):
            red_flags.append("没有代码示例")

        if re.search(r'(?i)todo|wip|work in progress|即将上线', readme[:1000]):
            red_flags.append("项目还在早期/WIP 阶段")

        # 检测是否是"Awesome List"类项目（知识汇总，非代码项目）
        if re.search(r'(?i)^#.*awesome|awesome-|^#.*list|curated list', readme[:500]):
            red_flags.append("Awesome List 类项目，非原创代码")

        # 绿旗指标（有实质内容）
        if re.search(r'(?i)benchmark|性能测试|comparison|对比', readme):
            green_flags.append("有性能测试或对比数据")

        if re.search(r'(?i)architecture|架构|design|设计', readme):
            green_flags.append("有架构设计说明")

        if repo_data.get("has_wiki", False):
            green_flags.append("有 Wiki 文档")

        if repo_data.get("has_pages", False):
            green_flags.append("有 GitHub Pages 文档站")

        # 计算实质分数
        red_score = len(red_flags) * 0.2
        green_score = len(green_flags) * 0.15
        substance_score = max(0, 1 - red_score + green_score)

        # 判断项目类型
        if substance_score >= 0.8 and len(green_flags) >= 2:
            project_nature = "substantial"  # 有实质内容
        elif substance_score >= 0.5:
            project_nature = "moderate"     # 一般
        elif len(red_flags) >= 2:
            project_nature = "shallow"      # 水货嫌疑
        else:
            project_nature = "unclear"      # 不清楚

        return {
            "substance_score": round(substance_score, 2),
            "project_nature": project_nature,
            "red_flags": red_flags,
            "green_flags": green_flags,
            "is_awesome_list": "Awesome List" in str(red_flags),
        }

    def _assess_quality_metrics(self, readme: str, repo_data: Dict) -> Dict:
        """评估质量指标"""

        # 文档完整性检查
        doc_sections = {
            "quick_start": bool(re.search(r'(?i)#.*quick start|#.*快速开始|#.*usage|#.*使用', readme)),
            "configuration": bool(re.search(r'(?i)#.*config|#.*配置', readme)),
            "contributing": bool(re.search(r'(?i)#.*contributing|#.*贡献', readme)),
            "license": bool(re.search(r'(?i)#.*license|#.*许可', readme)),
            "changelog": bool(re.search(r'(?i)#.*changelog|#.*更新|#.*release', readme)),
        }

        doc_completeness = sum(doc_sections.values()) / len(doc_sections)

        # 维护活跃度指标
        pushed_at = repo_data.get("pushed_at", "")
        activity_indicator = "unknown"
        if pushed_at:
            try:
                pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                days_ago = (datetime.now() - pushed.replace(tzinfo=None)).days
                if days_ago < 7:
                    activity_indicator = "very_active"
                elif days_ago < 30:
                    activity_indicator = "active"
                elif days_ago < 90:
                    activity_indicator = "moderate"
                else:
                    activity_indicator = "stale"
            except:
                pass

        # 社区健康度
        has_issues = repo_data.get("has_issues", False)
        has_discussions = repo_data.get("has_discussions", False)

        return {
            "doc_completeness": round(doc_completeness, 2),
            "doc_sections": [k for k, v in doc_sections.items() if v],
            "activity_indicator": activity_indicator,
            "has_issue_tracking": has_issues,
            "has_discussions": has_discussions,
            "overall_quality": self._calculate_overall_quality(doc_completeness, activity_indicator),
        }

    def _calculate_overall_quality(self, doc_score: float, activity: str) -> str:
        """计算整体质量等级"""
        activity_scores = {
            "very_active": 1.0,
            "active": 0.8,
            "moderate": 0.6,
            "stale": 0.3,
            "unknown": 0.5,
        }

        activity_score = activity_scores.get(activity, 0.5)
        overall = doc_score * 0.5 + activity_score * 0.5

        if overall >= 0.8:
            return "high"
        elif overall >= 0.6:
            return "medium"
        else:
            return "low"
