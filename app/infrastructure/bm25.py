"""
BM25 关键词检索模块

使用 rank-bm25 库实现 BM25 检索，支持中英文混合分词
"""

import logging
from typing import List, Dict
import re

logger = logging.getLogger(__name__)


class BM25SearchEngine:
    """BM25 搜索引擎（基于 rank-bm25，支持中文分词）"""
    
    def __init__(self):
        self.bm25 = None
        self.documents = []
        self.corpus = []
        self._jieba_initialized = False
    
    def _init_jieba(self):
        """初始化 jieba 分词器"""
        if self._jieba_initialized:
            return
        
        try:
            import jieba
            jieba.initialize()
            self._jieba_initialized = True
            logger.info("jieba 分词器初始化完成")
        except ImportError:
            logger.warning("jieba 未安装，将使用简单分词")
            self._jieba_initialized = False
    
    def build_index(self, documents: List[Dict]) -> None:
        """构建索引"""
        from rank_bm25 import BM25Okapi
        
        self._init_jieba()
        self.documents = documents
        self.corpus = []
        
        for doc in documents:
            search_text = doc.get("search_text", "")
            repo_name = doc.get("repo_full_name", "")
            summary = doc.get("summary", "")
            reasons = " ".join(doc.get("reasons", []))
            language = doc.get("language", "")
            keywords = " ".join(doc.get("keywords", []))
            tech_stack = " ".join(doc.get("tech_stack", []))
            
            text = f"{repo_name} {search_text} {summary} {reasons} {language} {keywords} {tech_stack}"
            tokens = self._tokenize(text)
            self.corpus.append(tokens)
        
        if self.corpus:
            self.bm25 = BM25Okapi(self.corpus)
            logger.info(f"BM25 索引构建完成，共 {len(documents)} 个文档")
        else:
            logger.warning("BM25 索引构建：文档为空")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        智能分词（支持中英文混合）
        
        策略：
        1. 中文：使用 jieba 分词
        2. 英文：按空格分割，保留技术术语
        3. 过滤停用词和短词
        """
        if not text:
            return []
        
        STOPWORDS = {
            "的", "是", "在", "有", "和", "了", "与", "及", "等", "为",
            "对", "这", "那", "我", "你", "他", "她", "它", "们",
            "一个", "可以", "使用", "进行", "通过", "支持", "提供",
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once"
        }
        
        TECH_TERMS = {
            "python", "javascript", "typescript", "java", "golang", "rust",
            "react", "vue", "angular", "nodejs", "django", "flask", "fastapi",
            "docker", "kubernetes", "k8s", "api", "sdk", "cli", "gui",
            "ai", "ml", "dl", "nlp", "cv", "llm", "gpt", "bert", "transformer",
            "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
            "linux", "windows", "macos", "ios", "android", "web", "app"
        }
        
        tokens = []
        
        if self._jieba_initialized:
            import jieba
            
            chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
            chinese_matches = chinese_pattern.findall(text)
            
            english_text = chinese_pattern.sub(' ', text)
            
            for chinese_part in chinese_matches:
                words = jieba.lcut(chinese_part)
                for word in words:
                    word = word.strip().lower()
                    if len(word) >= 2 and word not in STOPWORDS:
                        tokens.append(word)
            
            english_words = re.findall(r'[a-zA-Z][a-zA-Z0-9_-]*', english_text)
            for word in english_words:
                word = word.lower()
                if word in TECH_TERMS or len(word) >= 3:
                    if word not in STOPWORDS:
                        tokens.append(word)
        else:
            words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z][a-zA-Z0-9_-]*', text)
            for word in words:
                word = word.lower()
                if len(word) >= 2 and word not in STOPWORDS:
                    tokens.append(word)
        
        return tokens
    
    def search(
        self, 
        query: str, 
        top_k: int = 10
    ) -> List[Dict]:
        """搜索"""
        if not self.bm25 or not self.documents:
            return []
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        scores = self.bm25.get_scores(query_tokens)
        
        doc_scores = list(enumerate(scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for doc_idx, score in doc_scores[:top_k]:
            doc = self.documents[doc_idx].copy()
            doc["bm25_score"] = float(score)
            results.append(doc)
        
        return results
