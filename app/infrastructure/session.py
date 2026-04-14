"""
会话管理模块

支持多用户会话隔离，每个会话有独立的状态和历史记录
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """会话状态"""
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    last_filters: Optional[Dict] = None
    last_query_time: Optional[datetime] = None
    query_count: int = 0
    history: List[Dict] = field(default_factory=list)
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """检查会话是否过期"""
        return (datetime.now() - self.last_active) > timedelta(minutes=timeout_minutes)
    
    def touch(self):
        """更新最后活跃时间"""
        self.last_active = datetime.now()
    
    def add_to_history(self, query: str, answer: str, projects: List[Dict]):
        """添加到历史记录"""
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "answer": answer,
            "projects": projects[:3]  # 只保留前3个项目
        })
        
        if len(self.history) > 20:
            self.history = self.history[-20:]


class SessionManager:
    """
    会话管理器
    
    管理所有用户会话，支持：
    - 会话创建和获取
    - 自动过期清理
    - 会话状态隔离
    """
    
    def __init__(self, session_timeout: int = 30):
        self.sessions: Dict[str, SessionState] = {}
        self.session_timeout = session_timeout
    
    def get_or_create(self, session_id: Optional[str] = None) -> SessionState:
        """
        获取或创建会话
        
        Args:
            session_id: 会话ID，如果为None则创建新会话
        
        Returns:
            会话状态
        """
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            if not session.is_expired(self.session_timeout):
                session.touch()
                return session
        
        import uuid
        new_session_id = session_id or str(uuid.uuid4())[:8]
        
        session = SessionState(session_id=new_session_id)
        self.sessions[new_session_id] = session
        
        logger.debug(f"创建新会话: {new_session_id}")
        return session
    
    def get(self, session_id: str) -> Optional[SessionState]:
        """获取会话（不创建）"""
        session = self.sessions.get(session_id)
        if session and not session.is_expired(self.session_timeout):
            session.touch()
            return session
        return None
    
    def delete(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.debug(f"删除会话: {session_id}")
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """清理过期会话"""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_timeout)
        ]
        
        for sid in expired:
            del self.sessions[sid]
        
        if expired:
            logger.info(f"清理 {len(expired)} 个过期会话")
        
        return len(expired)
    
    def get_active_count(self) -> int:
        """获取活跃会话数"""
        return len([
            s for s in self.sessions.values()
            if not s.is_expired(self.session_timeout)
        ])


_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
