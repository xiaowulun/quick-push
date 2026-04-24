import logging
import os
import threading
from abc import ABC, abstractmethod
from typing import Dict, List

logger = logging.getLogger(__name__)


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, results: List[Dict], top_k: int = 5) -> List[Dict]:
        pass


class CrossEncoderReranker(Reranker):
    """
    Cross-Encoder reranker.

    Parameters are injected by config.py to keep env lean.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        enabled: bool = True,
        local_files_only: bool = True,
        max_length: int = 384,
        batch_size: int = 16,
    ):
        self.model_name = model_name
        self.enabled = bool(enabled)
        self.local_files_only = bool(local_files_only)
        # Keep tuning parameters in config.py.
        self.max_length = int(max_length)
        self.batch_size = int(batch_size)
        self.model = None
        self._model_lock = threading.Lock()
        self._load_failed_permanently = False
        # Runtime status for observability / evaluation.
        self.last_run_used_cross_encoder = False
        self.last_run_reason = "not_run"
        self.stats = {
            "total_calls": 0,
            "applied_calls": 0,
            "disabled_calls": 0,
            "fallback_load_error_calls": 0,
            "fallback_predict_error_calls": 0,
            "empty_input_calls": 0,
        }

    def reset_stats(self) -> None:
        self.last_run_used_cross_encoder = False
        self.last_run_reason = "not_run"
        self.stats = {
            "total_calls": 0,
            "applied_calls": 0,
            "disabled_calls": 0,
            "fallback_load_error_calls": 0,
            "fallback_predict_error_calls": 0,
            "empty_input_calls": 0,
        }
        self._load_failed_permanently = False

    def get_stats(self) -> Dict[str, int]:
        return dict(self.stats)

    def _load_model(self) -> None:
        if self.model is not None:
            return
        with self._model_lock:
            if self.model is not None:
                return

            resolved_model_name = self.model_name
            if self.local_files_only:
                # Force offline behavior to avoid long HF network retries on cold start.
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                # If model is not a local directory, require it to exist in HF cache.
                if not os.path.isdir(resolved_model_name):
                    try:
                        from huggingface_hub import try_to_load_from_cache

                        cached_config = try_to_load_from_cache(
                            repo_id=resolved_model_name,
                            filename="config.json",
                        )
                        if not cached_config:
                            raise RuntimeError(
                                f"Rerank model not found in local cache: {resolved_model_name}"
                            )
                        # Load from local snapshot directory directly to avoid any online HEAD checks.
                        resolved_model_name = os.path.dirname(cached_config)
                    except Exception as e:
                        raise RuntimeError(
                            f"Rerank local-only mode requires pre-cached model: {resolved_model_name}"
                        ) from e

            from sentence_transformers import CrossEncoder
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(
                "Load Cross-Encoder model=%s max_length=%s batch_size=%s device=%s local_files_only=%s",
                resolved_model_name,
                self.max_length,
                self.batch_size,
                device,
                self.local_files_only,
            )

            self.model = CrossEncoder(
                resolved_model_name,
                max_length=self.max_length,
                device=device,
            )

    def warmup(self) -> bool:
        """Preload model and run a tiny dry-run inference for cold-start mitigation."""
        if not self.enabled:
            return False
        if self._load_failed_permanently:
            return False
        try:
            self._load_model()
            # Tiny dry-run to initialize tokenizer/model graph path.
            _ = self.model.predict([["warmup query", "warmup doc"]], batch_size=1, show_progress_bar=False)
            return True
        except TypeError:
            try:
                _ = self.model.predict([["warmup query", "warmup doc"]])
                return True
            except Exception as e:
                logger.warning("Cross-Encoder warmup failed (fallback path): %s", str(e))
        except Exception as e:
            logger.warning("Cross-Encoder warmup failed: %s", str(e))
        self._load_failed_permanently = True
        return False

    async def rerank(self, query: str, results: List[Dict], top_k: int = 5) -> List[Dict]:
        self.stats["total_calls"] += 1

        if not results:
            self.last_run_used_cross_encoder = False
            self.last_run_reason = "empty_input"
            self.stats["empty_input_calls"] += 1
            return []

        if not self.enabled:
            logger.info("Rerank disabled; return fused results directly")
            self.last_run_used_cross_encoder = False
            self.last_run_reason = "disabled"
            self.stats["disabled_calls"] += 1
            return results[:top_k]

        if self._load_failed_permanently:
            self.last_run_used_cross_encoder = False
            self.last_run_reason = "fallback_load_error_cached"
            self.stats["fallback_load_error_calls"] += 1
            return results[:top_k]

        try:
            self._load_model()
        except Exception as e:
            logger.warning("Cross-Encoder unavailable, fallback to fused results: %s", str(e))
            self.last_run_used_cross_encoder = False
            self.last_run_reason = "fallback_load_error"
            self._load_failed_permanently = True
            self.stats["fallback_load_error_calls"] += 1
            return results[:top_k]

        pairs: List[List[str]] = []
        for result in results:
            doc_text = self._build_doc_text(result)
            pairs.append([query, doc_text])

        try:
            scores = self.model.predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False,
            )
        except TypeError:
            scores = self.model.predict(pairs)
        except Exception as e:
            logger.warning("Cross-Encoder predict failed, fallback to fused results: %s", str(e))
            self.last_run_used_cross_encoder = False
            self.last_run_reason = "fallback_predict_error"
            self.stats["fallback_predict_error_calls"] += 1
            return results[:top_k]

        for i, result in enumerate(results):
            result["rerank_score"] = float(scores[i])
            result["rerank_applied"] = True

        results.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        self.last_run_used_cross_encoder = True
        self.last_run_reason = "applied"
        self.stats["applied_calls"] += 1
        return results[:top_k]

    @staticmethod
    def _build_doc_text(result: Dict) -> str:
        parts: List[str] = []
        if result.get("repo_full_name"):
            parts.append(str(result["repo_full_name"]))
        if result.get("section"):
            parts.append(str(result["section"]))
        if result.get("summary"):
            parts.append(str(result["summary"]))
        if result.get("chunk_text"):
            parts.append(str(result["chunk_text"]))
        if result.get("reasons"):
            parts.extend([str(x) for x in result.get("reasons", [])])
        return " ".join(parts)
