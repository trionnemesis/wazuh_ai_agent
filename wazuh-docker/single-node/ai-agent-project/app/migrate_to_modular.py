#!/usr/bin/env python3
"""
遷移腳本：測試新的模組化架構
這個腳本幫助驗證重構後的模組是否正常工作
"""

import asyncio
import sys
import logging
from pathlib import Path

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_imports():
    """測試所有模組是否可以正常導入"""
    logger.info("測試模組導入...")
    
    try:
        # 核心模組
        from core.config import validate_config, get_config_summary
        logger.info("✅ core.config 導入成功")
        
        from core.scheduler import get_scheduler, start_scheduler, shutdown_scheduler
        logger.info("✅ core.scheduler 導入成功")
        
        # API 模組
        from api.endpoints import router
        logger.info("✅ api.endpoints 導入成功")
        
        from api.health_check import perform_health_check
        logger.info("✅ api.health_check 導入成功")
        
        # 服務模組
        from services.metrics import REGISTRY, record_processing_time
        logger.info("✅ services.metrics 導入成功")
        
        from services.opensearch_service import get_opensearch_client
        logger.info("✅ services.opensearch_service 導入成功")
        
        from services.neo4j_service import get_neo4j_driver
        logger.info("✅ services.neo4j_service 導入成功")
        
        from services.alert_service import query_new_alerts, triage_new_alerts
        logger.info("✅ services.alert_service 導入成功")
        
        from services.retrieval_service import execute_retrieval, execute_hybrid_retrieval
        logger.info("✅ services.retrieval_service 導入成功")
        
        from services.decision_service import determine_contextual_queries, determine_graph_queries
        logger.info("✅ services.decision_service 導入成功")
        
        from services.graph_service import extract_graph_entities, build_graph_relationships
        logger.info("✅ services.graph_service 導入成功")
        
        from services.llm_service import get_llm, get_analysis_chain
        logger.info("✅ services.llm_service 導入成功")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ 導入錯誤: {e}")
        return False

async def test_config():
    """測試配置模組"""
    logger.info("\n測試配置模組...")
    
    try:
        from core.config import validate_config, get_config_summary
        
        # 測試配置驗證
        try:
            validate_config()
            logger.info("✅ 配置驗證通過")
        except ValueError as e:
            logger.warning(f"⚠️ 配置驗證失敗: {e}")
        
        # 獲取配置摘要
        summary = get_config_summary()
        logger.info(f"✅ 配置摘要: {summary}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 配置測試失敗: {e}")
        return False

async def test_connections():
    """測試資料庫連接"""
    logger.info("\n測試資料庫連接...")
    
    # 測試 OpenSearch
    try:
        from services.opensearch_service import check_opensearch_connection
        if await check_opensearch_connection():
            logger.info("✅ OpenSearch 連接成功")
        else:
            logger.warning("⚠️ OpenSearch 連接失敗")
    except Exception as e:
        logger.error(f"❌ OpenSearch 測試失敗: {e}")
    
    # 測試 Neo4j
    try:
        from services.neo4j_service import check_neo4j_connection
        if await check_neo4j_connection():
            logger.info("✅ Neo4j 連接成功")
        else:
            logger.warning("⚠️ Neo4j 連接失敗")
    except Exception as e:
        logger.error(f"❌ Neo4j 測試失敗: {e}")

async def test_scheduler():
    """測試排程器"""
    logger.info("\n測試排程器...")
    
    try:
        from core.scheduler import get_scheduler, get_scheduler_status
        
        scheduler = get_scheduler()
        status = get_scheduler_status()
        logger.info(f"✅ 排程器狀態: {status}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 排程器測試失敗: {e}")
        return False

async def test_alert_query():
    """測試警報查詢功能"""
    logger.info("\n測試警報查詢...")
    
    try:
        from services.alert_service import query_new_alerts
        
        alerts = await query_new_alerts(limit=5)
        logger.info(f"✅ 查詢到 {len(alerts)} 個新警報")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 警報查詢測試失敗: {e}")
        return False

async def compare_with_original():
    """與原始 main.py 進行功能對比"""
    logger.info("\n與原始實現進行對比...")
    
    # 這裡可以添加更多的對比測試
    # 例如：性能測試、功能一致性測試等
    
    logger.info("📊 建議進行以下額外測試：")
    logger.info("   - 端到端流程測試")
    logger.info("   - API 端點測試")
    logger.info("   - 並發處理測試")
    logger.info("   - 記憶體使用對比")

async def main():
    """主測試流程"""
    logger.info("🚀 開始測試新的模組化架構\n")
    
    # 1. 測試導入
    if not await test_imports():
        logger.error("導入測試失敗，請檢查模組結構")
        sys.exit(1)
    
    # 2. 測試配置
    await test_config()
    
    # 3. 測試連接
    await test_connections()
    
    # 4. 測試排程器
    await test_scheduler()
    
    # 5. 測試警報查詢
    await test_alert_query()
    
    # 6. 與原始版本對比
    await compare_with_original()
    
    logger.info("\n✅ 基本測試完成！")
    logger.info("📝 下一步：")
    logger.info("   1. 運行 main_new.py 測試完整應用")
    logger.info("   2. 比較與 main.py 的功能差異")
    logger.info("   3. 進行性能和穩定性測試")
    logger.info("   4. 逐步遷移到新架構")

if __name__ == "__main__":
    asyncio.run(main())