"""
数据库迁移脚本 - 添加向量化相关字段
"""

import sqlite3
from pathlib import Path


def migrate_database():
    """迁移数据库，添加新字段"""
    
    db_path = Path(".cache/analysis_cache.db")
    
    if not db_path.exists():
        print("数据库不存在，将在首次运行时自动创建")
        return
    
    print("开始数据库迁移...")
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(analysis_cache)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 添加缺失的字段
        new_columns = {
            "search_text": "TEXT",
            "embedding": "TEXT",
            "keywords": "TEXT",
            "tech_stack": "TEXT",
            "use_cases": "TEXT"
        }
        
        for column_name, column_type in new_columns.items():
            if column_name not in columns:
                try:
                    sql = f"ALTER TABLE analysis_cache ADD COLUMN {column_name} {column_type}"
                    cursor.execute(sql)
                    print(f"  [OK] 添加字段: {column_name}")
                except sqlite3.OperationalError as e:
                    print(f"  [FAIL] 添加字段失败 {column_name}: {e}")
            else:
                print(f"  [SKIP] 字段已存在: {column_name}")
        
        conn.commit()
    
    print("数据库迁移完成！")


if __name__ == "__main__":
    migrate_database()
