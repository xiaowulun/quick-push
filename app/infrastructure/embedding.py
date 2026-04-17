import asyncio
import logging
from typing import List, Optional

import numpy as np
from openai import OpenAI

from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Text embedding engine."""

    def __init__(self):
        self.config = get_config()
        self.client = OpenAI(
            api_key=self.config.openai.api_key,
            base_url=self.config.openai.base_url,
        )
        self.model = "BAAI/bge-large-zh-v1.5"
        self.dimension = 1024
        self.max_retries = max(1, int(getattr(self.config.behavior, "max_retries", 3)))
        self.base_retry_delay = 1.5
        self.max_batch_size = 32

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """Embed a single text with retry."""
        if not text or not text.strip():
            logger.warning("Text is empty, skip embedding")
            return None

        text = text.strip()
        text_len = len(text)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=text,
                    encoding_format="float",
                )
                embedding = response.data[0].embedding
                logger.info(
                    "Embedding success model=%s dim=%s len=%s attempt=%s/%s",
                    self.model,
                    len(embedding),
                    text_len,
                    attempt,
                    self.max_retries,
                )
                return embedding
            except Exception as e:
                if attempt >= self.max_retries:
                    logger.error(
                        "Embedding failed model=%s len=%s attempts=%s error_type=%s error=%s",
                        self.model,
                        text_len,
                        self.max_retries,
                        type(e).__name__,
                        str(e),
                    )
                    return None

                delay = self.base_retry_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Embedding retry model=%s len=%s attempt=%s/%s wait=%.1fs error_type=%s error=%s",
                    self.model,
                    text_len,
                    attempt,
                    self.max_retries,
                    delay,
                    type(e).__name__,
                    str(e),
                )
                await asyncio.sleep(delay)

        return None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Embed texts in chunks to avoid provider batch-size limits."""
        if not texts:
            return []

        valid_positions = [i for i, t in enumerate(texts) if t and t.strip()]
        if not valid_positions:
            return [None] * len(texts)

        valid_texts = [texts[i].strip() for i in valid_positions]
        result: List[Optional[List[float]]] = [None] * len(texts)

        total_chunks = (len(valid_texts) + self.max_batch_size - 1) // self.max_batch_size
        success_chunks = 0

        for chunk_idx in range(total_chunks):
            start = chunk_idx * self.max_batch_size
            end = min(start + self.max_batch_size, len(valid_texts))
            chunk_texts = valid_texts[start:end]
            chunk_positions = valid_positions[start:end]

            chunk_embeddings: Optional[List[List[float]]] = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=chunk_texts,
                        encoding_format="float",
                    )
                    chunk_embeddings = [data.embedding for data in response.data]
                    break
                except Exception as e:
                    if attempt >= self.max_retries:
                        logger.error(
                            "Batch embedding failed model=%s chunk=%s/%s batch=%s attempts=%s error_type=%s error=%s",
                            self.model,
                            chunk_idx + 1,
                            total_chunks,
                            len(chunk_texts),
                            self.max_retries,
                            type(e).__name__,
                            str(e),
                        )
                        chunk_embeddings = None
                        break

                    delay = self.base_retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Batch embedding retry model=%s chunk=%s/%s batch=%s attempt=%s/%s wait=%.1fs error_type=%s error=%s",
                        self.model,
                        chunk_idx + 1,
                        total_chunks,
                        len(chunk_texts),
                        attempt,
                        self.max_retries,
                        delay,
                        type(e).__name__,
                        str(e),
                    )
                    await asyncio.sleep(delay)

            if chunk_embeddings and len(chunk_embeddings) == len(chunk_positions):
                for pos, emb in zip(chunk_positions, chunk_embeddings):
                    result[pos] = emb
                success_chunks += 1

        missing_count = sum(1 for v in result if v is None)
        logger.info(
            "Batch embedding completed model=%s total=%s chunks=%s/%s missing=%s",
            self.model,
            len(valid_texts),
            success_chunks,
            total_chunks,
            missing_count,
        )
        return result

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
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
            logger.error("Cosine similarity failed: %s", str(e))
            return 0.0

    @staticmethod
    def batch_cosine_similarity(query_vec: List[float], vectors: List[List[float]]) -> List[float]:
        """Calculate cosine similarity between one query and multiple vectors."""
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
            logger.error("Batch cosine similarity failed: %s", str(e))
            return [0.0] * len(vectors)
