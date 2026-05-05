import json
import sqlite3
from datetime import datetime
from typing import Dict, List

from app.infrastructure.cache_base import SQLiteStore


class ChunkStore(SQLiteStore):
    """analysis_chunks table helpers."""

    def replace_chunks(self, repo_full_name: str, chunks: List[Dict]) -> None:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM analysis_chunks WHERE repo_full_name = ?",
                (repo_full_name,),
            )

            for chunk in chunks:
                conn.execute(
                    """
                    INSERT INTO analysis_chunks
                    (
                        chunk_id, repo_full_name, chunk_index, chunk_text, section, path, heading, updated_at,
                        embedding, keywords, tech_stack, use_cases, analyzed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["chunk_id"],
                        repo_full_name,
                        chunk["chunk_index"],
                        chunk["chunk_text"],
                        chunk.get("section"),
                        chunk.get("path"),
                        chunk.get("heading"),
                        chunk.get("updated_at"),
                        json.dumps(chunk.get("embedding")) if chunk.get("embedding") else None,
                        json.dumps(chunk.get("keywords")) if chunk.get("keywords") else None,
                        json.dumps(chunk.get("tech_stack")) if chunk.get("tech_stack") else None,
                        json.dumps(chunk.get("use_cases")) if chunk.get("use_cases") else None,
                        datetime.now().isoformat(),
                    ),
                )

            conn.commit()

    def get_all_chunks(self) -> List[Dict]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    c.chunk_id,
                    c.repo_full_name,
                    c.chunk_index,
                    c.chunk_text,
                    c.section,
                    c.path,
                    c.heading,
                    c.updated_at,
                    c.embedding,
                    c.keywords,
                    c.tech_stack,
                    c.use_cases,
                    ac.summary,
                    ac.reasons,
                    ri.category,
                    th.language,
                    th.stars,
                    th.record_date
                FROM analysis_chunks c
                LEFT JOIN analysis_cache ac ON c.repo_full_name = ac.repo_full_name
                LEFT JOIN repo_info ri ON c.repo_full_name = ri.repo_full_name
                LEFT JOIN (
                    SELECT
                        repo_full_name,
                        language,
                        stars,
                        record_date,
                        ROW_NUMBER() OVER (PARTITION BY repo_full_name ORDER BY record_date DESC) as rn
                    FROM trending_history
                ) th ON c.repo_full_name = th.repo_full_name AND th.rn = 1
                WHERE c.embedding IS NOT NULL
                ORDER BY c.repo_full_name, c.chunk_index
                """
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "chunk_id": row["chunk_id"],
                        "repo_full_name": row["repo_full_name"],
                        "chunk_index": row["chunk_index"],
                        "chunk_text": row["chunk_text"],
                        "section": row["section"],
                        "path": row["path"],
                        "heading": row["heading"],
                        "updated_at": row["updated_at"],
                        "embedding": json.loads(row["embedding"]) if row["embedding"] else None,
                        "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                        "tech_stack": json.loads(row["tech_stack"]) if row["tech_stack"] else [],
                        "use_cases": json.loads(row["use_cases"]) if row["use_cases"] else [],
                        "summary": row["summary"] or "",
                        "reasons": json.loads(row["reasons"]) if row["reasons"] else [],
                        "category": row["category"],
                        "language": row["language"],
                        "stars": row["stars"],
                        "record_date": row["record_date"],
                    }
                )

            return results

