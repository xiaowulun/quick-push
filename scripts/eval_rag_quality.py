import argparse
import asyncio
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.infrastructure.cache import AnalysisCache
from app.knowledge.chat import RAGChatService
from app.knowledge.search import SearchService


@dataclass
class EvalItem:
    query: str
    gold_chunk_ids: List[str] = field(default_factory=list)
    gold_repo_names: List[str] = field(default_factory=list)
    expected_keywords: List[str] = field(default_factory=list)


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


def _extract_chunk_ids(results: Sequence[Dict]) -> List[str]:
    out = []
    for r in results:
        cid = r.get("chunk_id")
        if cid:
            out.append(str(cid))
    return out


def _extract_repo_names(results: Sequence[Dict]) -> List[str]:
    out = []
    for r in results:
        name = r.get("repo_full_name")
        if name:
            out.append(str(name))
    return out


def _recall_at_k(item: EvalItem, pred_chunk_ids: List[str], pred_repo_names: List[str], k: int) -> Optional[float]:
    if item.gold_chunk_ids:
        gold = {x for x in item.gold_chunk_ids if x}
        pred = set(pred_chunk_ids[:k])
        return _safe_div(len(gold & pred), len(gold)) if gold else None

    if item.gold_repo_names:
        gold = {x for x in item.gold_repo_names if x}
        pred = set(pred_repo_names[:k])
        return _safe_div(len(gold & pred), len(gold)) if gold else None

    return None


def _hit_at_1(item: EvalItem, pred_chunk_ids: List[str], pred_repo_names: List[str]) -> Optional[bool]:
    if item.gold_chunk_ids:
        top1 = pred_chunk_ids[0] if pred_chunk_ids else ""
        return top1 in set(item.gold_chunk_ids)
    if item.gold_repo_names:
        top1 = pred_repo_names[0] if pred_repo_names else ""
        return top1 in set(item.gold_repo_names)
    return None


def _collect_citations(answer: str) -> List[str]:
    return sorted(set(re.findall(r"\[S(\d+)\]", answer or "")), key=lambda x: int(x))


def _keyword_off_topic(answer: str, expected_keywords: List[str]) -> Optional[bool]:
    keys = [k.strip().lower() for k in (expected_keywords or []) if k and k.strip()]
    if not keys:
        return None
    ans = (answer or "").lower()
    return not any(k in ans for k in keys)


def _pick_tokens(text: str, limit: int = 4) -> List[str]:
    text = _norm_text(text).lower()
    if not text:
        return []

    stop = {
        "repo", "project", "readme", "summary", "language", "unknown", "the", "and",
        "for", "with", "from", "that", "this", "are", "was", "were", "use", "using",
    }
    tokens = re.findall(r"[a-z][a-z0-9_-]{2,}", text)
    out: List[str] = []
    seen = set()
    for t in tokens:
        if t in stop or t in seen:
            continue
        out.append(t)
        seen.add(t)
        if len(out) >= limit:
            break
    return out


def auto_build_eval_set(path: Path, size: int = 80) -> int:
    cache = AnalysisCache()
    chunks = cache.get_all_chunks()
    if not chunks:
        raise RuntimeError("analysis_chunks 为空，无法自动构建评测集。请先完成索引。")

    items: List[EvalItem] = []
    for c in chunks:
        chunk_id = str(c.get("chunk_id") or "").strip()
        repo = str(c.get("repo_full_name") or "").strip()
        heading = str(c.get("heading") or c.get("section") or "").strip()
        body = str(c.get("chunk_text") or "").strip()
        if not chunk_id or not repo or len(body) < 30:
            continue

        tokens = _pick_tokens(f"{heading} {body}", limit=4)
        query_parts = [heading] if heading else []
        query_parts.extend(tokens[:3])
        query = _norm_text(" ".join(query_parts))
        if len(query) < 6:
            query = _norm_text(body[:60])
        if len(query) < 4:
            continue

        items.append(
            EvalItem(
                query=query,
                gold_chunk_ids=[chunk_id],
                gold_repo_names=[repo],
                expected_keywords=tokens[:3],
            )
        )
        if len(items) >= size:
            break

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(
                json.dumps(
                    {
                        "query": it.query,
                        "gold_chunk_ids": it.gold_chunk_ids,
                        "gold_repo_names": it.gold_repo_names,
                        "expected_keywords": it.expected_keywords,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return len(items)


def load_eval_set(path: Path) -> List[EvalItem]:
    if not path.exists():
        raise FileNotFoundError(f"评测集不存在: {path}")

    items: List[EvalItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            query = _norm_text(str(raw.get("query") or ""))
            if not query:
                raise ValueError(f"{path}:{line_no} 缺少 query")
            items.append(
                EvalItem(
                    query=query,
                    gold_chunk_ids=[str(x) for x in (raw.get("gold_chunk_ids") or []) if str(x).strip()],
                    gold_repo_names=[str(x) for x in (raw.get("gold_repo_names") or []) if str(x).strip()],
                    expected_keywords=[str(x) for x in (raw.get("expected_keywords") or []) if str(x).strip()],
                )
            )
    if not items:
        raise ValueError("评测集为空")
    return items


async def _baseline_chunks(search_service: SearchService, query: str, top_k: int, mode: str) -> List[Dict]:
    if mode == "vector":
        return await search_service.hybrid_engine._vector_search(query, top_k=top_k)  # pylint: disable=protected-access
    if mode == "hybrid":
        return await search_service.hybrid_engine.search(query=query, top_k=top_k)
    raise ValueError(f"未知 baseline 模式: {mode}")


async def _candidate_chunks(search_service: SearchService, query: str, top_k: int) -> List[Dict]:
    coarse_k = max(top_k * 6, 30)
    variants = search_service.query_rewriter.rewrite(query, max_variants=3)
    variant_results: List[Tuple] = []
    for variant in variants:
        coarse = await search_service.hybrid_engine.search(query=variant.text, top_k=coarse_k)
        if coarse:
            variant_results.append((variant, coarse))

    if not variant_results:
        return []

    fused = search_service._fuse_multi_query_results(  # pylint: disable=protected-access
        variant_results=variant_results,
        top_k=max(top_k * 8, 40),
    )
    if not fused:
        return []

    rerank_k = min(len(fused), max(top_k, 30))
    reranked = await search_service.reranker.rerank(query=query, results=fused, top_k=rerank_k)
    return reranked[:top_k]


async def _collect_stream_text(async_gen) -> str:
    out = []
    async for chunk in async_gen:
        if chunk.get("type") == "content":
            out.append(chunk.get("content", ""))
    return "".join(out)


async def run_eval(
    items: List[EvalItem],
    top_k: int,
    baseline_mode: str,
    check_answers: bool,
    max_answer_queries: int,
) -> Dict:
    search_service = SearchService()
    search_service._ensure_index()  # pylint: disable=protected-access

    recalls_baseline: List[float] = []
    recalls_candidate: List[float] = []
    hit1_baseline: List[bool] = []
    hit1_candidate: List[bool] = []

    trace_total = 0
    trace_good = 0

    for item in items:
        b_chunks = await _baseline_chunks(search_service, item.query, top_k=top_k, mode=baseline_mode)
        c_chunks = await _candidate_chunks(search_service, item.query, top_k=top_k)

        b_chunk_ids = _extract_chunk_ids(b_chunks)
        b_repo_names = _extract_repo_names(b_chunks)
        c_chunk_ids = _extract_chunk_ids(c_chunks)
        c_repo_names = _extract_repo_names(c_chunks)

        rb = _recall_at_k(item, b_chunk_ids, b_repo_names, top_k)
        rc = _recall_at_k(item, c_chunk_ids, c_repo_names, top_k)
        if rb is not None:
            recalls_baseline.append(rb)
        if rc is not None:
            recalls_candidate.append(rc)

        hb = _hit_at_1(item, b_chunk_ids, b_repo_names)
        hc = _hit_at_1(item, c_chunk_ids, c_repo_names)
        if hb is not None:
            hit1_baseline.append(bool(hb))
        if hc is not None:
            hit1_candidate.append(bool(hc))

        repo_results = await search_service.search_projects(
            query=item.query,
            coarse_top_k=max(20, top_k * 2),
            final_top_k=5,
        )
        for r in repo_results:
            trace_total += 1
            if r.get("repo_full_name") and r.get("path") and r.get("heading") and r.get("evidence_chunk"):
                trace_good += 1

    result: Dict[str, Dict] = {
        "retrieval": {
            "eval_queries": len(items),
            "baseline_mode": baseline_mode,
            "recall_at_k_baseline": round(mean(recalls_baseline), 6) if recalls_baseline else None,
            "recall_at_k_candidate": round(mean(recalls_candidate), 6) if recalls_candidate else None,
            "recall_delta": (
                round(mean(recalls_candidate) - mean(recalls_baseline), 6)
                if recalls_candidate and recalls_baseline
                else None
            ),
        },
        "traceability": {
            "result_level_traceable_rate": round(_safe_div(trace_good, trace_total), 6) if trace_total else None,
            "traceable_results": trace_good,
            "total_results": trace_total,
        },
        "off_topic_proxy": {
            "definition": "proxy=1-hit@1（Top1未命中标注视为潜在答非所问）",
            "baseline": round(1.0 - _safe_div(sum(hit1_baseline), len(hit1_baseline)), 6) if hit1_baseline else None,
            "candidate": round(1.0 - _safe_div(sum(hit1_candidate), len(hit1_candidate)), 6) if hit1_candidate else None,
            "delta": (
                round(
                    (1.0 - _safe_div(sum(hit1_candidate), len(hit1_candidate)))
                    - (1.0 - _safe_div(sum(hit1_baseline), len(hit1_baseline))),
                    6,
                )
                if hit1_baseline and hit1_candidate
                else None
            ),
        },
    }

    if not check_answers:
        return result

    chat_service = RAGChatService()
    limit = min(max_answer_queries, len(items))

    citation_presence = 0
    citation_valid = 0
    citation_total = 0

    off_topic_baseline: List[bool] = []
    off_topic_candidate: List[bool] = []

    for item in items[:limit]:
        projects = await chat_service.retrieve_projects(item.query, top_k=5, filters=None)
        chat_result = await chat_service.chat(item.query, top_k=5)
        answer = chat_result.get("answer", "")

        cites = _collect_citations(answer)
        if cites:
            citation_presence += 1

        for c in cites:
            citation_total += 1
            idx = int(c) - 1
            if 0 <= idx < len(projects):
                p = projects[idx]
                if p.evidence_path and p.evidence_heading and p.evidence_chunk:
                    citation_valid += 1

        base_answer = await _collect_stream_text(chat_service._chat_without_retrieval(item.query))  # pylint: disable=protected-access
        cand_off = _keyword_off_topic(answer, item.expected_keywords)
        base_off = _keyword_off_topic(base_answer, item.expected_keywords)
        if cand_off is not None:
            off_topic_candidate.append(cand_off)
        if base_off is not None:
            off_topic_baseline.append(base_off)

    answer_eval = {
        "sampled_queries": limit,
        "citation_presence_rate": round(_safe_div(citation_presence, limit), 6) if limit else None,
        "citation_valid_rate": round(_safe_div(citation_valid, citation_total), 6) if citation_total else None,
        "citation_total": citation_total,
    }
    if off_topic_baseline and off_topic_candidate:
        b = _safe_div(sum(1 for x in off_topic_baseline if x), len(off_topic_baseline))
        c = _safe_div(sum(1 for x in off_topic_candidate if x), len(off_topic_candidate))
        answer_eval["keyword_off_topic_baseline"] = round(b, 6)
        answer_eval["keyword_off_topic_candidate"] = round(c, 6)
        answer_eval["keyword_off_topic_delta"] = round(c - b, 6)

    result["answer_checks"] = answer_eval
    return result


def print_summary(report: Dict, k: int) -> None:
    retrieval = report.get("retrieval", {})
    traceability = report.get("traceability", {})
    off_topic = report.get("off_topic_proxy", {})

    print("\n=== RAG 质量评测 ===")
    print(f"评测查询数: {retrieval.get('eval_queries')}")
    print(f"Recall@{k} baseline: {retrieval.get('recall_at_k_baseline')}")
    print(f"Recall@{k} candidate: {retrieval.get('recall_at_k_candidate')}")
    print(f"Recall@{k} delta: {retrieval.get('recall_delta')}")
    print(f"证据块可追溯率(result-level): {traceability.get('result_level_traceable_rate')}")
    print(f"答非所问代理占比 baseline: {off_topic.get('baseline')}")
    print(f"答非所问代理占比 candidate: {off_topic.get('candidate')}")
    print(f"答非所问代理占比 delta: {off_topic.get('delta')}")

    ans = report.get("answer_checks")
    if ans:
        print("\n--- 回答检查(可选) ---")
        print(f"采样查询数: {ans.get('sampled_queries')}")
        print(f"回答引用存在率: {ans.get('citation_presence_rate')}")
        print(f"回答引用有效率: {ans.get('citation_valid_rate')}")
        if "keyword_off_topic_baseline" in ans:
            print(f"关键词答非所问 baseline: {ans.get('keyword_off_topic_baseline')}")
            print(f"关键词答非所问 candidate: {ans.get('keyword_off_topic_candidate')}")
            print(f"关键词答非所问 delta: {ans.get('keyword_off_topic_delta')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG quality: Recall@K, traceability, off-topic proxy.")
    parser.add_argument("--eval-set", type=Path, default=Path("data/eval/auto_eval_set.jsonl"))
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--baseline", choices=["vector", "hybrid"], default="vector")
    parser.add_argument("--auto-generate", type=int, default=80, help="When eval-set missing, auto-build size N.")
    parser.add_argument("--check-answers", action="store_true", help="Call chat model to verify answer citations.")
    parser.add_argument("--max-answer-queries", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("data/eval/eval_report.json"))
    return parser.parse_args()


def _validate_report(report: Dict) -> None:
    delta = report.get("retrieval", {}).get("recall_delta")
    if delta is not None and (math.isnan(delta) or math.isinf(delta)):
        raise ValueError("invalid recall delta")


async def _main_async(args: argparse.Namespace) -> int:
    if not args.eval_set.exists():
        count = auto_build_eval_set(args.eval_set, size=args.auto_generate)
        print(f"已自动生成评测集: {args.eval_set} ({count}条)")

    items = load_eval_set(args.eval_set)
    report = await run_eval(
        items=items,
        top_k=args.top_k,
        baseline_mode=args.baseline,
        check_answers=args.check_answers,
        max_answer_queries=args.max_answer_queries,
    )
    _validate_report(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(report, k=args.top_k)
    print(f"\n报告已写入: {args.output}")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
