"""
智能快取服務模組
提供記憶體快取機制來優化常用查詢結果
"""

import logging
import hashlib
import json
from typing import Any, Dict, Optional, Callable, Union, List
from datetime import datetime, timedelta
from functools import wraps
import asyncio

from cachetools import TTLCache, LRUCache
from cachetools.keys import hashkey

logger = logging.getLogger(__name__)

class CacheService:
    """智能快取服務，提供LRU和TTL快取機制"""
    
    def __init__(self):
        # 查詢結果快取 - 使用TTL快取，5分鐘過期
        self.query_cache = TTLCache(maxsize=1000, ttl=300)  # 5分鐘TTL
        
        # 向量搜尋快取 - 使用LRU快取
        self.vector_cache = LRUCache(maxsize=500)
        
        # 圖形查詢快取 - 使用TTL快取，10分鐘過期
        self.graph_cache = TTLCache(maxsize=500, ttl=600)  # 10分鐘TTL
        
        # 快取統計
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0
        }
        
        logger.info("CacheService initialized with TTL and LRU caches")
    
    def _generate_cache_key(self, prefix: str, params: Union[Dict, tuple]) -> str:
        """生成快取鍵"""
        if isinstance(params, dict):
            # 將字典轉換為穩定的字符串表示
            stable_str = json.dumps(params, sort_keys=True, default=str)
        else:
            stable_str = str(params)
        
        # 使用SHA256生成短鍵
        hash_obj = hashlib.sha256(stable_str.encode())
        return f"{prefix}:{hash_obj.hexdigest()[:16]}"
    
    def get(self, cache_type: str, key: str) -> Optional[Any]:
        """從快取中獲取資料"""
        self.stats['total_requests'] += 1
        
        cache = self._get_cache(cache_type)
        if cache is None:
            return None
        
        try:
            value = cache.get(key)
            if value is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for {cache_type}:{key}")
                return value
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for {cache_type}:{key}")
                return None
        except KeyError:
            self.stats['misses'] += 1
            return None
    
    def set(self, cache_type: str, key: str, value: Any) -> None:
        """將資料存入快取"""
        cache = self._get_cache(cache_type)
        if cache is None:
            return
        
        try:
            # 檢查快取是否已滿
            if len(cache) >= cache.maxsize:
                self.stats['evictions'] += 1
            
            cache[key] = value
            logger.debug(f"Cached {cache_type}:{key}")
        except Exception as e:
            logger.error(f"Failed to cache {cache_type}:{key}: {str(e)}")
    
    def invalidate(self, cache_type: str, key: Optional[str] = None) -> None:
        """使快取無效"""
        cache = self._get_cache(cache_type)
        if cache is None:
            return
        
        if key:
            cache.pop(key, None)
            logger.debug(f"Invalidated cache {cache_type}:{key}")
        else:
            cache.clear()
            logger.info(f"Cleared all {cache_type} cache")
    
    def _get_cache(self, cache_type: str) -> Optional[Union[TTLCache, LRUCache]]:
        """根據類型獲取對應的快取實例"""
        cache_map = {
            'query': self.query_cache,
            'vector': self.vector_cache,
            'graph': self.graph_cache
        }
        return cache_map.get(cache_type)
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計資訊"""
        hit_rate = (self.stats['hits'] / self.stats['total_requests'] * 100) if self.stats['total_requests'] > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': f"{hit_rate:.2f}%",
            'query_cache_size': len(self.query_cache),
            'vector_cache_size': len(self.vector_cache),
            'graph_cache_size': len(self.graph_cache),
            'query_cache_maxsize': self.query_cache.maxsize,
            'vector_cache_maxsize': self.vector_cache.maxsize,
            'graph_cache_maxsize': self.graph_cache.maxsize
        }
    
    def cache_query_result(self, func: Callable) -> Callable:
        """查詢結果快取裝飾器"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成快取鍵
            cache_key = self._generate_cache_key('query', (args, kwargs))
            
            # 嘗試從快取獲取
            cached_result = self.get('query', cache_key)
            if cached_result is not None:
                return cached_result
            
            # 執行原始函數
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 存入快取
            self.set('query', cache_key, result)
            
            return result
        
        return wrapper
    
    def cache_vector_search(self, func: Callable) -> Callable:
        """向量搜尋快取裝飾器"""
        @wraps(func)
        async def wrapper(alert_vector: List[float], *args, **kwargs):
            # 生成快取鍵 - 使用向量的前10個值作為鍵的一部分
            vector_key = str(alert_vector[:10]) if len(alert_vector) >= 10 else str(alert_vector)
            cache_key = self._generate_cache_key('vector', (vector_key, args, kwargs))
            
            # 嘗試從快取獲取
            cached_result = self.get('vector', cache_key)
            if cached_result is not None:
                return cached_result
            
            # 執行原始函數
            if asyncio.iscoroutinefunction(func):
                result = await func(alert_vector, *args, **kwargs)
            else:
                result = func(alert_vector, *args, **kwargs)
            
            # 存入快取
            self.set('vector', cache_key, result)
            
            return result
        
        return wrapper
    
    def cache_graph_query(self, func: Callable) -> Callable:
        """圖形查詢快取裝飾器"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成快取鍵
            cache_key = self._generate_cache_key('graph', (args, kwargs))
            
            # 嘗試從快取獲取
            cached_result = self.get('graph', cache_key)
            if cached_result is not None:
                return cached_result
            
            # 執行原始函數
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 存入快取
            self.set('graph', cache_key, result)
            
            return result
        
        return wrapper

# 創建全域快取服務實例
cache_service = CacheService()

# 匯出常用功能
__all__ = ['cache_service', 'CacheService']