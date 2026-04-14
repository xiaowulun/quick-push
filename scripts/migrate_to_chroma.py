"""
数据迁移脚本 - 将 SQLite 中的向量数据迁移到 ChromaDB

使用方法：
    conda activate llm
    python scripts/migrate_to_chroma.py
    python scripts/migrate_to_chroma.py --test  # 迁移后测试搜索功能
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.cache import AnalysisCache
from app.infrastructure.chroma_store import ChromaVectorStore


def migrate_to_chroma():
    """迁移 SQLite 向量数据到 ChromaDB"""
    
    print("=" * 60)
    print("SQLite → ChromaDB 数据迁移")
    print("=" * 60)
    
    cache = AnalysisCache()
    chroma_store = ChromaVectorStore()
    
    print("\n[1/3] 从 SQLite 加载向量数据...")
    all_embeddings = cache.get_all_embeddings()
    
    if not all_embeddings:
        print("❌ SQLite 中没有向量数据，无需迁移")
        return
    
    print(f"   找到 {len(all_embeddings)} 条向量数据")
    
    print("\n[2/3] 迁移数据到 ChromaDB...")
    
    ids = []
    embeddings = []
    metadatas = []
    
    for doc in all_embeddings:
        embedding = doc.get("embedding")
        if not embedding:
            continue
        
        ids.append(doc.get("repo_full_name"))
        embeddings.append(embedding)
        metadatas.append({
            "summary": doc.get("summary", ""),
            "language": doc.get("language", ""),
            "category": doc.get("category", ""),
            "keywords": ",".join(doc.get("keywords", [])),
            "tech_stack": ",".join(doc.get("tech_stack", [])),
            "use_cases": ",".join(doc.get("use_cases", []))
        })
    
    if not embeddings:
        print("❌ 没有有效的向量数据")
        return
    
    success_count = chroma_store.batch_upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas
    )
    
    print(f"   成功迁移 {success_count} 条数据")
    
    print("\n[3/3] 验证迁移结果...")
    chroma_count = chroma_store.count()
    print(f"   ChromaDB 中共有 {chroma_count} 条向量")
    
    print("\n" + "=" * 60)
    print("✅ 迁移完成！")
    print(f"   SQLite 向量数: {len(all_embeddings)}")
    print(f"   ChromaDB 向量数: {chroma_count}")
    print("=" * 60)


def test_search():
    """测试搜索功能"""
    
    print("\n" + "=" * 60)
    print("测试 ChromaDB 搜索")
    print("=" * 60)
    
    from app.knowledge.search import SearchService
    
    async def _test():
        service = SearchService()
        
        test_queries = [
            "Python 爬虫",
            "机器学习",
            "Web 框架"
        ]
        
        for query in test_queries:
            print(f"\n查询: {query}")
            results = await service.search_projects(
                query=query,
                coarse_top_k=20,
                final_top_k=3
            )
            
            if results:
                for i, r in enumerate(results, 1):
                    score = r.get('rerank_score', r.get('rrf_score', 0))
                    print(f"  {i}. {r.get('repo_full_name')} (分数: {score:.3f})")
            else:
                print("  无结果")
    
    asyncio.run(_test())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SQLite → ChromaDB 数据迁移")
    parser.add_argument("--test", action="store_true", help="迁移后测试搜索功能")
    args = parser.parse_args()
    
    migrate_to_chroma()
    
    if args.test:
        test_search()
