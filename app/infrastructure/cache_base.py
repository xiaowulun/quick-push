import sqlite3
from pathlib import Path


class SQLiteStore:
    """Shared sqlite helper for cache stores."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

