#!/usr/bin/env python3
"""
快速修正向量欄位問題的自動化腳本
無需使用者互動，適合背景執行
"""

import os
import asyncio
import logging
from datetime import datetime
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# 設置日誌
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenSearch 連線配置
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")


async def quick_fix():
    """快速修正向量欄位問題"""
    client = AsyncOpenSearch(
        hosts=[OPENSEARCH_URL],
        http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
        connection_class=AsyncHttpConnection
    )
    
    try:
        logger.info("🚀 開始快速修正向量欄位問題...")
        
        # 1. 定義索引模板
        template_name = "wazuh-alerts-vector-template"
        template_body = {
            "index_patterns": ["wazuh-alerts-*"],
            "priority": 1,
            "template": {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 512
                    }
                },
                "mappings": {
                    "properties": {
                        "alert_vector": {
                            "type": "dense_vector",
                            "dims": 768,
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
                                "triage_report": {"type": "text", "analyzer": "standard"},
                                "provider": {"type": "keyword"},
                                "timestamp": {"type": "date"},
                                "risk_level": {"type": "keyword"},
                                "vector_dimension": {"type": "integer"},
                                "processing_time_ms": {"type": "integer"}
                            }
                        }
                    }
                }
            }
        }
        
        # 2. 刪除並重建索引模板
        try:
            await client.indices.delete_index_template(name=template_name)
            logger.info("已刪除舊的索引模板")
        except:
            pass
            
        response = await client.indices.put_index_template(
            name=template_name,
            body=template_body
        )
        
        if response.get('acknowledged'):
            logger.info("✅ 索引模板建立成功")
        else:
            logger.error("❌ 索引模板建立失敗")
            return
            
        # 3. 檢查現有索引
        try:
            indices = await client.indices.get("wazuh-alerts-*")
            index_list = list(indices.keys())
            logger.info(f"找到 {len(index_list)} 個 Wazuh 索引")
        except:
            logger.info("沒有找到現有的 Wazuh 索引，模板已設置完成")
            return
            
        # 4. 檢查每個索引是否需要修正
        for index_name in index_list:
            try:
                mapping = await client.indices.get_mapping(index=index_name)
                properties = mapping[index_name]['mappings'].get('properties', {})
                
                if 'alert_vector' in properties:
                    vector_type = properties['alert_vector'].get('type')
                    if vector_type == 'dense_vector':
                        logger.info(f"✅ {index_name} 的向量欄位已正確配置")
                        continue
                        
                logger.info(f"⚠️  {index_name} 需要修正向量欄位")
                
                # 5. 重新索引
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_index = f"{index_name}-fixed-{timestamp}"
                
                # 建立新索引
                await client.indices.create(index=new_index)
                logger.info(f"建立新索引: {new_index}")
                
                # 重新索引資料
                reindex_body = {
                    "source": {"index": index_name},
                    "dest": {"index": new_index}
                }
                
                response = await client.reindex(body=reindex_body)
                total = response.get('total', 0)
                logger.info(f"重新索引完成: 共 {total} 筆文件")
                
                # 刪除舊索引並建立別名
                await client.indices.delete(index=index_name)
                await client.indices.put_alias(index=new_index, name=index_name)
                logger.info(f"✅ {index_name} 修正完成")
                
            except Exception as e:
                logger.error(f"處理 {index_name} 時發生錯誤: {str(e)}")
                continue
                
        # 6. 測試向量搜尋
        logger.info("\n測試向量搜尋功能...")
        test_vector = [0.1] * 768
        search_body = {
            "size": 1,
            "query": {
                "knn": {
                    "alert_vector": {
                        "vector": test_vector,
                        "k": 1
                    }
                }
            }
        }
        
        try:
            response = await client.search(
                index="wazuh-alerts-*",
                body=search_body
            )
            logger.info("✅ 向量搜尋測試成功")
        except Exception as e:
            if "is not knn_vector type" in str(e):
                logger.error("❌ 向量搜尋測試失敗：欄位類型仍然不正確")
            else:
                logger.warning(f"向量搜尋測試警告: {str(e)}")
                
        logger.info("\n🎉 向量欄位修正程序完成！")
        
    except Exception as e:
        logger.error(f"修正過程發生錯誤: {str(e)}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(quick_fix())