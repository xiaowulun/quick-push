"""
重试工具模块

提供统一的重试机制，支持指数退避和自定义重试策略
"""

import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    指数退避重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数基数
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
    
    Returns:
        装饰后的函数
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=2.0)
        def fetch_data():
            return requests.get("https://api.example.com/data")
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} 重试 {max_retries} 次后仍失败: {str(e)}")
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    logger.warning(f"{func.__name__} 第 {attempt + 1} 次失败: {str(e)}，{delay:.1f} 秒后重试")
                    
                    if on_retry:
                        on_retry(attempt, e, delay)
                    
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_backoff_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    异步指数退避重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数基数
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
    
    Returns:
        装饰后的异步函数
    """
    import asyncio
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} 重试 {max_retries} 次后仍失败: {str(e)}")
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    logger.warning(f"{func.__name__} 第 {attempt + 1} 次失败: {str(e)}，{delay:.1f} 秒后重试")
                    
                    if on_retry:
                        await on_retry(attempt, e, delay)
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_fallback(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    fallback_value=None
):
    """
    带默认返回值的重试装饰器
    
    重试失败后返回 fallback_value 而不是抛出异常
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数基数
        exceptions: 需要重试的异常类型
        fallback_value: 失败后的默认返回值
    
    Returns:
        装饰后的函数
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} 重试 {max_retries} 次后仍失败，返回默认值: {str(e)}")
                        return fallback_value
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    logger.warning(f"{func.__name__} 第 {attempt + 1} 次失败: {str(e)}，{delay:.1f} 秒后重试")
                    time.sleep(delay)
            
            return fallback_value
        
        return wrapper
    return decorator
