#!/usr/bin/env python3
"""
OpenSearch 索引範本設置腳本
用於手動建立和驗證 Wazuh 警報向量化所需的索引範本
"""

import os
import asyncio
import logging
import json
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

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

async def create_index_template(client):
    """建立或更新索引範本"""
    template_name = "wazuh-alerts-vector-template"
    
    # 索引範本定義
    template_body = {
        "index_patterns": ["wazuh-alerts-*"],
        "priority": 1,
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "index": {
                    "knn": True,  # 啟用 KNN 搜尋
                    "knn.algo_param.ef_search": 512
                }
            },
            "mappings": {
                "properties": {
                    "alert_vector": {
                        "type": "dense_vector",
                        "dims": 768,  # Gemini text-embedding-004 預設維度
                        "index": True,
                        "similarity": "cosine",
                        "index_options": {
                            "type": "hnsw",
                            "m": 16,
                            "ef_construction": 512
                        }
                    },
                    "ai_analysis": {
                        "type": "object",
                        "properties": {
                            "triage_report": {
                                "type": "text",
                                "analyzer": "standard"
                            },
                            "provider": {
                                "type": "keyword"
                            },
                            "timestamp": {
                                "type": "date"
                            },
                            "risk_level": {
                                "type": "keyword"
                            },
                            "vector_dimension": {
                                "type": "integer"
                            },
                            "processing_time_ms": {
                                "type": "integer"
                            }
                        }
                    }
                }
            }
        }
    }
    
    try:
        # 檢查範本是否已存在
        try:
            existing_template = await client.indices.get_index_template(name=template_name)
            logger.info(f"索引範本 '{template_name}' 已存在")
            
            # 顯示現有範本的詳細資訊
            if existing_template and 'index_templates' in existing_template:
                for template in existing_template['index_templates']:
                    if template['name'] == template_name:
                        logger.info(f"現有範本配置: {json.dumps(template, indent=2, ensure_ascii=False)}")
            
            # 詢問是否要更新
            response = input("是否要更新現有的索引範本? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                logger.info("跳過範本更新")
                return True
                
        except Exception:
            logger.info(f"索引範本 '{template_name}' 不存在，將建立新範本")
        
        # 建立或更新範本
        await client.indices.put_index_template(name=template_name, body=template_body)
        logger.info(f"✅ 成功建立/更新索引範本: {template_name}")
        
        # 驗證範本
        template_response = await client.indices.get_index_template(name=template_name)
        logger.info(f"✅ 範本驗證成功: {template_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 建立索引範本失敗: {str(e)}")
        return False

async def verify_existing_indices(client):
    """檢查現有的 wazuh-alerts 索引"""
    try:
        # 獲取所有 wazuh-alerts 索引
        indices_response = await client.indices.get(index="wazuh-alerts-*")
        
        if not indices_response:
            logger.info("目前沒有 wazuh-alerts-* 索引")
            return True
        
        logger.info(f"找到 {len(indices_response)} 個 wazuh-alerts 索引:")
        
        for index_name, index_info in indices_response.items():
            logger.info(f"  📁 {index_name}")
            
            # 檢查索引的 mapping
            mappings = index_info.get('mappings', {})
            properties = mappings.get('properties', {})
            
            has_vector_field = 'alert_vector' in properties
            has_ai_analysis = 'ai_analysis' in properties
            
            logger.info(f"    - alert_vector 欄位: {'✅' if has_vector_field else '❌'}")
            logger.info(f"    - ai_analysis 欄位: {'✅' if has_ai_analysis else '❌'}")
            
            if has_vector_field:
                vector_config = properties['alert_vector']
                logger.info(f"    - 向量維度: {vector_config.get('dims', 'Unknown')}")
                logger.info(f"    - 相似度算法: {vector_config.get('similarity', 'Unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"檢查現有索引時發生錯誤: {str(e)}")
        return False

async def test_vector_operations(client):
    """測試向量操作"""
    try:
        # 建立測試索引
        test_index = "test-vector-index"
        test_doc = {
            "test_field": "test content",
            "alert_vector": [0.1] * 768,  # 測試向量
            "ai_analysis": {
                "triage_report": "Test analysis",
                "provider": "test",
                "timestamp": "2024-01-01T00:00:00.000Z"
            }
        }
        
        # 建立測試文件
        await client.index(index=test_index, body=test_doc, id="test-doc")
        logger.info("✅ 成功建立測試文件")
        
        # 等待索引
        await asyncio.sleep(2)
        
        # 測試向量搜尋
        search_vector = [0.1] * 768
        search_body = {
            "query": {
                "knn": {
                    "alert_vector": {
                        "vector": search_vector,
                        "k": 1
                    }
                }
            }
        }
        
        search_response = await client.search(index=test_index, body=search_body)
        
        if search_response['hits']['total']['value'] > 0:
            logger.info("✅ 向量搜尋測試成功")
        else:
            logger.warning("⚠️ 向量搜尋沒有返回結果")
        
        # 清理測試索引
        await client.indices.delete(index=test_index)
        logger.info("✅ 清理測試索引完成")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 向量操作測試失敗: {str(e)}")
        return False

async def main():
    """主要執行函數"""
    logger.info("🚀 開始設置 OpenSearch 索引範本...")
    
    # 建立客戶端
    client = await get_opensearch_client()
    
    try:
        # 測試連線
        cluster_health = await client.cluster.health()
        logger.info(f"✅ OpenSearch 連線成功: {cluster_health['cluster_name']}")
        
        # 1. 檢查現有索引
        logger.info("\n📊 檢查現有索引...")
        await verify_existing_indices(client)
        
        # 2. 建立索引範本
        logger.info("\n🛠️ 建立索引範本...")
        template_success = await create_index_template(client)
        
        if template_success:
            # 3. 測試向量操作
            logger.info("\n🧪 測試向量操作...")
            await test_vector_operations(client)
            
            logger.info("\n🎉 索引範本設置完成!")
            logger.info("現在您可以啟動 AI Agent，新的警報將自動包含向量欄位。")
        else:
            logger.error("❌ 索引範本設置失敗")
            
    except Exception as e:
        logger.error(f"❌ 設置過程中發生錯誤: {str(e)}")
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())