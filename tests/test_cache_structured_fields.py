import sqlite3
import uuid
from pathlib import Path

from app.infrastructure.cache import AnalysisCache


def _table_columns(db_path, table_name):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _workspace_db_path(prefix: str) -> Path:
    base = Path("data/sqlite")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{prefix}-{uuid.uuid4().hex}.db"


def _cleanup_db_file(db_path: Path) -> None:
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


def test_cache_migrates_structured_field_columns_for_legacy_db():
    db_path = _workspace_db_path("legacy")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE analysis_cache (
                repo_full_name TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                reasons TEXT NOT NULL,
                analyzed_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE analysis_chunks (
                chunk_id TEXT PRIMARY KEY,
                repo_full_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                analyzed_at TIMESTAMP
            )
            """
        )
        conn.commit()

    try:
        AnalysisCache(db_path=str(db_path))

        analysis_cache_columns = _table_columns(db_path, "analysis_cache")
        assert "keywords" in analysis_cache_columns
        assert "tech_stack" in analysis_cache_columns
        assert "use_cases" in analysis_cache_columns
        assert "search_text" in analysis_cache_columns
        assert "embedding" in analysis_cache_columns

        analysis_chunks_columns = _table_columns(db_path, "analysis_chunks")
        assert "keywords" in analysis_chunks_columns
        assert "tech_stack" in analysis_chunks_columns
        assert "use_cases" in analysis_chunks_columns
        assert "embedding" in analysis_chunks_columns
    finally:
        _cleanup_db_file(db_path)


def test_cache_roundtrip_structured_fields():
    db_path = _workspace_db_path("roundtrip")
    cache = AnalysisCache(db_path=str(db_path))

    try:
        cache.set(
            repo_full_name="owner/repo",
            summary="A useful project",
            reasons=["Reason 1"],
            keywords=["agent", "workflow"],
            tech_stack=["Python", "FastAPI"],
            use_cases=["AI Agent"],
        )

        saved = cache.get("owner/repo")
        assert saved is not None
        assert saved["keywords"] == ["agent", "workflow"]
        assert saved["tech_stack"] == ["Python", "FastAPI"]
        assert saved["use_cases"] == ["AI Agent"]
    finally:
        _cleanup_db_file(db_path)


def test_cache_structured_fields_default_to_empty_lists():
    db_path = _workspace_db_path("defaults")
    cache = AnalysisCache(db_path=str(db_path))

    try:
        cache.set(
            repo_full_name="owner/defaults",
            summary="No tags yet",
            reasons=["Reason A"],
        )

        saved = cache.get("owner/defaults")
        assert saved is not None
        assert saved["keywords"] == []
        assert saved["tech_stack"] == []
        assert saved["use_cases"] == []
    finally:
        _cleanup_db_file(db_path)
