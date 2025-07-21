"""
快取服務測試
測試記憶體快取機制的功能和效能
"""

import asyncio
import time
import json
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cache_service import CacheService

async def test_cache_basic_operations():
    """測試快取基本操作"""
    print("\n=== 測試快取基本操作 ===")
    
    cache = CacheService()
    
    # 測試設置和獲取
    cache.set('query', 'test_key', {'data': 'test_value'})
    result = cache.get('query', 'test_key')
    assert result == {'data': 'test_value'}
    print("✅ 設置和獲取測試通過")
    
    # 測試快取未命中
    result = cache.get('query', 'non_existent_key')
    assert result is None
    print("✅ 快取未命中測試通過")
    
    # 測試快取無效化
    cache.invalidate('query', 'test_key')
    result = cache.get('query', 'test_key')
    assert result is None
    print("✅ 快取無效化測試通過")
    
    # 測試快取統計
    stats = cache.get_stats()
    print(f"📊 快取統計: {json.dumps(stats, indent=2)}")

async def test_cache_decorators():
    """測試快取裝飾器"""
    print("\n=== 測試快取裝飾器 ===")
    
    cache = CacheService()
    call_count = 0
    
    @cache.cache_query_result
    async def expensive_query(param1, param2):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # 模擬耗時操作
        return f"Result for {param1}, {param2}"
    
    # 第一次調用 - 應該執行函數
    start = time.time()
    result1 = await expensive_query("test", "123")
    duration1 = time.time() - start
    print(f"第一次調用: {result1} (耗時: {duration1:.3f}秒)")
    
    # 第二次調用 - 應該從快取返回
    start = time.time()
    result2 = await expensive_query("test", "123")
    duration2 = time.time() - start
    print(f"第二次調用: {result2} (耗時: {duration2:.3f}秒)")
    
    assert result1 == result2
    assert call_count == 1  # 函數只應該被調用一次
    assert duration2 < duration1 * 0.1  # 快取調用應該快得多
    print("✅ 快取裝飾器測試通過")

async def test_ttl_cache():
    """測試TTL快取過期"""
    print("\n=== 測試TTL快取過期 ===")
    
    # 創建一個短TTL的快取用於測試
    from cachetools import TTLCache
    test_cache = TTLCache(maxsize=10, ttl=1)  # 1秒過期
    
    # 設置值
    test_cache['test_key'] = 'test_value'
    assert test_cache.get('test_key') == 'test_value'
    print("✅ TTL快取設置成功")
    
    # 等待過期
    await asyncio.sleep(1.5)
    assert test_cache.get('test_key') is None
    print("✅ TTL快取過期測試通過")

async def test_lru_cache():
    """測試LRU快取驅逐"""
    print("\n=== 測試LRU快取驅逐 ===")
    
    from cachetools import LRUCache
    test_cache = LRUCache(maxsize=3)
    
    # 填滿快取
    test_cache['key1'] = 'value1'
    test_cache['key2'] = 'value2'
    test_cache['key3'] = 'value3'
    
    # 訪問 key1，使其成為最近使用
    _ = test_cache['key1']
    
    # 添加新鍵，應該驅逐 key2（最少使用）
    test_cache['key4'] = 'value4'
    
    assert 'key1' in test_cache
    assert 'key2' not in test_cache
    assert 'key3' in test_cache
    assert 'key4' in test_cache
    print("✅ LRU驅逐測試通過")

async def test_cache_performance():
    """測試快取效能提升"""
    print("\n=== 測試快取效能提升 ===")
    
    cache = CacheService()
    
    # 模擬昂貴的查詢
    async def simulate_expensive_query(query_id):
        await asyncio.sleep(0.5)  # 模擬500ms延遲
        return {
            'query_id': query_id,
            'timestamp': datetime.now().isoformat(),
            'data': [i for i in range(100)]
        }
    
    # 不使用快取的查詢
    print("\n不使用快取:")
    start = time.time()
    for i in range(5):
        result = await simulate_expensive_query('test_query')
    no_cache_duration = time.time() - start
    print(f"5次查詢耗時: {no_cache_duration:.3f}秒")
    
    # 使用快取的查詢
    print("\n使用快取:")
    @cache.cache_query_result
    async def cached_query(query_id):
        return await simulate_expensive_query(query_id)
    
    start = time.time()
    for i in range(5):
        result = await cached_query('test_query')
    cached_duration = time.time() - start
    print(f"5次查詢耗時: {cached_duration:.3f}秒")
    
    speedup = no_cache_duration / cached_duration
    print(f"\n🚀 效能提升: {speedup:.1f}x")
    
    # 獲取最終統計
    stats = cache.get_stats()
    print(f"\n📊 最終快取統計:")
    print(f"  - 總請求數: {stats['total_requests']}")
    print(f"  - 命中數: {stats['hits']}")
    print(f"  - 未命中數: {stats['misses']}")
    print(f"  - 命中率: {stats['hit_rate']}")

async def main():
    """主測試函數"""
    print("🧪 開始測試智能快取服務\n")
    
    try:
        await test_cache_basic_operations()
        await test_cache_decorators()
        await test_ttl_cache()
        await test_lru_cache()
        await test_cache_performance()
        
        print("\n✅ 所有測試通過！")
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())