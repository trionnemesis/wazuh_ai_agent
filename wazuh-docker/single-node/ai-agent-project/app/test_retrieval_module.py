#!/usr/bin/env python3
"""
檢索模組測試腳本
測試 AlertRetrievalModule 的核心功能
"""

import os
import asyncio
import logging
import json
from typing import List, Dict, Any
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# 設定 logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 導入檢索模組 (需要從 main.py 導入)
import sys
sys.path.append('.')

class RetrievalModuleTester:
    """檢索模組測試器"""
    
    def __init__(self):
        # OpenSearch 配置
        self.opensearch_url = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
        self.opensearch_user = os.getenv("OPENSEARCH_USER", "admin")
        self.opensearch_password = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")
        
        # 創建 OpenSearch 客戶端
        self.client = AsyncOpenSearch(
            hosts=[self.opensearch_url],
            http_auth=(self.opensearch_user, self.opensearch_password),
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False,
            connection_class=AsyncHttpConnection
        )
        
        # 導入檢索模組
        from main import AlertRetrievalModule
        self.retrieval_module = AlertRetrievalModule(self.client)
        
    async def test_opensearch_connection(self) -> bool:
        """測試 OpenSearch 連接"""
        try:
            info = await self.client.info()
            logging.info(f"✅ OpenSearch 連接成功: {info['version']['number']}")
            return True
        except Exception as e:
            logging.error(f"❌ OpenSearch 連接失敗: {str(e)}")
            return False
    
    async def check_existing_alerts(self) -> Dict[str, Any]:
        """檢查現有的警報數據"""
        try:
            # 查詢所有警報
            all_alerts_response = await self.client.search(
                index="wazuh-alerts-*",
                body={"query": {"match_all": {}}},
                size=0  # 只要總數
            )
            total_alerts = all_alerts_response['hits']['total']['value']
            
            # 查詢有向量的警報
            vector_alerts_response = await self.client.search(
                index="wazuh-alerts-*",
                body={"query": {"exists": {"field": "alert_vector"}}},
                size=0
            )
            alerts_with_vectors = vector_alerts_response['hits']['total']['value']
            
            # 查詢有AI分析的警報
            analyzed_alerts_response = await self.client.search(
                index="wazuh-alerts-*",
                body={"query": {"exists": {"field": "ai_analysis"}}},
                size=0
            )
            analyzed_alerts = analyzed_alerts_response['hits']['total']['value']
            
            stats = {
                "total_alerts": total_alerts,
                "alerts_with_vectors": alerts_with_vectors,
                "analyzed_alerts": analyzed_alerts
            }
            
            logging.info(f"📊 警報統計:")
            logging.info(f"  總警報數: {total_alerts}")
            logging.info(f"  有向量的警報: {alerts_with_vectors}")
            logging.info(f"  已分析的警報: {analyzed_alerts}")
            
            return stats
            
        except Exception as e:
            logging.error(f"❌ 檢查警報數據失敗: {str(e)}")
            return {}
    
    async def create_sample_vector_alert(self) -> str:
        """創建一個範例向量警報用於測試"""
        try:
            # 創建一個測試警報
            sample_alert = {
                "timestamp": "2024-01-15T10:30:00Z",
                "rule": {
                    "description": "Failed SSH login attempt",
                    "level": 5,
                    "id": "5712"
                },
                "agent": {
                    "name": "test-server",
                    "ip": "192.168.1.100"
                },
                "location": "/var/log/auth.log",
                "full_log": "Failed password for admin from 192.168.1.50",
                "ai_analysis": {
                    "triage_report": "This is a test analysis of a failed SSH login attempt. The source IP should be monitored for additional attempts.",
                    "provider": "test",
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                "alert_vector": [0.1] * 768  # 假的向量，實際應該是768維
            }
            
            # 插入到 OpenSearch
            response = await self.client.index(
                index="wazuh-alerts-test",
                body=sample_alert
            )
            
            alert_id = response['_id']
            logging.info(f"✅ 創建測試警報: {alert_id}")
            return alert_id
            
        except Exception as e:
            logging.error(f"❌ 創建測試警報失敗: {str(e)}")
            return ""
    
    async def test_vector_retrieval(self, query_vector: List[float]) -> bool:
        """測試向量檢索功能"""
        try:
            logging.info("🔍 測試向量檢索功能...")
            
            # 使用檢索模組進行搜尋
            similar_alerts = await self.retrieval_module.retrieve_similar_alerts(
                query_vector=query_vector,
                k=3
            )
            
            if similar_alerts:
                logging.info(f"✅ 檢索模組測試成功，找到 {len(similar_alerts)} 筆相似警報")
                
                # 顯示檢索結果詳情
                for i, alert in enumerate(similar_alerts, 1):
                    score = alert.get('_score', 0)
                    source = alert['_source']
                    rule_desc = source.get('rule', {}).get('description', 'N/A')
                    logging.info(f"  相似警報 #{i}: 分數={score:.4f}, 規則={rule_desc}")
                    
                return True
            else:
                logging.warning("⚠️ 沒有找到相似警報，可能是數據不足")
                return False
                
        except Exception as e:
            logging.error(f"❌ 向量檢索測試失敗: {str(e)}")
            return False
    
    async def test_context_formatting(self) -> bool:
        """測試歷史上下文格式化功能"""
        try:
            logging.info("📝 測試歷史上下文格式化...")
            
            # 先獲取一些樣本警報
            query_vector = [0.1] * 768  # 假的查詢向量
            similar_alerts = await self.retrieval_module.retrieve_similar_alerts(
                query_vector=query_vector,
                k=2
            )
            
            if similar_alerts:
                # 測試格式化功能
                formatted_context = self.retrieval_module.format_historical_context(similar_alerts)
                
                logging.info("✅ 上下文格式化測試成功")
                logging.info(f"📄 格式化後的上下文長度: {len(formatted_context)} 字元")
                logging.info("📄 格式化後的上下文預覽:")
                print("-" * 80)
                print(formatted_context[:500] + "..." if len(formatted_context) > 500 else formatted_context)
                print("-" * 80)
                
                return True
            else:
                # 測試空結果的處理
                formatted_context = self.retrieval_module.format_historical_context([])
                logging.info("✅ 空結果格式化測試成功")
                logging.info(f"📄 空結果回應: {formatted_context}")
                return True
                
        except Exception as e:
            logging.error(f"❌ 上下文格式化測試失敗: {str(e)}")
            return False
    
    async def test_retrieval_performance(self) -> Dict[str, float]:
        """測試檢索效能"""
        try:
            import time
            
            logging.info("⚡ 測試檢索效能...")
            
            query_vector = [0.1] * 768
            
            # 測試多次檢索的平均時間
            times = []
            for i in range(3):
                start_time = time.time()
                await self.retrieval_module.retrieve_similar_alerts(query_vector, k=5)
                end_time = time.time()
                times.append(end_time - start_time)
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)
            
            performance_stats = {
                "average_time": avg_time,
                "max_time": max_time,
                "min_time": min_time
            }
            
            logging.info("📊 檢索效能統計:")
            logging.info(f"  平均檢索時間: {avg_time:.3f} 秒")
            logging.info(f"  最大檢索時間: {max_time:.3f} 秒")
            logging.info(f"  最小檢索時間: {min_time:.3f} 秒")
            
            # 檢查是否符合效能要求
            if avg_time < 0.5:  # 500ms
                logging.info("✅ 檢索效能符合要求 (< 500ms)")
            else:
                logging.warning("⚠️ 檢索效能需要優化")
            
            return performance_stats
            
        except Exception as e:
            logging.error(f"❌ 效能測試失敗: {str(e)}")
            return {}
    
    async def cleanup_test_data(self):
        """清理測試數據"""
        try:
            # 刪除測試索引
            await self.client.indices.delete(index="wazuh-alerts-test", ignore=[404])
            logging.info("🧹 測試數據清理完成")
        except Exception as e:
            logging.warning(f"⚠️ 清理測試數據時發生錯誤: {str(e)}")
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """執行所有測試"""
        logging.info("🚀 開始執行檢索模組測試套件...")
        
        test_results = {}
        
        try:
            # 1. 測試 OpenSearch 連接
            test_results["opensearch_connection"] = await self.test_opensearch_connection()
            
            # 2. 檢查現有警報數據
            alert_stats = await self.check_existing_alerts()
            test_results["data_availability"] = alert_stats.get("analyzed_alerts", 0) > 0
            
            # 3. 如果沒有足夠數據，創建測試數據
            if not test_results["data_availability"]:
                logging.info("📦 創建測試數據...")
                test_alert_id = await self.create_sample_vector_alert()
                test_results["test_data_creation"] = bool(test_alert_id)
                # 等待數據索引完成
                await asyncio.sleep(2)
            
            # 4. 測試向量檢索
            query_vector = [0.1] * 768  # 假的查詢向量
            test_results["vector_retrieval"] = await self.test_vector_retrieval(query_vector)
            
            # 5. 測試上下文格式化
            test_results["context_formatting"] = await self.test_context_formatting()
            
            # 6. 測試效能
            performance_stats = await self.test_retrieval_performance()
            test_results["performance_test"] = bool(performance_stats)
            
            # 7. 清理測試數據
            await self.cleanup_test_data()
            
        except Exception as e:
            logging.error(f"❌ 測試套件執行失敗: {str(e)}")
        
        finally:
            await self.client.close()
        
        # 顯示測試結果摘要
        logging.info("📋 測試結果摘要:")
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logging.info(f"  {test_name}: {status}")
        
        total_tests = len(test_results)
        passed_tests = sum(test_results.values())
        logging.info(f"🎯 總測試通過率: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        
        return test_results

async def main():
    """主函數"""
    print("=" * 80)
    print("🔬 agenticRAG 檢索模組測試套件")
    print("=" * 80)
    
    tester = RetrievalModuleTester()
    test_results = await tester.run_all_tests()
    
    print("=" * 80)
    print("✅ 測試完成!")
    print("=" * 80)
    
    return test_results

if __name__ == "__main__":
    asyncio.run(main())