#!/usr/bin/env python3
"""
智能快取功能演示腳本

此腳本演示了向量嵌入智能快取的使用方式和效能提升。

使用方法:
    python examples/cache_demo.py
"""

import asyncio
import time
import sys
import os
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.embedding_service import GeminiEmbeddingService
from app.utils.cache_manager import get_cache_manager


async def demo_single_embedding():
    """演示單一嵌入的快取效果"""
    print("\n=== 單一嵌入快取演示 ===")
    
    service = GeminiEmbeddingService()
    test_texts = [
        "This is a security alert about unauthorized access",
        "Network intrusion detected from external IP",
        "This is a security alert about unauthorized access",  # 重複
        "Malware activity detected on host server",
        "Network intrusion detected from external IP",  # 重複
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n測試 {i}: {text[:50]}...")
        
        start_time = time.time()
        vector = await service.embed_query(text)
        elapsed_time = time.time() - start_time
        
        print(f"  向量維度: {len(vector)}")
        print(f"  執行時間: {elapsed_time:.3f} 秒")
        
        # 檢查快取狀態
        stats = service.get_cache_stats()
        print(f"  快取狀態 - 命中: {stats['hits']}, 未命中: {stats['misses']}, 命中率: {stats['hit_rate']}")


async def demo_batch_embedding():
    """演示批次嵌入的快取效果"""
    print("\n\n=== 批次嵌入快取演示 ===")
    
    service = GeminiEmbeddingService()
    
    # 第一批文本
    batch1 = [
        "Alert 1: Suspicious login attempt",
        "Alert 2: Port scanning detected",
        "Alert 3: File integrity violation",
    ]
    
    print("\n第一批處理:")
    start_time = time.time()
    vectors1 = await service.embed_documents(batch1)
    elapsed_time = time.time() - start_time
    print(f"  處理 {len(batch1)} 個文本，耗時: {elapsed_time:.3f} 秒")
    
    # 第二批文本（部分重複）
    batch2 = [
        "Alert 1: Suspicious login attempt",  # 重複
        "Alert 4: DNS tunneling detected",    # 新的
        "Alert 2: Port scanning detected",    # 重複
        "Alert 5: Privilege escalation",      # 新的
    ]
    
    print("\n第二批處理（部分重複）:")
    start_time = time.time()
    vectors2 = await service.embed_documents(batch2)
    elapsed_time = time.time() - start_time
    print(f"  處理 {len(batch2)} 個文本，耗時: {elapsed_time:.3f} 秒")
    
    # 顯示最終統計
    stats = service.get_cache_stats()
    print(f"\n最終快取統計:")
    print(f"  總請求: {stats['total_requests']}")
    print(f"  命中次數: {stats['hits']}")
    print(f"  未命中次數: {stats['misses']}")
    print(f"  命中率: {stats['hit_rate']}")
    print(f"  快取使用率: {stats['usage_rate']}")


async def demo_cache_management():
    """演示快取管理功能"""
    print("\n\n=== 快取管理功能演示 ===")
    
    service = GeminiEmbeddingService()
    cache_manager = service.cache_manager
    
    # 添加一些測試數據
    test_texts = ["Test " + str(i) for i in range(10)]
    await service.embed_documents(test_texts)
    
    # 顯示快取配置
    print("\n快取配置:")
    print(f"  最大容量: {cache_manager.maxsize}")
    print(f"  TTL: {cache_manager.ttl} 秒")
    print(f"  啟用狀態: {cache_manager.enabled}")
    
    # 顯示當前統計
    stats = service.get_cache_stats()
    print(f"\n當前統計:")
    print(f"  快取大小: {stats['size']}/{stats['maxsize']}")
    print(f"  使用率: {stats['usage_rate']}")
    
    # 清空快取
    print("\n清空快取...")
    service.clear_cache()
    
    stats = service.get_cache_stats()
    print(f"清空後快取大小: {stats['size']}")


async def main():
    """主函數"""
    print("=== Wazuh GraphRAG 智能快取演示 ===")
    print("此演示展示向量嵌入快取如何提升系統效能")
    
    try:
        # 演示單一嵌入快取
        await demo_single_embedding()
        
        # 演示批次嵌入快取
        await demo_batch_embedding()
        
        # 演示快取管理
        await demo_cache_management()
        
        print("\n\n演示完成！")
        print("\n總結:")
        print("1. 相同文本的重複嵌入會從快取獲取，速度提升 100-1000 倍")
        print("2. 批次處理支援部分快取命中，只對新項目進行 API 調用")
        print("3. 快取管理 API 提供完整的監控和控制功能")
        
    except Exception as e:
        print(f"\n錯誤: {str(e)}")
        print("請確保已設置 GOOGLE_API_KEY 環境變數")


if __name__ == "__main__":
    asyncio.run(main())