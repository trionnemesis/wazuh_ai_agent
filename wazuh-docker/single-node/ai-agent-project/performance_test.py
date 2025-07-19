#!/usr/bin/env python3
"""
Wazuh GraphRAG 效能測試腳本
用於測試系統在不同負載下的效能表現
"""

import asyncio
import time
import statistics
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Any

# 測試配置
API_BASE_URL = "http://localhost:8000"
CONCURRENT_REQUESTS = [1, 5, 10, 20]  # 不同並發數測試
REQUESTS_PER_TEST = 100  # 每個測試的請求數

async def make_request(session: aiohttp.ClientSession, endpoint: str) -> Dict[str, Any]:
    """發送單個請求並記錄響應時間"""
    start_time = time.time()
    
    try:
        async with session.get(f"{API_BASE_URL}{endpoint}") as response:
            data = await response.json()
            elapsed_time = time.time() - start_time
            return {
                "success": True,
                "status": response.status,
                "elapsed_time": elapsed_time,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        elapsed_time = time.time() - start_time
        return {
            "success": False,
            "error": str(e),
            "elapsed_time": elapsed_time,
            "timestamp": datetime.now().isoformat()
        }

async def run_concurrent_test(endpoint: str, concurrent: int, total_requests: int) -> Dict[str, Any]:
    """運行並發測試"""
    print(f"\n🚀 測試並發數: {concurrent}, 總請求數: {total_requests}")
    
    async with aiohttp.ClientSession() as session:
        # 預熱請求
        print("📊 預熱中...")
        for _ in range(5):
            await make_request(session, endpoint)
        
        # 實際測試
        print("🔥 開始測試...")
        start_time = time.time()
        
        # 創建所有任務
        tasks = []
        for i in range(total_requests):
            if i % concurrent == 0 and i > 0:
                # 等待當前批次完成
                await asyncio.gather(*tasks)
                tasks = []
            
            task = asyncio.create_task(make_request(session, endpoint))
            tasks.append(task)
        
        # 等待最後一批任務
        if tasks:
            await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # 收集所有結果
        all_results = []
        for task in asyncio.all_tasks():
            if task.done() and not task.cancelled():
                try:
                    result = task.result()
                    if isinstance(result, dict) and "elapsed_time" in result:
                        all_results.append(result)
                except:
                    pass
    
    # 計算統計資訊
    successful_requests = [r for r in all_results if r.get("success", False)]
    failed_requests = [r for r in all_results if not r.get("success", False)]
    response_times = [r["elapsed_time"] for r in successful_requests]
    
    if response_times:
        stats = {
            "concurrent": concurrent,
            "total_requests": total_requests,
            "successful": len(successful_requests),
            "failed": len(failed_requests),
            "total_time": total_time,
            "requests_per_second": len(successful_requests) / total_time,
            "avg_response_time": statistics.mean(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "p50_response_time": statistics.median(response_times),
            "p95_response_time": sorted(response_times)[int(len(response_times) * 0.95)] if len(response_times) > 20 else max(response_times),
            "p99_response_time": sorted(response_times)[int(len(response_times) * 0.99)] if len(response_times) > 100 else max(response_times),
        }
    else:
        stats = {
            "concurrent": concurrent,
            "total_requests": total_requests,
            "successful": 0,
            "failed": len(failed_requests),
            "error": "所有請求都失敗了"
        }
    
    return stats

async def main():
    """主測試函數"""
    print("🎯 Wazuh GraphRAG 效能測試")
    print("=" * 50)
    
    # 測試端點
    endpoints = [
        "/health",
        "/metrics",
    ]
    
    for endpoint in endpoints:
        print(f"\n📍 測試端點: {endpoint}")
        print("-" * 50)
        
        results = []
        for concurrent in CONCURRENT_REQUESTS:
            result = await run_concurrent_test(endpoint, concurrent, REQUESTS_PER_TEST)
            results.append(result)
            
            # 打印結果
            print(f"\n📊 結果統計:")
            print(f"  ✅ 成功請求: {result.get('successful', 0)}")
            print(f"  ❌ 失敗請求: {result.get('failed', 0)}")
            print(f"  ⚡ RPS: {result.get('requests_per_second', 0):.2f}")
            print(f"  ⏱️ 平均響應時間: {result.get('avg_response_time', 0):.3f}s")
            print(f"  📈 P95 響應時間: {result.get('p95_response_time', 0):.3f}s")
            print(f"  📈 P99 響應時間: {result.get('p99_response_time', 0):.3f}s")
        
        # 保存結果
        with open(f"performance_test_results_{endpoint.replace('/', '_')}.json", "w") as f:
            json.dump({
                "endpoint": endpoint,
                "timestamp": datetime.now().isoformat(),
                "results": results
            }, f, indent=2)
    
    print("\n✅ 測試完成！結果已保存到 performance_test_results_*.json")

if __name__ == "__main__":
    asyncio.run(main())