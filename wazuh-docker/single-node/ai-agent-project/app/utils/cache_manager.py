"""
快取管理器工具模組
提供全域快取服務的管理和配置
"""

import logging
from typing import Optional
from ..services.cache_service import CacheService, init_cache_service

logger = logging.getLogger(__name__)

# 全域快取服務實例
_cache_service: Optional[CacheService] = None

def get_cache_service() -> Optional[CacheService]:
    """
    獲取全域快取服務實例
    
    Returns:
        CacheService 實例或 None
    """
    global _cache_service
    return _cache_service

def initialize_cache_service(
    lru_maxsize: int = 1000,
    ttl_maxsize: int = 500,
    ttl_seconds: int = 3600,
    enable_cache: bool = True
) -> Optional[CacheService]:
    """
    初始化全域快取服務
    
    Args:
        lru_maxsize: LRU 快取最大容量
        ttl_maxsize: TTL 快取最大容量
        ttl_seconds: TTL 快取過期時間（秒）
        enable_cache: 是否啟用快取
        
    Returns:
        CacheService 實例或 None
    """
    global _cache_service
    
    if not enable_cache:
        logger.info("快取功能已停用")
        _cache_service = None
        return None
    
    try:
        _cache_service = init_cache_service(
            lru_maxsize=lru_maxsize,
            ttl_maxsize=ttl_maxsize,
            ttl_seconds=ttl_seconds
        )
        logger.info("快取管理器初始化成功")
        return _cache_service
    except Exception as e:
        logger.error(f"快取管理器初始化失敗: {str(e)}")
        _cache_service = None
        return None

def get_cache_stats():
    """
    獲取快取統計資訊
    
    Returns:
        統計資訊字典或空字典
    """
    if _cache_service:
        return _cache_service.get_stats()
    return {}

def clear_all_caches():
    """清除所有快取"""
    if _cache_service:
        _cache_service.clear_cache()
        logger.info("所有快取已清除")

def is_cache_enabled() -> bool:
    """檢查快取是否已啟用"""
    return _cache_service is not None