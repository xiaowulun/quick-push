"""
向量化工具模块

提供文本向量化和相似度计算功能
"""

import logging
from typing import List, Optional, Dict
import numpy as np
from openai import OpenAI

from core.config import get_config

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """文本向量化引擎"""

    def __init__(self):
        self.config = get_config()
        self.client = OpenAI(
            api_key=self.config.openai.api_key,
            base_url=self.config.openai.base_url
        )
        self.model = "BAAI/bge-large-zh-v1.5"
        self.dimension = 1024

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """
        将文本转换为向量
        
        Args:
            text: 待向量化的文本
        
        Returns:
            向量列表，失败返回 None
        """
        try:
            if not text or not text.strip():
                logger.warning("文本为空，无法向量化")
                return None

            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )

            embedding = response.data[0].embedding
            logger.info(f"文本向量化成功，维度: {len(embedding)}")
            return embedding

        except Exception as e:
            logger.error(f"文本向量化失败: {str(e)}")
            return None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量文本向量化
        
        Args:
            texts: 文本列表
        
        Returns:
            向量列表
        """
        try:
            if not texts:
                return []

            valid_texts = [t for t in texts if t and t.strip()]
            if not valid_texts:
                return [None] * len(texts)

            response = self.client.embeddings.create(
                model=self.model,
                input=valid_texts,
                encoding_format="float"
            )

            embeddings = {i: data.embedding for i, data in enumerate(response.data)}
            
            result = []
            valid_idx = 0
            for text in texts:
                if text and text.strip():
                    result.append(embeddings.get(valid_idx))
                    valid_idx += 1
                else:
                    result.append(None)

            logger.info(f"批量向量化成功，处理 {len(valid_texts)} 个文本")
            return result

        except Exception as e:
            logger.error(f"批量向量化失败: {str(e)}")
            return [None] * len(texts)

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
        
        Returns:
            相似度分数 [0, 1]
        """
        try:
            if not vec1 or not vec2:
                return 0.0

            v1 = np.array(vec1)
            v2 = np.array(vec2)

            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(similarity)

        except Exception as e:
            logger.error(f"计算相似度失败: {str(e)}")
            return 0.0

    @staticmethod
    def batch_cosine_similarity(
        query_vec: List[float],
        vectors: List[List[float]]
    ) -> List[float]:
        """
        批量计算余弦相似度
        
        Args:
            query_vec: 查询向量
            vectors: 向量列表
        
        Returns:
            相似度分数列表
        """
        try:
            if not query_vec or not vectors:
                return [0.0] * len(vectors)

            query = np.array(query_vec)
            docs = np.array(vectors)

            query_norm = np.linalg.norm(query)
            if query_norm == 0:
                return [0.0] * len(vectors)

            query_normalized = query / query_norm

            docs_norm = np.linalg.norm(docs, axis=1, keepdims=True)
            docs_norm[docs_norm == 0] = 1
            docs_normalized = docs / docs_norm

            similarities = np.dot(docs_normalized, query_normalized)

            return similarities.tolist()

        except Exception as e:
            logger.error(f"批量计算相似度失败: {str(e)}")
            return [0.0] * len(vectors)


class VectorSearchEngine:
    """向量搜索引擎"""

    def __init__(self):
        self.embedding_engine = EmbeddingEngine()

    async def search(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5,
        threshold: float = 0.5
    ) -> List[Dict]:
        """
        向量搜索
        
        Args:
            query: 查询文本
            documents: 文档列表，每个文档需包含 embedding 字段
            top_k: 返回前 k 个结果
            threshold: 相似度阈值
        
        Returns:
            匹配的文档列表，按相似度降序排列
        """
        try:
            if not query or not documents:
                return []

            query_embedding = await self.embedding_engine.embed_text(query)
            if not query_embedding:
                logger.error("查询向量化失败")
                return []

            valid_docs = [doc for doc in documents if doc.get("embedding")]
            if not valid_docs:
                logger.warning("没有有效的文档向量")
                return []

            embeddings = [doc["embedding"] for doc in valid_docs]
            similarities = EmbeddingEngine.batch_cosine_similarity(
                query_embedding,
                embeddings
            )

            results = []
            for doc, similarity in zip(valid_docs, similarities):
                if similarity >= threshold:
                    result = doc.copy()
                    result["similarity"] = similarity
                    results.append(result)

            results.sort(key=lambda x: x["similarity"], reverse=True)

            logger.info(
                f"搜索完成，查询: '{query[:50]}...', "
                f"匹配 {len(results)} 个结果（阈值: {threshold}）"
            )

            return results[:top_k]

        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return []

    async def hybrid_search(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict]:
        """
        混合搜索（向量 + 关键词）
        
        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前 k 个结果
            vector_weight: 向量搜索权重
            keyword_weight: 关键词搜索权重
        
        Returns:
            匹配的文档列表
        """
        try:
            if not query or not documents:
                return []

            vector_results = await self.search(
                query,
                documents,
                top_k=len(documents),
                threshold=0.0
            )

            query_lower = query.lower()
            keyword_scores = {}
            for doc in documents:
                score = 0.0
                search_text = doc.get("search_text", "").lower()
                keywords = doc.get("keywords", [])

                if query_lower in search_text:
                    score += 0.5

                for keyword in keywords:
                    if keyword.lower() in query_lower:
                        score += 0.3

                keyword_scores[doc["repo_full_name"]] = score

            combined_results = {}
            for result in vector_results:
                repo_name = result["repo_full_name"]
                vector_score = result["similarity"]
                keyword_score = keyword_scores.get(repo_name, 0.0)

                combined_score = (
                    vector_weight * vector_score +
                    keyword_weight * keyword_score
                )

                result["combined_score"] = combined_score
                result["vector_score"] = vector_score
                result["keyword_score"] = keyword_score
                combined_results[repo_name] = result

            final_results = sorted(
                combined_results.values(),
                key=lambda x: x["combined_score"],
                reverse=True
            )

            logger.info(
                f"混合搜索完成，查询: '{query[:50]}...', "
                f"返回 {len(final_results[:top_k])} 个结果"
            )

            return final_results[:top_k]

        except Exception as e:
            logger.error(f"混合搜索失败: {str(e)}")
            return []
