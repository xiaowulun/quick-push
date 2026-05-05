import shutil
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/sqlite/analysis_cache.db")
LEGACY_DB_PATH = Path(".cache/analysis_cache.db")


def migrate_legacy_db_if_needed(db_path: Path, explicit_db_path: bool) -> None:
    """
    当未显式传入 db_path 且目标路径不存在时，
    将历史 `.cache/analysis_cache.db` 自动复制到新目录。
    """
    if explicit_db_path:
        return
    if db_path.exists() or not LEGACY_DB_PATH.exists():
        return
    if LEGACY_DB_PATH.resolve() == db_path.resolve():
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LEGACY_DB_PATH, db_path)


def ensure_column(conn: sqlite3.Connection, table_name: str, column_def: str) -> None:
    """确保旧数据库具备新增列（轻量迁移）。"""
    column_name = column_def.split()[0]
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")


def init_cache_schema(db_path: Path) -> None:
    """初始化数据库表结构。"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
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
            """
        )

        conn.execute(
            """
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
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS repo_info (
                repo_full_name TEXT PRIMARY KEY,
                first_seen DATE,
                last_seen DATE,
                total_appearances INTEGER DEFAULT 0,
                category TEXT
            )
            """
        )

        conn.execute(
            """
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
            """
        )

        ensure_column(conn, "analysis_cache", "readme_content TEXT")
        ensure_column(conn, "analysis_cache", "readme_hash TEXT")
        ensure_column(conn, "analysis_cache", "source_updated_at TEXT")
        ensure_column(conn, "analysis_cache", "search_text TEXT")
        ensure_column(conn, "analysis_cache", "embedding TEXT")
        ensure_column(conn, "analysis_cache", "keywords TEXT")
        ensure_column(conn, "analysis_cache", "tech_stack TEXT")
        ensure_column(conn, "analysis_cache", "use_cases TEXT")
        ensure_column(conn, "trending_history", "description TEXT")
        ensure_column(conn, "trending_history", "repo_updated_at TEXT")
        ensure_column(conn, "analysis_chunks", "embedding TEXT")
        ensure_column(conn, "analysis_chunks", "keywords TEXT")
        ensure_column(conn, "analysis_chunks", "tech_stack TEXT")
        ensure_column(conn, "analysis_chunks", "use_cases TEXT")
        ensure_column(conn, "analysis_chunks", "path TEXT")
        ensure_column(conn, "analysis_chunks", "heading TEXT")
        ensure_column(conn, "analysis_chunks", "updated_at TEXT")

        conn.commit()

