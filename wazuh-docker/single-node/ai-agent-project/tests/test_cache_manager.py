# === 快取管理器單元測試 ===
#
# 測試智能快取功能的正確性和效能
#
# 版本: 1.0
# 創建: 2024年12月

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from app.utils.cache_manager import CacheManager, embedding_cache, batch_embedding_cache, get_cache_manager


class TestCacheManager:
    """快取管理器測試類"""
    
    def test_cache_initialization(self):
        """測試快取管理器初始化"""
        cache = CacheManager(maxsize=100, ttl=60, enabled=True)
        
        assert cache.maxsize == 100
        assert cache.ttl == 60
        assert cache.enabled is True
        assert len(cache.cache) == 0
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0
    
    def test_cache_key_generation(self):
        """測試快取鍵值生成"""
        cache = CacheManager()
        
        # 相同內容應產生相同鍵值
        key1 = cache._generate_cache_key("test content", "prefix")
        key2 = cache._generate_cache_key("test content", "prefix")
        assert key1 == key2
        
        # 不同內容應產生不同鍵值
        key3 = cache._generate_cache_key("different content", "prefix")
        assert key1 != key3
        
        # 不同前綴應產生不同鍵值
        key4 = cache._generate_cache_key("test content", "other_prefix")
        assert key1 != key4
    
    def test_cache_get_set(self):
        """測試快取的獲取和設置"""
        cache = CacheManager(maxsize=10, ttl=60)
        
        # 設置值
        cache.set("key1", [1.0, 2.0, 3.0])
        
        # 獲取值（應該命中）
        value = cache.get("key1")
        assert value == [1.0, 2.0, 3.0]
        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 0
        
        # 獲取不存在的值（應該未命中）
        value = cache.get("key2")
        assert value is None
        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 1
    
    def test_cache_eviction(self):
        """測試 LRU 淘汰機制"""
        cache = CacheManager(maxsize=3, ttl=60)
        
        # 填滿快取
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # 添加第四個項目，應該淘汰最舊的
        cache.set("key4", "value4")
        
        # key1 應該被淘汰
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
        assert cache.stats["evictions"] == 1
    
    def test_cache_ttl_expiration(self):
        """測試 TTL 過期機制"""
        cache = CacheManager(maxsize=10, ttl=0.1)  # 0.1秒過期
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # 等待過期
        time.sleep(0.2)
        assert cache.get("key1") is None
    
    def test_cache_disabled(self):
        """測試停用快取的情況"""
        cache = CacheManager(enabled=False)
        
        cache.set("key1", "value1")
        assert cache.get("key1") is None
        assert len(cache.cache) == 0
    
    def test_cache_clear(self):
        """測試清空快取"""
        cache = CacheManager()
        
        # 添加一些項目
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache.cache) == 2
        
        # 清空快取
        cache.clear()
        assert len(cache.cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_stats(self):
        """測試快取統計功能"""
        cache = CacheManager(maxsize=10, ttl=60)
        
        # 執行一些操作
        cache.set("key1", "value1")
        cache.get("key1")  # 命中
        cache.get("key2")  # 未命中
        
        stats = cache.get_stats()
        
        assert stats["enabled"] is True
        assert stats["size"] == 1
        assert stats["maxsize"] == 10
        assert stats["ttl"] == 60
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == "50.00%"
        assert stats["usage_rate"] == "10.00%"
    
    def test_cache_reset_stats(self):
        """測試重置統計"""
        cache = CacheManager()
        
        # 執行一些操作
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("key2")
        
        # 重置統計
        cache.reset_stats()
        
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0
        assert cache.stats["total_requests"] == 0
        assert len(cache.cache) == 1  # 快取內容應該保留


class TestEmbeddingCacheDecorator:
    """測試向量嵌入快取裝飾器"""
    
    @pytest.mark.asyncio
    async def test_embedding_cache_decorator(self):
        """測試單一嵌入快取裝飾器"""
        cache = CacheManager()
        
        # 模擬的嵌入服務
        class MockEmbeddingService:
            call_count = 0
            
            @embedding_cache(cache, prefix="test")
            async def embed_query(self, text: str):
                self.call_count += 1
                return [1.0, 2.0, 3.0]
        
        service = MockEmbeddingService()
        
        # 第一次調用應該執行實際函數
        result1 = await service.embed_query("test text")
        assert result1 == [1.0, 2.0, 3.0]
        assert service.call_count == 1
        
        # 第二次調用應該使用快取
        result2 = await service.embed_query("test text")
        assert result2 == [1.0, 2.0, 3.0]
        assert service.call_count == 1  # 不應增加
        
        # 不同文字應該執行實際函數
        result3 = await service.embed_query("different text")
        assert result3 == [1.0, 2.0, 3.0]
        assert service.call_count == 2
    
    @pytest.mark.asyncio
    async def test_batch_embedding_cache_decorator(self):
        """測試批次嵌入快取裝飾器"""
        cache = CacheManager()
        
        # 模擬的嵌入服務
        class MockEmbeddingService:
            call_count = 0
            
            @batch_embedding_cache(cache, prefix="batch_test")
            async def embed_documents(self, texts: list):
                self.call_count += 1
                # 返回與輸入數量相同的向量
                return [[float(i), float(i+1), float(i+2)] for i in range(len(texts))]
        
        service = MockEmbeddingService()
        
        # 第一次調用，所有都應該計算
        texts1 = ["text1", "text2", "text3"]
        results1 = await service.embed_documents(texts1)
        assert len(results1) == 3
        assert service.call_count == 1
        
        # 第二次調用相同文本，應該全部從快取獲取
        results2 = await service.embed_documents(texts1)
        assert results2 == results1
        assert service.call_count == 1  # 不應增加
        
        # 部分重複的文本，應該只計算新的
        texts3 = ["text1", "text4", "text2"]  # text1和text2已快取
        results3 = await service.embed_documents(texts3)
        assert len(results3) == 3
        assert service.call_count == 2  # 只為text4調用一次
        assert results3[0] == results1[0]  # text1的結果應該相同
        assert results3[2] == results1[1]  # text2的結果應該相同


class TestGlobalCacheManager:
    """測試全局快取管理器"""
    
    @patch.dict('os.environ', {
        'EMBEDDING_CACHE_SIZE': '500',
        'EMBEDDING_CACHE_TTL': '1800',
        'EMBEDDING_CACHE_ENABLED': 'true'
    })
    def test_get_cache_manager_with_env(self):
        """測試從環境變數讀取配置"""
        # 重置全局實例
        import app.utils.cache_manager
        app.utils.cache_manager._global_cache_manager = None
        
        manager = get_cache_manager()
        
        assert manager.maxsize == 500
        assert manager.ttl == 1800
        assert manager.enabled is True
        
        # 第二次調用應該返回相同實例
        manager2 = get_cache_manager()
        assert manager is manager2
    
    @patch.dict('os.environ', {
        'EMBEDDING_CACHE_ENABLED': 'false'
    })
    def test_get_cache_manager_disabled(self):
        """測試停用快取的情況"""
        # 重置全局實例
        import app.utils.cache_manager
        app.utils.cache_manager._global_cache_manager = None
        
        manager = get_cache_manager()
        assert manager.enabled is False