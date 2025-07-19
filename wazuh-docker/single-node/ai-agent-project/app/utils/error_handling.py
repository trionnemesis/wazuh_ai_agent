"""
統一錯誤處理模組
提供標準化的錯誤處理機制和裝飾器
"""

import logging
import traceback
import functools
from typing import Any, Callable, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseApplicationError(Exception):
    """應用程式基礎錯誤類"""
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()


class OpenSearchError(BaseApplicationError):
    """OpenSearch 相關錯誤"""
    pass


class Neo4jError(BaseApplicationError):
    """Neo4j 相關錯誤"""
    pass


class LLMError(BaseApplicationError):
    """大型語言模型相關錯誤"""
    pass


class EmbeddingError(BaseApplicationError):
    """向量嵌入相關錯誤"""
    pass


class ValidationError(BaseApplicationError):
    """數據驗證錯誤"""
    pass


class ConfigurationError(BaseApplicationError):
    """配置錯誤"""
    pass


def handle_errors(
    default_return: Any = None,
    log_level: str = "error",
    reraise: bool = False,
    error_message: Optional[str] = None
):
    """
    統一錯誤處理裝飾器
    
    Args:
        default_return: 發生錯誤時的默認返回值
        log_level: 日誌級別 (error, warning, info)
        reraise: 是否重新拋出異常
        error_message: 自定義錯誤消息
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except BaseApplicationError as e:
                # 處理已知的應用程式錯誤
                _log_error(log_level, f"{error_message or func.__name__} 失敗: {e.message}", e)
                if reraise:
                    raise
                return default_return
            except Exception as e:
                # 處理未知錯誤
                error_msg = f"{error_message or func.__name__} 發生未預期錯誤"
                _log_error(log_level, error_msg, e)
                if reraise:
                    raise BaseApplicationError(
                        message=error_msg,
                        error_code="UnexpectedError",
                        details={"original_error": str(e), "traceback": traceback.format_exc()}
                    )
                return default_return
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseApplicationError as e:
                # 處理已知的應用程式錯誤
                _log_error(log_level, f"{error_message or func.__name__} 失敗: {e.message}", e)
                if reraise:
                    raise
                return default_return
            except Exception as e:
                # 處理未知錯誤
                error_msg = f"{error_message or func.__name__} 發生未預期錯誤"
                _log_error(log_level, error_msg, e)
                if reraise:
                    raise BaseApplicationError(
                        message=error_msg,
                        error_code="UnexpectedError",
                        details={"original_error": str(e), "traceback": traceback.format_exc()}
                    )
                return default_return
        
        # 根據函數類型返回相應的包裝器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def _log_error(level: str, message: str, exception: Exception):
    """內部日誌記錄函數"""
    log_func = getattr(logger, level, logger.error)
    log_func(f"{message}: {str(exception)}")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Traceback: {traceback.format_exc()}")


class ErrorContext:
    """錯誤上下文管理器"""
    def __init__(self, operation: str, reraise: bool = True):
        self.operation = operation
        self.reraise = reraise
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
            
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        if isinstance(exc_val, BaseApplicationError):
            logger.error(f"{self.operation} 失敗 (耗時 {duration:.2f}s): {exc_val.message}")
        else:
            logger.error(
                f"{self.operation} 發生未預期錯誤 (耗時 {duration:.2f}s): {str(exc_val)}",
                exc_info=True
            )
            
        return not self.reraise


# 異步版本的錯誤上下文管理器
class AsyncErrorContext:
    """異步錯誤上下文管理器"""
    def __init__(self, operation: str, reraise: bool = True):
        self.operation = operation
        self.reraise = reraise
        self.start_time = None
        
    async def __aenter__(self):
        self.start_time = datetime.utcnow()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
            
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        if isinstance(exc_val, BaseApplicationError):
            logger.error(f"{self.operation} 失敗 (耗時 {duration:.2f}s): {exc_val.message}")
        else:
            logger.error(
                f"{self.operation} 發生未預期錯誤 (耗時 {duration:.2f}s): {str(exc_val)}",
                exc_info=True
            )
            
        return not self.reraise


# 導入必要的模組
import asyncio