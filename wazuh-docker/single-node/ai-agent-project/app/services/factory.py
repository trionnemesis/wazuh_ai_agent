"""
服務工廠模式
提供統一的服務實例化和管理
"""

import os
from typing import Dict, Any, Optional, Type, TypeVar
from services.base import BaseService, ServiceError
from utils.logging_middleware import get_logger

# 服務類型變量
T = TypeVar('T', bound=BaseService)

logger = get_logger(__name__)


class ServiceFactory:
    """服務工廠類"""
    
    def __init__(self):
        self._services: Dict[str, BaseService] = {}
        self._service_classes: Dict[str, Type[BaseService]] = {}
        self._configurations: Dict[str, Dict[str, Any]] = {}
    
    def register_service(
        self,
        name: str,
        service_class: Type[T],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        註冊服務類
        
        Args:
            name: 服務名稱
            service_class: 服務類
            config: 服務配置
        """
        if name in self._service_classes:
            logger.warning(f"服務 {name} 已註冊，將被覆蓋")
        
        self._service_classes[name] = service_class
        if config:
            self._configurations[name] = config
        
        logger.info(f"註冊服務: {name} ({service_class.__name__})")
    
    async def get_service(self, name: str) -> BaseService:
        """
        獲取服務實例
        
        Args:
            name: 服務名稱
            
        Returns:
            服務實例
            
        Raises:
            ServiceError: 如果服務未註冊或初始化失敗
        """
        # 檢查服務是否已創建
        if name in self._services:
            return self._services[name]
        
        # 檢查服務是否已註冊
        if name not in self._service_classes:
            raise ServiceError(
                message=f"服務 {name} 未註冊",
                error_code="SERVICE_NOT_REGISTERED"
            )
        
        # 創建服務實例
        service_class = self._service_classes[name]
        config = self._configurations.get(name, {})
        
        try:
            service = service_class(config)
            await service.initialize()
            self._services[name] = service
            logger.info(f"創建並初始化服務: {name}")
            return service
        except Exception as e:
            logger.error(f"初始化服務 {name} 失敗: {str(e)}")
            raise ServiceError(
                message=f"初始化服務 {name} 失敗",
                error_code="SERVICE_INITIALIZATION_FAILED",
                details={"error": str(e)}
            )
    
    async def initialize_all(self) -> None:
        """初始化所有已註冊的服務"""
        for name in self._service_classes:
            if name not in self._services:
                await self.get_service(name)
    
    async def shutdown_all(self) -> None:
        """關閉所有服務"""
        for name, service in list(self._services.items()):
            try:
                await service.shutdown()
                del self._services[name]
                logger.info(f"關閉服務: {name}")
            except Exception as e:
                logger.error(f"關閉服務 {name} 失敗: {str(e)}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """獲取所有服務的狀態"""
        status = {
            "registered": list(self._service_classes.keys()),
            "initialized": list(self._services.keys()),
            "services": {}
        }
        
        for name, service in self._services.items():
            status["services"][name] = {
                "class": service.__class__.__name__,
                "initialized": service.is_initialized()
            }
        
        return status
    
    async def health_check(self) -> Dict[str, Any]:
        """執行所有服務的健康檢查"""
        results = {}
        
        for name, service in self._services.items():
            try:
                results[name] = await service.health_check()
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results


# 全局服務工廠實例
service_factory = ServiceFactory()


# 便捷函數
async def get_service(name: str) -> BaseService:
    """獲取服務的便捷函數"""
    return await service_factory.get_service(name)


def register_service(
    name: str,
    service_class: Type[BaseService],
    config: Optional[Dict[str, Any]] = None
) -> None:
    """註冊服務的便捷函數"""
    service_factory.register_service(name, service_class, config)


# 預定義的服務配置
def load_service_configurations():
    """從環境變數加載服務配置"""
    return {
        "opensearch": {
            "url": os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200"),
            "user": os.getenv("OPENSEARCH_USER", "admin"),
            "password": os.getenv("OPENSEARCH_PASSWORD", "SecretPassword"),
            "max_connections": int(os.getenv("OPENSEARCH_MAX_CONNECTIONS", "20")),
            "timeout": int(os.getenv("OPENSEARCH_TIMEOUT", "30"))
        },
        "neo4j": {
            "uri": os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            "user": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", "password"),
            "database": os.getenv("NEO4J_DATABASE", "neo4j")
        },
        "llm": {
            "provider": os.getenv("LLM_PROVIDER", "anthropic"),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "gemini_api_key": os.getenv("GEMINI_API_KEY"),
            "model": os.getenv("LLM_MODEL", "claude-3-sonnet-20240229"),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4000"))
        },
        "embedding": {
            "model": os.getenv("EMBEDDING_MODEL", "models/embedding-001"),
            "batch_size": int(os.getenv("EMBEDDING_BATCH_SIZE", "100")),
            "retry_max_attempts": int(os.getenv("EMBEDDING_RETRY_MAX_ATTEMPTS", "3"))
        }
    }