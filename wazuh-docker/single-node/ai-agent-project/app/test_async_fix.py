#!/usr/bin/env python3
"""
測試異步問題修復
"""

import asyncio
import logging
from services.opensearch_service import get_opensearch_client
from services.alert_service import query_new_alerts
from utils.cache_manager import initialize_cache_service
from api.health_check import perform_health_check

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_opensearch_connection():
    """測試 OpenSearch 連接"""
    try:
        logger.info("測試 OpenSearch 連接...")
        client = await get_opensearch_client()
        info = await client.info()
        logger.info(f"✅ OpenSearch 連接成功: {info['version']['distribution']}")
        return True
    except Exception as e:
        logger.error(f"❌ OpenSearch 連接失敗: {str(e)}")
        return False

async def test_query_alerts():
    """測試查詢警報"""
    try:
        logger.info("測試查詢警報...")
        alerts = await query_new_alerts(limit=5)
        logger.info(f"✅ 查詢警報成功，找到 {len(alerts)} 個警報")
        return True
    except Exception as e:
        logger.error(f"❌ 查詢警報失敗: {str(e)}")
        return False

async def test_health_check():
    """測試健康檢查"""
    try:
        logger.info("測試健康檢查...")
        # 初始化快取服務
        cache_service = initialize_cache_service(
            lru_maxsize=1000,
            ttl_maxsize=500,
            ttl_seconds=3600,
            enable_cache=True
        )
        
        # 執行健康檢查
        result = await perform_health_check(cache_service)
        logger.info(f"✅ 健康檢查成功: {result['status']}")
        return True
    except Exception as e:
        logger.error(f"❌ 健康檢查失敗: {str(e)}")
        return False

async def main():
    """主測試函數"""
    logger.info("=== 開始測試異步問題修復 ===")
    
    tests = [
        ("OpenSearch 連接", test_opensearch_connection),
        ("查詢警報", test_query_alerts),
        ("健康檢查", test_health_check)
    ]
    
    results = []
    for name, test_func in tests:
        logger.info(f"\n--- 測試: {name} ---")
        success = await test_func()
        results.append((name, success))
    
    logger.info("\n=== 測試結果總結 ===")
    for name, success in results:
        status = "✅ 通過" if success else "❌ 失敗"
        logger.info(f"{name}: {status}")
    
    # 關閉連接
    from services.opensearch_service import close_opensearch_client
    await close_opensearch_client()

if __name__ == "__main__":
    asyncio.run(main())