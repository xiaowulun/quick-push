import json
import sqlite3
from datetime import date
from typing import Dict, List, Optional

from app.infrastructure.cache_base import SQLiteStore


class HistoryStore(SQLiteStore):
    """trending_history + repo_info + project detail queries."""

    def save_trending_record(
        self,
        record_date: date,
        repo_full_name: str,
        description: str,
        repo_updated_at: Optional[str],
        language: str,
        stars: int,
        stars_today: int,
        rank: int,
        since_type: str,
        category: Optional[str] = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trending_history
                (record_date, repo_full_name, description, repo_updated_at, language, stars, stars_today, rank, since_type, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_date,
                    repo_full_name,
                    description,
                    repo_updated_at,
                    language,
                    stars,
                    stars_today,
                    rank,
                    since_type,
                    category,
                ),
            )

            conn.execute(
                """
                INSERT INTO repo_info (repo_full_name, first_seen, last_seen, total_appearances, category)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(repo_full_name) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    total_appearances = repo_info.total_appearances + 1,
                    category = COALESCE(excluded.category, repo_info.category)
                """,
                (repo_full_name, record_date, record_date, category),
            )

            conn.commit()

    def get_trending_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        repo_name: Optional[str] = None,
        since_type: Optional[str] = None,
    ) -> List[Dict]:
        query = "SELECT * FROM trending_history WHERE 1=1"
        params = []

        if start_date:
            query += " AND record_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND record_date <= ?"
            params.append(end_date)
        if repo_name:
            query += " AND repo_full_name = ?"
            params.append(repo_name)
        if since_type:
            query += " AND since_type = ?"
            params.append(since_type)

        query += " ORDER BY record_date DESC, rank ASC"

        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_record_date(self, since_type: Optional[str] = None) -> Optional[date]:
        query = "SELECT MAX(record_date) AS latest_date FROM trending_history"
        params: List[str] = []
        if since_type:
            query += " WHERE since_type = ?"
            params.append(since_type)

        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(query, params).fetchone()
            if not row:
                return None

            raw = row["latest_date"]
            if not raw:
                return None
            try:
                return date.fromisoformat(str(raw))
            except Exception:
                return None

    def get_project_detail(self, repo_full_name: str, history_limit: int = 12) -> Optional[Dict]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row

            analysis_row = conn.execute(
                """
                SELECT summary, reasons, keywords, tech_stack, use_cases
                FROM analysis_cache
                WHERE repo_full_name = ?
                """,
                (repo_full_name,),
            ).fetchone()

            latest_row = conn.execute(
                """
                SELECT
                    record_date, description, repo_updated_at, language, stars, stars_today, rank, since_type, category
                FROM trending_history
                WHERE repo_full_name = ?
                ORDER BY record_date DESC, rank ASC
                LIMIT 1
                """,
                (repo_full_name,),
            ).fetchone()

            repo_info_row = conn.execute(
                """
                SELECT first_seen, last_seen, total_appearances, category
                FROM repo_info
                WHERE repo_full_name = ?
                """,
                (repo_full_name,),
            ).fetchone()

            if not analysis_row and not latest_row and not repo_info_row:
                return None

            history_rows = conn.execute(
                """
                SELECT record_date, stars, stars_today, rank, since_type, language, category
                FROM trending_history
                WHERE repo_full_name = ?
                ORDER BY record_date DESC, rank ASC
                LIMIT ?
                """,
                (repo_full_name, max(1, int(history_limit))),
            ).fetchall()

            evidence_row = conn.execute(
                """
                SELECT chunk_id, chunk_text, section, path, heading, updated_at
                FROM analysis_chunks
                WHERE repo_full_name = ?
                ORDER BY
                    CASE WHEN section LIKE 'readme:%' THEN 0 ELSE 1 END,
                    chunk_index ASC
                LIMIT 1
                """,
                (repo_full_name,),
            ).fetchone()

            def _json_list(value):
                if not value:
                    return []
                try:
                    data = json.loads(value)
                    return data if isinstance(data, list) else []
                except (TypeError, json.JSONDecodeError):
                    return []

            trend_history: List[Dict] = []
            for row in history_rows:
                trend_history.append(
                    {
                        "record_date": str(row["record_date"]) if row["record_date"] is not None else "",
                        "stars": int(row["stars"] or 0),
                        "stars_today": int(row["stars_today"] or 0),
                        "rank": row["rank"],
                        "since_type": row["since_type"],
                        "language": row["language"],
                        "category": row["category"],
                    }
                )

            best_rank = None
            ranks = [int(item["rank"]) for item in trend_history if item.get("rank") is not None]
            if ranks:
                best_rank = min(ranks)

            if trend_history:
                first_seen = trend_history[-1]["record_date"]
                last_seen = trend_history[0]["record_date"]
                latest_stars = trend_history[0]["stars"]
                avg_stars_today = round(
                    sum(item.get("stars_today", 0) for item in trend_history) / len(trend_history), 2
                )
            else:
                first_seen = str(repo_info_row["first_seen"]) if repo_info_row and repo_info_row["first_seen"] else None
                last_seen = str(repo_info_row["last_seen"]) if repo_info_row and repo_info_row["last_seen"] else None
                latest_stars = int(latest_row["stars"] or 0) if latest_row else 0
                avg_stars_today = float(latest_row["stars_today"] or 0) if latest_row else 0.0

            category = "infra_and_tools"
            if latest_row and latest_row["category"]:
                category = latest_row["category"]
            elif repo_info_row and repo_info_row["category"]:
                category = repo_info_row["category"]

            basic = {
                "repo_full_name": repo_full_name,
                "url": f"https://github.com/{repo_full_name}",
                "description": latest_row["description"] if latest_row and latest_row["description"] else "",
                "language": latest_row["language"] if latest_row and latest_row["language"] else "Unknown",
                "category": category,
                "stars": int(latest_row["stars"] or 0) if latest_row else 0,
                "stars_today": int(latest_row["stars_today"] or 0) if latest_row else 0,
                "rank": latest_row["rank"] if latest_row else None,
                "since_type": latest_row["since_type"] if latest_row else None,
                "repo_updated_at": latest_row["repo_updated_at"] if latest_row else None,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "total_appearances": int(repo_info_row["total_appearances"] or 0) if repo_info_row else len(trend_history),
            }

            return {
                "basic": basic,
                "summary": analysis_row["summary"] if analysis_row else "",
                "reasons": _json_list(analysis_row["reasons"]) if analysis_row else [],
                "keywords": _json_list(analysis_row["keywords"]) if analysis_row else [],
                "tech_stack": _json_list(analysis_row["tech_stack"]) if analysis_row else [],
                "use_cases": _json_list(analysis_row["use_cases"]) if analysis_row else [],
                "evidence": {
                    "chunk_id": evidence_row["chunk_id"] if evidence_row else None,
                    "chunk_text": evidence_row["chunk_text"] if evidence_row and evidence_row["chunk_text"] else "",
                    "section": evidence_row["section"] if evidence_row else None,
                    "path": evidence_row["path"] if evidence_row else None,
                    "heading": evidence_row["heading"] if evidence_row else None,
                    "updated_at": evidence_row["updated_at"] if evidence_row else None,
                },
                "trend_summary": {
                    "total_records": len(trend_history),
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "best_rank": best_rank,
                    "latest_stars": latest_stars,
                    "avg_stars_today": avg_stars_today,
                },
                "trend_history": trend_history,
            }

