#!/usr/bin/env python3
"""
OpenSearch 索引模板設定腳本
用於確保 wazuh-alerts-* 索引包含向量搜尋所需的 alert_vector 欄位
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OpenSearchTemplateManager:
    """OpenSearch 索引模板管理器"""
    
    def __init__(self):
        self.opensearch_url = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
        self.opensearch_user = os.getenv("OPENSEARCH_USER", "admin")
        self.opensearch_password = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")
        self.embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))
        
        self.client = AsyncOpenSearch(
            hosts=[self.opensearch_url],
            http_auth=(self.opensearch_user, self.opensearch_password),
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False,
            connection_class=AsyncHttpConnection
        )
    
    async def test_connection(self) -> bool:
        """測試 OpenSearch 連接"""
        try:
            info = await self.client.info()
            logger.info(f"成功連接到 OpenSearch: {info['version']['number']}")
            return True
        except Exception as e:
            logger.error(f"無法連接到 OpenSearch: {str(e)}")
            return False
    
    def get_wazuh_alerts_template(self) -> Dict[str, Any]:
        """獲取 wazuh-alerts 索引模板配置"""
        return {
            "index_patterns": ["wazuh-alerts-*"],
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.knn": True,  # 啟用 KNN 搜尋
                "index.knn.algo_param.ef_search": 100,  # KNN 搜尋參數
                "index.knn.space_type": "cosinesimil"   # 使用餘弦相似度
            },
            "mappings": {
                "properties": {
                    "alert_vector": {
                        "type": "knn_vector",
                        "dimension": self.embedding_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 200,
                                "m": 16
                            }
                        }
                    },
                    "ai_analysis": {
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
                            "confidence_score": {
                                "type": "float"
                            }
                        }
                    },
                    # 確保原有的 Wazuh 欄位仍可正常使用
                    "rule": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "level": {"type": "integer"},
                            "description": {"type": "text"},
                            "groups": {"type": "keyword"}
                        }
                    },
                    "agent": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "name": {"type": "keyword"},
                            "ip": {"type": "ip"}
                        }
                    },
                    "timestamp": {
                        "type": "date"
                    }
                }
            }
        }
    
    async def create_or_update_template(self, template_name: str) -> bool:
        """建立或更新索引模板"""
        try:
            template_body = self.get_wazuh_alerts_template()
            
            # 檢查模板是否已存在
            template_exists = await self.client.indices.exists_template(name=template_name)
            
            if template_exists:
                logger.info(f"索引模板 '{template_name}' 已存在，正在更新...")
                # 刪除舊模板
                await self.client.indices.delete_template(name=template_name)
                logger.info(f"已刪除舊的索引模板 '{template_name}'")
            
            # 建立新模板
            await self.client.indices.put_template(name=template_name, body=template_body)
            logger.info(f"成功建立/更新索引模板 '{template_name}'")
            
            # 驗證模板
            template_info = await self.client.indices.get_template(name=template_name)
            logger.info(f"模板驗證成功: {template_name}")
            logger.info(f"索引模式: {template_info[template_name]['index_patterns']}")
            logger.info(f"向量維度: {self.embedding_dimension}")
            
            return True
            
        except Exception as e:
            logger.error(f"建立/更新索引模板失敗: {str(e)}")
            return False
    
    async def check_existing_indices(self) -> None:
        """檢查現有的 wazuh-alerts 索引並更新映射"""
        try:
            # 獲取所有匹配的索引
            indices_response = await self.client.indices.get("wazuh-alerts-*")
            
            for index_name in indices_response.keys():
                logger.info(f"檢查索引: {index_name}")
                
                # 檢查是否已有 alert_vector 欄位
                mapping = await self.client.indices.get_mapping(index=index_name)
                properties = mapping[index_name]['mappings'].get('properties', {})
                
                if 'alert_vector' not in properties:
                    logger.info(f"為索引 {index_name} 添加 alert_vector 欄位")
                    
                    # 添加 alert_vector 欄位映射
                    await self.client.indices.put_mapping(
                        index=index_name,
                        body={
                            "properties": {
                                "alert_vector": {
                                    "type": "knn_vector",
                                    "dimension": self.embedding_dimension,
                                    "method": {
                                        "name": "hnsw",
                                        "space_type": "cosinesimil",
                                        "engine": "nmslib"
                                    }
                                }
                            }
                        }
                    )
                    logger.info(f"成功為索引 {index_name} 添加 alert_vector 欄位")
                else:
                    logger.info(f"索引 {index_name} 已包含 alert_vector 欄位")
                    
        except Exception as e:
            logger.warning(f"檢查現有索引時發生錯誤: {str(e)}")
    
    async def close(self):
        """關閉 OpenSearch 連接"""
        await self.client.close()

async def main():
    """主要執行函式"""
    logger.info("開始設定 OpenSearch 索引模板...")
    
    template_manager = OpenSearchTemplateManager()
    
    try:
        # 測試連接
        if not await template_manager.test_connection():
            logger.error("無法連接到 OpenSearch，請檢查配置")
            sys.exit(1)
        
        # 建立索引模板
        template_name = "wazuh-alerts-ai-template"
        success = await template_manager.create_or_update_template(template_name)
        
        if not success:
            logger.error("索引模板設定失敗")
            sys.exit(1)
        
        # 檢查並更新現有索引
        await template_manager.check_existing_indices()
        
        logger.info("索引模板設定完成！")
        
    except Exception as e:
        logger.error(f"設定過程中發生錯誤: {str(e)}")
        sys.exit(1)
    
    finally:
        await template_manager.close()

if __name__ == "__main__":
    asyncio.run(main())