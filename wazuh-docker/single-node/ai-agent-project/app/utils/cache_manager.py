
"""
快取管理器工具模組
提供全域快取服務的管理和配置
"""

import os
import logging
import hashlib
import time
from typing import Optional, Any, Dict, List, Callable, Union
from functools import wraps
from cachetools import TTLCache
import asyncio

from ..services.cache_service import CacheService, init_cache_service

logger = logging.getLogger(__name__)

# 全域快取服務實例
_cache_service: Optional[CacheService] = None
_global_cache_manager: Optional['CacheManager'] = None


class CacheManager:
    """
    專門為嵌入向量設計的快取管理器
    
    使用 TTL (Time To Live) 快取策略，支援：
    - 單一查詢快取
    - 批次查詢快取（支援部分命中）
    - 快取統計追蹤
    - 可配置的快取大小和過期時間
    """
    
    def __init__(self, maxsize: int = 1000, ttl: int = 3600, enabled: bool = True):
        """
        初始化快取管理器
        
        Args:
            maxsize: 快取最大容量
            ttl: 快取過期時間（秒）
            enabled: 是否啟用快取
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.enabled = enabled
        
        # 初始化 TTL 快取
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl) if enabled else {}
        
        # 統計資訊
        self.stats = {
            "hits": 0,
            "misses": 0,
            "partial_hits": 0,
            "total_requests": 0
        }
        
        logger.info(f"CacheManager 初始化: maxsize={maxsize}, ttl={ttl}s, enabled={enabled}")
    
    def _generate_cache_key(self, content: str, prefix: str = "") -> str:
        """
        生成快取鍵值
        
        Args:
            content: 快取內容
            prefix: 鍵值前綴
            
        Returns:
            快取鍵值
        """
        hash_value = hashlib.md5(content.encode()).hexdigest()
        return f"{prefix}:{hash_value}" if prefix else hash_value
    
    def get(self, key: str) -> Optional[Any]:
        """獲取快取值"""
        if not self.enabled:
            return None
            
        value = self.cache.get(key)
        if value is not None:
            self.stats["hits"] += 1
        else:
            self.stats["misses"] += 1
        self.stats["total_requests"] += 1
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """設置快取值"""
        if self.enabled:
            self.cache[key] = value
    
    def get_batch(self, keys: List[str]) -> Dict[str, Any]:
        """
        批次獲取快取值
        
        Args:
            keys: 鍵值列表
            
        Returns:
            找到的鍵值對字典
        """
        if not self.enabled:
            return {}
            
        results = {}
        hits = 0
        
        for key in keys:
            value = self.cache.get(key)
            if value is not None:
                results[key] = value
                hits += 1
        
        # 更新統計
        self.stats["total_requests"] += len(keys)
        self.stats["hits"] += hits
        self.stats["misses"] += len(keys) - hits
        
        if hits > 0 and hits < len(keys):
            self.stats["partial_hits"] += 1
            
        return results
    
    def set_batch(self, items: Dict[str, Any]) -> None:
        """批次設置快取值"""
        if self.enabled:
            for key, value in items.items():
                self.cache[key] = value
    
    def clear(self) -> None:
        """清除所有快取"""
        if self.enabled:
            self.cache.clear()
            logger.info("快取已清除")
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計資訊"""
        hit_rate = 0
        if self.stats["total_requests"] > 0:
            hit_rate = (self.stats["hits"] / self.stats["total_requests"]) * 100
            
        return {
            "hit_rate": f"{hit_rate:.2f}%",
            "size": len(self.cache),
            "maxsize": self.maxsize,
            "ttl": self.ttl,
            "enabled": self.enabled,
            **self.stats
        }
    
    def reset_stats(self) -> None:
        """重置統計資訊"""
        self.stats = {
            "hits": 0,
            "misses": 0,
            "partial_hits": 0,
            "total_requests": 0
        }


def embedding_cache(cache_manager: CacheManager, prefix: str = "embed"):
    """
    嵌入向量快取裝飾器（單一查詢）
    
    Args:
        cache_manager: CacheManager 實例
        prefix: 快取鍵值前綴
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, text: str) -> List[float]:
            if not cache_manager.enabled:
                return await func(self, text)
            
            # 生成快取鍵值
            cache_key = cache_manager._generate_cache_key(text, prefix)
            
            # 檢查快取
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"快取命中: {cache_key[:16]}...")
                return cached_value
            
            # 計算新值
            start_time = time.time()
            result = await func(self, text)
            compute_time = (time.time() - start_time) * 1000
            
            # 存入快取
            cache_manager.set(cache_key, result)
            logger.debug(f"快取儲存: {cache_key[:16]}... (計算耗時: {compute_time:.2f}ms)")
            
            return result
        
        return wrapper
    return decorator


def batch_embedding_cache(cache_manager: CacheManager, prefix: str = "batch"):
    """
    批次嵌入向量快取裝飾器
    
    支援部分快取命中，只對未快取的項目進行計算
    
    Args:
        cache_manager: CacheManager 實例
        prefix: 快取鍵值前綴
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, texts: List[str]) -> List[List[float]]:
            if not cache_manager.enabled:
                return await func(self, texts)
            
            # 生成所有鍵值
            keys = [cache_manager._generate_cache_key(text, prefix) for text in texts]
            key_to_index = {key: i for i, key in enumerate(keys)}
            
            # 批次檢查快取
            cached_results = cache_manager.get_batch(keys)
            
            # 找出需要計算的項目
            uncached_indices = []
            uncached_texts = []
            results = [None] * len(texts)
            
            for i, key in enumerate(keys):
                if key in cached_results:
                    results[i] = cached_results[key]
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(texts[i])
            
            # 如果有未快取的項目，進行計算
            if uncached_texts:
                logger.debug(f"批次快取: {len(cached_results)}/{len(texts)} 命中")
                
                start_time = time.time()
                computed_results = await func(self, uncached_texts)
                compute_time = (time.time() - start_time) * 1000
                
                # 更新結果並存入快取
                items_to_cache = {}
                for i, result in enumerate(computed_results):
                    original_index = uncached_indices[i]
                    results[original_index] = result
                    cache_key = keys[original_index]
                    items_to_cache[cache_key] = result
                
                cache_manager.set_batch(items_to_cache)
                logger.debug(f"批次快取儲存: {len(items_to_cache)} 項 (計算耗時: {compute_time:.2f}ms)")
            else:
                logger.debug(f"批次快取: 完全命中 ({len(texts)} 項)")
            
            return results
        
        return wrapper
    return decorator


def get_cache_manager() -> CacheManager:
    """
    獲取全域 CacheManager 實例（單例模式）
    
    從環境變數讀取配置：
    - EMBEDDING_CACHE_SIZE: 快取大小（預設: 1000）
    - EMBEDDING_CACHE_TTL: TTL 秒數（預設: 3600）
    - EMBEDDING_CACHE_ENABLED: 是否啟用（預設: true）
    
    Returns:
        CacheManager 實例
    """
    global _global_cache_manager
    
    if _global_cache_manager is None:
        maxsize = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
        ttl = int(os.getenv("EMBEDDING_CACHE_TTL", "3600"))
        enabled = os.getenv("EMBEDDING_CACHE_ENABLED", "true").lower() == "true"
        
        _global_cache_manager = CacheManager(
            maxsize=maxsize,
            ttl=ttl,
            enabled=enabled
        )
        
        logger.info(f"全域 CacheManager 已初始化: maxsize={maxsize}, ttl={ttl}s, enabled={enabled}")
    
    return _global_cache_manager


# 保留原有的函數以維持相容性
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


