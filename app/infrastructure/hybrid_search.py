"""
混合检索模块

结合向量检索和 BM25 关键词检索，使用 RRF 融合
"""

import logging
from typing import List, Dict, Optional

from app.infrastructure.embedding import EmbeddingEngine
from app.infrastructure.bm25 import BM25SearchEngine
from app.infrastructure.chroma_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    混合检索引擎
    
    使用 RRF (Reciprocal Rank Fusion) 融合向量和 BM25 检索结果
    
    RRF 公式: score(d) = Σ 1/(k + rank(d))
    - k = 60 (经典参数)
    - rank(d) 是文档在某个检索结果中的排名（从 1 开始）
    """

    def __init__(self, rrf_k: int = 60):
        self.embedding_engine = EmbeddingEngine()
        self.bm25_engine = BM25SearchEngine()
        self.chroma_store = ChromaVectorStore()
        self.rrf_k = rrf_k
        self.documents = []
        self.doc_map = {}
        self.is_indexed = False

    def build_index(self, documents: List[Dict]) -> None:
        """构建混合索引"""
        self.documents = documents
        self.doc_map = {}
        self.bm25_engine.build_index(documents)

        embeddings = []
        ids = []
        metadatas = []

        for doc in documents:
            embedding = doc.get("embedding")
            doc_id = doc.get("chunk_id") or doc.get("repo_full_name")
            if doc_id:
                self.doc_map[doc_id] = doc
            if embedding:
                embeddings.append(embedding)
                ids.append(doc_id)
                metadatas.append({
                    "chunk_id": doc_id or "",
                    "repo_full_name": doc.get("repo_full_name") or "",
                    "chunk_index": doc.get("chunk_index", 0),
                    "section": doc.get("section") or "",
                    "summary": doc.get("summary") or "",
                    "language": doc.get("language") or "",
                    "category": doc.get("category") or "",
                    "keywords": ",".join(doc.get("keywords", [])),
                    "tech_stack": ",".join(doc.get("tech_stack", [])),
                    "use_cases": ",".join(doc.get("use_cases", []))
                })

        if embeddings:
            self.chroma_store.batch_upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )

        self.is_indexed = True
        logger.info(f"混合索引构建完成，共 {len(documents)} 个文档，向量 {len(embeddings)} 个")

    async def search(
        self,
        query: str,
        top_k: int = 20
    ) -> List[Dict]:
        """
        混合搜索（粗排）
        
        使用 RRF 融合向量和 BM25 检索结果
        
        Args:
            query: 查询文本
            top_k: 返回数量（默认 20，用于粗排）
        
        Returns:
            融合后的结果列表
        """
        if not self.is_indexed or not self.documents:
            logger.warning("索引未构建或文档为空")
            return []

        vector_results = await self._vector_search(query, top_k * 2)
        bm25_results = self._bm25_search(query, top_k * 2)

        merged_results = self._rrf_fusion(
            vector_results=vector_results,
            bm25_results=bm25_results,
            top_k=top_k
        )

        return merged_results

    async def _vector_search(self, query: str, top_k: int) -> List[Dict]:
        """向量检索"""
        try:
            query_embedding = await self.embedding_engine.embed_text(query)
            if not query_embedding:
                return []

            results = self.chroma_store.search(
                query_embedding=query_embedding,
                top_k=top_k
            )

            formatted_results = []
            for result in results:
                doc_id = result.get("repo_full_name")
                doc_data = self.doc_map.get(doc_id)

                if doc_data:
                    formatted_result = doc_data.copy()
                    formatted_result["chunk_id"] = doc_data.get("chunk_id", doc_id)
                    formatted_result["vector_score"] = result.get("similarity", 0)
                    formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            return []

    def _bm25_search(self, query: str, top_k: int) -> List[Dict]:
        """BM25 检索"""
        try:
            return self.bm25_engine.search(query, top_k=top_k)
        except Exception as e:
            logger.error(f"BM25 检索失败: {str(e)}")
            return []

    def _rrf_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """
        RRF (Reciprocal Rank Fusion) 融合
        
        公式: score(d) = Σ 1/(k + rank(d))
        
        Args:
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果
            top_k: 返回数量
        
        Returns:
            融合后的结果列表
        """
        rrf_scores = {}
        doc_map = {}

        for rank, result in enumerate(vector_results, start=1):
            doc_id = result.get("chunk_id") or result.get("repo_full_name")
            if not doc_id:
                continue
            
            rrf_score = 1.0 / (self.rrf_k + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + rrf_score
            doc_map[doc_id] = result

        for rank, result in enumerate(bm25_results, start=1):
            doc_id = result.get("chunk_id") or result.get("repo_full_name")
            if not doc_id:
                continue
            
            rrf_score = 1.0 / (self.rrf_k + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + rrf_score
            
            if doc_id not in doc_map:
                doc_map[doc_id] = result

        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        results = []
        for doc_id, rrf_score in sorted_docs[:top_k]:
            doc = doc_map[doc_id].copy()
            doc["rrf_score"] = rrf_score
            results.append(doc)

        return results
