"""
向量化工具模块

提供文本向量化和相似度计算功能
"""

import logging
from typing import List, Optional
import numpy as np
from openai import OpenAI

from app.infrastructure.config import get_config

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
        """将文本转换为向量"""
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
        """批量文本向量化"""
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
        """计算两个向量的余弦相似度"""
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
        """批量计算余弦相似度"""
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
