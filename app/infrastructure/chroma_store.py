"""
ChromaDB 向量存储模块

提供向量持久化存储和高效检索功能
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """ChromaDB 向量存储"""

    DEFAULT_PERSIST_DIR = Path("data/chroma")

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = Path(persist_dir or os.getenv("CHROMA_PERSIST_DIR", str(self.DEFAULT_PERSIST_DIR)))
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = None
        self._collection = None
        self.collection_name = "github_projects"

        logger.info(f"ChromaDB 初始化完成，存储路径: {self.persist_dir}")

    @property
    def client(self):
        """延迟加载 ChromaDB 客户端"""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings
            
            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        return self._client

    @property
    def collection(self):
        """延迟加载 collection"""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "GitHub 项目向量索引"},
                embedding_function=None
            )
        return self._collection

    def upsert(
        self,
        repo_full_name: str,
        embedding: List[float],
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        插入或更新向量

        Args:
            repo_full_name: 项目全名（作为唯一 ID）
            embedding: 向量
            metadata: 元数据（language, category, summary 等）

        Returns:
            是否成功
        """
        try:
            safe_id = self._safe_id(repo_full_name)

            safe_metadata = self._sanitize_metadata(metadata or {})
            self.collection.upsert(
                ids=[safe_id],
                embeddings=[embedding],
                metadatas=[safe_metadata],
                documents=[repo_full_name]
            )

            logger.debug(f"向量更新成功: {repo_full_name}")
            return True

        except Exception as e:
            logger.error(f"向量更新失败: {str(e)}")
            return False

    def batch_upsert(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict]] = None
    ) -> int:
        """
        批量插入或更新向量

        Args:
            ids: 项目全名列表
            embeddings: 向量列表
            metadatas: 元数据列表

        Returns:
            成功数量
        """
        try:
            safe_ids = [self._safe_id(id_) for id_ in ids]
            safe_metadatas = [self._sanitize_metadata(m) for m in (metadatas or [{}] * len(ids))]

            self.collection.upsert(
                ids=safe_ids,
                embeddings=embeddings,
                metadatas=safe_metadatas,
                documents=ids
            )

            logger.info(f"批量向量更新成功: {len(ids)} 个")
            return len(ids)

        except Exception as e:
            logger.error(f"批量向量更新失败: {str(e)}")
            return 0

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where: Optional[Dict] = None
    ) -> List[Dict]:
        """
        向量检索

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            where: 元数据过滤条件

        Returns:
            检索结果列表
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["metadatas", "distances", "documents"]
            )

            formatted_results = []
            if results and results["ids"]:
                for i, id_ in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1 - distance

                    formatted_results.append({
                        "id": id_,
                        "repo_full_name": results["documents"][0][i] if results["documents"] else id_,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": distance,
                        "similarity": similarity
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            return []

    def get(self, repo_full_name: str) -> Optional[Dict]:
        """
        获取单个向量

        Args:
            repo_full_name: 项目全名

        Returns:
            向量数据
        """
        try:
            safe_id = self._safe_id(repo_full_name)

            results = self.collection.get(
                ids=[safe_id],
                include=["embeddings", "metadatas", "documents"]
            )

            if results and results["ids"]:
                return {
                    "id": results["ids"][0],
                    "repo_full_name": results["documents"][0] if results["documents"] else results["ids"][0],
                    "embedding": results["embeddings"][0] if results["embeddings"] else None,
                    "metadata": results["metadatas"][0] if results["metadatas"] else {}
                }

            return None

        except Exception as e:
            logger.error(f"获取向量失败: {str(e)}")
            return None

    def delete(self, repo_full_name: str) -> bool:
        """
        删除向量

        Args:
            repo_full_name: 项目全名

        Returns:
            是否成功
        """
        try:
            safe_id = self._safe_id(repo_full_name)
            self.collection.delete(ids=[safe_id])
            logger.debug(f"向量删除成功: {repo_full_name}")
            return True

        except Exception as e:
            logger.error(f"向量删除失败: {str(e)}")
            return False

    def count(self) -> int:
        """获取向量数量"""
        return self.collection.count()

    def get_all_ids(self) -> List[str]:
        """获取所有 ID"""
        try:
            results = self.collection.get(include=["documents"])
            return results["documents"] if results and results["documents"] else []
        except Exception as e:
            logger.error(f"获取所有 ID 失败: {str(e)}")
            return []

    def _safe_id(self, id_: str) -> str:
        """
        生成安全的 ID（ChromaDB 对 ID 有长度限制）
        """
        import hashlib
        return hashlib.md5(id_.encode()).hexdigest()

    def _sanitize_metadata(self, metadata: Optional[Dict]) -> Dict:
        """Chroma metadata only accepts scalar values and cannot contain None."""
        if not metadata:
            return {}

        sanitized = {}
        for key, value in metadata.items():
            if value is None:
                sanitized[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            else:
                sanitized[key] = str(value)
        return sanitized
