# === 智能快取管理器模組 ===
#
# 本模組實現了高效的記憶體快取機制，專門針對向量嵌入結果進行優化。
# 使用 LRU (Least Recently Used) 演算法管理快取，並支援 TTL (Time To Live) 過期機制。
#
# 核心特性：
# 1. LRU 快取策略，自動淘汰最少使用的項目
# 2. TTL 過期機制，確保快取資料的時效性
# 3. 執行緒安全，支援並發訪問
# 4. 統計資訊收集，便於監控和優化
# 5. 可配置的快取大小和過期時間
#
# 版本: 1.0
# 創建: 2024年12月

import os
import time
import hashlib
import logging
from typing import Any, Optional, Dict, Tuple
from functools import wraps
from cachetools import TTLCache
from threading import Lock
import asyncio
from datetime import datetime, timedelta

# 獲取當前模組的日誌記錄器
logger = logging.getLogger(__name__)


class CacheManager:
    """
    智能快取管理器，提供高效的記憶體快取服務
    
    本類別實現了一個執行緒安全的 LRU + TTL 快取系統，專門優化用於
    向量嵌入結果的快取。支援快取統計、自動過期、容量管理等功能。
    
    Attributes:
        cache (TTLCache): 底層快取存儲，支援 LRU 和 TTL
        lock (Lock): 執行緒鎖，確保並發安全
        stats (Dict): 快取統計資訊
        enabled (bool): 快取是否啟用
    """
    
    def __init__(self, maxsize: int = 1000, ttl: int = 3600, enabled: bool = True):
        """
        初始化快取管理器
        
        Args:
            maxsize (int): 最大快取項目數，預設 1000
            ttl (int): 快取過期時間（秒），預設 3600（1小時）
            enabled (bool): 是否啟用快取，預設 True
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.enabled = enabled
        
        # 初始化 TTL 快取
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.lock = Lock()
        
        # 初始化統計資訊
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_requests": 0,
            "cache_size": 0,
            "last_reset": datetime.now()
        }
        
        logger.info(f"CacheManager 初始化完成")
        logger.info(f"  💾 最大容量: {maxsize}")
        logger.info(f"  ⏱️ TTL: {ttl} 秒")
        logger.info(f"  🔄 狀態: {'啟用' if enabled else '停用'}")
    
    def _generate_cache_key(self, content: str, prefix: str = "") -> str:
        """
        生成快取鍵值
        
        使用 SHA256 雜湊確保鍵值的一致性和唯一性
        
        Args:
            content (str): 要快取的內容
            prefix (str): 鍵值前綴，用於區分不同類型的快取
            
        Returns:
            str: 生成的快取鍵值
        """
        # 使用 SHA256 生成穩定的鍵值
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()[:16]  # 使用前16個字符以節省記憶體
        
        if prefix:
            return f"{prefix}:{hash_hex}"
        return hash_hex
    
    def get(self, key: str) -> Optional[Any]:
        """
        從快取中獲取值
        
        Args:
            key (str): 快取鍵值
            
        Returns:
            Optional[Any]: 快取的值，如果不存在或已過期則返回 None
        """
        if not self.enabled:
            return None
        
        with self.lock:
            self.stats["total_requests"] += 1
            
            try:
                value = self.cache[key]
                self.stats["hits"] += 1
                logger.debug(f"快取命中: {key}")
                return value
            except KeyError:
                self.stats["misses"] += 1
                logger.debug(f"快取未命中: {key}")
                return None
    
    def set(self, key: str, value: Any) -> None:
        """
        設置快取值
        
        Args:
            key (str): 快取鍵值
            value (Any): 要快取的值
        """
        if not self.enabled:
            return
        
        with self.lock:
            # 檢查是否會觸發淘汰
            if len(self.cache) >= self.maxsize:
                self.stats["evictions"] += 1
            
            self.cache[key] = value
            self.stats["cache_size"] = len(self.cache)
            logger.debug(f"快取設置: {key}")
    
    def clear(self) -> None:
        """清空所有快取"""
        with self.lock:
            self.cache.clear()
            self.stats["cache_size"] = 0
            logger.info("快取已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取快取統計資訊
        
        Returns:
            Dict[str, Any]: 包含命中率、使用率等統計資訊
        """
        with self.lock:
            total = self.stats["total_requests"]
            hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
            
            return {
                "enabled": self.enabled,
                "size": len(self.cache),
                "maxsize": self.maxsize,
                "ttl": self.ttl,
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "evictions": self.stats["evictions"],
                "total_requests": total,
                "hit_rate": f"{hit_rate:.2f}%",
                "usage_rate": f"{(len(self.cache) / self.maxsize * 100):.2f}%",
                "last_reset": self.stats["last_reset"].isoformat()
            }
    
    def reset_stats(self) -> None:
        """重置統計資訊"""
        with self.lock:
            self.stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "total_requests": 0,
                "cache_size": len(self.cache),
                "last_reset": datetime.now()
            }
            logger.info("快取統計已重置")


def embedding_cache(cache_manager: CacheManager, prefix: str = "embed"):
    """
    向量嵌入快取裝飾器
    
    用於裝飾非同步向量嵌入函數，自動處理快取邏輯
    
    Args:
        cache_manager (CacheManager): 快取管理器實例
        prefix (str): 快取鍵值前綴
        
    Returns:
        裝飾器函數
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, text: str, *args, **kwargs):
            # 生成快取鍵值
            cache_key = cache_manager._generate_cache_key(text, prefix)
            
            # 嘗試從快取獲取
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"使用快取的向量嵌入結果")
                return cached_value
            
            # 執行實際的向量嵌入
            result = await func(self, text, *args, **kwargs)
            
            # 存入快取
            if result is not None:
                cache_manager.set(cache_key, result)
            
            return result
        
        return wrapper
    return decorator


def batch_embedding_cache(cache_manager: CacheManager, prefix: str = "batch_embed"):
    """
    批次向量嵌入快取裝飾器
    
    用於裝飾批次向量嵌入函數，支援部分快取命中
    
    Args:
        cache_manager (CacheManager): 快取管理器實例
        prefix (str): 快取鍵值前綴
        
    Returns:
        裝飾器函數
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, texts: list, *args, **kwargs):
            if not cache_manager.enabled:
                return await func(self, texts, *args, **kwargs)
            
            # 檢查每個文本的快取狀態
            results = [None] * len(texts)
            uncached_indices = []
            uncached_texts = []
            
            for i, text in enumerate(texts):
                cache_key = cache_manager._generate_cache_key(text, prefix)
                cached_value = cache_manager.get(cache_key)
                
                if cached_value is not None:
                    results[i] = cached_value
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
            
            # 如果所有都命中快取
            if not uncached_texts:
                logger.debug(f"批次快取全部命中 ({len(texts)} 項)")
                return results
            
            # 處理未快取的項目
            logger.debug(f"批次快取部分命中: {len(texts) - len(uncached_texts)}/{len(texts)}")
            new_embeddings = await func(self, uncached_texts, *args, **kwargs)
            
            # 更新結果並存入快取
            for i, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
                if i < len(new_embeddings):
                    embedding = new_embeddings[i]
                    results[idx] = embedding
                    
                    # 存入快取
                    cache_key = cache_manager._generate_cache_key(text, prefix)
                    cache_manager.set(cache_key, embedding)
            
            return results
        
        return wrapper
    return decorator


# 全局快取管理器實例
_global_cache_manager = None


def get_cache_manager() -> CacheManager:
    """
    獲取全局快取管理器實例（單例模式）
    
    Returns:
        CacheManager: 全局快取管理器實例
    """
    global _global_cache_manager
    
    if _global_cache_manager is None:
        # 從環境變數讀取配置
        maxsize = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
        ttl = int(os.getenv("EMBEDDING_CACHE_TTL", "3600"))
        enabled = os.getenv("EMBEDDING_CACHE_ENABLED", "true").lower() == "true"
        
        _global_cache_manager = CacheManager(
            maxsize=maxsize,
            ttl=ttl,
            enabled=enabled
        )
    
    return _global_cache_manager