"""Agent 基类"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from app.infrastructure.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        config = get_config()
        self.max_retries = config.behavior.max_retries
        self.timeout = 60.0

    @abstractmethod
    async def execute(self, **kwargs) -> AgentResult:
        """执行 Agent 任务"""
        pass

    def log(self, level: str, message: str):
        """日志记录"""
        getattr(logger, level)(f"[{self.name}] {message}")
