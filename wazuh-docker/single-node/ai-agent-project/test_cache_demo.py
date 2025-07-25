#!/usr/bin/env python3
"""
智能快取功能演示腳本
展示快取機制如何提升系統效能
"""

import asyncio
import time
import hashlib
from services.cache_service import CacheService
from utils.cache_manager import initialize_cache_service

async def simulate_embedding_query(text: str, delay: float = 0.2):
    """模擬向量嵌入查詢（帶延遲）"""
    await asyncio.sleep(delay)  # 模擬 API 調用延遲
    # 生成模擬的向量
    hash_value = hashlib.md5(text.encode()).hexdigest()
    vector = [float(int(hash_value[i:i+2], 16)) / 255.0 for i in range(0, 32, 2)]
    return vector * 48  # 768維向量

async def simulate_neo4j_query(query: str, delay: float = 0.1):
    """模擬 Neo4j 查詢（帶延遲）"""
    await asyncio.sleep(delay)  # 模擬查詢延遲
    return [
        {"id": "alert1", "type": "Alert", "severity": "high"},
        {"id": "host1", "type": "Host", "name": "server-01"},
        {"id": "ip1", "type": "IPAddress", "address": "192.168.1.100"}
    ]

async def main():
    """主演示程式"""
    print("=== 智能快取功能演示 ===\n")
    
    # 初始化快取服務
    cache_service = initialize_cache_service(
        lru_maxsize=100,
        ttl_maxsize=50,
        ttl_seconds=300,
        enable_cache=True
    )
    
    if not cache_service:
        print("❌ 快取服務初始化失敗")
        return
    
    print("✅ 快取服務已初始化\n")
    
    # 演示 1: 向量嵌入快取
    print("📊 演示 1: 向量嵌入快取")
    print("-" * 40)
    
    test_texts = [
        "Suspicious SSH login attempt from unknown IP",
        "Failed authentication for user admin",
        "Suspicious SSH login attempt from unknown IP",  # 重複
        "Port scan detected on multiple ports",
        "Failed authentication for user admin"  # 重複
    ]
    
    for i, text in enumerate(test_texts, 1):
        cache_key = f"embed:{hashlib.md5(text.encode()).hexdigest()}"
        
        start_time = time.time()
        vector = await cache_service.get_or_compute(
            cache_key=cache_key,
            compute_func=lambda t=text: simulate_embedding_query(t),
            cache_type='ttl'
        )
        elapsed = (time.time() - start_time) * 1000
        
        print(f"{i}. 文本: '{text[:40]}...'")
        print(f"   耗時: {elapsed:.2f}ms")
        print(f"   向量維度: {len(vector)}")
        print()
    
    # 顯示快取統計
    stats = cache_service.get_stats()
    print(f"快取統計:")
    print(f"  - 命中率: {stats['hit_rate']}")
    print(f"  - 總請求: {stats['total_requests']}")
    print(f"  - 命中次數: {stats['hits']}")
    print(f"  - 未命中次數: {stats['misses']}")
    print(f"  - 節省時間: {stats['saved_time_ms']:.2f}ms\n")
    
    # 演示 2: Neo4j 查詢快取
    print("\n🔍 演示 2: Neo4j 查詢快取")
    print("-" * 40)
    
    queries = [
        ("MATCH (a:Alert) RETURN a LIMIT 10", {}),
        ("MATCH (h:Host)-[:TRIGGERED]->(a:Alert) RETURN h, a", {"host": "server-01"}),
        ("MATCH (a:Alert) RETURN a LIMIT 10", {}),  # 重複
        ("MATCH (ip:IPAddress) WHERE ip.address = $ip RETURN ip", {"ip": "192.168.1.100"}),
        ("MATCH (h:Host)-[:TRIGGERED]->(a:Alert) RETURN h, a", {"host": "server-01"})  # 重複
    ]
    
    for i, (query, params) in enumerate(queries, 1):
        cache_key = f"neo4j:{hashlib.md5((query + str(params)).encode()).hexdigest()}"
        
        start_time = time.time()
        result = await cache_service.get_or_compute(
            cache_key=cache_key,
            compute_func=lambda q=query: simulate_neo4j_query(q),
            cache_type='lru'
        )
        elapsed = (time.time() - start_time) * 1000
        
        print(f"{i}. 查詢: '{query[:50]}...'")
        print(f"   參數: {params}")
        print(f"   耗時: {elapsed:.2f}ms")
        print(f"   結果數: {len(result)}")
        print()
    
    # 最終統計
    final_stats = cache_service.get_stats()
    cache_info = cache_service.get_cache_info()
    
    print("\n📈 最終快取統計")
    print("-" * 40)
    print(f"總體效能:")
    print(f"  - 總命中率: {final_stats['hit_rate']}")
    print(f"  - 總節省時間: {final_stats['saved_time_ms']:.2f}ms")
    print(f"  - 平均節省時間: {cache_info['performance']['avg_saved_time_ms']:.2f}ms/次")
    print(f"\n快取使用情況:")
    print(f"  - LRU 快取: {cache_info['lru_cache']['usage']} ({cache_info['lru_cache']['size']}/{cache_info['lru_cache']['maxsize']})")
    print(f"  - TTL 快取: {cache_info['ttl_cache']['usage']} ({cache_info['ttl_cache']['size']}/{cache_info['ttl_cache']['maxsize']})")
    
    print("\n✅ 演示完成！快取機制有效減少了重複查詢的延遲。")

if __name__ == "__main__":
    asyncio.run(main())