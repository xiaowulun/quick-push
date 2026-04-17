import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class OpenAIConfig(BaseModel):
    api_key: str = Field(description="OpenAI API Key")
    base_url: str = Field(default="https://api.siliconflow.cn/v1", description="API Base URL")
    request_timeout: int = Field(default=90, description="OpenAI 请求超时时间（秒）")
    model_fast: str = Field(default="Qwen/Qwen2.5-7B-Instruct", description="快速分析模型")
    model_standard: str = Field(default="Qwen/Qwen3-VL-32B-Thinking", description="标准分析模型")
    model_pro: str = Field(default="Qwen/Qwen-Max", description="深度分析模型")
    model_chat: str = Field(default="Qwen/Qwen-32B-Chat", description="对话模型")
    model_fallback: str = Field(default="Qwen/Qwen2.5-14B-Instruct", description="备用模型")


class GitHubConfig(BaseModel):
    token: str = Field(default="", description="GitHub Token")
    api_base: str = Field(default="https://api.github.com", description="GitHub API Base URL")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    rate_limit: int = Field(default=10, description="API 限流（每秒请求数）")


class FeishuConfig(BaseModel):
    app_id: Optional[str] = Field(default=None, description="飞书 App ID")
    app_secret: Optional[str] = Field(default=None, description="飞书 App Secret")
    receive_id: Optional[str] = Field(default=None, description="接收消息的用户 ID 或群 ID")
    receive_id_type: str = Field(default="chat_id", description="接收 ID 类型")


class MultimodalConfig(BaseModel):
    max_chars: int = Field(default=3000, description="README 最大字符数")
    max_images: int = Field(default=3, description="最大图片数量")
    enable_multimodal: bool = Field(default=True, description="是否启用多模态输入")


class BehaviorConfig(BaseModel):
    max_retries: int = Field(default=3, description="LLM 调用最大重试次数")
    max_concurrency: int = Field(default=3, description="最大并发数")


class RedditConfig(BaseModel):
    cookie: Optional[str] = Field(default=None, description="Reddit Cookie")
    enabled: bool = Field(default=True, description="是否启用 Reddit 检索")
    timeout: int = Field(default=30, description="Playwright 超时时间（秒）")


class Config:
    openai: OpenAIConfig
    github: GitHubConfig
    feishu: FeishuConfig
    behavior: BehaviorConfig
    multimodal: MultimodalConfig
    reddit: RedditConfig

    def __init__(self):
        self.openai = OpenAIConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
            request_timeout=int(os.getenv("OPENAI_REQUEST_TIMEOUT", "90")),
            model_fast=os.getenv("OPENAI_MODEL_FAST", "Qwen/Qwen2.5-7B-Instruct"),
            model_standard=os.getenv("OPENAI_MODEL_STANDARD", "Qwen/Qwen3-VL-32B-Thinking"),
            model_pro=os.getenv("OPENAI_MODEL_PRO", "Qwen/Qwen-Max"),
            model_chat=os.getenv("OPENAI_MODEL_CHAT", "Qwen/Qwen-32B-Chat"),
            model_fallback=os.getenv("OPENAI_MODEL_FALLBACK", "Qwen/Qwen2.5-14B-Instruct"),
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
        self.multimodal = MultimodalConfig(
            max_chars=int(os.getenv("MULTIMODAL_MAX_CHARS", "3000")),
            max_images=int(os.getenv("MULTIMODAL_MAX_IMAGES", "3")),
            enable_multimodal=os.getenv("MULTIMODAL_ENABLE", "false").lower() == "true",
        )
        self.reddit = RedditConfig(
            cookie=os.getenv("REDDIT_COOKIE"),
            enabled=os.getenv("REDDIT_ENABLED", "true").lower() == "true",
            timeout=int(os.getenv("REDDIT_TIMEOUT", "30")),
        )

    def validate(self) -> list[str]:
        errors = []

        if not self.openai.api_key:
            errors.append("OPENAI_API_KEY 未设置")

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
            raise ValueError(f"配置验证失败：{', '.join(errors)}")
    return _config


def reset_config() -> None:
    global _config
    _config = None


def get_model_for_task(task_type: str) -> str:
    """
    根据任务类型返回模型名称
    
    Args:
        task_type: 任务类型
            - "fast": 快速分析（分类、关键词提取）
            - "standard": 标准分析（Multi-Agent）
            - "pro": 深度分析（复杂推理）
            - "chat": 对话（RAG 问答）
            - "fallback": 备用模型
    
    Returns:
        str: 模型名称
    """
    config = get_config()
    model_map = {
        "fast": config.openai.model_fast,
        "standard": config.openai.model_standard,
        "pro": config.openai.model_pro,
        "chat": config.openai.model_chat,
        "fallback": config.openai.model_fallback,
    }
    return model_map.get(task_type, config.openai.model_standard)
