"""
重排序模块

提供 Cross-encoder 重排序功能
"""

import logging
from typing import List, Dict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Reranker(ABC):
    """重排序器基类"""
    
    @abstractmethod
    async def rerank(
        self, 
        query: str, 
        results: List[Dict], 
        top_k: int = 5
    ) -> List[Dict]:
        """重排序"""
        pass


class CrossEncoderReranker(Reranker):
    """
    Cross-Encoder 重排序器
    
    使用 Cross-Encoder 模型对检索结果进行重排序
    
    原理：
    ┌─────────────────────────────────────────────────────────┐
    │  Bi-Encoder（向量检索）                                   │
    │                                                          │
    │  Query ──┐                                              │
    │          ├──► [Encoder] ──► Vector Q                    │
    │          │                        │                      │
    │  Doc ────┘                        │ cosine              │
    │                                    │ similarity          │
    │  Doc ────► [Encoder] ──► Vector D ─┘                     │
    │                                                          │
    │  优点：快，可预计算                                       │
    │  缺点：Query 和 Doc 没有交互，精度有限                     │
    └─────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────┐
    │  Cross-Encoder（重排序）                                  │
    │                                                          │
    │  Query + [SEP] + Doc ──► [Encoder] ──► Score            │
    │                                                          │
    │  优点：精度高，Query 和 Doc 深度交互                       │
    │  缺点：慢，不能预计算                                      │
    └─────────────────────────────────────────────────────────┘
    
    典型流程：
    1. Bi-Encoder 快速召回 Top-100
    2. Cross-Encoder 重排序 Top-10
    """
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self.model = None
    
    def _load_model(self):
        """懒加载模型"""
        if self.model is not None:
            return
        
        try:
            from sentence_transformers import CrossEncoder
            
            logger.info(f"正在加载 Cross-Encoder 模型: {self.model_name}")
            
            self.model = CrossEncoder(
                self.model_name,
                max_length=512
            )
            
            logger.info(f"Cross-Encoder 模型加载完成: {self.model_name}")
            
        except ImportError as e:
            logger.warning(f"Cross-Encoder 依赖导入失败（可能是 sentence_transformers 或 torch 环境问题）: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Cross-Encoder 模型加载失败: {str(e)}")
            raise
    
    async def rerank(
        self, 
        query: str, 
        results: List[Dict], 
        top_k: int = 5
    ) -> List[Dict]:
        """
        使用 Cross-Encoder 重排序
        
        Args:
            query: 用户查询
            results: 检索结果列表
            top_k: 返回数量（默认 5）
        
        Returns:
            重排序后的结果列表
        """
        if not results:
            return []
        
        try:
            self._load_model()
        except Exception:
            logger.warning("Cross-Encoder 不可用，返回原始结果")
            return results[:top_k]
        
        pairs = []
        for result in results:
            doc_text = self._build_doc_text(result)
            pairs.append([query, doc_text])
        
        scores = self.model.predict(pairs)
        
        for i, result in enumerate(results):
            result["rerank_score"] = float(scores[i])
        
        results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        return results[:top_k]
    
    def _build_doc_text(self, result: Dict) -> str:
        """构建文档文本"""
        parts = []
        
        if result.get("repo_full_name"):
            parts.append(result["repo_full_name"])
        
        if result.get("section"):
            parts.append(result["section"])
        
        if result.get("summary"):
            parts.append(result["summary"])
        
        if result.get("chunk_text"):
            parts.append(result["chunk_text"])
        
        if result.get("reasons"):
            parts.extend(result["reasons"])
        
        return " ".join(parts)
