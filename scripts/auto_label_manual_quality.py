import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        data = json.loads(line)
        if isinstance(data, dict):
            rows.append(data)
    return rows


def _dump_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _repo_tokens(repo_full_name: str) -> List[str]:
    repo = (repo_full_name or "").strip().lower()
    if not repo:
        return []
    out = [repo]
    if "/" in repo:
        out.append(repo.split("/", 1)[1])
    return [x for x in out if x]


def auto_label_row(row: Dict[str, Any]) -> Dict[str, Any]:
    answer = str(row.get("answer") or "").lower()
    gold_repos = [str(x).strip() for x in (row.get("gold_repo_names") or []) if str(x).strip()]
    evidence = row.get("evidence_candidates") or []
    cited = row.get("citations") or []

    gold_tokens: List[str] = []
    for repo in gold_repos:
        gold_tokens.extend(_repo_tokens(repo))

    answer_hit_gold = any(token in answer for token in gold_tokens) if gold_tokens else False
    top_evidence_repo = ""
    if evidence and isinstance(evidence[0], dict):
        top_evidence_repo = str(evidence[0].get("repo_full_name") or "").strip()

    top_is_gold = bool(top_evidence_repo and top_evidence_repo in set(gold_repos))
    off_topic = not (answer_hit_gold or top_is_gold)

    # citation-consistent proxy: citation index can map to evidence candidates.
    citation_consistent = True
    if cited:
        for c in cited:
            try:
                idx = int(c) - 1
            except (TypeError, ValueError):
                citation_consistent = False
                break
            if idx < 0 or idx >= len(evidence):
                citation_consistent = False
                break
    else:
        citation_consistent = False

    grounded = bool(evidence) and citation_consistent

    row["manual_off_topic"] = bool(off_topic)
    row["manual_grounded"] = bool(grounded)
    row["manual_citation_consistent"] = bool(citation_consistent)
    row["manual_best_repo"] = top_evidence_repo or (gold_repos[0] if gold_repos else "")
    row["manual_reason"] = (
        "auto: no gold repo mention and top evidence not gold"
        if off_topic
        else "auto: gold repo/evidence matched"
    )
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-label manual quality sample (initial pass).")
    parser.add_argument("--input", type=Path, required=True, help="Input manual sample JSONL.")
    parser.add_argument("--output", type=Path, required=True, help="Output labeled JSONL.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = _load_jsonl(args.input)
    labeled = [auto_label_row(dict(r)) for r in rows]
    _dump_jsonl(args.output, labeled)
    print(f"labeled rows: {len(labeled)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

