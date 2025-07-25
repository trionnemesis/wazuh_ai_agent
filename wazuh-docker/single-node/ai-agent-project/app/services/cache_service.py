"""
智能快取服務模組
實作記憶體快取機制以優化常用查詢的效能


"""

import logging
import hashlib
import json
import time
from typing import Any, Dict, Optional, Callable
from functools import wraps
from cachetools import TTLCache, LRUCache
import asyncio

logger = logging.getLogger(__name__)


class CacheService:
    """
    智能快取服務
    
    提供多層級快取策略：
    - LRU (Least Recently Used) 快取：用於高頻查詢
    - TTL (Time To Live) 快取：用於時效性資料
    - 統計分析：追蹤快取命中率和效能提升
    """
    
    def __init__(self, 
                 lru_maxsize: int = 1000,
                 ttl_maxsize: int = 500,
                 ttl_seconds: int = 3600):
        """
        初始化快取服務
        
        Args:
            lru_maxsize: LRU 快取最大容量
            ttl_maxsize: TTL 快取最大容量
            ttl_seconds: TTL 快取過期時間（秒）
        """
        # 初始化快取儲存
        self.lru_cache = LRUCache(maxsize=lru_maxsize)
        self.ttl_cache = TTLCache(maxsize=ttl_maxsize, ttl=ttl_seconds)

        
        # 快取統計
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0,
            'saved_time_ms': 0
        }
        
        # 快取配置
        self.config = {
            'lru_maxsize': lru_maxsize,
            'ttl_maxsize': ttl_maxsize,
            'ttl_seconds': ttl_seconds
        }
        
        logger.info(f"快取服務初始化完成 - LRU: {lru_maxsize}, TTL: {ttl_maxsize}/{ttl_seconds}s")
    
    def _generate_cache_key(self, 
                           func_name: str, 
                           args: tuple, 
                           kwargs: dict) -> str:
        """
        生成快取鍵值
        
        Args:
            func_name: 函數名稱
            args: 位置參數
            kwargs: 關鍵字參數
            
        Returns:
            str: 快取鍵值
        """
        # 將參數序列化為穩定的字串
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': kwargs
        }
        
        # 使用 JSON 序列化並計算 hash
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        cache_key = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{func_name}:{cache_key}"
    
    async def get_or_compute(self,
                            cache_key: str,
                            compute_func: Callable,
                            cache_type: str = 'lru',
                            ttl_override: Optional[int] = None) -> Any:
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        # 選擇快取儲存
        cache_store = self.lru_cache if cache_type == 'lru' else self.ttl_cache
        
        # 檢查快取
        if cache_key in cache_store:
            self.stats['hits'] += 1
            result = cache_store[cache_key]
            
            # 計算節省的時間
            elapsed_ms = (time.time() - start_time) * 1000
            self.stats['saved_time_ms'] += elapsed_ms
            
            logger.debug(f"快取命中: {cache_key} (節省 {elapsed_ms:.2f}ms)")
            return result
        
        # 快取未命中，執行計算
        self.stats['misses'] += 1
        logger.debug(f"快取未命中: {cache_key}")
        
        try:
            # 執行計算函數
            if asyncio.iscoroutinefunction(compute_func):
                result = await compute_func()
            else:
                result = compute_func()
            
            # 儲存結果到快取
            if cache_type == 'ttl' and ttl_override:
                # 使用自訂 TTL
                temp_cache = TTLCache(maxsize=1, ttl=ttl_override)
                temp_cache[cache_key] = result
                cache_store.update(temp_cache)
            else:
                cache_store[cache_key] = result
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"計算完成並快取: {cache_key} (耗時 {elapsed_ms:.2f}ms)")
            
            return result
            
        except Exception as e:
            logger.error(f"計算函數執行失敗: {str(e)}")
            raise
    
    def cache_embedding(self, ttl_seconds: int = 3600):
        """
        用於向量嵌入的快取裝飾器
        
        Args:
            ttl_seconds: 快取過期時間（秒）
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(self, text: str, *args, **kwargs):
                # 生成快取鍵值
                cache_key = f"embed:{hashlib.md5(text.encode()).hexdigest()}"
                
                # 使用快取服務
                cache_service = getattr(self, '_cache_service', None)
                if not cache_service:
                    # 如果沒有快取服務，直接執行函數
                    return await func(self, text, *args, **kwargs)
                
                # 獲取或計算結果
                result = await cache_service.get_or_compute(
                    cache_key=cache_key,
                    compute_func=lambda: func(self, text, *args, **kwargs),
                    cache_type='ttl',
                    ttl_override=ttl_seconds
                )
                
                return result
            
            return wrapper
        return decorator
    
    def cache_query_result(self, func):
        """
        快取查詢結果的裝飾器
        
        用於包裝 OpenSearch 查詢函數，自動處理快取邏輯。
        
        Args:
            func: 要包裝的查詢函數
            
        Returns:
            包裝後的函數
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成快取鍵值
            # 從參數中提取有意義的快取鍵組成部分
            cache_key_parts = [func.__name__]
            
            # 處理位置參數
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    cache_key_parts.append(str(arg))
                elif isinstance(arg, dict):
                    # 對字典參數進行排序以確保一致性
                    sorted_items = sorted(arg.items())
                    cache_key_parts.append(str(sorted_items))
                elif isinstance(arg, list):
                    cache_key_parts.append(str(arg))
            
            # 處理關鍵字參數
            for key, value in sorted(kwargs.items()):
                cache_key_parts.append(f"{key}={value}")
            
            # 生成最終的快取鍵
            cache_key = hashlib.md5(":".join(cache_key_parts).encode()).hexdigest()
            cache_key = f"query:{cache_key}"
            
            # 獲取或計算結果
            result = await self.get_or_compute(
                cache_key=cache_key,
                compute_func=lambda: func(*args, **kwargs),
                cache_type='ttl'  # 查詢結果使用 TTL 快取
            )
            
            return result
        
        return wrapper
    
    def cache_neo4j_query(self, cache_type: str = 'lru'):
        """
        用於 Neo4j 查詢的快取裝飾器
        
        Args:
            cache_type: 快取類型 ('lru' 或 'ttl')
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 提取查詢參數
                query = args[0] if args else kwargs.get('query', '')
                parameters = args[1] if len(args) > 1 else kwargs.get('parameters', {})
                
                # 生成快取鍵值
                cache_key = f"neo4j:{hashlib.md5((query + str(parameters)).encode()).hexdigest()}"
                
                # 獲取全域快取服務
                from utils.cache_manager import get_cache_service
                cache_service = get_cache_service()
                
                if not cache_service:
                    # 如果沒有快取服務，直接執行函數
                    return await func(*args, **kwargs)
                
                # 獲取或計算結果
                result = await cache_service.get_or_compute(
                    cache_key=cache_key,
                    compute_func=lambda: func(*args, **kwargs),
                    cache_type=cache_type
                )
                
                return result
            
            return wrapper
        return decorator
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """
        清除快取
        
        Args:
            cache_type: 要清除的快取類型，None 表示清除所有
        """
        if cache_type == 'lru' or cache_type is None:
            self.lru_cache.clear()
            logger.info("LRU 快取已清除")
        
        if cache_type == 'ttl' or cache_type is None:
            self.ttl_cache.clear()
            logger.info("TTL 快取已清除")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取快取統計資訊
        
        Returns:
            統計資訊字典
        """
        hit_rate = 0
        if self.stats['total_requests'] > 0:
            hit_rate = (self.stats['hits'] / self.stats['total_requests']) * 100
        
        return {
            'hit_rate': f"{hit_rate:.2f}%",
            'total_requests': self.stats['total_requests'],
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'saved_time_ms': self.stats['saved_time_ms'],
            'lru_size': len(self.lru_cache),
            'ttl_size': len(self.ttl_cache),
            'config': self.config
        }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        獲取詳細的快取資訊
        
        Returns:
            快取資訊字典
        """
        info = {
            'lru_cache': {
                'size': len(self.lru_cache),
                'maxsize': self.config['lru_maxsize'],
                'usage': f"{(len(self.lru_cache) / self.config['lru_maxsize']) * 100:.1f}%"
            },
            'ttl_cache': {
                'size': len(self.ttl_cache),
                'maxsize': self.config['ttl_maxsize'],
                'ttl_seconds': self.config['ttl_seconds'],
                'usage': f"{(len(self.ttl_cache) / self.config['ttl_maxsize']) * 100:.1f}%"
            },
            'performance': {
                'hit_rate': f"{(self.stats['hits'] / max(self.stats['total_requests'], 1)) * 100:.2f}%",
                'avg_saved_time_ms': self.stats['saved_time_ms'] / max(self.stats['hits'], 1)
            }
        }
        
        return info

# 全域快取服務實例
_cache_service: Optional[CacheService] = None

def get_cache_service() -> Optional[CacheService]:
    """獲取全域快取服務實例"""
    return _cache_service

def init_cache_service(**kwargs) -> CacheService:
    """初始化全域快取服務"""
    global _cache_service
    _cache_service = CacheService(**kwargs)
    logger.info("全域快取服務已初始化")
    return _cache_service

