"""
統一的日誌和監控中間件
提供結構化日誌、請求追蹤和效能監控
"""

import time
import uuid
import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from contextvars import ContextVar
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge

# 設置日誌格式
class StructuredFormatter(logging.Formatter):
    """結構化日誌格式化器"""
    
    def format(self, record):
        # 基本日誌資訊
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加請求追蹤 ID（如果存在）
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        # 添加額外的上下文資訊
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # 添加異常資訊（如果存在）
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


# 請求追蹤 ID 的上下文變數
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """請求日誌和追蹤中間件"""
    
    def __init__(self, app, logger_name: str = "api.requests"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
        
        # Prometheus 指標
        self.request_count = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"]
        )
        
        self.request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"]
        )
        
        self.active_requests = Gauge(
            "http_requests_active",
            "Active HTTP requests"
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成請求追蹤 ID
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        
        # 記錄請求開始
        start_time = time.time()
        self.active_requests.inc()
        
        # 提取請求資訊
        request_info = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", "")
        }
        
        # 記錄請求
        self.logger.info(
            "Request started",
            extra={"extra_fields": request_info}
        )
        
        try:
            # 處理請求
            response = await call_next(request)
            
            # 計算處理時間
            duration = time.time() - start_time
            
            # 更新指標
            self.request_count.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            
            self.request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            # 記錄響應
            response_info = {
                **request_info,
                "status_code": response.status_code,
                "duration_seconds": duration
            }
            
            self.logger.info(
                "Request completed",
                extra={"extra_fields": response_info}
            )
            
            # 添加追蹤 ID 到響應頭
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # 記錄錯誤
            duration = time.time() - start_time
            
            error_info = {
                **request_info,
                "duration_seconds": duration,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            self.logger.error(
                "Request failed",
                extra={"extra_fields": error_info},
                exc_info=True
            )
            
            # 更新錯誤指標
            self.request_count.labels(
                method=request.method,
                endpoint=request.url.path,
                status=500
            ).inc()
            
            raise
            
        finally:
            self.active_requests.dec()
            request_id_var.set(None)


class ContextLogger:
    """帶上下文的日誌記錄器"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _log(self, level: str, message: str, **kwargs):
        """內部日誌方法"""
        extra_fields = kwargs.copy()
        
        # 添加請求 ID（如果存在）
        request_id = request_id_var.get()
        if request_id:
            extra_fields["request_id"] = request_id
        
        # 獲取日誌方法
        log_method = getattr(self.logger, level)
        
        # 記錄日誌
        log_method(
            message,
            extra={"extra_fields": extra_fields}
        )
    
    def debug(self, message: str, **kwargs):
        """DEBUG 級別日誌"""
        self._log("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """INFO 級別日誌"""
        self._log("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """WARNING 級別日誌"""
        self._log("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """ERROR 級別日誌"""
        self._log("error", message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """CRITICAL 級別日誌"""
        self._log("critical", message, **kwargs)


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None
):
    """
    設置統一的日誌配置
    
    Args:
        log_level: 日誌級別
        log_format: 日誌格式 (json 或 plain)
        log_file: 日誌文件路徑（可選）
    """
    # 設置根日誌記錄器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除現有的處理器
    root_logger.handlers.clear()
    
    # 創建格式化器
    if log_format == "json":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    # 添加控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加文件處理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> ContextLogger:
    """
    獲取帶上下文的日誌記錄器
    
    Args:
        name: 日誌記錄器名稱
        
    Returns:
        ContextLogger 實例
    """
    return ContextLogger(logging.getLogger(name))


# 預定義的日誌記錄器
api_logger = get_logger("api")
service_logger = get_logger("service")
database_logger = get_logger("database")