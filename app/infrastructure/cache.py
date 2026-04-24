import json
import os
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional


class AnalysisCache:
    """分析结果缓存，基于 SQLite"""

    DEFAULT_DB_PATH = Path("data/sqlite/analysis_cache.db")
    LEGACY_DB_PATH = Path(".cache/analysis_cache.db")

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or os.getenv("SQLITE_DB_PATH", str(self.DEFAULT_DB_PATH)))
        self._migrate_legacy_db_if_needed(explicit_db_path=bool(db_path))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _migrate_legacy_db_if_needed(self, explicit_db_path: bool) -> None:
        """
        当未显式传入 db_path 且目标路径不存在时，
        将历史 `.cache/analysis_cache.db` 自动复制到新目录。
        """
        if explicit_db_path:
            return
        if self.db_path.exists() or not self.LEGACY_DB_PATH.exists():
            return
        if self.LEGACY_DB_PATH.resolve() == self.db_path.resolve():
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.LEGACY_DB_PATH, self.db_path)

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    repo_full_name TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    readme_content TEXT,
                    readme_hash TEXT,
                    source_updated_at TEXT,
                    search_text TEXT,
                    embedding TEXT,
                    keywords TEXT,
                    tech_stack TEXT,
                    use_cases TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS trending_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_date DATE NOT NULL,
                    repo_full_name TEXT NOT NULL,
                    description TEXT,
                    repo_updated_at TEXT,
                    language TEXT,
                    stars INTEGER,
                    stars_today INTEGER,
                    rank INTEGER,
                    since_type TEXT NOT NULL,
                    category TEXT,
                    UNIQUE(record_date, repo_full_name, since_type)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS repo_info (
                    repo_full_name TEXT PRIMARY KEY,
                    first_seen DATE,
                    last_seen DATE,
                    total_appearances INTEGER DEFAULT 0,
                    category TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    repo_full_name TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    section TEXT,
                    path TEXT,
                    heading TEXT,
                    updated_at TEXT,
                    embedding TEXT,
                    keywords TEXT,
                    tech_stack TEXT,
                    use_cases TEXT,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo_full_name, chunk_index)
                )
            """)

            self._ensure_column(conn, "analysis_cache", "readme_content TEXT")
            self._ensure_column(conn, "analysis_cache", "readme_hash TEXT")
            self._ensure_column(conn, "analysis_cache", "source_updated_at TEXT")
            self._ensure_column(conn, "analysis_cache", "search_text TEXT")
            self._ensure_column(conn, "analysis_cache", "embedding TEXT")
            self._ensure_column(conn, "analysis_cache", "keywords TEXT")
            self._ensure_column(conn, "analysis_cache", "tech_stack TEXT")
            self._ensure_column(conn, "analysis_cache", "use_cases TEXT")
            self._ensure_column(conn, "trending_history", "description TEXT")
            self._ensure_column(conn, "trending_history", "repo_updated_at TEXT")
            self._ensure_column(conn, "analysis_chunks", "embedding TEXT")
            self._ensure_column(conn, "analysis_chunks", "keywords TEXT")
            self._ensure_column(conn, "analysis_chunks", "tech_stack TEXT")
            self._ensure_column(conn, "analysis_chunks", "use_cases TEXT")
            self._ensure_column(conn, "analysis_chunks", "path TEXT")
            self._ensure_column(conn, "analysis_chunks", "heading TEXT")
            self._ensure_column(conn, "analysis_chunks", "updated_at TEXT")

            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_def: str) -> None:
        """确保旧数据库具备新增列（轻量迁移）。"""
        column_name = column_def.split()[0]
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")

    def get(self, repo_full_name: str) -> Optional[Dict]:
        """获取缓存的分析结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT summary, reasons, analyzed_at, readme_content, readme_hash, source_updated_at,
                       keywords, tech_stack, use_cases
                FROM analysis_cache
                WHERE repo_full_name = ?
                """,
                (repo_full_name,)
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
    ):
        """保存分析结果到缓存"""
        keywords_json = json.dumps(keywords) if keywords is not None else None
        tech_stack_json = json.dumps(tech_stack) if tech_stack is not None else None
        use_cases_json = json.dumps(use_cases) if use_cases is not None else None

        with sqlite3.connect(self.db_path) as conn:
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
                )
            )
            conn.commit()

    def exists(self, repo_full_name: str) -> bool:
        """检查是否存在缓存"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM analysis_cache WHERE repo_full_name = ?",
                (repo_full_name,)
            )
            return cursor.fetchone() is not None

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
        category: Optional[str] = None
    ):
        """保存趋势记录"""
        with sqlite3.connect(self.db_path) as conn:
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
                )
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
                (repo_full_name, record_date, record_date, category)
            )

            conn.commit()

    def get_trending_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        repo_name: Optional[str] = None,
        since_type: Optional[str] = None
    ) -> List[Dict]:
        """查询趋势历史"""
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

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_project_detail(self, repo_full_name: str, history_limit: int = 12) -> Optional[Dict]:
        """按 repo 聚合详情：分析结果 + 最新趋势 + 历史摘要 + 证据片段。"""
        with sqlite3.connect(self.db_path) as conn:
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
        use_cases: list = None
    ):
        """保存分析结果和向量数据到缓存"""
        with sqlite3.connect(self.db_path) as conn:
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
                    json.dumps(use_cases) if use_cases else None
                )
            )
            conn.commit()

    def get_embedding(self, repo_full_name: str) -> Optional[Dict]:
        """获取项目的向量数据"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    summary, reasons, readme_content, readme_hash, source_updated_at,
                    search_text, embedding, keywords, tech_stack, use_cases, analyzed_at
                FROM analysis_cache
                WHERE repo_full_name = ?
                """,
                (repo_full_name,)
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
                    "analyzed_at": row["analyzed_at"]
                }
            return None

    def get_all_embeddings(self) -> List[Dict]:
        """获取所有项目的向量数据"""
        with sqlite3.connect(self.db_path) as conn:
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
                results.append({
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
                })
            return results

    def replace_chunks(
        self,
        repo_full_name: str,
        chunks: List[Dict]
    ) -> None:
        """替换项目的全部 chunk（先删后插）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM analysis_chunks WHERE repo_full_name = ?",
                (repo_full_name,)
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
                        datetime.now().isoformat()
                    )
                )

            conn.commit()

    def get_all_chunks(self) -> List[Dict]:
        """获取所有已向量化的 chunk 数据"""
        with sqlite3.connect(self.db_path) as conn:
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
                results.append({
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
                })

            return results

    def build_search_text(
        self,
        repo_full_name: str,
        summary: str,
        reasons: list,
        language: str = "",
        category: str = ""
    ) -> str:
        """构建用于向量化的综合文本"""
        parts = []

        parts.append(f"项目名称: {repo_full_name}")

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
