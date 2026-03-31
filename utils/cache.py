import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path


class AnalysisCache:
    """分析结果缓存，基于 SQLite"""

    def __init__(self, db_path: str = ".cache/analysis_cache.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    repo_full_name TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get(self, repo_full_name: str) -> Optional[Dict]:
        """获取缓存的分析结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT summary, reasons, analyzed_at FROM analysis_cache WHERE repo_full_name = ?",
                (repo_full_name,)
            )
            row = cursor.fetchone()

            if row:
                return {
                    "summary": row["summary"],
                    "reasons": json.loads(row["reasons"]),
                    "analyzed_at": row["analyzed_at"]
                }
            return None

    def set(self, repo_full_name: str, summary: str, reasons: list):
        """保存分析结果到缓存"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analysis_cache (repo_full_name, summary, reasons, analyzed_at)
                VALUES (?, ?, ?, ?)
                """,
                (repo_full_name, summary, json.dumps(reasons), datetime.now().isoformat())
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

    def clear(self):
        """清空所有缓存"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM analysis_cache")
            conn.commit()

    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM analysis_cache")
            count = cursor.fetchone()[0]
            return {"total_cached": count}
