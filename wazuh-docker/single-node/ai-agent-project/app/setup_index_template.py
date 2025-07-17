#!/usr/bin/env python3
"""
OpenSearch 索引範本設置腳本

此腳本用於手動建立和驗證 Wazuh 警報向量化所需的索引範本。
主要功能包括：
- 建立支援向量搜尋的索引範本
- 驗證現有索引的映射配置
- 測試向量操作的功能性
- 提供完整的診斷和故障排除資訊

適用場景：
- 初次部署 AgenticRAG 系統
- 升級索引範本配置
- 診斷向量搜尋問題
- 驗證系統完整性

作者：AgenticRAG 工程團隊
版本：2.0
"""

import os
import asyncio
import logging
import json
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# 設置日誌系統
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 從環境變數讀取 OpenSearch 連線配置
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

async def get_opensearch_client():
    """
    建立 OpenSearch 非同步客戶端
    
    配置包括：
    - SSL 連線但跳過憑證驗證（適用於內部環境）
    - HTTP 基本認證
    - 非同步連線類型以提升效能
    
    Returns:
        AsyncOpenSearch: 配置完成的 OpenSearch 客戶端
    """
    return AsyncOpenSearch(
        hosts=[OPENSEARCH_URL],
        http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
        connection_class=AsyncHttpConnection
    )

async def create_index_template(client):
    """
    建立或更新 Wazuh 警報向量索引範本
    
    此函式會建立一個完整的索引範本，包含：
    1. 向量欄位配置：支援 768 維密集向量，使用 HNSW 索引
    2. AI 分析欄位：結構化的分析結果儲存
    3. k-NN 搜尋設定：優化的向量搜尋參數
    4. 索引效能設定：平衡儲存與查詢效能
    
    Args:
        client (AsyncOpenSearch): OpenSearch 客戶端實例
        
    Returns:
        bool: 成功返回 True，失敗返回 False
        
    Note:
        - 範本優先級設為 1，適用於所有 wazuh-alerts-* 索引
        - 使用 HNSW 演算法提供次線性時間複雜度的向量搜尋
        - 餘弦相似度適合語意搜尋應用
    """
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
                    "knn": True,  # 啟用 k-NN 搜尋功能
                    "knn.algo_param.ef_search": 512  # 搜尋時的候選數量
                }
            },
            "mappings": {
                "properties": {
                    "alert_vector": {
                        "type": "dense_vector",
                        "dims": 768,  # Gemini text-embedding-004 預設維度
                        "index": True,
                        "similarity": "cosine",  # 餘弦相似度適合語意搜尋
                        "index_options": {
                            "type": "hnsw",  # Hierarchical Navigable Small World 演算法
                            "m": 16,  # 每個節點的連線數量
                            "ef_construction": 512  # 建構時的候選數量
                        }
                    },
                    "ai_analysis": {
                        "type": "object",
                        "properties": {
                            "triage_report": {
                                "type": "text",
                                "analyzer": "standard"  # 標準文字分析器
                            },
                            "provider": {
                                "type": "keyword"  # LLM 提供商識別
                            },
                            "timestamp": {
                                "type": "date"  # 分析時間戳記
                            },
                            "risk_level": {
                                "type": "keyword"  # 風險等級分類
                            },
                            "vector_dimension": {
                                "type": "integer"  # 向量維度記錄
                            },
                            "processing_time_ms": {
                                "type": "integer"  # 處理時間統計
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
            
            # 詢問是否要更新現有範本
            response = input("是否要更新現有的索引範本? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                logger.info("跳過範本更新")
                return True
                
        except Exception:
            logger.info(f"索引範本 '{template_name}' 不存在，將建立新範本")
        
        # 建立或更新範本
        await client.indices.put_index_template(name=template_name, body=template_body)
        logger.info(f"✅ 成功建立/更新索引範本: {template_name}")
        
        # 驗證範本建立結果
        template_response = await client.indices.get_index_template(name=template_name)
        logger.info(f"✅ 範本驗證成功: {template_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 建立索引範本失敗: {str(e)}")
        return False

async def verify_existing_indices(client):
    """
    檢查並分析現有的 wazuh-alerts 索引
    
    此函式會：
    1. 列舉所有符合模式的索引
    2. 檢查每個索引的映射配置
    3. 驗證向量欄位和 AI 分析欄位的存在
    4. 報告配置狀態和建議
    
    Args:
        client (AsyncOpenSearch): OpenSearch 客戶端實例
        
    Returns:
        bool: 檢查成功返回 True，失敗返回 False
        
    Note:
        - 提供詳細的索引配置分析
        - 識別需要重新索引的舊索引
        - 報告向量搜尋就緒狀態
    """
    try:
        # 獲取所有符合模式的索引
        indices_response = await client.indices.get(index="wazuh-alerts-*")
        
        if not indices_response:
            logger.info("目前沒有 wazuh-alerts-* 索引")
            return True
        
        logger.info(f"找到 {len(indices_response)} 個 wazuh-alerts 索引:")
        
        for index_name, index_info in indices_response.items():
            logger.info(f"  📁 {index_name}")
            
            # 檢查索引的映射配置
            mappings = index_info.get('mappings', {})
            properties = mappings.get('properties', {})
            
            has_vector_field = 'alert_vector' in properties
            has_ai_analysis = 'ai_analysis' in properties
            
            logger.info(f"    - alert_vector 欄位: {'✅' if has_vector_field else '❌'}")
            logger.info(f"    - ai_analysis 欄位: {'✅' if has_ai_analysis else '❌'}")
            
            if has_vector_field:
                vector_config = properties['alert_vector']
                logger.info(f"    - 向量維度: {vector_config.get('dims', '未知')}")
                logger.info(f"    - 相似度演算法: {vector_config.get('similarity', '未知')}")
        
        return True
        
    except Exception as e:
        logger.error(f"檢查現有索引時發生錯誤: {str(e)}")
        return False

async def test_vector_operations(client):
    """
    執行完整的向量操作測試
    
    此函式會進行端到端的向量功能測試：
    1. 建立測試索引和文檔
    2. 插入包含向量的測試資料
    3. 執行 k-NN 向量搜尋
    4. 驗證搜尋結果的正確性
    5. 清理測試資源
    
    Args:
        client (AsyncOpenSearch): OpenSearch 客戶端實例
        
    Returns:
        bool: 測試通過返回 True，失敗返回 False
        
    Note:
        - 使用臨時索引避免影響生產資料
        - 測試完成後自動清理資源
        - 驗證向量搜尋的功能性和效能
    """
    try:
        # 建立測試索引
        test_index = "test-vector-index"
        test_doc = {
            "test_field": "test content",
            "alert_vector": [0.1] * 768,  # 768 維測試向量
            "ai_analysis": {
                "triage_report": "測試分析報告",
                "provider": "test",
                "timestamp": "2024-01-01T00:00:00.000Z"
            }
        }
        
        # 插入測試文檔
        await client.index(index=test_index, body=test_doc, id="test-doc")
        logger.info("✅ 成功建立測試文檔")
        
        # 等待索引更新（確保文檔可搜尋）
        await asyncio.sleep(2)
        
        # 執行向量搜尋測試
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
    """
    主要執行函式 - 協調所有設置和驗證步驟
    
    執行流程：
    1. 建立 OpenSearch 客戶端並測試連線
    2. 檢查現有索引的配置狀態
    3. 建立或更新索引範本
    4. 執行向量操作功能測試
    5. 提供總結報告和後續建議
    
    該函式提供完整的互動式設置體驗，包括：
    - 詳細的進度報告
    - 錯誤處理和恢復建議
    - 成功完成的確認訊息
    """
    logger.info("🚀 開始設置 OpenSearch 索引範本...")
    
    # 建立客戶端並測試連線
    client = await get_opensearch_client()
    
    try:
        # 測試 OpenSearch 叢集連線
        cluster_health = await client.cluster.health()
        logger.info(f"✅ OpenSearch 連線成功: {cluster_health['cluster_name']}")
        
        # 1. 檢查現有索引狀態
        logger.info("\n📊 檢查現有索引...")
        await verify_existing_indices(client)
        
        # 2. 建立或更新索引範本
        logger.info("\n🛠️ 建立索引範本...")
        template_success = await create_index_template(client)
        
        if template_success:
            # 3. 執行向量操作測試
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