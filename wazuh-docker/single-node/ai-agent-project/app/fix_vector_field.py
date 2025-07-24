#!/usr/bin/env python3
"""
修正 OpenSearch 中 alert_vector 欄位類型錯誤的腳本

問題：Field 'alert_vector' is not knn_vector type
原因：現有索引沒有正確的向量欄位映射

解決方案：
1. 確保索引模板已正確套用
2. 重新索引現有資料到新索引
3. 驗證向量搜尋功能

作者：資深 Python 工程師
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection
from typing import Dict, List, Optional

# 設置日誌
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenSearch 連線配置
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")


class VectorFieldFixer:
    """修正向量欄位問題的主要類別"""
    
    def __init__(self):
        self.client = None
        self.template_name = "wazuh-alerts-vector-template"
        
    async def __aenter__(self):
        """非同步上下文管理器進入"""
        self.client = AsyncOpenSearch(
            hosts=[OPENSEARCH_URL],
            http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False,
            connection_class=AsyncHttpConnection
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同步上下文管理器退出"""
        if self.client:
            await self.client.close()
            
    async def check_existing_indices(self) -> List[str]:
        """檢查現有的 Wazuh 索引"""
        logger.info("🔍 檢查現有的 Wazuh 索引...")
        
        try:
            # 獲取所有 wazuh-alerts-* 索引
            indices = await self.client.indices.get("wazuh-alerts-*")
            index_list = list(indices.keys())
            
            logger.info(f"找到 {len(index_list)} 個 Wazuh 索引:")
            for idx in index_list:
                logger.info(f"  - {idx}")
                
            return index_list
            
        except Exception as e:
            logger.error(f"檢查索引失敗: {str(e)}")
            return []
            
    async def check_index_mapping(self, index_name: str) -> Dict:
        """檢查索引的映射配置"""
        try:
            mapping = await self.client.indices.get_mapping(index=index_name)
            properties = mapping[index_name]['mappings'].get('properties', {})
            
            # 檢查 alert_vector 欄位
            if 'alert_vector' in properties:
                vector_config = properties['alert_vector']
                logger.info(f"\n📋 索引 {index_name} 的 alert_vector 欄位配置:")
                logger.info(f"  類型: {vector_config.get('type', 'undefined')}")
                
                if vector_config.get('type') == 'dense_vector':
                    logger.info("  ✅ 欄位類型正確")
                    logger.info(f"  維度: {vector_config.get('dims', 'undefined')}")
                    logger.info(f"  相似度: {vector_config.get('similarity', 'undefined')}")
                else:
                    logger.warning(f"  ❌ 欄位類型不正確: {vector_config.get('type')}")
                    
                return vector_config
            else:
                logger.warning(f"  ❌ 索引 {index_name} 沒有 alert_vector 欄位")
                return {}
                
        except Exception as e:
            logger.error(f"檢查映射失敗: {str(e)}")
            return {}
            
    async def ensure_index_template(self) -> bool:
        """確保索引模板已正確設置"""
        logger.info("\n🔧 確保索引模板已正確設置...")
        
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
            # 刪除舊的模板（如果存在）
            try:
                await self.client.indices.delete_index_template(name=self.template_name)
                logger.info("  已刪除舊的索引模板")
            except:
                pass
                
            # 建立新的模板
            response = await self.client.indices.put_index_template(
                name=self.template_name,
                body=template_body
            )
            
            if response.get('acknowledged'):
                logger.info("  ✅ 索引模板建立成功")
                return True
            else:
                logger.error("  ❌ 索引模板建立失敗")
                return False
                
        except Exception as e:
            logger.error(f"  ❌ 設置索引模板時發生錯誤: {str(e)}")
            return False
            
    async def reindex_with_correct_mapping(self, source_index: str) -> bool:
        """重新索引資料到具有正確映射的新索引"""
        logger.info(f"\n📦 重新索引 {source_index}...")
        
        # 產生新索引名稱
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_index = f"{source_index}-fixed-{timestamp}"
        
        try:
            # 建立新索引（會自動套用模板）
            await self.client.indices.create(index=temp_index)
            logger.info(f"  建立臨時索引: {temp_index}")
            
            # 執行重新索引
            reindex_body = {
                "source": {
                    "index": source_index
                },
                "dest": {
                    "index": temp_index
                }
            }
            
            response = await self.client.reindex(body=reindex_body)
            total = response.get('total', 0)
            logger.info(f"  重新索引完成: 共 {total} 筆文件")
            
            # 刪除舊索引
            await self.client.indices.delete(index=source_index)
            logger.info(f"  已刪除舊索引: {source_index}")
            
            # 建立別名指向新索引
            await self.client.indices.put_alias(index=temp_index, name=source_index)
            logger.info(f"  建立別名: {source_index} -> {temp_index}")
            
            return True
            
        except Exception as e:
            logger.error(f"  ❌ 重新索引失敗: {str(e)}")
            return False
            
    async def test_vector_search(self, index_name: str) -> bool:
        """測試向量搜尋功能"""
        logger.info(f"\n🧪 測試向量搜尋功能 (索引: {index_name})...")
        
        try:
            # 建立測試向量
            test_vector = [0.1] * 768
            
            # 執行向量搜尋
            search_body = {
                "size": 5,
                "query": {
                    "knn": {
                        "alert_vector": {
                            "vector": test_vector,
                            "k": 5
                        }
                    }
                }
            }
            
            response = await self.client.search(
                index=index_name,
                body=search_body
            )
            
            hits = response.get('hits', {}).get('total', {}).get('value', 0)
            logger.info(f"  ✅ 向量搜尋成功，找到 {hits} 筆結果")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "is not knn_vector type" in error_msg:
                logger.error(f"  ❌ 向量搜尋失敗: 欄位類型錯誤")
            else:
                logger.error(f"  ❌ 向量搜尋失敗: {error_msg}")
            return False
            
    async def fix_all_indices(self) -> None:
        """修正所有索引的向量欄位問題"""
        logger.info("🚀 開始修正向量欄位問題...\n")
        
        # 1. 確保索引模板正確
        if not await self.ensure_index_template():
            logger.error("無法設置索引模板，程序終止")
            return
            
        # 2. 檢查現有索引
        indices = await self.check_existing_indices()
        if not indices:
            logger.warning("沒有找到任何 Wazuh 索引")
            return
            
        # 3. 檢查並修正每個索引
        needs_fix = []
        for index in indices:
            mapping = await self.check_index_mapping(index)
            if not mapping or mapping.get('type') != 'dense_vector':
                needs_fix.append(index)
                
        if not needs_fix:
            logger.info("\n✅ 所有索引的向量欄位都已正確配置")
            return
            
        logger.info(f"\n需要修正的索引: {needs_fix}")
        
        # 4. 詢問是否繼續
        response = input("\n是否要修正這些索引? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            logger.info("操作已取消")
            return
            
        # 5. 執行修正
        for index in needs_fix:
            success = await self.reindex_with_correct_mapping(index)
            if success:
                # 測試修正後的索引
                await self.test_vector_search(index)
                
        logger.info("\n🎉 修正程序完成！")
        
        # 6. 最終驗證
        logger.info("\n📊 最終驗證結果:")
        indices = await self.check_existing_indices()
        for index in indices:
            await self.check_index_mapping(index)
            await self.test_vector_search(index)


async def main():
    """主程式入口"""
    async with VectorFieldFixer() as fixer:
        await fixer.fix_all_indices()


if __name__ == "__main__":
    asyncio.run(main())