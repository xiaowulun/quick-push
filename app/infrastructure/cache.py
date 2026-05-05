import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from app.infrastructure.cache_analysis_store import AnalysisStore
from app.infrastructure.cache_chunk_store import ChunkStore
from app.infrastructure.cache_history_store import HistoryStore
from app.infrastructure.cache_schema import (
    DEFAULT_DB_PATH as CACHE_DEFAULT_DB_PATH,
    init_cache_schema,
    migrate_legacy_db_if_needed,
)


class AnalysisCache:
    """分析结果缓存，基于 SQLite（Facade）。"""

    DEFAULT_DB_PATH = CACHE_DEFAULT_DB_PATH

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or os.getenv("SQLITE_DB_PATH", str(self.DEFAULT_DB_PATH)))
        migrate_legacy_db_if_needed(self.db_path, explicit_db_path=bool(db_path))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        init_cache_schema(self.db_path)

        self.analysis_store = AnalysisStore(self.db_path)
        self.history_store = HistoryStore(self.db_path)
        self.chunk_store = ChunkStore(self.db_path)

    def get(self, repo_full_name: str) -> Optional[Dict]:
        return self.analysis_store.get(repo_full_name)

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
        self.analysis_store.set(
            repo_full_name=repo_full_name,
            summary=summary,
            reasons=reasons,
            readme_content=readme_content,
            readme_hash=readme_hash,
            source_updated_at=source_updated_at,
            keywords=keywords,
            tech_stack=tech_stack,
            use_cases=use_cases,
        )

    def exists(self, repo_full_name: str) -> bool:
        return self.analysis_store.exists(repo_full_name)

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
        self.history_store.save_trending_record(
            record_date=record_date,
            repo_full_name=repo_full_name,
            description=description,
            repo_updated_at=repo_updated_at,
            language=language,
            stars=stars,
            stars_today=stars_today,
            rank=rank,
            since_type=since_type,
            category=category,
        )

    def get_trending_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        repo_name: Optional[str] = None,
        since_type: Optional[str] = None,
    ) -> List[Dict]:
        return self.history_store.get_trending_history(
            start_date=start_date,
            end_date=end_date,
            repo_name=repo_name,
            since_type=since_type,
        )

    def get_latest_record_date(self, since_type: Optional[str] = None) -> Optional[date]:
        return self.history_store.get_latest_record_date(since_type=since_type)

    def get_project_detail(self, repo_full_name: str, history_limit: int = 12) -> Optional[Dict]:
        return self.history_store.get_project_detail(repo_full_name=repo_full_name, history_limit=history_limit)

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
        self.analysis_store.set_with_embedding(
            repo_full_name=repo_full_name,
            summary=summary,
            reasons=reasons,
            readme_content=readme_content,
            readme_hash=readme_hash,
            source_updated_at=source_updated_at,
            search_text=search_text,
            embedding=embedding,
            keywords=keywords,
            tech_stack=tech_stack,
            use_cases=use_cases,
        )

    def get_embedding(self, repo_full_name: str) -> Optional[Dict]:
        return self.analysis_store.get_embedding(repo_full_name)

    def get_all_embeddings(self) -> List[Dict]:
        return self.analysis_store.get_all_embeddings()

    def replace_chunks(self, repo_full_name: str, chunks: List[Dict]) -> None:
        self.chunk_store.replace_chunks(repo_full_name=repo_full_name, chunks=chunks)

    def get_all_chunks(self) -> List[Dict]:
        return self.chunk_store.get_all_chunks()

    def build_search_text(
        self,
        repo_full_name: str,
        summary: str,
        reasons: list,
        language: str = "",
        category: str = "",
    ) -> str:
        return self.analysis_store.build_search_text(
            repo_full_name=repo_full_name,
            summary=summary,
            reasons=reasons,
            language=language,
            category=category,
        )
