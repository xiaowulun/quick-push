"""Agent 基类"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    agent_name: Optional[str] = None


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

    def log_start(self, context: Dict[str, Any]):
        """记录任务开始"""
        repo_name = context.get("repo_name", "unknown")
        self.log("info", f"开始分析: {repo_name}")

    def log_end(self, result: AgentResult):
        """记录任务结束"""
        if result.success:
            self.log("info", f"分析完成")
        else:
            self.log("error", f"分析失败: {result.error}")

    def create_success_result(self, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> AgentResult:
        """创建成功结果"""
        return AgentResult(
            success=True,
            data=data,
            metadata=metadata,
            agent_name=self.name
        )

    def create_error_result(self, error: str) -> AgentResult:
        """创建错误结果"""
        return AgentResult(
            success=False,
            error=error,
            agent_name=self.name
        )
