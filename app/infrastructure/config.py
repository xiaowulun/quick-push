import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


MODEL_EASY_DEFAULT = "Qwen/Qwen3-32B"
MODEL_MEDIUM_DEFAULT = "Pro/MiniMaxAI/MiniMax-M2.5"
MODEL_HARD_DEFAULT = "Pro/deepseek-ai/DeepSeek-V3"
ALLOWED_CHAT_MODELS = {MODEL_EASY_DEFAULT, MODEL_MEDIUM_DEFAULT, MODEL_HARD_DEFAULT}


def normalize_model_name(raw_name: str) -> str:
    return str(raw_name or "").strip()


class OpenAIConfig(BaseModel):
    api_key: str = Field(description="OpenAI API Key")
    base_url: str = Field(default="https://api.siliconflow.cn/v1", description="API Base URL")
    request_timeout: int = Field(default=90, description="OpenAI request timeout (seconds)")
    model_easy: str = Field(default=MODEL_EASY_DEFAULT, description="Low-latency model for simple tasks")
    model_medium: str = Field(default=MODEL_MEDIUM_DEFAULT, description="Balanced model for most chat tasks")
    model_hard: str = Field(default=MODEL_HARD_DEFAULT, description="High-capability model for hard tasks")

    # Backward-compatible aliases.
    @property
    def model_fast(self) -> str:
        return self.model_easy

    @property
    def model_chat(self) -> str:
        return self.model_medium

    @property
    def model_standard(self) -> str:
        return self.model_medium

    @property
    def model_pro(self) -> str:
        return self.model_hard

    @property
    def model_fallback(self) -> str:
        return self.model_easy


class GitHubConfig(BaseModel):
    token: str = Field(default="", description="GitHub token")
    api_base: str = Field(default="https://api.github.com", description="GitHub API base URL")
    max_retries: int = Field(default=3, description="Max retries")
    timeout: int = Field(default=30, description="Request timeout (seconds)")
    rate_limit: int = Field(default=10, description="Rate limit (req/s)")


class FeishuConfig(BaseModel):
    app_id: Optional[str] = Field(default=None, description="Feishu App ID")
    app_secret: Optional[str] = Field(default=None, description="Feishu App Secret")
    receive_id: Optional[str] = Field(default=None, description="Message receiver ID")
    receive_id_type: str = Field(default="chat_id", description="Receiver ID type")


class MultimodalConfig(BaseModel):
    max_chars: int = Field(default=3000, description="Max README chars")
    max_images: int = Field(default=3, description="Max image count")
    enable_multimodal: bool = Field(default=True, description="Enable multimodal input")


class BehaviorConfig(BaseModel):
    max_retries: int = Field(default=3, description="Max LLM retries")
    max_concurrency: int = Field(default=3, description="Max concurrency")


class RetrievalConfig(BaseModel):
    # Keep common retrieval/rerank tuning in code config to avoid .env clutter.
    rerank_enabled: bool = Field(default=True, description="Enable rerank")
    rerank_model_name: str = Field(default="BAAI/bge-reranker-base", description="Rerank model")
    rerank_warmup_on_start: bool = Field(default=True, description="Warm up reranker on service startup")
    search_max_variants: int = Field(default=2, description="Max query variants")
    search_coarse_multiplier: int = Field(default=4, description="Coarse recall multiplier")
    search_fused_multiplier: int = Field(default=8, description="Fused pool multiplier")
    search_parallel_variants: bool = Field(default=True, description="Parallelize variant retrieval")
    rerank_top_k_cap: int = Field(default=12, description="Rerank pool cap")
    rerank_multiplier: int = Field(default=4, description="Rerank pool multiplier")
    rerank_min_pool: int = Field(default=8, description="Rerank min pool")
    rerank_local_files_only: bool = Field(default=True, description="Use local rerank files only")
    rerank_max_length: int = Field(default=384, description="Rerank max length")
    rerank_batch_size: int = Field(default=16, description="Rerank batch size")


class RAGChatConfig(BaseModel):
    max_tokens: int = Field(default=1200, description="RAG response max tokens")

class Config:
    openai: OpenAIConfig
    github: GitHubConfig
    feishu: FeishuConfig
    behavior: BehaviorConfig
    retrieval: RetrievalConfig
    rag_chat: RAGChatConfig
    multimodal: MultimodalConfig

    def __init__(self):
        def _env(name: str, default: str = "") -> str:
            return str(os.getenv(name, default)).strip()

        def _model_env(primary: str, legacy: str, default: str) -> str:
            raw = _env(primary, _env(legacy, default))
            normalized = normalize_model_name(raw)
            if normalized in ALLOWED_CHAT_MODELS:
                return normalized
            return default

        self.openai = OpenAIConfig(
            api_key=_env("OPENAI_API_KEY", ""),
            base_url=_env("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
            request_timeout=int(os.getenv("OPENAI_REQUEST_TIMEOUT", "90")),
            model_easy=_model_env("OPENAI_MODEL_EASY", "OPENAI_MODEL_FAST", MODEL_EASY_DEFAULT),
            model_medium=_model_env("OPENAI_MODEL_MEDIUM", "OPENAI_MODEL_CHAT", MODEL_MEDIUM_DEFAULT),
            model_hard=_model_env("OPENAI_MODEL_HARD", "OPENAI_MODEL_PRO", MODEL_HARD_DEFAULT),
        )

        self.github = GitHubConfig(
            token=os.getenv("GITHUB_TOKEN", ""),
            api_base=os.getenv("GITHUB_API_BASE", "https://api.github.com"),
            rate_limit=int(os.getenv("GITHUB_RATE_LIMIT", "10")),
        )

        self.feishu = FeishuConfig(
            app_id=os.getenv("FEISHU_APP_ID"),
            app_secret=os.getenv("FEISHU_APP_SECRET"),
            receive_id=os.getenv("FEISHU_RECEIVE_ID"),
            receive_id_type=os.getenv("FEISHU_RECEIVE_ID_TYPE", "chat_id"),
        )

        self.behavior = BehaviorConfig(
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            max_concurrency=int(os.getenv("MAX_CONCURRENCY", "3")),
        )

        # Only keep rerank model name override in .env. Other knobs stay in code.
        self.retrieval = RetrievalConfig(
            rerank_model_name=os.getenv("RERANK_MODEL_NAME", "BAAI/bge-reranker-base"),
        )
        self.rag_chat = RAGChatConfig()

        self.multimodal = MultimodalConfig(
            max_chars=int(os.getenv("MULTIMODAL_MAX_CHARS", "3000")),
            max_images=int(os.getenv("MULTIMODAL_MAX_IMAGES", "3")),
            enable_multimodal=os.getenv("MULTIMODAL_ENABLE", "false").lower() == "true",
        )

    def validate(self) -> list[str]:
        errors = []

        if not self.openai.api_key:
            errors.append("OPENAI_API_KEY not set")

        return errors

    def is_feishu_configured(self) -> bool:
        return bool(self.feishu.app_id and self.feishu.app_secret and self.feishu.receive_id)


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
        errors = _config.validate()
        if errors:
            raise ValueError(f"Config validation failed: {', '.join(errors)}")
    return _config


def reset_config() -> None:
    global _config
    _config = None


def get_model_for_task(task_type: str) -> str:
    """Return model name by task difficulty/task type."""
    config = get_config()
    t = str(task_type or "").strip().lower()
    if t in {"easy", "fast", "parse", "parser", "classify", "classifier", "rewrite", "fallback"}:
        return config.openai.model_easy
    if t in {"hard", "pro", "deep", "analyst", "editor"}:
        return config.openai.model_hard
    return config.openai.model_medium
