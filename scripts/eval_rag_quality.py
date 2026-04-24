import argparse
import asyncio
import json
import math
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence

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
    query_type: str = "general"
    hard_negative_repo_names: List[str] = field(default_factory=list)


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


def _mean_or_none(values: List[float]) -> Optional[float]:
    return round(mean(values), 6) if values else None


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


def _clip_text(text: str, limit: int = 240) -> str:
    norm = _norm_text(text)
    if len(norm) <= limit:
        return norm
    return norm[: max(0, limit - 3)] + "..."


def _coerce_bool(value) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y"}:
        return True
    if raw in {"0", "false", "no", "n"}:
        return False
    return None


def _load_json_or_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    text = None
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            text = path.read_text(encoding=enc).strip()
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return []
    text = text.lstrip("\ufeff")
    if not text:
        return []

    if text.startswith("["):
        raw = json.loads(text)
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        return []

    rows: List[Dict] = []
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        data = json.loads(line)
        if isinstance(data, dict):
            rows.append(data)
    return rows


def export_manual_off_topic_samples(
    records: List[Dict], sample_size: int, output_path: Path, seed: int
) -> int:
    if sample_size <= 0 or not records:
        return 0

    size = min(sample_size, len(records))
    idxs = list(range(len(records)))
    random.Random(seed).shuffle(idxs)
    picked = [records[i] for i in idxs[:size]]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for i, row in enumerate(picked, start=1):
            row_out = dict(row)
            row_out["sample_id"] = i
            row_out["manual_off_topic"] = None
            row_out["manual_reason"] = ""
            row_out["manual_grounded"] = None
            row_out["manual_citation_consistent"] = None
            row_out["manual_best_repo"] = ""
            f.write(json.dumps(row_out, ensure_ascii=False) + "\n")
    return size


def compute_manual_off_topic_rate(labeled_path: Path) -> Dict[str, Optional[float]]:
    rows = _load_json_or_jsonl(labeled_path)
    labeled_total = 0
    off_topic_count = 0
    grounded_labeled = 0
    grounded_count = 0
    citation_labeled = 0
    citation_consistent_count = 0
    for row in rows:
        label = _coerce_bool(row.get("manual_off_topic"))
        if label is None:
            pass
        else:
            labeled_total += 1
            if label:
                off_topic_count += 1

        grounded = _coerce_bool(row.get("manual_grounded"))
        if grounded is not None:
            grounded_labeled += 1
            if grounded:
                grounded_count += 1

        citation = _coerce_bool(row.get("manual_citation_consistent"))
        if citation is not None:
            citation_labeled += 1
            if citation:
                citation_consistent_count += 1
    return {
        "manual_off_topic_labeled": labeled_total,
        "manual_off_topic_count": off_topic_count,
        "manual_off_topic_rate": round(_safe_div(off_topic_count, labeled_total), 6) if labeled_total else None,
        "manual_grounded_labeled": grounded_labeled,
        "manual_grounded_rate": round(_safe_div(grounded_count, grounded_labeled), 6) if grounded_labeled else None,
        "manual_citation_labeled": citation_labeled,
        "manual_citation_consistent_rate": (
            round(_safe_div(citation_consistent_count, citation_labeled), 6) if citation_labeled else None
        ),
    }


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
        raise RuntimeError("analysis_chunks is empty, cannot auto-build eval set. Please build index first.")

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
                query_type="auto",
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
                        "query_type": it.query_type,
                        "hard_negative_repo_names": it.hard_negative_repo_names,
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
    text = None
    last_err: Optional[Exception] = None
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError as e:
            last_err = e
            continue
    if text is None:
        raise ValueError(f"Failed to decode evaluation set file: {path} ({last_err})")

    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip().lstrip("\ufeff")
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
                query_type=_norm_text(str(raw.get("query_type") or "general")).lower() or "general",
                hard_negative_repo_names=[
                    str(x) for x in (raw.get("hard_negative_repo_names") or []) if str(x).strip()
                ],
            )
        )

    if not items:
        raise ValueError("evaluation set is empty")
    return items


async def _baseline_chunks(search_service: SearchService, query: str, top_k: int, mode: str) -> List[Dict]:
    if mode == "vector":
        return await search_service.hybrid_engine.vector_search(query, top_k=top_k)
    if mode == "hybrid":
        return await search_service.hybrid_engine.search(query=query, top_k=top_k)
    raise ValueError(f"unknown baseline mode: {mode}")


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
    disable_rerank: bool,
    manual_off_topic_sample: int,
    manual_off_topic_output: Path,
    manual_off_topic_seed: int,
    manual_off_topic_labeled: Optional[Path],
) -> Dict:
    search_service = SearchService()
    if disable_rerank:
        # Keep evaluation mode consistent: both candidate pipeline and search_projects skip rerank.
        search_service.rerank_enabled = False
        search_service.reranker = None

    recalls_baseline: List[float] = []
    recalls_candidate: List[float] = []
    hit1_baseline: List[bool] = []
    hit1_candidate: List[bool] = []
    by_type: Dict[str, Dict[str, List[Any]]] = {}
    hard_negative_baseline_top1_hits: List[bool] = []
    hard_negative_candidate_top1_hits: List[bool] = []
    rerank_reason_counts: Dict[str, int] = {}
    rerank_total_calls = 0
    rerank_effective_calls = 0

    trace_total = 0
    trace_good = 0
    trace_with_chunk_id = 0
    trace_with_path_heading = 0

    for item in items:
        query_type = item.query_type or "general"
        if query_type not in by_type:
            by_type[query_type] = {
                "recall_baseline": [],
                "recall_candidate": [],
                "hit1_baseline": [],
                "hit1_candidate": [],
            }

        b_chunks = await _baseline_chunks(search_service, item.query, top_k=top_k, mode=baseline_mode)
        c_chunks = await search_service.search_projects(
            query=item.query,
            coarse_top_k=max(20, top_k * 2),
            final_top_k=top_k,
        )
        if not disable_rerank and search_service.reranker:
            rerank_total_calls += 1
            rerank_reason = str(getattr(search_service.reranker, "last_run_reason", "unknown"))
            rerank_reason_counts[rerank_reason] = rerank_reason_counts.get(rerank_reason, 0) + 1
            if bool(getattr(search_service.reranker, "last_run_used_cross_encoder", False)):
                rerank_effective_calls += 1

        b_chunk_ids = _extract_chunk_ids(b_chunks)
        b_repo_names = _extract_repo_names(b_chunks)
        c_chunk_ids = _extract_chunk_ids(c_chunks)
        c_repo_names = _extract_repo_names(c_chunks)

        rb = _recall_at_k(item, b_chunk_ids, b_repo_names, top_k)
        rc = _recall_at_k(item, c_chunk_ids, c_repo_names, top_k)
        if rb is not None:
            recalls_baseline.append(rb)
            by_type[query_type]["recall_baseline"].append(rb)
        if rc is not None:
            recalls_candidate.append(rc)
            by_type[query_type]["recall_candidate"].append(rc)

        hb = _hit_at_1(item, b_chunk_ids, b_repo_names)
        hc = _hit_at_1(item, c_chunk_ids, c_repo_names)
        if hb is not None:
            hit1_baseline.append(bool(hb))
            by_type[query_type]["hit1_baseline"].append(bool(hb))
        if hc is not None:
            hit1_candidate.append(bool(hc))
            by_type[query_type]["hit1_candidate"].append(bool(hc))

        if item.hard_negative_repo_names:
            hn_set = set(item.hard_negative_repo_names)
            baseline_top1_repo = b_repo_names[0] if b_repo_names else ""
            candidate_top1_repo = c_repo_names[0] if c_repo_names else ""
            hard_negative_baseline_top1_hits.append(baseline_top1_repo in hn_set)
            hard_negative_candidate_top1_hits.append(candidate_top1_repo in hn_set)

        for r in c_chunks[:5]:
            trace_total += 1
            has_core = bool(r.get("repo_full_name")) and bool(r.get("evidence_chunk"))
            has_chunk_id = bool(r.get("chunk_id"))
            has_path_heading = bool(r.get("path")) and bool(r.get("heading"))
            if has_core and has_chunk_id:
                trace_with_chunk_id += 1
            if has_core and has_path_heading:
                trace_with_path_heading += 1
            if has_core and (has_chunk_id or has_path_heading):
                trace_good += 1

    hit1_baseline_rate = _safe_div(sum(hit1_baseline), len(hit1_baseline)) if hit1_baseline else None
    hit1_candidate_rate = _safe_div(sum(hit1_candidate), len(hit1_candidate)) if hit1_candidate else None
    by_type_report: Dict[str, Dict[str, Optional[float]]] = {}
    for qtype, payload in by_type.items():
        type_hit1_baseline = (
            _safe_div(sum(payload["hit1_baseline"]), len(payload["hit1_baseline"]))
            if payload["hit1_baseline"]
            else None
        )
        type_hit1_candidate = (
            _safe_div(sum(payload["hit1_candidate"]), len(payload["hit1_candidate"]))
            if payload["hit1_candidate"]
            else None
        )
        by_type_report[qtype] = {
            "count": len(payload["hit1_candidate"]) or len(payload["hit1_baseline"]) or len(payload["recall_candidate"]) or len(payload["recall_baseline"]),
            "recall_at_k_baseline": _mean_or_none(payload["recall_baseline"]),
            "recall_at_k_candidate": _mean_or_none(payload["recall_candidate"]),
            "recall_delta": (
                round(mean(payload["recall_candidate"]) - mean(payload["recall_baseline"]), 6)
                if payload["recall_candidate"] and payload["recall_baseline"]
                else None
            ),
            "hit_at_1_baseline": round(type_hit1_baseline, 6) if type_hit1_baseline is not None else None,
            "hit_at_1_candidate": round(type_hit1_candidate, 6) if type_hit1_candidate is not None else None,
            "hit_at_1_delta": (
                round(type_hit1_candidate - type_hit1_baseline, 6)
                if type_hit1_candidate is not None and type_hit1_baseline is not None
                else None
            ),
        }

    result: Dict[str, Dict] = {
        "retrieval": {
            "eval_queries": len(items),
            "baseline_mode": baseline_mode,
            "candidate_rerank_enabled": not disable_rerank,
            "recall_at_k_baseline": _mean_or_none(recalls_baseline),
            "recall_at_k_candidate": _mean_or_none(recalls_candidate),
            "recall_delta": (
                round(mean(recalls_candidate) - mean(recalls_baseline), 6)
                if recalls_candidate and recalls_baseline
                else None
            ),
            "hit_at_1_baseline": round(hit1_baseline_rate, 6) if hit1_baseline_rate is not None else None,
            "hit_at_1_candidate": round(hit1_candidate_rate, 6) if hit1_candidate_rate is not None else None,
            "hit_at_1_delta": (
                round(hit1_candidate_rate - hit1_baseline_rate, 6)
                if hit1_baseline_rate is not None and hit1_candidate_rate is not None
                else None
            ),
            "rerank_total_calls": rerank_total_calls if not disable_rerank else None,
            "rerank_effective_calls": rerank_effective_calls if not disable_rerank else None,
            "rerank_effective_rate": (
                round(_safe_div(rerank_effective_calls, rerank_total_calls), 6)
                if (not disable_rerank and rerank_total_calls > 0)
                else None
            ),
            "rerank_reason_distribution": rerank_reason_counts if not disable_rerank else None,
        },
        "retrieval_by_query_type": by_type_report,
        "hard_negative_confusion": {
            "query_count": len(hard_negative_candidate_top1_hits),
            "top1_confused_as_hard_negative_baseline": (
                round(_safe_div(sum(hard_negative_baseline_top1_hits), len(hard_negative_baseline_top1_hits)), 6)
                if hard_negative_baseline_top1_hits
                else None
            ),
            "top1_confused_as_hard_negative_candidate": (
                round(_safe_div(sum(hard_negative_candidate_top1_hits), len(hard_negative_candidate_top1_hits)), 6)
                if hard_negative_candidate_top1_hits
                else None
            ),
        },
        "traceability": {
            "result_level_traceable_rate": round(_safe_div(trace_good, trace_total), 6) if trace_total else None,
            "traceable_by_chunk_id_rate": round(_safe_div(trace_with_chunk_id, trace_total), 6) if trace_total else None,
            "traceable_by_path_heading_rate": round(_safe_div(trace_with_path_heading, trace_total), 6) if trace_total else None,
            "traceable_results": trace_good,
            "total_results": trace_total,
        },
        "off_topic_proxy": {
            "definition": "proxy = 1 - hit@1 (Top1 miss implies potential off-topic).",
            "baseline": round(1.0 - hit1_baseline_rate, 6) if hit1_baseline_rate is not None else None,
            "candidate": round(1.0 - hit1_candidate_rate, 6) if hit1_candidate_rate is not None else None,
            "delta": (
                round((1.0 - hit1_candidate_rate) - (1.0 - hit1_baseline_rate), 6)
                if hit1_baseline_rate is not None and hit1_candidate_rate is not None
                else None
            ),
        },
    }

    if not check_answers:
        if manual_off_topic_labeled:
            result["answer_checks"] = {
                "manual_off_topic_labeled_file": str(manual_off_topic_labeled),
                **compute_manual_off_topic_rate(manual_off_topic_labeled),
            }
        return result

    chat_service = RAGChatService()
    limit = min(max_answer_queries, len(items))

    citation_presence = 0
    citation_valid = 0
    citation_total = 0

    off_topic_candidate: List[bool] = []
    manual_records: List[Dict] = []

    for item in items[:limit]:
        projects = await chat_service.retrieve_projects(item.query, top_k=5, filters=None)
        answer = await _collect_stream_text(chat_service.chat_stream(item.query, top_k=5))

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

        cand_off = _keyword_off_topic(answer, item.expected_keywords)
        if cand_off is not None:
            off_topic_candidate.append(cand_off)

        evidence = []
        for p in projects[:3]:
            evidence.append(
                {
                    "repo_full_name": getattr(p, "repo_full_name", ""),
                    "evidence_path": getattr(p, "evidence_path", ""),
                    "evidence_heading": getattr(p, "evidence_heading", ""),
                    "evidence_chunk_preview": _clip_text(getattr(p, "evidence_chunk", ""), limit=200),
                }
            )
        manual_records.append(
            {
                "query": item.query,
                "query_type": item.query_type,
                "answer": answer,
                "citations": cites,
                "gold_chunk_ids": item.gold_chunk_ids,
                "gold_repo_names": item.gold_repo_names,
                "expected_keywords": item.expected_keywords,
                "hard_negative_repo_names": item.hard_negative_repo_names,
                "evidence_candidates": evidence,
            }
        )

    answer_eval = {
        "sampled_queries": limit,
        "citation_presence_rate": round(_safe_div(citation_presence, limit), 6) if limit else None,
        "citation_valid_rate": round(_safe_div(citation_valid, citation_total), 6) if citation_total else None,
        "citation_total": citation_total,
    }
    if off_topic_candidate:
        c = _safe_div(sum(1 for x in off_topic_candidate if x), len(off_topic_candidate))
        answer_eval["keyword_off_topic_candidate"] = round(c, 6)

    exported_count = export_manual_off_topic_samples(
        records=manual_records,
        sample_size=manual_off_topic_sample,
        output_path=manual_off_topic_output,
        seed=manual_off_topic_seed,
    )
    if exported_count:
        answer_eval["manual_off_topic_sample_size"] = exported_count
        answer_eval["manual_off_topic_sample_file"] = str(manual_off_topic_output)

    if manual_off_topic_labeled:
        answer_eval["manual_off_topic_labeled_file"] = str(manual_off_topic_labeled)
        answer_eval.update(compute_manual_off_topic_rate(manual_off_topic_labeled))

    result["answer_checks"] = answer_eval
    return result


def print_summary(report: Dict, k: int) -> None:
    retrieval = report.get("retrieval", {})
    traceability = report.get("traceability", {})
    off_topic = report.get("off_topic_proxy", {})

    print("\n=== RAG 质量评测 ===")
    print(f"Eval queries: {retrieval.get('eval_queries')}")
    print(f"Recall@{k} baseline: {retrieval.get('recall_at_k_baseline')}")
    print(f"Recall@{k} candidate: {retrieval.get('recall_at_k_candidate')}")
    print(f"Recall@{k} delta: {retrieval.get('recall_delta')}")
    print(f"Hit@1 baseline: {retrieval.get('hit_at_1_baseline')}")
    print(f"Hit@1 candidate: {retrieval.get('hit_at_1_candidate')}")
    print(f"Hit@1 delta: {retrieval.get('hit_at_1_delta')}")
    if retrieval.get("rerank_effective_rate") is not None:
        print(f"Rerank effective rate: {retrieval.get('rerank_effective_rate')} ({retrieval.get('rerank_effective_calls')}/{retrieval.get('rerank_total_calls')})")
    print(f"证据可追溯率(result-level): {traceability.get('result_level_traceable_rate')}")
    print(f"Off-topic proxy baseline: {off_topic.get('baseline')}")
    print(f"Off-topic proxy candidate: {off_topic.get('candidate')}")
    print(f"Off-topic proxy delta: {off_topic.get('delta')}")

    hard_negative = report.get("hard_negative_confusion", {})
    if hard_negative:
        print(
            "Hard-negative top1 confusion baseline/candidate: "
            f"{hard_negative.get('top1_confused_as_hard_negative_baseline')} / "
            f"{hard_negative.get('top1_confused_as_hard_negative_candidate')}"
        )

    by_type = report.get("retrieval_by_query_type", {})
    if by_type:
        print("\n--- By Query Type ---")
        for qtype, stats in sorted(by_type.items()):
            print(
                f"{qtype}: count={stats.get('count')} "
                f"recall={stats.get('recall_at_k_candidate')} "
                f"hit@1={stats.get('hit_at_1_candidate')}"
            )
    if retrieval.get("rerank_reason_distribution"):
        print(f"Rerank reason distribution: {retrieval.get('rerank_reason_distribution')}")

    ans = report.get("answer_checks")
    if ans:
        print("\n--- 回答检查（可选）---")
        def _print_if_present(label: str, key: str) -> None:
            if key in ans:
                print(f"{label}: {ans.get(key)}")

        _print_if_present("Sampled queries", "sampled_queries")
        _print_if_present("Citation presence rate", "citation_presence_rate")
        _print_if_present("Citation valid rate", "citation_valid_rate")
        _print_if_present("Keyword off-topic rate baseline", "keyword_off_topic_baseline")
        _print_if_present("Keyword off-topic rate candidate", "keyword_off_topic_candidate")
        _print_if_present("Keyword off-topic rate delta", "keyword_off_topic_delta")
        _print_if_present("人工抽样文件", "manual_off_topic_sample_file")
        _print_if_present("人工抽样答非所问率", "manual_off_topic_rate")
        _print_if_present("人工抽样已标注数", "manual_off_topic_labeled")
        _print_if_present("Manual grounded rate", "manual_grounded_rate")
        _print_if_present("人工 grounded 已标注数", "manual_grounded_labeled")
        _print_if_present("人工引用一致率", "manual_citation_consistent_rate")
        _print_if_present("Manual citation labeled", "manual_citation_labeled")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG quality: Recall@K, traceability, off-topic proxy.")
    parser.add_argument("--eval-set", type=Path, default=Path("data/eval/auto_eval_set.jsonl"))
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--baseline", choices=["vector", "hybrid"], default="vector")
    parser.add_argument(
        "--max-eval-queries",
        type=int,
        default=None,
        help="Optionally cap evaluation queries for faster iteration (e.g. 60).",
    )
    parser.add_argument("--auto-generate", type=int, default=200, help="When eval-set missing, auto-build size N.")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate eval-set even if it already exists.")
    parser.add_argument("--disable-rerank", action="store_true", help="Disable Cross-Encoder rerank in candidate pipeline.")
    parser.add_argument("--check-answers", action="store_true", help="Call chat model to verify answer citations.")
    parser.add_argument("--max-answer-queries", type=int, default=200)
    parser.add_argument(
        "--manual-off-topic-sample",
        type=int,
        default=50,
        help="Export N candidate answers for human off-topic annotation (non-proxy).",
    )
    parser.add_argument(
        "--manual-off-topic-output",
        type=Path,
        default=Path("data/eval/manual_off_topic_sample.jsonl"),
        help="JSONL output for manual off-topic labeling.",
    )
    parser.add_argument(
        "--manual-off-topic-seed",
        type=int,
        default=42,
        help="Random seed when sampling manual annotation records.",
    )
    parser.add_argument(
        "--manual-off-topic-labeled",
        type=Path,
        default=None,
        help="Read labeled JSON/JSONL and report manual off-topic rate. Label field: manual_off_topic=true/false.",
    )
    parser.add_argument(
        "--manual-off-topic-only",
        action="store_true",
        help="Only compute manual off-topic rate from labeled file, skip retrieval/chat evaluation.",
    )
    parser.add_argument("--output", type=Path, default=Path("data/eval/eval_report.json"))
    return parser.parse_args()


def _validate_report(report: Dict) -> None:
    delta = report.get("retrieval", {}).get("recall_delta")
    if delta is not None and (math.isnan(delta) or math.isinf(delta)):
        raise ValueError("invalid recall delta")


async def _main_async(args: argparse.Namespace) -> int:
    if args.manual_off_topic_only:
        if not args.manual_off_topic_labeled:
            raise ValueError("--manual-off-topic-only requires --manual-off-topic-labeled")
        report = {
            "answer_checks": {
                "manual_off_topic_labeled_file": str(args.manual_off_topic_labeled),
                **compute_manual_off_topic_rate(args.manual_off_topic_labeled),
            }
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"人工抽样答非所问率: {report['answer_checks'].get('manual_off_topic_rate')}")
        print(f"人工抽样已标注数: {report['answer_checks'].get('manual_off_topic_labeled')}")
        print(f"\nReport written to: {args.output}")
        return 0

    if args.regenerate or (not args.eval_set.exists()):
        count = auto_build_eval_set(args.eval_set, size=args.auto_generate)
        print(f"Auto-generated eval set: {args.eval_set} ({count})")

    items = load_eval_set(args.eval_set)
    if args.max_eval_queries is not None and args.max_eval_queries > 0:
        items = items[: args.max_eval_queries]
    report = await run_eval(
        items=items,
        top_k=args.top_k,
        baseline_mode=args.baseline,
        check_answers=args.check_answers,
        max_answer_queries=args.max_answer_queries,
        disable_rerank=args.disable_rerank,
        manual_off_topic_sample=args.manual_off_topic_sample,
        manual_off_topic_output=args.manual_off_topic_output,
        manual_off_topic_seed=args.manual_off_topic_seed,
        manual_off_topic_labeled=args.manual_off_topic_labeled,
    )
    _validate_report(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(report, k=args.top_k)
    print(f"\nReport written to: {args.output}")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())


