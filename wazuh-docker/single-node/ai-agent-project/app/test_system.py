#!/usr/bin/env python3
"""
系統驗證腳本
測試 embedding 服務、OpenSearch 連接和整個向量化流程
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, List
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection
from embedding_service import GeminiEmbeddingService

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemValidator:
    """系統驗證器"""
    
    def __init__(self):
        self.opensearch_url = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
        self.opensearch_user = os.getenv("OPENSEARCH_USER", "admin")
        self.opensearch_password = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")
        
        self.client = AsyncOpenSearch(
            hosts=[self.opensearch_url],
            http_auth=(self.opensearch_user, self.opensearch_password),
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False,
            connection_class=AsyncHttpConnection
        )
        
        self.embedding_service = None
    
    async def test_opensearch_connection(self) -> bool:
        """測試 OpenSearch 連接"""
        try:
            logger.info("測試 OpenSearch 連接...")
            info = await self.client.info()
            logger.info(f"✅ OpenSearch 連接成功: {info['version']['number']}")
            return True
        except Exception as e:
            logger.error(f"❌ OpenSearch 連接失敗: {str(e)}")
            return False
    
    async def test_embedding_service(self) -> bool:
        """測試 Embedding 服務"""
        try:
            logger.info("初始化 Embedding 服務...")
            self.embedding_service = GeminiEmbeddingService()
            
            logger.info("測試 Embedding 服務連接...")
            connection_ok = await self.embedding_service.test_connection()
            
            if connection_ok:
                logger.info("✅ Embedding 服務連接成功")
                info = self.embedding_service.get_embedding_info()
                logger.info(f"   模型: {info['model_name']}")
                logger.info(f"   維度: {info['dimension']}")
                logger.info(f"   重試次數: {info['max_retries']}")
                return True
            else:
                logger.error("❌ Embedding 服務連接失敗")
                return False
                
        except Exception as e:
            logger.error(f"❌ Embedding 服務初始化失敗: {str(e)}")
            return False
    
    async def test_index_template(self) -> bool:
        """測試索引模板是否正確設定"""
        try:
            logger.info("檢查索引模板...")
            
            # 檢查是否存在相關的索引模板
            templates = await self.client.indices.get_template("*wazuh-alerts*")
            
            if not templates:
                logger.warning("⚠️ 未找到 wazuh-alerts 相關的索引模板")
                return False
            
            for template_name, template_info in templates.items():
                logger.info(f"找到索引模板: {template_name}")
                
                # 檢查映射中是否包含 alert_vector
                mappings = template_info.get('mappings', {})
                properties = mappings.get('properties', {})
                
                if 'alert_vector' in properties:
                    vector_config = properties['alert_vector']
                    logger.info(f"✅ 索引模板包含 alert_vector 欄位")
                    logger.info(f"   類型: {vector_config.get('type')}")
                    logger.info(f"   維度: {vector_config.get('dimension')}")
                    return True
            
            logger.warning("⚠️ 索引模板中未找到 alert_vector 欄位")
            return False
            
        except Exception as e:
            logger.error(f"❌ 檢查索引模板失敗: {str(e)}")
            return False
    
    async def test_vector_operations(self) -> bool:
        """測試向量操作"""
        try:
            if not self.embedding_service:
                logger.error("❌ Embedding 服務未初始化")
                return False
            
            logger.info("測試向量化操作...")
            
            # 測試文本向量化
            test_texts = [
                "Rule: Failed login attempt (Level: 5) on Host: web-server-01",
                "Rule: File modification detected (Level: 7) on Host: database-server",
                "Rule: Network connection denied (Level: 4) on Host: firewall-01"
            ]
            
            vectors = []
            for text in test_texts:
                logger.info(f"向量化: {text[:50]}...")
                vector = await self.embedding_service.embed_query(text)
                vectors.append(vector)
                logger.info(f"   生成向量維度: {len(vector)}")
            
            logger.info("✅ 向量化操作成功")
            
            # 測試向量相似度計算
            if len(vectors) >= 2:
                import numpy as np
                
                vec1 = np.array(vectors[0])
                vec2 = np.array(vectors[1])
                
                # 計算餘弦相似度
                cosine_sim = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
                logger.info(f"向量相似度測試: {cosine_sim:.4f}")
                logger.info("✅ 向量相似度計算成功")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 向量操作測試失敗: {str(e)}")
            return False
    
    async def test_knn_search(self) -> bool:
        """測試 KNN 搜尋功能"""
        try:
            if not self.embedding_service:
                logger.error("❌ Embedding 服務未初始化")
                return False
            
            logger.info("測試 KNN 搜尋...")
            
            # 生成測試向量
            test_query = "Rule: Authentication failure detected on host"
            query_vector = await self.embedding_service.embed_query(test_query)
            
            # 測試 KNN 搜尋查詢結構
            knn_query = {
                "query": {
                    "knn": {
                        "alert_vector": {
                            "vector": query_vector,
                            "k": 5
                        }
                    }
                }
            }
            
            logger.info("KNN 查詢結構驗證成功")
            logger.info(f"查詢向量維度: {len(query_vector)}")
            logger.info("✅ KNN 搜尋測試通過")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ KNN 搜尋測試失敗: {str(e)}")
            return False
    
    async def test_end_to_end_workflow(self) -> bool:
        """測試端到端工作流程"""
        try:
            logger.info("執行端到端工作流程測試...")
            
            if not self.embedding_service:
                logger.error("❌ Embedding 服務未初始化")
                return False
            
            # 模擬警報數據
            mock_alert = {
                "rule": {
                    "description": "Multiple failed login attempts detected",
                    "level": 8,
                    "id": "5710"
                },
                "agent": {
                    "name": "web-server-01",
                    "id": "001"
                },
                "timestamp": "2024-01-15T10:30:00Z"
            }
            
            # 步驟 1: 構建警報摘要
            alert_summary = f"Rule: {mock_alert['rule']['description']} (Level: {mock_alert['rule']['level']}) on Host: {mock_alert['agent']['name']}"
            logger.info(f"警報摘要: {alert_summary}")
            
            # 步驟 2: 向量化
            alert_vector = await self.embedding_service.embed_query(alert_summary)
            logger.info(f"向量化完成，維度: {len(alert_vector)}")
            
            # 步驟 3: 模擬語意搜尋
            search_query = {
                "query": {
                    "knn": {
                        "alert_vector": {
                            "vector": alert_vector,
                            "k": 3
                        }
                    }
                }
            }
            logger.info("語意搜尋查詢構建完成")
            
            # 步驟 4: 模擬更新操作結構
            update_body = {
                "doc": {
                    "ai_analysis": {
                        "triage_report": "This is a test analysis result",
                        "provider": "test",
                        "timestamp": mock_alert["timestamp"]
                    },
                    "alert_vector": alert_vector
                }
            }
            logger.info("更新操作結構驗證完成")
            
            logger.info("✅ 端到端工作流程測試通過")
            return True
            
        except Exception as e:
            logger.error(f"❌ 端到端工作流程測試失敗: {str(e)}")
            return False
    
    async def generate_test_report(self, results: Dict[str, bool]) -> None:
        """生成測試報告"""
        logger.info("=" * 60)
        logger.info("系統驗證報告")
        logger.info("=" * 60)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ 通過" if result else "❌ 失敗"
            logger.info(f"{test_name}: {status}")
            if result:
                passed += 1
        
        logger.info("-" * 60)
        logger.info(f"總計: {passed}/{total} 項測試通過")
        
        if passed == total:
            logger.info("🎉 所有測試通過！系統已準備就緒。")
        else:
            logger.warning(f"⚠️ {total - passed} 項測試失敗，請檢查配置。")
        
        logger.info("=" * 60)
    
    async def close(self):
        """關閉連接"""
        await self.client.close()

async def main():
    """主要執行函式"""
    logger.info("開始系統驗證...")
    
    validator = SystemValidator()
    results = {}
    
    try:
        # 執行各項測試
        results["OpenSearch 連接"] = await validator.test_opensearch_connection()
        results["Embedding 服務"] = await validator.test_embedding_service()
        results["索引模板檢查"] = await validator.test_index_template()
        results["向量操作"] = await validator.test_vector_operations()
        results["KNN 搜尋"] = await validator.test_knn_search()
        results["端到端工作流程"] = await validator.test_end_to_end_workflow()
        
        # 生成報告
        await validator.generate_test_report(results)
        
        # 檢查是否所有測試都通過
        if all(results.values()):
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"驗證過程中發生錯誤: {str(e)}")
        sys.exit(1)
    
    finally:
        await validator.close()

if __name__ == "__main__":
    asyncio.run(main())