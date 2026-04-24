import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"report not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _get_path(data: Dict[str, Any], path: str) -> Optional[float]:
    cur: Any = data
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    if cur is None:
        return None
    try:
        return float(cur)
    except (TypeError, ValueError):
        return None


def _check_ge(name: str, value: Optional[float], threshold: Optional[float]) -> Tuple[bool, str]:
    if threshold is None:
        return True, f"SKIP {name} (no threshold)"
    if value is None:
        return False, f"FAIL {name}: missing value, require >= {threshold}"
    ok = value >= threshold
    return ok, f"{'PASS' if ok else 'FAIL'} {name}: value={value:.6f}, require >= {threshold:.6f}"


def _check_le(name: str, value: Optional[float], threshold: Optional[float]) -> Tuple[bool, str]:
    if threshold is None:
        return True, f"SKIP {name} (no threshold)"
    if value is None:
        return False, f"FAIL {name}: missing value, require <= {threshold}"
    ok = value <= threshold
    return ok, f"{'PASS' if ok else 'FAIL'} {name}: value={value:.6f}, require <= {threshold:.6f}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check eval regression against a baseline report.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--min-recall-delta", type=float, default=0.0)
    parser.add_argument("--min-hit1-delta", type=float, default=0.0)
    parser.add_argument("--min-recall-candidate", type=float, default=None)
    parser.add_argument("--min-hit1-candidate", type=float, default=None)
    parser.add_argument("--min-rerank-effective-rate", type=float, default=None)
    parser.add_argument("--max-manual-off-topic-rate", type=float, default=None)
    parser.add_argument("--max-manual-off-topic-increase", type=float, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = _load_report(args.baseline)
    candidate = _load_report(args.candidate)

    checks: List[Tuple[bool, str]] = []

    base_recall = _get_path(baseline, "retrieval.recall_at_k_candidate")
    cand_recall = _get_path(candidate, "retrieval.recall_at_k_candidate")
    base_hit1 = _get_path(baseline, "retrieval.hit_at_1_candidate")
    cand_hit1 = _get_path(candidate, "retrieval.hit_at_1_candidate")

    recall_delta = None if (base_recall is None or cand_recall is None) else cand_recall - base_recall
    hit1_delta = None if (base_hit1 is None or cand_hit1 is None) else cand_hit1 - base_hit1

    checks.append(_check_ge("recall_delta_vs_baseline", recall_delta, args.min_recall_delta))
    checks.append(_check_ge("hit1_delta_vs_baseline", hit1_delta, args.min_hit1_delta))
    checks.append(_check_ge("candidate_recall", cand_recall, args.min_recall_candidate))
    checks.append(_check_ge("candidate_hit1", cand_hit1, args.min_hit1_candidate))

    rerank_effective = _get_path(candidate, "retrieval.rerank_effective_rate")
    checks.append(_check_ge("candidate_rerank_effective_rate", rerank_effective, args.min_rerank_effective_rate))

    cand_manual_off_topic = _get_path(candidate, "answer_checks.manual_off_topic_rate")
    checks.append(_check_le("candidate_manual_off_topic_rate", cand_manual_off_topic, args.max_manual_off_topic_rate))

    base_manual_off_topic = _get_path(baseline, "answer_checks.manual_off_topic_rate")
    manual_off_topic_increase = None
    if base_manual_off_topic is not None and cand_manual_off_topic is not None:
        manual_off_topic_increase = cand_manual_off_topic - base_manual_off_topic
    checks.append(_check_le("manual_off_topic_increase_vs_baseline", manual_off_topic_increase, args.max_manual_off_topic_increase))

    failed = False
    print("=== Eval Regression Check ===")
    print(f"baseline: {args.baseline}")
    print(f"candidate: {args.candidate}")
    for ok, message in checks:
        print(message)
        if not ok:
            failed = True

    if failed:
        print("Result: FAIL")
        return 1
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

