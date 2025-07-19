"""
服務基類和接口定義
提供所有服務的抽象基類和通用功能
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
from utils.error_handling import handle_errors, BaseApplicationError
from utils.logging_middleware import get_logger


class BaseService(ABC):
    """所有服務的抽象基類"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化服務
        
        Args:
            config: 服務配置字典
        """
        self.config = config or {}
        self.logger = get_logger(self.__class__.__module__)
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        初始化服務（異步）
        子類應該覆寫此方法以執行初始化邏輯
        """
        if self._initialized:
            self.logger.warning(f"{self.__class__.__name__} 已經初始化")
            return
            
        self.logger.info(f"初始化 {self.__class__.__name__}")
        await self._initialize()
        self._initialized = True
        self.logger.info(f"{self.__class__.__name__} 初始化完成")
    
    @abstractmethod
    async def _initialize(self) -> None:
        """子類必須實現的初始化方法"""
        pass
    
    async def shutdown(self) -> None:
        """
        關閉服務（異步）
        子類應該覆寫此方法以執行清理邏輯
        """
        if not self._initialized:
            return
            
        self.logger.info(f"關閉 {self.__class__.__name__}")
        await self._shutdown()
        self._initialized = False
        self.logger.info(f"{self.__class__.__name__} 已關閉")
    
    @abstractmethod
    async def _shutdown(self) -> None:
        """子類必須實現的關閉方法"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        Returns:
            包含健康狀態信息的字典
        """
        pass
    
    def is_initialized(self) -> bool:
        """檢查服務是否已初始化"""
        return self._initialized


class DataService(BaseService):
    """數據服務的基類"""
    
    @abstractmethod
    async def get(self, id: str) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取數據"""
        pass
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新數據"""
        pass
    
    @abstractmethod
    async def update(self, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新現有數據"""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """刪除數據"""
        pass
    
    @abstractmethod
    async def search(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """搜索數據"""
        pass


class ProcessingService(BaseService):
    """處理服務的基類"""
    
    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """處理數據"""
        pass
    
    @abstractmethod
    async def batch_process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量處理數據"""
        pass


class CacheableService(BaseService):
    """支持緩存的服務基類"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = self.config.get("cache_enabled", True)
        self._cache_ttl = self.config.get("cache_ttl", 3600)
    
    async def get_from_cache(self, key: str) -> Optional[Any]:
        """從緩存獲取數據"""
        if not self._cache_enabled:
            return None
        return self._cache.get(key)
    
    async def set_cache(self, key: str, value: Any) -> None:
        """設置緩存數據"""
        if self._cache_enabled:
            self._cache[key] = value
    
    async def clear_cache(self) -> None:
        """清除緩存"""
        self._cache.clear()


class ServiceError(BaseApplicationError):
    """服務相關錯誤"""
    pass


class ServiceNotInitializedError(ServiceError):
    """服務未初始化錯誤"""
    def __init__(self, service_name: str):
        super().__init__(
            message=f"服務 {service_name} 尚未初始化",
            error_code="SERVICE_NOT_INITIALIZED"
        )