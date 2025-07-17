#!/usr/bin/env python3
"""
驗證向量化流程腳本
檢查 Wazuh 警報是否成功向量化並儲存到 OpenSearch
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection
from embedding_service import GeminiEmbeddingService

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 從環境變數讀取配置
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

async def get_opensearch_client():
    """建立 OpenSearch 客戶端"""
    return AsyncOpenSearch(
        hosts=[OPENSEARCH_URL],
        http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
        connection_class=AsyncHttpConnection
    )

async def check_embedding_service():
    """檢查 Embedding 服務是否正常工作"""
    logger.info("🧪 測試 Embedding 服務...")
    
    try:
        embedding_service = GeminiEmbeddingService()
        
        # 測試連線
        connection_ok = await embedding_service.test_connection()
        if not connection_ok:
            logger.error("❌ Embedding 服務連線失敗")
            return False
        
        # 測試向量化
        test_alert = {
            'rule': {
                'description': 'Test SSH login attempt',
                'level': 5,
                'id': '5715',
                'groups': ['syslog', 'sshd']
            },
            'agent': {
                'name': 'test-server'
            },
            'data': {
                'srcip': '192.168.1.100',
                'user': 'admin'
            }
        }
        
        vector = await embedding_service.embed_alert_content(test_alert)
        
        if vector and len(vector) > 0:
            logger.info(f"✅ Embedding 服務正常，向量維度: {len(vector)}")
            return True
        else:
            logger.error("❌ Embedding 服務返回空向量")
            return False
            
    except Exception as e:
        logger.error(f"❌ Embedding 服務測試失敗: {str(e)}")
        return False

async def check_vectorized_alerts(client):
    """檢查已向量化的警報"""
    logger.info("🔍 檢查已向量化的警報...")
    
    try:
        # 搜尋包含向量的警報
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "alert_vector"}},
                        {"exists": {"field": "ai_analysis"}}
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "_source": ["rule", "agent", "ai_analysis", "timestamp"]
        }
        
        response = await client.search(
            index="wazuh-alerts-*",
            body=search_body,
            size=10
        )
        
        total_vectorized = response['hits']['total']['value']
        alerts = response['hits']['hits']
        
        logger.info(f"📊 找到 {total_vectorized} 個已向量化的警報")
        
        if alerts:
            logger.info("最近的向量化警報:")
            for i, alert in enumerate(alerts[:5], 1):
                source = alert['_source']
                rule = source.get('rule', {})
                agent = source.get('agent', {})
                ai_analysis = source.get('ai_analysis', {})
                
                logger.info(f"  {i}. 警報ID: {alert['_id']}")
                logger.info(f"     規則: {rule.get('description', 'N/A')}")
                logger.info(f"     主機: {agent.get('name', 'N/A')}")
                logger.info(f"     分析提供者: {ai_analysis.get('provider', 'N/A')}")
                logger.info(f"     向量維度: {ai_analysis.get('vector_dimension', 'N/A')}")
                logger.info("")
        
        return total_vectorized > 0
        
    except Exception as e:
        logger.error(f"❌ 檢查向量化警報失敗: {str(e)}")
        return False

async def test_vector_search(client):
    """測試向量搜尋功能"""
    logger.info("🎯 測試向量搜尋功能...")
    
    try:
        # 先取得一個已向量化的警報
        search_body = {
            "query": {"exists": {"field": "alert_vector"}},
            "size": 1
        }
        
        response = await client.search(
            index="wazuh-alerts-*",
            body=search_body
        )
        
        if not response['hits']['hits']:
            logger.warning("⚠️ 沒有找到已向量化的警報進行測試")
            return False
        
        # 取得第一個警報的向量
        first_alert = response['hits']['hits'][0]
        alert_vector = first_alert['_source'].get('alert_vector')
        
        if not alert_vector:
            logger.error("❌ 警報沒有向量欄位")
            return False
        
        # 使用這個向量進行相似搜尋
        vector_search_body = {
            "query": {
                "knn": {
                    "alert_vector": {
                        "vector": alert_vector,
                        "k": 5
                    }
                }
            },
            "_source": ["rule", "agent", "ai_analysis", "timestamp"]
        }
        
        similar_response = await client.search(
            index="wazuh-alerts-*",
            body=vector_search_body,
            size=5
        )
        
        similar_alerts = similar_response['hits']['hits']
        
        if similar_alerts:
            logger.info(f"✅ 向量搜尋成功，找到 {len(similar_alerts)} 個相似警報")
            
            for i, alert in enumerate(similar_alerts, 1):
                score = alert.get('_score', 0)
                rule = alert['_source'].get('rule', {})
                logger.info(f"  {i}. 相似度: {score:.4f} - {rule.get('description', 'N/A')}")
            
            return True
        else:
            logger.warning("⚠️ 向量搜尋沒有返回結果")
            return False
            
    except Exception as e:
        logger.error(f"❌ 向量搜尋測試失敗: {str(e)}")
        return False

async def check_new_alerts(client):
    """檢查是否有待處理的新警報"""
    logger.info("📥 檢查待處理的新警報...")
    
    try:
        search_body = {
            "query": {
                "bool": {
                    "must_not": [{"exists": {"field": "ai_analysis"}}]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
        }
        
        response = await client.search(
            index="wazuh-alerts-*",
            body=search_body,
            size=5
        )
        
        new_alerts_count = response['hits']['total']['value']
        alerts = response['hits']['hits']
        
        logger.info(f"📊 找到 {new_alerts_count} 個待處理的新警報")
        
        if alerts:
            logger.info("最新的待處理警報:")
            for i, alert in enumerate(alerts, 1):
                source = alert['_source']
                rule = source.get('rule', {})
                agent = source.get('agent', {})
                
                logger.info(f"  {i}. 警報ID: {alert['_id']}")
                logger.info(f"     規則: {rule.get('description', 'N/A')}")
                logger.info(f"     主機: {agent.get('name', 'N/A')}")
                logger.info(f"     時間: {source.get('timestamp', 'N/A')}")
                logger.info("")
        
        return new_alerts_count
        
    except Exception as e:
        logger.error(f"❌ 檢查新警報失敗: {str(e)}")
        return -1

async def verify_index_template(client):
    """驗證索引範本是否正確設置"""
    logger.info("🛠️ 驗證索引範本...")
    
    try:
        template_name = "wazuh-alerts-vector-template"
        
        # 檢查範本是否存在
        template_response = await client.indices.get_index_template(name=template_name)
        
        if not template_response or 'index_templates' not in template_response:
            logger.error(f"❌ 索引範本 '{template_name}' 不存在")
            return False
        
        template = template_response['index_templates'][0]
        mappings = template['index_template']['template']['mappings']
        properties = mappings.get('properties', {})
        
        # 檢查 alert_vector 欄位
        if 'alert_vector' not in properties:
            logger.error("❌ 索引範本缺少 alert_vector 欄位")
            return False
        
        vector_config = properties['alert_vector']
        if vector_config.get('type') != 'dense_vector':
            logger.error("❌ alert_vector 欄位類型不正確")
            return False
        
        # 檢查 ai_analysis 欄位
        if 'ai_analysis' not in properties:
            logger.error("❌ 索引範本缺少 ai_analysis 欄位")
            return False
        
        logger.info("✅ 索引範本配置正確")
        logger.info(f"   - 向量維度: {vector_config.get('dims', 'Unknown')}")
        logger.info(f"   - 相似度算法: {vector_config.get('similarity', 'Unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 驗證索引範本失敗: {str(e)}")
        return False

async def main():
    """主要驗證流程"""
    logger.info("🚀 開始驗證向量化流程...")
    
    # 驗證結果統計
    checks = {
        "embedding_service": False,
        "index_template": False,
        "vectorized_alerts": False,
        "vector_search": False,
        "new_alerts_check": False
    }
    
    try:
        # 1. 檢查 Embedding 服務
        logger.info("\n" + "="*50)
        checks["embedding_service"] = await check_embedding_service()
        
        # 2. 建立 OpenSearch 客戶端並檢查連線
        client = await get_opensearch_client()
        cluster_health = await client.cluster.health()
        logger.info(f"✅ OpenSearch 連線成功: {cluster_health['cluster_name']}")
        
        # 3. 驗證索引範本
        logger.info("\n" + "="*50)
        checks["index_template"] = await verify_index_template(client)
        
        # 4. 檢查已向量化的警報
        logger.info("\n" + "="*50)
        checks["vectorized_alerts"] = await check_vectorized_alerts(client)
        
        # 5. 測試向量搜尋
        if checks["vectorized_alerts"]:
            logger.info("\n" + "="*50)
            checks["vector_search"] = await test_vector_search(client)
        
        # 6. 檢查新警報
        logger.info("\n" + "="*50)
        new_alerts_count = await check_new_alerts(client)
        checks["new_alerts_check"] = new_alerts_count >= 0
        
        # 結果總結
        logger.info("\n" + "="*50)
        logger.info("📋 驗證結果總結:")
        
        for check_name, result in checks.items():
            status = "✅ 通過" if result else "❌ 失敗"
            logger.info(f"   {check_name}: {status}")
        
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        
        logger.info(f"\n總體結果: {passed_checks}/{total_checks} 項檢查通過")
        
        if passed_checks == total_checks:
            logger.info("🎉 所有檢查都通過！向量化流程運行正常。")
        elif passed_checks >= total_checks * 0.8:
            logger.info("⚠️ 大部分檢查通過，系統基本正常運行。")
        else:
            logger.error("❌ 多項檢查失敗，請檢查配置和環境。")
        
        if new_alerts_count > 0:
            logger.info(f"\n💡 提示: 有 {new_alerts_count} 個新警報等待處理。")
            logger.info("    請確保 AI Agent 正在運行以處理這些警報。")
        
        await client.close()
        
    except Exception as e:
        logger.error(f"❌ 驗證過程中發生錯誤: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())