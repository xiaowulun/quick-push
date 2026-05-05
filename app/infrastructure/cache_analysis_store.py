import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from app.infrastructure.cache_base import SQLiteStore


class AnalysisStore(SQLiteStore):
    """analysis_cache table read/write and embedding views."""

    def get(self, repo_full_name: str) -> Optional[Dict]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT summary, reasons, analyzed_at, readme_content, readme_hash, source_updated_at,
                       keywords, tech_stack, use_cases
                FROM analysis_cache
                WHERE repo_full_name = ?
                """,
                (repo_full_name,),
            )
            row = cursor.fetchone()

            if row:
                return {
                    "summary": row["summary"],
                    "reasons": json.loads(row["reasons"]),
                    "analyzed_at": row["analyzed_at"],
                    "readme_content": row["readme_content"] or "",
                    "readme_hash": row["readme_hash"] or "",
                    "source_updated_at": row["source_updated_at"] or "",
                    "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                    "tech_stack": json.loads(row["tech_stack"]) if row["tech_stack"] else [],
                    "use_cases": json.loads(row["use_cases"]) if row["use_cases"] else [],
                }
            return None

    def set(
        self,
        repo_full_name: str,
        summary: str,
        reasons: list,
        readme_content: Optional[str] = None,
        readme_hash: Optional[str] = None,
        source_updated_at: Optional[str] = None,
        keywords: Optional[list] = None,
        tech_stack: Optional[list] = None,
        use_cases: Optional[list] = None,
    ) -> None:
        keywords_json = json.dumps(keywords) if keywords is not None else None
        tech_stack_json = json.dumps(tech_stack) if tech_stack is not None else None
        use_cases_json = json.dumps(use_cases) if use_cases is not None else None

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_cache
                (
                    repo_full_name, summary, reasons, analyzed_at, readme_content, readme_hash, source_updated_at,
                    keywords, tech_stack, use_cases
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_full_name) DO UPDATE SET
                    summary = excluded.summary,
                    reasons = excluded.reasons,
                    analyzed_at = excluded.analyzed_at,
                    readme_content = excluded.readme_content,
                    readme_hash = excluded.readme_hash,
                    source_updated_at = excluded.source_updated_at,
                    keywords = COALESCE(excluded.keywords, analysis_cache.keywords),
                    tech_stack = COALESCE(excluded.tech_stack, analysis_cache.tech_stack),
                    use_cases = COALESCE(excluded.use_cases, analysis_cache.use_cases)
                """,
                (
                    repo_full_name,
                    summary,
                    json.dumps(reasons),
                    datetime.now().isoformat(),
                    readme_content,
                    readme_hash,
                    source_updated_at,
                    keywords_json,
                    tech_stack_json,
                    use_cases_json,
                ),
            )
            conn.commit()

    def exists(self, repo_full_name: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM analysis_cache WHERE repo_full_name = ?",
                (repo_full_name,),
            )
            return cursor.fetchone() is not None

    def set_with_embedding(
        self,
        repo_full_name: str,
        summary: str,
        reasons: list,
        readme_content: str = None,
        readme_hash: Optional[str] = None,
        source_updated_at: Optional[str] = None,
        search_text: str = None,
        embedding: list = None,
        keywords: list = None,
        tech_stack: list = None,
        use_cases: list = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analysis_cache
                (
                    repo_full_name, summary, reasons, analyzed_at, readme_content, readme_hash, source_updated_at,
                    search_text, embedding, keywords, tech_stack, use_cases
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_full_name,
                    summary,
                    json.dumps(reasons),
                    datetime.now().isoformat(),
                    readme_content,
                    readme_hash,
                    source_updated_at,
                    search_text,
                    json.dumps(embedding) if embedding else None,
                    json.dumps(keywords) if keywords else None,
                    json.dumps(tech_stack) if tech_stack else None,
                    json.dumps(use_cases) if use_cases else None,
                ),
            )
            conn.commit()

    def get_embedding(self, repo_full_name: str) -> Optional[Dict]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    summary, reasons, readme_content, readme_hash, source_updated_at,
                    search_text, embedding, keywords, tech_stack, use_cases, analyzed_at
                FROM analysis_cache
                WHERE repo_full_name = ?
                """,
                (repo_full_name,),
            )
            row = cursor.fetchone()

            if row:
                return {
                    "summary": row["summary"],
                    "reasons": json.loads(row["reasons"]),
                    "readme_content": row["readme_content"] or "",
                    "readme_hash": row["readme_hash"] or "",
                    "source_updated_at": row["source_updated_at"] or "",
                    "search_text": row["search_text"],
                    "embedding": json.loads(row["embedding"]) if row["embedding"] else None,
                    "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                    "tech_stack": json.loads(row["tech_stack"]) if row["tech_stack"] else [],
                    "use_cases": json.loads(row["use_cases"]) if row["use_cases"] else [],
                    "analyzed_at": row["analyzed_at"],
                }
            return None

    def get_all_embeddings(self) -> List[Dict]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    ac.repo_full_name,
                    ac.summary,
                    ac.reasons,
                    ac.readme_content,
                    ac.readme_hash,
                    ac.source_updated_at,
                    ac.search_text,
                    ac.embedding,
                    ac.keywords,
                    ac.tech_stack,
                    ac.use_cases,
                    ri.category,
                    th.language,
                    th.stars,
                    th.record_date,
                    th.repo_updated_at
                FROM analysis_cache ac
                LEFT JOIN repo_info ri ON ac.repo_full_name = ri.repo_full_name
                LEFT JOIN (
                    SELECT
                        repo_full_name,
                        language,
                        stars,
                        repo_updated_at,
                        record_date,
                        ROW_NUMBER() OVER (PARTITION BY repo_full_name ORDER BY record_date DESC) as rn
                    FROM trending_history
                ) th ON ac.repo_full_name = th.repo_full_name AND th.rn = 1
                WHERE ac.embedding IS NOT NULL
                """
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "repo_full_name": row["repo_full_name"],
                        "summary": row["summary"],
                        "reasons": json.loads(row["reasons"]),
                        "readme_content": row["readme_content"] or "",
                        "readme_hash": row["readme_hash"] or "",
                        "source_updated_at": row["source_updated_at"] or "",
                        "search_text": row["search_text"],
                        "embedding": json.loads(row["embedding"]) if row["embedding"] else None,
                        "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                        "tech_stack": json.loads(row["tech_stack"]) if row["tech_stack"] else [],
                        "use_cases": json.loads(row["use_cases"]) if row["use_cases"] else [],
                        "category": row["category"],
                        "language": row["language"],
                        "stars": row["stars"],
                        "record_date": row["record_date"],
                        "repo_updated_at": row["repo_updated_at"],
                    }
                )
            return results

    @staticmethod
    def build_search_text(
        repo_full_name: str,
        summary: str,
        reasons: list,
        language: str = "",
        category: str = "",
    ) -> str:
        parts = [f"项目名称: {repo_full_name}"]

        if language:
            parts.append(f"编程语言: {language}")
        if category:
            parts.append(f"项目分类: {category}")
        if summary:
            parts.append(f"项目简介: {summary}")
        if reasons:
            parts.append("核心特点:")
            for reason in reasons:
                parts.append(f"  - {reason}")
        return "\n".join(parts)
