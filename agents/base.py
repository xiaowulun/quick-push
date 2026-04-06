"""
Agent 基类定义
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    agent_name: str = ""

    def __post_init__(self):
        if not self.agent_name:
            self.agent_name = self.__class__.__name__


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, name: str, config: Optional[Dict] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"agents.{name}")

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        执行 Agent 任务

        Args:
            context: 任务上下文，包含项目信息、历史数据等

        Returns:
            AgentResult: 执行结果
        """
        pass

    def log_start(self, context: Dict[str, Any]):
        """记录任务开始"""
        repo_name = context.get("repo_name", "unknown")
        self.logger.info(f"[{self.name}] 开始分析项目: {repo_name}")

    def log_end(self, result: AgentResult):
        """记录任务结束"""
        status = "成功" if result.success else "失败"
        self.logger.info(f"[{self.name}] 分析完成: {status}")
        if result.error:
            self.logger.error(f"[{self.name}] 错误: {result.error}")

    def create_success_result(
        self,
        data: Dict[str, Any],
        metadata: Optional[Dict] = None
    ) -> AgentResult:
        """创建成功结果"""
        return AgentResult(
            success=True,
            data=data,
            metadata=metadata or {},
            agent_name=self.name
        )

    def create_error_result(
        self,
        error: str,
        metadata: Optional[Dict] = None
    ) -> AgentResult:
        """创建失败结果"""
        return AgentResult(
            success=False,
            error=error,
            metadata=metadata or {},
            agent_name=self.name
        )
