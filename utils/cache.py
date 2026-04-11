import sqlite3
import json
from datetime import datetime, date
from typing import Optional, Dict, List
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
            # 分析结果缓存表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    repo_full_name TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    search_text TEXT,
                    embedding TEXT,
                    keywords TEXT,
                    tech_stack TEXT,
                    use_cases TEXT
                )
            """)

            # 趋势历史记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trending_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_date DATE NOT NULL,
                    repo_full_name TEXT NOT NULL,
                    language TEXT,
                    stars INTEGER,
                    stars_today INTEGER,
                    rank INTEGER,
                    since_type TEXT NOT NULL,
                    category TEXT,
                    UNIQUE(record_date, repo_full_name, since_type)
                )
            """)

            # 项目信息维度表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS repo_info (
                    repo_full_name TEXT PRIMARY KEY,
                    first_seen DATE,
                    last_seen DATE,
                    total_appearances INTEGER DEFAULT 0,
                    category TEXT
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
            analysis_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM trending_history")
            history_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM repo_info")
            repo_count = cursor.fetchone()[0]

            return {
                "total_cached": analysis_count,
                "trending_records": history_count,
                "tracked_repos": repo_count
            }

    # ========== 趋势分析相关方法 ==========

    def save_trending_record(
        self,
        record_date: date,
        repo_full_name: str,
        language: str,
        stars: int,
        stars_today: int,
        rank: int,
        since_type: str,
        category: Optional[str] = None
    ):
        """保存趋势记录"""
        with sqlite3.connect(self.db_path) as conn:
            # 保存趋势记录
            conn.execute(
                """
                INSERT OR REPLACE INTO trending_history
                (record_date, repo_full_name, language, stars, stars_today, rank, since_type, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_date, repo_full_name, language, stars, stars_today, rank, since_type, category)
            )

            # 更新项目信息
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

    def get_hot_repos(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """获取近期热门项目（上榜次数最多）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    repo_full_name,
                    COUNT(*) as appearances,
                    AVG(rank) as avg_rank,
                    MAX(record_date) as last_seen
                FROM trending_history
                WHERE record_date >= date('now', '-{} days')
                GROUP BY repo_full_name
                ORDER BY appearances DESC, avg_rank ASC
                LIMIT {}
                """.format(days, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_category_trends(self, days: int = 7) -> List[Dict]:
        """获取分类趋势统计"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    category,
                    COUNT(*) as count,
                    COUNT(DISTINCT record_date) as days
                FROM trending_history
                WHERE record_date >= date('now', '-{} days')
                AND category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
                """.format(days)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_new_stars(self, days: int = 7, limit: int = 5) -> List[Dict]:
        """获取新星项目（首次上榜）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT DISTINCT
                    th.repo_full_name,
                    th.record_date,
                    th.rank,
                    th.stars,
                    th.category
                FROM trending_history th
                JOIN repo_info ri ON th.repo_full_name = ri.repo_full_name
                WHERE th.record_date >= date('now', '-{} days')
                AND ri.first_seen >= date('now', '-{} days')
                ORDER BY th.rank ASC
                LIMIT {}
                """.format(days, days, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def generate_trend_report(self, days: int = 7) -> Dict:
        """生成趋势报表"""
        return {
            "period": f"最近 {days} 天",
            "hot_repos": self.get_hot_repos(days),
            "category_trends": self.get_category_trends(days),
            "new_stars": self.get_new_stars(days),
            "total_records": len(self.get_trending_history(
                start_date=date.today().isoformat(),
                end_date=date.today().isoformat()
            ))
        }

    # ========== 向量搜索相关方法 ==========

    def set_with_embedding(
        self,
        repo_full_name: str,
        summary: str,
        reasons: list,
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
                (repo_full_name, summary, reasons, analyzed_at, search_text, embedding, keywords, tech_stack, use_cases)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_full_name,
                    summary,
                    json.dumps(reasons),
                    datetime.now().isoformat(),
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
                SELECT summary, reasons, search_text, embedding, keywords, tech_stack, use_cases, analyzed_at
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
                    ac.search_text,
                    ac.embedding,
                    ac.keywords,
                    ac.tech_stack,
                    ac.use_cases,
                    ri.category,
                    th.language,
                    th.stars
                FROM analysis_cache ac
                LEFT JOIN repo_info ri ON ac.repo_full_name = ri.repo_full_name
                LEFT JOIN trending_history th ON ac.repo_full_name = th.repo_full_name
                WHERE ac.embedding IS NOT NULL
                GROUP BY ac.repo_full_name
                """
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "repo_full_name": row["repo_full_name"],
                    "summary": row["summary"],
                    "reasons": json.loads(row["reasons"]),
                    "search_text": row["search_text"],
                    "embedding": json.loads(row["embedding"]) if row["embedding"] else None,
                    "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                    "tech_stack": json.loads(row["tech_stack"]) if row["tech_stack"] else [],
                    "use_cases": json.loads(row["use_cases"]) if row["use_cases"] else [],
                    "category": row["category"],
                    "language": row["language"],
                    "stars": row["stars"]
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
        """
        构建用于向量化的综合文本
        
        Args:
            repo_full_name: 项目全名
            summary: 项目分析
            reasons: 爆火原因
            language: 编程语言
            category: 分类
        
        Returns:
            综合文本描述
        """
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
