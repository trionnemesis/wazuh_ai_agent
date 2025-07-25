"""

快取服務測試模組
驗證智能快取功能的正確性和效能提升
"""

import pytest
import asyncio
import time
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock

from services.cache_service import CacheService
from utils.cache_manager import initialize_cache_service, get_cache_service

class TestCacheService:
    """快取服務單元測試"""
    
    @pytest.fixture
    def cache_service(self):
        """創建測試用的快取服務實例"""
        return CacheService(
            lru_maxsize=100,
            ttl_maxsize=50,
            ttl_seconds=60
        )
    
    @pytest.mark.asyncio
    async def test_lru_cache_basic(self, cache_service):
        """測試 LRU 快取基本功能"""
        # 定義計算函數
        call_count = 0
        async def compute_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        # 第一次調用 - 應該執行計算
        result1 = await cache_service.get_or_compute(
            cache_key="test_key_1",
            compute_func=compute_func,
            cache_type='lru'
        )
        assert result1 == "result_1"
        assert call_count == 1
        
        # 第二次調用相同的鍵 - 應該從快取返回
        result2 = await cache_service.get_or_compute(
            cache_key="test_key_1",
            compute_func=compute_func,
            cache_type='lru'
        )
        assert result2 == "result_1"  # 相同的結果
        assert call_count == 1  # 計算函數沒有被再次調用
        
        # 統計資訊驗證
        stats = cache_service.get_stats()
        assert stats['total_requests'] == 2
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == "50.00%"
    
    @pytest.mark.asyncio
    async def test_ttl_cache_expiration(self, cache_service):
        """測試 TTL 快取過期功能"""
        # 創建短期 TTL 快取
        short_ttl_cache = CacheService(
            lru_maxsize=100,
            ttl_maxsize=50,
            ttl_seconds=1  # 1秒過期
        )
        
        call_count = 0
        async def compute_func():
            nonlocal call_count
            call_count += 1
            return f"ttl_result_{call_count}"
        
        # 第一次調用
        result1 = await short_ttl_cache.get_or_compute(
            cache_key="ttl_test",
            compute_func=compute_func,
            cache_type='ttl'
        )
        assert result1 == "ttl_result_1"
        
        # 立即再次調用 - 應該從快取返回
        result2 = await short_ttl_cache.get_or_compute(
            cache_key="ttl_test",
            compute_func=compute_func,
            cache_type='ttl'
        )
        assert result2 == "ttl_result_1"
        
        # 等待過期
        await asyncio.sleep(1.5)
        
        # 過期後調用 - 應該重新計算
        result3 = await short_ttl_cache.get_or_compute(
            cache_key="ttl_test",
            compute_func=compute_func,
            cache_type='ttl'
        )
        assert result3 == "ttl_result_2"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache_service):
        """測試快取鍵值生成"""
        key1 = cache_service._generate_cache_key(
            "test_func",
            ("arg1", "arg2"),
            {"kwarg1": "value1"}
        )
        
        # 相同參數應該生成相同的鍵
        key2 = cache_service._generate_cache_key(
            "test_func",
            ("arg1", "arg2"),
            {"kwarg1": "value1"}
        )
        assert key1 == key2
        
        # 不同參數應該生成不同的鍵
        key3 = cache_service._generate_cache_key(
            "test_func",
            ("arg1", "arg3"),  # 不同的參數
            {"kwarg1": "value1"}
        )
        assert key1 != key3
    
    def test_cache_clear(self, cache_service):
        """測試快取清除功能"""
        # 添加一些數據到快取
        cache_service.lru_cache["lru_key"] = "lru_value"
        cache_service.ttl_cache["ttl_key"] = "ttl_value"
        
        # 清除 LRU 快取
        cache_service.clear_cache('lru')
        assert len(cache_service.lru_cache) == 0
        assert len(cache_service.ttl_cache) == 1
        
        # 清除所有快取
        cache_service.clear_cache()
        assert len(cache_service.lru_cache) == 0
        assert len(cache_service.ttl_cache) == 0
    
    def test_cache_info(self, cache_service):
        """測試快取資訊獲取"""
        # 添加一些數據
        for i in range(10):
            cache_service.lru_cache[f"lru_{i}"] = f"value_{i}"
        
        info = cache_service.get_cache_info()
        
        assert info['lru_cache']['size'] == 10
        assert info['lru_cache']['maxsize'] == 100
        assert info['lru_cache']['usage'] == "10.0%"
        
        assert 'ttl_cache' in info
        assert 'performance' in info


class TestEmbeddingCache:
    """測試嵌入服務的快取功能"""
    
    @pytest.mark.asyncio
    async def test_embedding_cache_integration(self):
        """測試嵌入服務與快取的整合"""
        # 初始化快取服務
        cache_service = initialize_cache_service(enable_cache=True)
        
        # 模擬嵌入服務
        with patch('app.embedding_service.GeminiEmbeddingService') as MockEmbedding:
            mock_service = MockEmbedding.return_value
            mock_service._cache_service = cache_service
            
            # 模擬 embed_query 方法
            embed_call_count = 0
            async def mock_embed(text):
                nonlocal embed_call_count
                embed_call_count += 1
                return [0.1, 0.2, 0.3] * 256  # 768維向量
            
            # 測試相同文本的多次嵌入
            test_text = "test security alert"
            cache_key = f"embed:{hashlib.md5(test_text.encode()).hexdigest()}"
            
            # 第一次調用
            result1 = await cache_service.get_or_compute(
                cache_key=cache_key,
                compute_func=lambda: mock_embed(test_text),
                cache_type='ttl'
            )
            
            # 第二次調用應該從快取返回
            result2 = await cache_service.get_or_compute(
                cache_key=cache_key,
                compute_func=lambda: mock_embed(test_text),
                cache_type='ttl'
            )
            
            assert result1 == result2
            assert embed_call_count == 1  # 只調用一次


class TestNeo4jCache:
    """測試 Neo4j 查詢的快取功能"""
    
    @pytest.mark.asyncio
    async def test_neo4j_query_cache(self):
        """測試 Neo4j 查詢快取"""
        # 初始化快取服務
        cache_service = initialize_cache_service(enable_cache=True)
        
        # 測試查詢
        test_query = "MATCH (n:Alert) RETURN n LIMIT 10"
        test_params = {"limit": 10}
        cache_key = f"neo4j:{hashlib.md5((test_query + str(test_params)).encode()).hexdigest()}"
        
        # 模擬查詢結果
        query_call_count = 0
        async def mock_query():
            nonlocal query_call_count
            query_call_count += 1
            return [{"id": 1, "type": "Alert"}, {"id": 2, "type": "Alert"}]
        
        # 第一次查詢
        result1 = await cache_service.get_or_compute(
            cache_key=cache_key,
            compute_func=mock_query,
            cache_type='lru'
        )
        
        # 第二次查詢應該從快取返回
        result2 = await cache_service.get_or_compute(
            cache_key=cache_key,
            compute_func=mock_query,
            cache_type='lru'
        )
        
        assert result1 == result2
        assert query_call_count == 1
        
        # 驗證快取統計
        stats = cache_service.get_stats()
        assert stats['hits'] >= 1


class TestCachePerformance:
    """測試快取效能提升"""
    
    @pytest.mark.asyncio
    async def test_performance_improvement(self):
        """測試快取帶來的效能提升"""
        cache_service = CacheService()
        
        # 模擬耗時操作
        async def slow_operation():
            await asyncio.sleep(0.1)  # 模擬100ms的操作
            return "slow_result"
        
        # 測量第一次調用時間
        start_time = time.time()
        result1 = await cache_service.get_or_compute(
            cache_key="perf_test",
            compute_func=slow_operation,
            cache_type='lru'
        )
        first_call_time = time.time() - start_time
        
        # 測量快取命中時間
        start_time = time.time()
        result2 = await cache_service.get_or_compute(
            cache_key="perf_test",
            compute_func=slow_operation,
            cache_type='lru'
        )
        cache_hit_time = time.time() - start_time
        
        # 驗證結果
        assert result1 == result2
        assert first_call_time > 0.09  # 應該超過100ms
        assert cache_hit_time < 0.01   # 快取命中應該非常快
        
        # 計算效能提升
        improvement_ratio = first_call_time / cache_hit_time
        assert improvement_ratio > 10  # 至少10倍的效能提升


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
