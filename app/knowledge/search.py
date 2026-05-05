"""
搜索服务模块

整合向量检索、BM25 与重排序，提供项目索引和搜索能力。
默认使用 chunk 级召回，再聚合为 repo 级结果。
"""

import logging
import hashlib
import re
import asyncio
import threading
from collections import defaultdict
from datetime import date, timedelta
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.analysis.readme import clean_readme_for_retrieval, split_readme_sections_for_retrieval
from app.analysis.structured_tags import extract_structured_tags
from app.infrastructure.cache import AnalysisCache
from app.infrastructure.chroma_store import ChromaVectorStore
from app.infrastructure.config import get_config
from app.infrastructure.embedding import EmbeddingEngine
from app.infrastructure.hybrid_search import HybridSearchEngine
from app.infrastructure.reranker import CrossEncoderReranker
from app.knowledge.query_rewriter import QueryRewriter, QueryVariant

logger = logging.getLogger(__name__)


class LLMProjectProfile(BaseModel):
    suitable_for: List[str] = Field(default_factory=list, description="适合人群或场景建议，2-4条")
    complexity: Literal["low", "medium", "high"] = "medium"
    maturity: Literal["early", "medium", "high"] = "medium"
    risk_notes: List[str] = Field(default_factory=list, description="主要风险提示，1-4条")


_PROFILE_PROMPT = ChatPromptTemplate.from_template(
    """你是开源项目选型顾问。请基于输入事实，输出 JSON 字段：
- suitable_for: 2-4条，面向团队场景，中文短句
- complexity: 只能是 low/medium/high
- maturity: 只能是 early/medium/high
- risk_notes: 1-4条，具体风险，中文短句

要求：
1) 只能基于提供事实，不要虚构。
2) 不要输出与事实冲突的结论。
3) 避免空泛套话。

项目：{repo_full_name}
语言：{language}
分类：{category}
summary：{summary}
reasons：{reasons}
keywords：{keywords}
tech_stack：{tech_stack}
use_cases：{use_cases}
trend_summary：{trend_summary}
evidence：{evidence}
"""
)


_PROFILE_LLM: Optional[ChatOpenAI] = None
_PROFILE_LLM_SIGNATURE: Optional[Tuple[str, str, float]] = None


def _sanitize_profile_list(values: Any, limit: int) -> List[str]:
    out: List[str] = []
    seen = set()
    if not isinstance(values, list):
        return out
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _get_profile_llm() -> Optional[ChatOpenAI]:
    global _PROFILE_LLM, _PROFILE_LLM_SIGNATURE
    try:
        config = get_config()
    except Exception as exc:
        logger.warning("项目画像 LLM 不可用（配置不可用），将使用规则版: %s", exc)
        return None

    if not config.openai.api_key:
        return None

    model_name = config.openai.model_fast
    timeout = float(config.openai.request_timeout)
    signature = (config.openai.base_url, model_name, timeout)
    if _PROFILE_LLM is not None and _PROFILE_LLM_SIGNATURE == signature:
        return _PROFILE_LLM

    _PROFILE_LLM = ChatOpenAI(
        api_key=config.openai.api_key,
        base_url=config.openai.base_url,
        model_name=model_name,
        temperature=0.1,
        timeout=timeout,
    )
    _PROFILE_LLM_SIGNATURE = signature
    return _PROFILE_LLM


def _derive_profile_with_llm(
    *,
    summary: str,
    reasons: List[str],
    keywords: List[str],
    tech_stack: List[str],
    use_cases: List[str],
    trend_summary: Dict[str, Any],
    basic: Dict[str, Any],
    evidence_text: str,
) -> Optional[Dict[str, Any]]:
    llm = _get_profile_llm()
    if llm is None:
        return None

    try:
        chain = _PROFILE_PROMPT | llm.with_structured_output(LLMProjectProfile)
        result = chain.invoke(
            {
                "repo_full_name": basic.get("repo_full_name") or "",
                "language": basic.get("language") or "Unknown",
                "category": basic.get("category") or "infra_and_tools",
                "summary": summary or "",
                "reasons": " | ".join([str(x) for x in reasons or []])[:800],
                "keywords": " | ".join([str(x) for x in keywords or []])[:500],
                "tech_stack": " | ".join([str(x) for x in tech_stack or []])[:500],
                "use_cases": " | ".join([str(x) for x in use_cases or []])[:500],
                "trend_summary": str(trend_summary or {})[:700],
                "evidence": (evidence_text or "")[:1200],
            }
        )
        payload = result.model_dump() if hasattr(result, "model_dump") else dict(result or {})
        payload["suitable_for"] = _sanitize_profile_list(payload.get("suitable_for"), 4)
        payload["risk_notes"] = _sanitize_profile_list(payload.get("risk_notes"), 6)
        return payload
    except Exception as exc:
        logger.warning("项目画像 LLM 生成失败，回退规则版: %s", exc)
        return None


def _derive_project_profile_rule(
    *,
    summary: str,
    reasons: List[str],
    keywords: List[str],
    tech_stack: List[str],
    use_cases: List[str],
    trend_summary: Dict[str, Any],
    basic: Dict[str, Any],
) -> Dict[str, Any]:
    """Rule-based project profile derivation."""
    use_case_to_audience = {
        "AI Agent": "适合需要构建智能体应用的团队",
        "RAG Knowledge Base": "适合需要知识库问答与检索增强的团队",
        "Code Assistant": "适合构建开发者工具或代码助手的团队",
        "Data Crawling": "适合做数据采集与情报抓取的团队",
        "Data Visualization": "适合做可视化报表与运营看板的团队",
        "Web Application": "适合交付 Web 产品与 SaaS 原型的团队",
        "Workflow Automation": "适合流程自动化和工作流编排场景",
        "Model Serving": "适合模型推理服务与部署场景",
        "DevOps": "适合基础设施与持续交付改造场景",
        "Education": "适合教学演示与课程实验场景",
    }

    advanced_stacks = {"Kubernetes", "Docker", "PyTorch", "TensorFlow", "LangChain"}
    complexity_score = 0.0
    complexity_score += min(2.0, max(0.0, (len(tech_stack) - 2) * 0.35))
    complexity_score += sum(0.6 for stack in tech_stack if stack in advanced_stacks)
    if "Model Serving" in use_cases:
        complexity_score += 0.8
    if "Workflow Automation" in use_cases:
        complexity_score += 0.4

    if complexity_score >= 2.8:
        complexity = "high"
    elif complexity_score >= 1.2:
        complexity = "medium"
    else:
        complexity = "low"

    stars = int(basic.get("stars") or 0)
    total_appearances = int(basic.get("total_appearances") or 0)
    total_records = int(trend_summary.get("total_records") or 0)
    best_rank = trend_summary.get("best_rank")
    maturity_score = 0.0
    if stars >= 5000:
        maturity_score += 2.0
    elif stars >= 1000:
        maturity_score += 1.2
    elif stars >= 300:
        maturity_score += 0.6

    if total_appearances >= 10:
        maturity_score += 1.0
    elif total_appearances >= 3:
        maturity_score += 0.5

    if total_records >= 10:
        maturity_score += 0.8
    elif total_records >= 4:
        maturity_score += 0.4

    if isinstance(best_rank, int) and best_rank > 0:
        if best_rank <= 3:
            maturity_score += 0.7
        elif best_rank <= 10:
            maturity_score += 0.4

    if maturity_score >= 3.0:
        maturity = "high"
    elif maturity_score >= 1.5:
        maturity = "medium"
    else:
        maturity = "early"

    suitable_for: List[str] = []
    for use_case in use_cases:
        audience = use_case_to_audience.get(str(use_case).strip())
        if audience and audience not in suitable_for:
            suitable_for.append(audience)
        if len(suitable_for) >= 4:
            break

    if not suitable_for:
        category = str(basic.get("category") or "").strip()
        language = str(basic.get("language") or "Unknown").strip()
        suitable_for.append(f"适合在 {language} 技术栈中做 PoC 与技术验证")
        if category:
            suitable_for.append(f"适合关注 {category} 方向开源方案的团队")

    risk_notes: List[str] = []
    if not summary.strip():
        risk_notes.append("项目摘要信息较少，建议补充 README 细读。")
    if len(reasons) < 2:
        risk_notes.append("推荐理由偏少，建议结合源码与 issue 进一步验证。")
    if len(tech_stack) == 0:
        risk_notes.append("技术栈识别不足，可能影响接入成本评估。")
    if total_records < 3:
        risk_notes.append("趋势历史样本较少，近期热度判断可能不稳定。")
    if complexity == "high":
        risk_notes.append("技术栈复杂度较高，落地前建议先做小范围验证。")
    if maturity == "early":
        risk_notes.append("项目成熟度偏早期，生产使用需额外风控。")
    if not risk_notes:
        risk_notes.append("未发现显著风险，仍建议结合实际场景完成 PoC 验证。")

    return {
        "suitable_for": suitable_for[:4],
        "complexity": complexity,
        "maturity": maturity,
        "risk_notes": risk_notes[:6],
        "keyword_hints": keywords[:6],
    }


def derive_project_profile(
    *,
    summary: str,
    reasons: List[str],
    keywords: List[str],
    tech_stack: List[str],
    use_cases: List[str],
    trend_summary: Dict[str, Any],
    basic: Dict[str, Any],
    evidence_text: str = "",
    allow_llm: bool = True,
) -> Dict[str, Any]:
    """Infer project profile, with optional LLM enhancement and deterministic fallback."""
    rule_profile = _derive_project_profile_rule(
        summary=summary,
        reasons=reasons,
        keywords=keywords,
        tech_stack=tech_stack,
        use_cases=use_cases,
        trend_summary=trend_summary,
        basic=basic,
    )

    llm_profile = None
    if allow_llm:
        llm_profile = _derive_profile_with_llm(
            summary=summary,
            reasons=reasons,
            keywords=keywords,
            tech_stack=tech_stack,
            use_cases=use_cases,
            trend_summary=trend_summary,
            basic=basic,
            evidence_text=evidence_text,
        )
    if not llm_profile:
        return rule_profile

    merged = dict(rule_profile)
    complexity = str(llm_profile.get("complexity") or "").strip().lower()
    maturity = str(llm_profile.get("maturity") or "").strip().lower()
    if complexity in {"low", "medium", "high"}:
        merged["complexity"] = complexity
    if maturity in {"early", "medium", "high"}:
        merged["maturity"] = maturity

    suitable_for = _sanitize_profile_list(llm_profile.get("suitable_for"), 4)
    risk_notes = _sanitize_profile_list(llm_profile.get("risk_notes"), 6)
    if suitable_for:
        merged["suitable_for"] = suitable_for
    if risk_notes:
        merged["risk_notes"] = risk_notes
    return merged


class SearchService:
    """搜索服务：chunk 召回 -> chunk 重排 -> repo 聚合。"""

    def __init__(self):
        self.config = get_config()
        self.cache = AnalysisCache()
        self.embedding_engine = EmbeddingEngine()
        self.chroma_store = ChromaVectorStore()
        self.hybrid_engine = HybridSearchEngine(rrf_k=60)
        retrieval = self.config.retrieval
        self.rerank_enabled = bool(retrieval.rerank_enabled)
        self.rerank_model_name = retrieval.rerank_model_name
        self.max_variants = max(1, int(retrieval.search_max_variants))
        self.coarse_multiplier = max(3, int(retrieval.search_coarse_multiplier))
        self.fused_multiplier = max(4, int(retrieval.search_fused_multiplier))
        self.variant_parallel = bool(retrieval.search_parallel_variants)
        # 缩小默认重排池，降低首包延迟。
        self.rerank_top_k_cap = max(6, int(retrieval.rerank_top_k_cap))
        self.rerank_multiplier = max(2, int(retrieval.rerank_multiplier))
        self.rerank_min_pool = max(4, int(retrieval.rerank_min_pool))
        self.reranker = (
            CrossEncoderReranker(
                model_name=self.rerank_model_name,
                enabled=self.rerank_enabled,
                local_files_only=bool(retrieval.rerank_local_files_only),
                max_length=int(retrieval.rerank_max_length),
                batch_size=int(retrieval.rerank_batch_size),
            )
            if self.rerank_enabled
            else None
        )
        self._rerank_warmup_started = False
        self._rerank_warmup_done = False
        self._rerank_warmup_lock = threading.Lock()
        self._index_warmup_started = False
        self._index_warmup_done = False
        self._index_warmup_lock = threading.Lock()
        self._ensure_index_lock = threading.Lock()
        self.query_rewriter = QueryRewriter()
        self._initialized = False
        if self.rerank_enabled and bool(retrieval.rerank_warmup_on_start):
            self.start_reranker_warmup()

    def start_reranker_warmup(self) -> None:
        """Start reranker warmup in a daemon thread (non-blocking)."""
        if not self.reranker:
            return
        with self._rerank_warmup_lock:
            if self._rerank_warmup_started:
                return
            self._rerank_warmup_started = True

        def _runner():
            started = perf_counter()
            ok = False
            try:
                ok = self.reranker.warmup()
            except Exception as e:
                logger.warning("Reranker warmup crashed: %s", e)
            finally:
                self._rerank_warmup_done = ok
                elapsed_ms = int((perf_counter() - started) * 1000)
                logger.info(
                    "Reranker warmup finished ok=%s elapsed_ms=%s",
                    ok,
                    elapsed_ms,
                )

        thread = threading.Thread(target=_runner, name="reranker-warmup", daemon=True)
        thread.start()

    def start_index_warmup(self) -> None:
        """Build retrieval index in a daemon thread (non-blocking)."""
        with self._index_warmup_lock:
            if self._index_warmup_started:
                return
            self._index_warmup_started = True

        def _runner():
            started = perf_counter()
            ok = False
            try:
                self._ensure_index()
                ok = bool(self._initialized)
            except Exception as e:
                logger.warning("Index warmup crashed: %s", e)
            finally:
                self._index_warmup_done = ok
                elapsed_ms = int((perf_counter() - started) * 1000)
                logger.info(
                    "Index warmup finished ok=%s elapsed_ms=%s initialized=%s",
                    ok,
                    elapsed_ms,
                    self._initialized,
                )

        thread = threading.Thread(target=_runner, name="search-index-warmup", daemon=True)
        thread.start()

    def _ensure_index(self) -> None:
        """确保检索索引已构建。"""
        if self._initialized:
            return

        with self._ensure_index_lock:
            if self._initialized:
                return

            all_chunks = self.cache.get_all_chunks()
            if not all_chunks:
                all_chunks = self._build_legacy_chunks()

            if all_chunks:
                self.hybrid_engine.build_index(all_chunks)
                self._initialized = True
                logger.info(f"搜索索引初始化完成，共 {len(all_chunks)} 个 chunk")

    def _build_legacy_chunks(self) -> List[Dict]:
        """兼容旧数据：从 repo 级 embedding 构造单 chunk 文档。"""
        legacy_docs = self.cache.get_all_embeddings()
        chunks: List[Dict] = []
        for doc in legacy_docs:
            text = (doc.get("search_text") or doc.get("summary") or "").strip()
            if not text:
                continue

            chunks.append({
                "chunk_id": f"{doc.get('repo_full_name', '')}#legacy",
                "repo_full_name": doc.get("repo_full_name", ""),
                "chunk_index": 0,
                "chunk_text": text,
                "section": "legacy",
                "path": "SUMMARY",
                "heading": "legacy",
                "updated_at": doc.get("repo_updated_at") or doc.get("source_updated_at"),
                "embedding": doc.get("embedding"),
                "keywords": doc.get("keywords", []),
                "tech_stack": doc.get("tech_stack", []),
                "use_cases": doc.get("use_cases", []),
                "summary": doc.get("summary", ""),
                "reasons": doc.get("reasons", []),
                "category": doc.get("category"),
                "language": doc.get("language"),
                "stars": doc.get("stars"),
                "record_date": doc.get("record_date"),
            })

        return chunks

    async def index_project(
        self,
        repo_full_name: str,
        summary: str,
        reasons: List[str],
        readme_content: str = "",
        language: str = "",
        category: str = "",
        source_updated_at: Optional[str] = None,
        keywords: List[str] = None,
        tech_stack: List[str] = None,
        use_cases: List[str] = None
    ) -> bool:
        """索引项目：保存 repo 级 embedding，并生成 chunk 索引。"""
        try:
            keywords = keywords or []
            tech_stack = tech_stack or []
            use_cases = use_cases or []
            if not keywords and not tech_stack and not use_cases:
                auto_tags = extract_structured_tags(
                    summary=summary,
                    reasons=reasons or [],
                    readme_content=readme_content or "",
                    repo_data={"language": language, "topics": []},
                    scout_data={},
                )
                keywords = auto_tags.get("keywords", [])
                tech_stack = auto_tags.get("tech_stack", [])
                use_cases = auto_tags.get("use_cases", [])

            search_text = self.cache.build_search_text(
                repo_full_name=repo_full_name,
                summary=summary,
                reasons=reasons,
                language=language,
                category=category,
            )

            # 保留 repo 级缓存，兼容已有逻辑和统计。
            embedding = await self.embedding_engine.embed_text(search_text)
            if not embedding:
                logger.error(f"项目 {repo_full_name} 向量化失败")
                return False

            self.cache.set_with_embedding(
                repo_full_name=repo_full_name,
                summary=summary,
                reasons=reasons,
                readme_content=readme_content,
                readme_hash=hashlib.sha256((readme_content or "").encode("utf-8")).hexdigest() if readme_content else None,
                source_updated_at=source_updated_at,
                search_text=search_text,
                embedding=embedding,
                keywords=keywords,
                tech_stack=tech_stack,
                use_cases=use_cases,
            )

            chunks = self._build_project_chunks(
                repo_full_name=repo_full_name,
                summary=summary,
                reasons=reasons,
                readme_content=readme_content,
                language=language,
                category=category,
                keywords=keywords,
                tech_stack=tech_stack,
                use_cases=use_cases,
                search_text=search_text,
                source_updated_at=source_updated_at,
            )
            if not chunks:
                logger.warning(f"项目 {repo_full_name} 没有可索引 chunk")
                return False

            chunk_embeddings = await self.embedding_engine.embed_batch([c["chunk_text"] for c in chunks])
            valid_chunks = []
            for chunk, chunk_embedding in zip(chunks, chunk_embeddings):
                if chunk_embedding:
                    chunk["embedding"] = chunk_embedding
                    valid_chunks.append(chunk)

            if not valid_chunks:
                logger.error(f"项目 {repo_full_name} 的 chunk 向量化全部失败")
                return False

            self.cache.replace_chunks(repo_full_name=repo_full_name, chunks=valid_chunks)

            self.chroma_store.batch_upsert(
                ids=[c["chunk_id"] for c in valid_chunks],
                embeddings=[c["embedding"] for c in valid_chunks],
                metadatas=[
                    {
                        "chunk_id": c["chunk_id"] or "",
                        "repo_full_name": c["repo_full_name"] or "",
                        "chunk_index": c["chunk_index"],
                        "section": c.get("section") or "",
                        "path": c.get("path") or "",
                        "heading": c.get("heading") or "",
                        "updated_at": c.get("updated_at") or "",
                        "summary": c.get("summary") or "",
                        "language": c.get("language") or "",
                        "category": c.get("category") or "",
                        "keywords": ",".join(c.get("keywords", [])),
                        "tech_stack": ",".join(c.get("tech_stack", [])),
                        "use_cases": ",".join(c.get("use_cases", [])),
                    }
                    for c in valid_chunks
                ],
            )

            self._initialized = False
            logger.info(f"项目 {repo_full_name} 索引成功，chunk 数: {len(valid_chunks)}")
            return True

        except Exception as e:
            logger.error(f"索引项目失败: {str(e)}")
            return False

    def _build_project_chunks(
        self,
        repo_full_name: str,
        summary: str,
        reasons: List[str],
        readme_content: str,
        language: str,
        category: str,
        keywords: List[str],
        tech_stack: List[str],
        use_cases: List[str],
        search_text: str,
        source_updated_at: Optional[str],
    ) -> List[Dict]:
        """把项目内容切分为多个可检索 chunk。"""
        sections: List[Tuple[str, str]] = []
        readme_sections: List[Tuple[str, str]] = []

        if readme_content and readme_content.strip():
            cleaned_readme = clean_readme_for_retrieval(readme_content)
            for section in split_readme_sections_for_retrieval(cleaned_readme):
                section_title = (section.get("section") or "README").strip()
                section_text = (section.get("text") or "").strip()
                if len(section_text) < 20:
                    continue
                readme_sections.append((f"readme:{section_title[:80]}", section_text))

        # README 作为主检索来源；只有缺失 README 时才使用 summary/reason 等信息作为备份。
        if readme_sections:
            sections = readme_sections[:16]
        else:
            if summary:
                sections.append(("summary", summary.strip()))

            for reason in reasons or []:
                reason = (reason or "").strip()
                if reason:
                    sections.append(("reason", reason))

            if keywords:
                sections.append(("keywords", "关键词: " + "、".join(keywords)))

            if tech_stack:
                sections.append(("tech_stack", "技术栈: " + "、".join(tech_stack)))

            if use_cases:
                sections.append(("use_cases", "使用场景: " + "、".join(use_cases)))

            if search_text:
                sections.append(("fallback", search_text.strip()))

        chunks: List[Dict] = []
        idx = 0
        for section_name, section_text in sections:
            piece_texts = self._split_text_to_chunks(section_text, max_chars=380, overlap_chars=60)
            for piece in piece_texts:
                if not piece.strip():
                    continue

                chunk_text = (
                    f"项目: {repo_full_name}\n"
                    f"语言: {language or 'unknown'}\n"
                    f"分类: {category or 'unknown'}\n"
                    f"{piece.strip()}"
                )

                chunks.append({
                    "chunk_id": f"{repo_full_name}#{idx:03d}",
                    "repo_full_name": repo_full_name,
                    "chunk_index": idx,
                    "chunk_text": chunk_text,
                    "section": section_name,
                    "path": "README.md" if section_name.startswith("readme:") else "SUMMARY",
                    "heading": section_name.split("readme:", 1)[1] if section_name.startswith("readme:") else section_name,
                    "updated_at": source_updated_at,
                    "summary": summary or "",
                    "reasons": reasons or [],
                    "keywords": keywords or [],
                    "tech_stack": tech_stack or [],
                    "use_cases": use_cases or [],
                    "language": language,
                    "category": category,
                })
                idx += 1

        return chunks

    def _split_text_to_chunks(self, text: str, max_chars: int = 380, overlap_chars: int = 60) -> List[str]:
        """按语义边界优先的轻量切块（句子优先，超长回退按字符切分）。"""
        text = (text or "").strip()
        if not text:
            return []

        sentences = re.split(r"(?<=[。！？!?；;\n])", text)
        sentences = [s.strip() for s in sentences if s and s.strip()]
        if not sentences:
            sentences = [text]

        chunks: List[str] = []
        current = ""

        for sentence in sentences:
            if len(sentence) > max_chars:
                if current:
                    chunks.append(current)
                    current = ""

                start = 0
                while start < len(sentence):
                    end = min(len(sentence), start + max_chars)
                    chunks.append(sentence[start:end])
                    if end >= len(sentence):
                        break
                    start = max(0, end - overlap_chars)
                continue

            if not current:
                current = sentence
                continue

            if len(current) + 1 + len(sentence) <= max_chars:
                current = f"{current} {sentence}"
            else:
                chunks.append(current)
                tail = current[-overlap_chars:] if overlap_chars > 0 and len(current) > overlap_chars else ""
                current = (tail + " " + sentence).strip() if tail else sentence

        if current:
            chunks.append(current)

        return chunks

    async def batch_index_projects(self, projects: List[Dict]) -> Dict[str, bool]:
        """批量索引项目"""
        results = {}
        for project in projects:
            repo_name = project.get("repo_full_name")
            if not repo_name:
                continue

            success = await self.index_project(
                repo_full_name=repo_name,
                summary=project.get("summary", ""),
                reasons=project.get("reasons", []),
                readme_content=project.get("readme_content") or project.get("readme") or "",
                language=project.get("language", ""),
                category=project.get("category", ""),
                source_updated_at=project.get("repo_updated_at") or project.get("source_updated_at"),
                keywords=project.get("keywords", []),
                tech_stack=project.get("tech_stack", []),
                use_cases=project.get("use_cases", []),
            )
            results[repo_name] = success

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"批量索引完成，成功 {success_count}/{len(results)} 个项目")
        return results

    async def search_projects(
        self,
        query: str,
        coarse_top_k: int = 20,
        final_top_k: int = 5,
        filters: Optional[Any] = None,
    ) -> List[Dict]:
        """搜索项目：chunk 召回+重排，最后聚合为 repo 结果。"""
        try:
            self._ensure_index()

            if not self._initialized:
                logger.warning("索引未初始化")
                return []

            coarse_k = max(coarse_top_k, final_top_k * self.coarse_multiplier)
            variants = self.query_rewriter.rewrite(query, max_variants=self.max_variants)
            variant_results = []
            if self.variant_parallel and len(variants) > 1:
                search_tasks = [
                    self.hybrid_engine.search(query=variant.text, top_k=coarse_k)
                    for variant in variants
                ]
                task_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                for variant, coarse_results in zip(variants, task_results):
                    if isinstance(coarse_results, Exception):
                        logger.warning("变体检索失败 query=%s reason=%s", variant.reason, coarse_results)
                        continue
                    filtered_results = self._apply_filters(coarse_results, filters)
                    if filtered_results:
                        variant_results.append((variant, filtered_results))
            else:
                for variant in variants:
                    coarse_results = await self.hybrid_engine.search(query=variant.text, top_k=coarse_k)
                    filtered_results = self._apply_filters(coarse_results, filters)
                    if filtered_results:
                        variant_results.append((variant, filtered_results))

            if not variant_results:
                return []

            fused_results = self._fuse_multi_query_results(
                variant_results=variant_results,
                top_k=max(coarse_top_k * 2, final_top_k * self.fused_multiplier),
            )
            if not fused_results:
                return []

            if self.rerank_enabled and self.reranker:
                rerank_pool = min(
                    len(fused_results),
                    min(max(final_top_k * self.rerank_multiplier, self.rerank_min_pool), self.rerank_top_k_cap),
                )
                candidate_pool = fused_results[:rerank_pool]
                reranked_chunks = await self.reranker.rerank(
                    query=query,
                    results=candidate_pool,
                    top_k=rerank_pool,
                )
            else:
                logger.info("Rerank 已关闭，直接使用融合结果")
                coarse_pick = max(final_top_k * 2, self.rerank_min_pool)
                reranked_chunks = fused_results[: min(len(fused_results), coarse_pick)]

            repo_results = self._aggregate_chunks_to_repos(
                chunk_results=reranked_chunks,
                top_k=final_top_k,
            )

            for result in repo_results:
                result.pop("embedding", None)
                result.pop("vector_score", None)
                result.pop("bm25_score", None)
                result["match_reasons"] = self._build_match_reasons(
                    query=query,
                    result=result,
                    filters=filters,
                )

            return repo_results

        except Exception as e:
            logger.error(f"搜索项目失败: {str(e)}")
            return []

    def _fuse_multi_query_results(
        self,
        variant_results: List[Tuple[QueryVariant, List[Dict]]],
        top_k: int,
    ) -> List[Dict]:
        """Fuse multi-query retrieval results via weighted RRF."""
        if not variant_results:
            return []

        fused_scores: Dict[str, float] = {}
        best_docs: Dict[str, Dict] = {}
        k = max(1, int(getattr(self.hybrid_engine, "rrf_k", 60)))

        for variant, docs in variant_results:
            weight = max(0.05, float(variant.weight))
            for rank, doc in enumerate(docs, start=1):
                doc_id = doc.get("chunk_id") or doc.get("repo_full_name")
                if not doc_id:
                    continue
                fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + (weight / (k + rank))
                if doc_id not in best_docs:
                    copied = doc.copy()
                    copied["matched_queries"] = [variant.reason]
                    best_docs[doc_id] = copied
                else:
                    matched = best_docs[doc_id].setdefault("matched_queries", [])
                    if variant.reason not in matched:
                        matched.append(variant.reason)

        ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        results: List[Dict] = []
        for doc_id, score in ranked[:top_k]:
            doc = best_docs[doc_id].copy()
            doc["multi_query_rrf_score"] = float(score)
            results.append(doc)
        return results

    def _aggregate_chunks_to_repos(self, chunk_results: List[Dict], top_k: int) -> List[Dict]:
        """把 chunk 结果聚合为 repo，并做去重和多样性控制。"""
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for chunk in chunk_results:
            repo = chunk.get("repo_full_name")
            if not repo:
                continue
            grouped[repo].append(chunk)

        candidates = []
        for repo_name, chunks in grouped.items():
            chunks.sort(key=lambda x: x.get("rerank_score", x.get("rrf_score", 0.0)), reverse=True)

            merged_keywords: List[str] = []
            merged_tech_stack: List[str] = []
            merged_use_cases: List[str] = []
            seen_keywords = set()
            seen_tech_stack = set()
            seen_use_cases = set()

            for chunk in chunks[:8]:
                for item in chunk.get("keywords", []) or []:
                    token = str(item).strip()
                    if token and token not in seen_keywords:
                        seen_keywords.add(token)
                        merged_keywords.append(token)
                for item in chunk.get("tech_stack", []) or []:
                    token = str(item).strip()
                    if token and token not in seen_tech_stack:
                        seen_tech_stack.add(token)
                        merged_tech_stack.append(token)
                for item in chunk.get("use_cases", []) or []:
                    token = str(item).strip()
                    if token and token not in seen_use_cases:
                        seen_use_cases.add(token)
                        merged_use_cases.append(token)

            deduped_chunks = []
            seen_text = set()
            for chunk in chunks:
                text_key = " ".join((chunk.get("chunk_text") or "").lower().split())
                if text_key in seen_text:
                    continue
                seen_text.add(text_key)
                deduped_chunks.append(chunk)
                if len(deduped_chunks) >= 2:
                    break

            if not deduped_chunks:
                continue

            top1 = deduped_chunks[0].get("rerank_score", deduped_chunks[0].get("rrf_score", 0.0))
            top2 = deduped_chunks[1].get("rerank_score", deduped_chunks[1].get("rrf_score", 0.0)) if len(deduped_chunks) > 1 else 0.0
            repo_score = float(top1 * 0.75 + top2 * 0.25)

            primary = deduped_chunks[0]
            reasons = primary.get("reasons", []) or []
            if not reasons and primary.get("chunk_text"):
                reasons = [primary["chunk_text"][:120]]

            candidates.append({
                "repo_full_name": repo_name,
                "summary": primary.get("summary", ""),
                "reasons": reasons[:3],
                "rerank_score": repo_score,
                "similarity": repo_score,
                "category": primary.get("category"),
                "language": primary.get("language"),
                "stars": primary.get("stars"),
                "keywords": merged_keywords[:12],
                "tech_stack": merged_tech_stack[:12],
                "use_cases": merged_use_cases[:12],
                "chunk_id": primary.get("chunk_id"),
                "evidence_chunk": primary.get("chunk_text", ""),
                "evidence_section": primary.get("section"),
                "path": (
                    primary.get("path")
                    or ("README.md" if str(primary.get("section") or "").startswith("readme:") else "SUMMARY")
                ),
                "heading": primary.get("heading") or primary.get("section"),
                "updated_at": primary.get("updated_at"),
            })

        if not candidates:
            return []

        return self._select_with_diversity(candidates, top_k)

    def _select_with_diversity(self, candidates: List[Dict], top_k: int) -> List[Dict]:
        """基于 repo 分数做贪心选择，抑制同类别/同语言过度重复。"""
        remaining = candidates[:]
        selected: List[Dict] = []
        category_count: Dict[str, int] = defaultdict(int)
        language_count: Dict[str, int] = defaultdict(int)

        while remaining and len(selected) < top_k:
            best_idx = 0
            best_score = float("-inf")

            for i, item in enumerate(remaining):
                category = item.get("category") or ""
                language = item.get("language") or ""
                base = item.get("rerank_score", 0.0)
                penalty = 1.0 + 0.18 * category_count[category] + 0.12 * language_count[language]
                score = base / penalty

                if score > best_score:
                    best_score = score
                    best_idx = i

            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            category_count[chosen.get("category") or ""] += 1
            language_count[chosen.get("language") or ""] += 1

        return selected

    def _apply_filters(self, results: List[Dict], filters: Optional[Any]) -> List[Dict]:
        """Apply query filters to coarse retrieval results before rerank."""
        if not filters:
            return results

        language = getattr(filters, "language", None)
        category = getattr(filters, "category", None)
        min_stars = getattr(filters, "min_stars", None)
        keywords = getattr(filters, "keywords", None) or []
        days = getattr(filters, "days", None)

        valid_categories = {
            "ai_ecosystem",
            "infra_and_tools",
            "product_and_ui",
            "knowledge_base",
        }
        if category:
            category_raw = str(category).strip().lower()
            category_compact = category_raw.replace("-", "_").replace(" ", "")
            normalized_category = None
            for cat in valid_categories:
                if cat in category_compact:
                    normalized_category = cat
                    break
            category = normalized_category

        normalized_keywords: List[str] = []
        for kw in keywords:
            text = re.sub(r"\s+", " ", str(kw).strip()).lower()
            if text:
                normalized_keywords.append(text)
        keywords = normalized_keywords

        filtered = []
        cutoff_date = None
        if days and days > 0:
            cutoff_date = date.today() - timedelta(days=days)

        for item in results:
            item_language = (item.get("language") or "").lower()
            item_category = item.get("category")
            item_stars = item.get("stars", 0) or 0
            summary = (item.get("summary") or "").lower()
            reason_text = " ".join(item.get("reasons", [])).lower()
            chunk_text = (item.get("chunk_text") or "").lower()
            repo_name = (item.get("repo_full_name") or "").lower()

            if language:
                lang = str(language).lower()
                if lang != item_language and lang not in item_language:
                    continue

            if category and item_category != category:
                continue

            if min_stars is not None and item_stars < min_stars:
                continue

            if keywords:
                keyword_hit = False
                for kw in keywords:
                    k = str(kw).lower().strip()
                    if not k:
                        continue
                    if k in summary or k in reason_text or k in repo_name or k in chunk_text:
                        keyword_hit = True
                        break
                if not keyword_hit:
                    continue

            if cutoff_date:
                record_date_str = item.get("record_date")
                if record_date_str:
                    try:
                        from datetime import datetime as dt

                        if isinstance(record_date_str, str):
                            record_date = dt.strptime(record_date_str, "%Y-%m-%d").date()
                        elif isinstance(record_date_str, date):
                            record_date = record_date_str
                        else:
                            record_date = None

                        if record_date and record_date < cutoff_date:
                            continue
                    except (ValueError, TypeError):
                        pass

            filtered.append(item)

        return filtered

    def _build_match_reasons(self, query: str, result: Dict, filters: Optional[Any]) -> List[str]:
        """Assemble deterministic match reasons from retrieval features and parsed filters."""
        reasons: List[str] = []
        repo_name = str(result.get("repo_full_name") or "").strip()
        language = str(result.get("language") or "").strip()
        category = str(result.get("category") or "").strip()
        stars = int(result.get("stars") or 0)
        score = float(result.get("rerank_score") or result.get("similarity") or 0.0)

        if score:
            reasons.append(f"语义相关度较高（score={score:.3f}）")
        if language:
            reasons.append(f"语言特征：{language}")
        if category:
            reasons.append(f"类别特征：{category}")

        if filters:
            f_lang = str(getattr(filters, "language", "") or "").strip().lower()
            f_category = str(getattr(filters, "category", "") or "").strip()
            f_stars = getattr(filters, "min_stars", None)
            f_keywords = [str(x).strip().lower() for x in (getattr(filters, "keywords", None) or []) if str(x).strip()]

            if f_lang and language.lower() == f_lang:
                reasons.append(f"命中语言过滤：{language}")
            if f_category and category == f_category:
                reasons.append(f"命中类别过滤：{category}")
            if isinstance(f_stars, int) and f_stars > 0 and stars >= f_stars:
                reasons.append(f"满足热度门槛：{stars} >= {f_stars}")

            if f_keywords:
                summary = str(result.get("summary") or "").lower()
                reason_text = " ".join([str(x) for x in (result.get("reasons") or [])]).lower()
                keywords_text = " ".join([str(x) for x in (result.get("keywords") or [])]).lower()
                tech_text = " ".join([str(x) for x in (result.get("tech_stack") or [])]).lower()
                use_cases_text = " ".join([str(x) for x in (result.get("use_cases") or [])]).lower()
                search_blob = " ".join([repo_name.lower(), summary, reason_text, keywords_text, tech_text, use_cases_text])
                hit_keywords = [kw for kw in f_keywords if kw and kw in search_blob][:3]
                if hit_keywords:
                    reasons.append("命中关键词：" + "、".join(hit_keywords))

        source_reasons = [str(x).strip() for x in (result.get("reasons") or []) if str(x).strip()]
        for src in source_reasons[:2]:
            reasons.append(f"检索证据：{src}")

        deduped: List[str] = []
        seen = set()
        for item in reasons:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= 6:
                break
        return deduped

    async def reindex_all_projects(self) -> Dict[str, int]:
        """重新索引所有项目"""
        try:
            today = date.today()
            records = self.cache.get_trending_history(
                start_date=today - timedelta(days=30),
                end_date=today,
            )

            stats = {
                "total": len(records),
                "success": 0,
                "failed": 0,
                "skipped": 0,
            }

            seen_repos = set()
            for record in records:
                repo_name = record["repo_full_name"]
                if repo_name in seen_repos:
                    stats["skipped"] += 1
                    continue

                seen_repos.add(repo_name)

                analysis = self.cache.get(repo_name)
                if not analysis:
                    stats["skipped"] += 1
                    continue

                auto_tags = extract_structured_tags(
                    summary=analysis.get("summary", ""),
                    reasons=analysis.get("reasons", []),
                    readme_content=analysis.get("readme_content", ""),
                    repo_data={"language": record.get("language", ""), "topics": []},
                    scout_data={},
                )
                keywords = analysis.get("keywords", []) or auto_tags.get("keywords", [])
                tech_stack = analysis.get("tech_stack", []) or auto_tags.get("tech_stack", [])
                use_cases = analysis.get("use_cases", []) or auto_tags.get("use_cases", [])

                success = await self.index_project(
                    repo_full_name=repo_name,
                    summary=analysis.get("summary", ""),
                    reasons=analysis.get("reasons", []),
                    readme_content=analysis.get("readme_content", ""),
                    language=record.get("language", ""),
                    category=record.get("category", ""),
                    source_updated_at=record.get("repo_updated_at"),
                    keywords=keywords,
                    tech_stack=tech_stack,
                    use_cases=use_cases,
                )

                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

            logger.info(f"重新索引完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"重新索引失败: {str(e)}")
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    def get_search_stats(self) -> Dict:
        """获取搜索统计信息"""
        try:
            all_chunks = self.cache.get_all_chunks()
            repo_set = {doc.get("repo_full_name") for doc in all_chunks if doc.get("repo_full_name")}

            return {
                "indexed_projects": len(repo_set),
                "indexed_chunks": len(all_chunks),
                "chroma_count": self.chroma_store.count(),
                "categories": list(set(doc.get("category") for doc in all_chunks if doc.get("category"))),
                "languages": list(set(doc.get("language") for doc in all_chunks if doc.get("language"))),
            }

        except Exception as e:
            logger.error(f"获取搜索统计失败: {str(e)}")
            return {
                "indexed_projects": 0,
                "indexed_chunks": 0,
                "chroma_count": 0,
                "categories": [],
                "languages": [],
            }
