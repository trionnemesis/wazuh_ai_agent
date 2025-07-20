"""
統一錯誤處理模組
提供標準化的錯誤處理機制和裝飾器
專為異步架構設計，避免任何同步阻塞操作
"""

import logging
import traceback
import functools
from typing import Any, Callable, Optional, Dict
from datetime import datetime
import asyncio

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
    統一錯誤處理裝飾器 (純異步版本)
    
    重要：此裝飾器只支援異步函數。
    在異步架構中，所有 IO 密集型操作都必須是異步的。
    
    Args:
        default_return: 發生錯誤時的默認返回值
        log_level: 日誌級別 (error, warning, info)
        reraise: 是否重新拋出異常
        error_message: 自定義錯誤消息
    """
    def decorator(func: Callable) -> Callable:
        # 檢查是否為異步函數
        if not asyncio.iscoroutinefunction(func):
            raise ValueError(
                f"Function '{func.__name__}' must be async. "
                "In this async-first architecture, all IO operations must be asynchronous. "
                "Please convert to async or use synchronous operations only for CPU-bound tasks."
            )
        
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
        
        return async_wrapper
    
    return decorator


def handle_sync_errors(
    default_return: Any = None,
    log_level: str = "error",
    reraise: bool = False,
    error_message: Optional[str] = None
):
    """
    同步錯誤處理裝飾器 - 僅用於 CPU 密集型計算
    
    警告：在這個異步優先的架構中，同步函數應該只用於：
    1. 純 CPU 密集型計算（如數據處理、加密等）
    2. 不涉及任何 IO 操作的工具函數
    
    所有涉及網路、資料庫、檔案系統的操作都必須使用異步版本。
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            raise ValueError(
                f"Function '{func.__name__}' is async but using sync error handler. "
                "Please use @handle_errors for async functions."
            )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseApplicationError as e:
                _log_error(log_level, f"{error_message or func.__name__} 失敗: {e.message}", e)
                if reraise:
                    raise
                return default_return
            except Exception as e:
                error_msg = f"{error_message or func.__name__} 發生未預期錯誤"
                _log_error(log_level, error_msg, e)
                if reraise:
                    raise BaseApplicationError(
                        message=error_msg,
                        error_code="UnexpectedError",
                        details={"original_error": str(e), "traceback": traceback.format_exc()}
                    )
                return default_return
        
        return sync_wrapper
    
    return decorator


def _log_error(level: str, message: str, exception: Exception):
    """內部日誌記錄函數"""
    log_func = getattr(logger, level, logger.error)
    log_func(f"{message}: {str(exception)}")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Traceback: {traceback.format_exc()}")


# 異步版本的錯誤上下文管理器
class AsyncErrorContext:
    """
    異步錯誤上下文管理器
    
    用於包裝異步代碼塊的錯誤處理。
    這是推薦的錯誤處理方式。
    """
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


# 為了向後相容，保留 ErrorContext 作為 AsyncErrorContext 的別名
# 但強烈建議使用 AsyncErrorContext 以明確表示異步性質
ErrorContext = AsyncErrorContext


# 輔助函數：確保異步執行
async def ensure_async(func: Callable, *args, **kwargs) -> Any:
    """
    確保函數以異步方式執行
    
    如果傳入的是同步函數，將在線程池中執行以避免阻塞事件循環。
    這應該只用於無法避免的第三方同步函數。
    """
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        # 警告：同步函數在異步環境中執行
        logger.warning(
            f"Executing sync function '{func.__name__}' in thread pool. "
            "Consider converting to async for better performance."
        )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)


# 異步重試裝飾器
def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    異步重試裝飾器
    
    Args:
        max_attempts: 最大重試次數
        delay: 初始延遲時間（秒）
        backoff: 延遲時間的倍增因子
        exceptions: 需要重試的異常類型
    """
    def decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise ValueError(f"@async_retry can only be used with async functions")
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            raise last_exception
        
        return wrapper
    
    return decorator