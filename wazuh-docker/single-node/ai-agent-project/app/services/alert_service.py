"""
警報服務模組
負責警報的查詢、處理和分析流程
"""

import logging
import traceback
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import time

from ..services.opensearch_service import get_opensearch_client
from ..services.decision_service import determine_contextual_queries, determine_graph_queries
from ..services.retrieval_service import execute_retrieval, execute_hybrid_retrieval
from ..services.graph_service import extract_graph_entities, build_graph_relationships, persist_to_graph_database
from ..services.llm_service import get_analysis_chain
from ..services.metrics import (
    new_alerts_found_total, pending_alerts_gauge, alerts_processed_total,
    alert_processing_errors_total, record_processing_time, update_pending_alerts
)
from ..embedding_service import GeminiEmbeddingService

logger = logging.getLogger(__name__)

# 初始化嵌入服務
embedding_service = GeminiEmbeddingService()

async def query_new_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    查詢新的、尚未分析的警報
    
    Args:
        limit: 要查詢的最大警報數量
        
    Returns:
        List[Dict]: 新警報列表
    """
    client = get_opensearch_client()
    
    query = {
        "query": {
            "bool": {
                "must_not": [
                    {"exists": {"field": "ai_analysis"}}
                ],
                "must": [
                    {"range": {"timestamp": {"gte": "now-24h"}}}
                ]
            }
        },
        "sort": [{"timestamp": {"order": "desc"}}],
        "size": limit
    }
    
    try:
        response = await client.search(index="wazuh-alerts-*", body=query)
        alerts = response['hits']['hits']
        logger.info(f"查詢到 {len(alerts)} 個新警報待處理")
        return alerts
    except Exception as e:
        logger.error(f"查詢新警報失敗: {str(e)}")
        return []

async def triage_new_alerts():
    """主要的警報分流任務，使用 Stage 4 GraphRAG 進行分析"""
    print("🚀 === STAGE 4 GRAPHRAG ALERT TRIAGE JOB EXECUTING ===")
    logger.info("🔬 Analyzing alerts with GraphRAG and enhanced threat intelligence...")
    
    try:
        # 查詢新警報
        alerts = await query_new_alerts(limit=10)
        
        # Prometheus 監控 - 記錄發現的新警報數量
        new_alerts_found_total.inc(len(alerts))
        
        if not alerts:
            print("📭 --- No new alerts found ---")
            logger.info("No new alerts requiring analysis")
            # 設置待處理警報數量為 0
            update_pending_alerts(0)
            return
            
        logger.info(f"🎯 Found {len(alerts)} new alerts to process with GraphRAG")
        
        # 設置待處理警報數量
        update_pending_alerts(len(alerts))
        
        # 處理每個警報
        successful_processing = 0
        failed_processing = 0
        
        for i, alert in enumerate(alerts, 1):
            alert_id = alert['_id']
            rule_desc = alert.get('_source', {}).get('rule', {}).get('description', 'Unknown')
            
            try:
                logger.info(f"🔄 [{i}/{len(alerts)}] Processing alert: {alert_id}")
                logger.info(f"   Rule: {rule_desc}")
                
                await process_single_alert(alert)
                
                successful_processing += 1
                alerts_processed_total.inc()
                print(f"✅ [{i}/{len(alerts)}] Successfully processed alert {alert_id}")
                logger.info(f"✅ Alert {alert_id} processing completed successfully")
                
            except Exception as e:
                failed_processing += 1
                alert_processing_errors_total.inc()
                print(f"❌ [{i}/{len(alerts)}] Failed to process alert {alert_id}: {str(e)}")
                logger.error(f"❌ Alert {alert_id} processing failed: {str(e)}")
                continue
        
        # 總結日誌
        print(f"📊 === GRAPHRAG TRIAGE BATCH SUMMARY ===")
        print(f"   ✅ Successful: {successful_processing}")
        print(f"   ❌ Failed: {failed_processing}")
        print(f"   📈 Success Rate: {(successful_processing/len(alerts)*100):.1f}%")
        
        logger.info(f"🎯 GraphRAG triage batch completed: {successful_processing}/{len(alerts)} successful")
            
    except Exception as e:
        print(f"💥 !!! CRITICAL ERROR IN GRAPHRAG TRIAGE JOB !!!")
        logger.error(f"Critical error during GraphRAG triage: {e}", exc_info=True)
        traceback.print_exc()

async def process_single_alert(alert: Dict[str, Any]) -> None:
    """
    處理單個警報的完整流程
    
    Args:
        alert: 警報資料
    """
    start_time = time.time()
    alert_id = alert['_id']
    source = alert['_source']
    
    try:
        # Step 1: 向量化警報
        logger.info(f"Step 1: Vectorizing alert {alert_id}")
        alert_vector = await embedding_service.embed_alert(source)
        
        if not alert_vector:
            raise ValueError("Failed to vectorize alert")
        
        # Step 2: 決定查詢策略 (Agentic)
        logger.info(f"Step 2: Determining contextual queries")
        queries = await determine_contextual_queries(source)
        
        # Step 3: 執行混合檢索 (GraphRAG + Traditional)
        logger.info(f"Step 3: Executing hybrid retrieval")
        context_data = await execute_hybrid_retrieval(source)
        
        # Step 4: LLM 分析
        logger.info(f"Step 4: Performing LLM analysis")
        analysis_chain = get_analysis_chain()
        analysis_result = await analysis_chain.ainvoke({
            "alert_summary": _create_alert_summary(source),
            **context_data
        })
        
        # Step 5: 提取圖形實體和關係
        logger.info(f"Step 5: Extracting graph entities")
        entities = await extract_graph_entities(source, context_data, analysis_result)
        relationships = await build_graph_relationships(entities, source, context_data)
        
        # Step 6: 持久化到圖形資料庫
        logger.info(f"Step 6: Persisting to graph database")
        graph_result = await persist_to_graph_database(entities, relationships, alert_id)
        
        # Step 7: 更新警報記錄
        logger.info(f"Step 7: Updating alert record")
        await update_alert_with_analysis(alert_id, {
            "vector": alert_vector,
            "analysis": analysis_result,
            "graph_entities": len(entities),
            "graph_relationships": len(relationships),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # 記錄處理時間
        processing_time = time.time() - start_time
        record_processing_time(processing_time)
        
        logger.info(f"✅ Alert {alert_id} processed successfully in {processing_time:.2f}s")
        
    except Exception as e:
        logger.error(f"Error processing alert {alert_id}: {str(e)}")
        raise

async def update_alert_with_analysis(alert_id: str, analysis_data: Dict[str, Any]) -> None:
    """
    更新警報記錄，添加分析結果
    
    Args:
        alert_id: 警報 ID
        analysis_data: 分析結果數據
    """
    client = get_opensearch_client()
    
    try:
        # 首先獲取警報索引
        get_response = await client.get(index="wazuh-alerts-*", id=alert_id)
        alert_index = get_response['_index']
        
        # 更新文檔
        update_body = {
            "doc": {
                "ai_analysis": analysis_data['analysis'],
                "alert_vector": analysis_data['vector'],
                "graph_metadata": {
                    "entities_count": analysis_data['graph_entities'],
                    "relationships_count": analysis_data['graph_relationships'],
                    "processed_at": analysis_data['timestamp']
                }
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logger.info(f"Successfully updated alert {alert_id} with analysis results")
        
    except Exception as e:
        logger.error(f"Failed to update alert {alert_id}: {str(e)}")
        raise

def _create_alert_summary(alert: Dict[str, Any]) -> str:
    """創建警報摘要"""
    return f"""
    Rule: {alert.get('rule', {}).get('description', 'N/A')}
    Level: {alert.get('rule', {}).get('level', 'N/A')}
    Agent: {alert.get('agent', {}).get('name', 'N/A')}
    Source IP: {alert.get('data', {}).get('srcip', 'N/A')}
    Destination IP: {alert.get('data', {}).get('dstip', 'N/A')}
    Event Type: {alert.get('decoder', {}).get('name', 'N/A')}
    Process: {alert.get('data', {}).get('process', 'N/A')}
    User: {alert.get('data', {}).get('srcuser', 'N/A')}
    Timestamp: {alert.get('timestamp', 'N/A')}
    """