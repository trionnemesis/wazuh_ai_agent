"""
檢索服務模組
負責所有檢索相關邏輯 (hybrid, graph, traditional)
"""

import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta

from opensearchpy import AsyncOpenSearch
from core.config import (
    OPENSEARCH_URL, OPENSEARCH_USER, OPENSEARCH_PASSWORD,
    OPENSEARCH_MAX_CONNECTIONS, OPENSEARCH_CONNECTION_TIMEOUT
)
from utils.cache_manager import get_cache_service

logger = logging.getLogger(__name__)

# 初始化 OpenSearch 客戶端
client = AsyncOpenSearch(
    hosts=[OPENSEARCH_URL],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
    pool_maxsize=OPENSEARCH_MAX_CONNECTIONS,
    max_retries=3,
    retry_on_timeout=True,
    timeout=OPENSEARCH_CONNECTION_TIMEOUT
)

async def execute_retrieval(queries: List[Dict[str, Any]], alert_vector: List[float]) -> Dict[str, Any]:
    """
    Stage 3: Enhanced retrieval function that executes multiple types of queries
    in parallel and aggregates results into a structured context object.
    
    Args:
        queries: List of query specifications from determine_contextual_queries
        alert_vector: Vector representation of the current alert
        
    Returns:
        Dictionary containing aggregated results from all queries
    """
    context_data = {
        'similar_alerts': [],
        'cpu_metrics': [],
        'network_logs': [],
        'process_data': [],
        'ssh_logs': [],
        'web_metrics': [],
        'user_activity': [],
        'memory_metrics': [],
        'filesystem_data': [],
        'additional_context': []
    }
    
    logger.info(f"🔄 EXECUTING RETRIEVAL: Processing {len(queries)} contextual queries in parallel")
    
    # Sort queries by priority for optimal execution order
    sorted_queries = sorted(queries, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x.get('priority', 'medium'), 1))
    
    # Step 1: Collect all query tasks without awaiting them
    tasks = []
    for i, query in enumerate(sorted_queries, 1):
        query_type = query['type']
        description = query['description']
        priority = query.get('priority', 'medium')
        parameters = query['parameters']
        
        logger.info(f"   [{i}/{len(queries)}] 🔍 {priority.upper()}: {description}")
        
        if query_type == 'vector_similarity':
            # K-NN vector search for similar alerts
            tasks.append(execute_vector_search(alert_vector, parameters))
        elif query_type == 'keyword_time_range':
            # Keyword and time-based search
            tasks.append(execute_keyword_time_search(parameters))
        else:
            # Handle unknown query types by adding a dummy coroutine that returns empty list
            async def dummy_query():
                logger.warning(f"Unknown query type: {query_type}")
                return []
            tasks.append(dummy_query())
    
    # Step 2: Execute all tasks in parallel using asyncio.gather
    all_results = []
    if tasks:
        try:
            logger.info(f"   🚀 Executing {len(tasks)} queries in parallel...")
            all_results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"   ✅ Parallel execution completed")
        except Exception as e:
            logger.error(f"   ❌ Parallel execution failed: {str(e)}")
            # Fallback to empty results if gather fails completely
            all_results = [[] for _ in tasks]
    
    # Step 3: Process results and categorize them based on query descriptions
    for i, query in enumerate(sorted_queries):
        if i >= len(all_results):
            continue
            
        result = all_results[i]
        query_type = query['type']
        description = query['description']
        
        # Handle exceptions in individual tasks
        if isinstance(result, Exception):
            logger.error(f"      ❌ Query failed: {description} with error {str(result)}")
            continue
        
        # Handle non-list results
        if not isinstance(result, list):
            logger.warning(f"      ⚠️ Query returned non-list result: {description}")
            continue
        
        # Categorize results based on query type and description
        if query_type == 'vector_similarity':
            context_data['similar_alerts'].extend(result)
            logger.info(f"      ✅ Found {len(result)} similar alerts")
        elif query_type == 'keyword_time_range':
            # Enhanced categorization based on description keywords
            description_lower = description.lower()
            if 'cpu' in description_lower:
                context_data['cpu_metrics'].extend(result)
            elif 'network' in description_lower:
                context_data['network_logs'].extend(result)
            elif 'process' in description_lower:
                context_data['process_data'].extend(result)
            elif 'ssh' in description_lower:
                context_data['ssh_logs'].extend(result)
            elif 'web' in description_lower:
                context_data['web_metrics'].extend(result)
            elif 'user' in description_lower:
                context_data['user_activity'].extend(result)
            elif 'memory' in description_lower:
                context_data['memory_metrics'].extend(result)
            elif 'file' in description_lower:
                context_data['filesystem_data'].extend(result)
            else:
                context_data['additional_context'].extend(result)
            
            logger.info(f"      ✅ Found {len(result)} contextual records")
    
    # Enhanced retrieval summary
    total_results = sum(len(results) for results in context_data.values())
    logger.info(f"📊 RETRIEVAL SUMMARY: {total_results} total contextual records (parallel execution)")
    for category, results in context_data.items():
        if results:
            logger.info(f"   {category}: {len(results)} records")
    
    return context_data

async def execute_vector_search(alert_vector: List[float], parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Execute k-NN vector similarity search for historical alerts.
    
    Args:
        alert_vector: Vector representation of the current alert
        parameters: Search parameters including k and filters
        
    Returns:
        List of similar historical alerts
    """
    # 獲取快取服務
    cache_service = get_cache_service()
    
    # 生成快取鍵值
    import hashlib
    cache_key = f"vector_search:{hashlib.md5(str(alert_vector[:10]).encode()).hexdigest()}:{parameters.get('k', 5)}"
    
    async def compute_search():
        try:
            k = parameters.get('k', 5)
            include_ai_analysis = parameters.get('include_ai_analysis', False)
            
            # Build k-NN search with filter support
            knn_search_body = {
                "size": k,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "alert_vector": {
                                        "vector": alert_vector,
                                        "k": k
                                    }
                                }
                            }
                        ]
                    }
                },
                "_source": ["rule", "agent", "ai_analysis", "timestamp", "data"]
            }
            
            # Add filter for alerts with AI analysis if requested
            if include_ai_analysis:
                if "filter" not in knn_search_body["query"]["bool"]:
                    knn_search_body["query"]["bool"]["filter"] = []
                knn_search_body["query"]["bool"]["filter"].append(
                    {"exists": {"field": "ai_analysis"}}
                )
            
            response = await client.search(
                index="wazuh-alerts-*",
                body=knn_search_body
            )
            
            similar_alerts = response.get('hits', {}).get('hits', [])
            return similar_alerts
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            return []
    
    # 如果有快取服務，使用快取
    if cache_service:
        result = await cache_service.get_or_compute(
            cache_key=cache_key,
            compute_func=compute_search,
            cache_type='ttl',
            ttl_override=300  # 5分鐘快取
        )
        return result
    else:
        # 沒有快取服務，直接執行
        return await compute_search()

async def execute_keyword_time_search(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Enhanced keyword and time-range search for system metrics and logs.
    
    Args:
        parameters: Search parameters including keywords, host, and time window
        
    Returns:
        List of matching documents
    """
    # 獲取快取服務
    cache_service = get_cache_service()
    
    # 生成快取鍵值
    import hashlib
    cache_key_parts = [
        "keyword_search",
        str(parameters.get('keywords', [])),
        parameters.get('host', ''),
        str(parameters.get('time_window_minutes', 5))
    ]
    cache_key = hashlib.md5(":".join(cache_key_parts).encode()).hexdigest()
    
    async def compute_search():
        try:
            keywords = parameters.get('keywords', [])
            host = parameters.get('host', '')
            time_window_minutes = parameters.get('time_window_minutes', 5)
            timestamp = parameters.get('timestamp')
            
            if not timestamp:
                logger.warning("No timestamp provided for time-range search")
                return []
            
            # Parse timestamp and calculate time range
            if isinstance(timestamp, str):
                alert_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                alert_time = datetime.utcnow()
            
            start_time = alert_time - timedelta(minutes=time_window_minutes)
            end_time = alert_time + timedelta(minutes=time_window_minutes)
            
            # Build enhanced keyword and time-range query
            search_body = {
                "size": 15,  # Increased for better context
                "query": {
                    "bool": {
                        "should": [  # Using should for better matching flexibility
                            {
                                "multi_match": {
                                    "query": " ".join(keywords),
                                    "fields": ["rule.description^2", "data.*", "full_log", "location"],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO"
                                }
                            },
                            {
                                "terms": {
                                    "rule.description.keyword": keywords
                                }
                            }
                        ],
                        "filter": [
                            {
                                "range": {
                                    "timestamp": {
                                        "gte": start_time.isoformat(),
                                        "lte": end_time.isoformat()
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "sort": [
                    {"timestamp": {"order": "desc"}},
                    {"_score": {"order": "desc"}}
                ]
            }
            
            # Add host filter if specified
            if host:
                search_body["query"]["bool"]["filter"].append(
                    {"term": {"agent.name.keyword": host}}
                )
            
            response = await client.search(
                index="wazuh-alerts-*",
                body=search_body
            )
            
            results = response.get('hits', {}).get('hits', [])
            return results
            
        except Exception as e:
            logger.error(f"Keyword/time search failed: {str(e)}")
            return []
    
    # 如果有快取服務，使用快取
    if cache_service:
        result = await cache_service.get_or_compute(
            cache_key=cache_key,
            compute_func=compute_search,
            cache_type='ttl',
            ttl_override=300  # 5分鐘快取
        )
        return result
    else:
        # 沒有快取服務，直接執行
        return await compute_search()

async def query_new_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """Query OpenSearch for new unanalyzed alerts"""
    try:
        response = await client.search(
            index="wazuh-alerts-*",
            body={
                "query": {
                    "bool": {
                        "must_not": [{"exists": {"field": "ai_analysis"}}]
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}],
                "size": limit
            }
        )
        
        alerts = response.get('hits', {}).get('hits', [])
        logger.info(f"Found {len(alerts)} new alerts to process")
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to query new alerts: {str(e)}")
        raise

async def execute_hybrid_retrieval(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    混合檢索系統：結合圖形查詢和傳統檢索方法
    為 GraphRAG 提供最佳的上下文檢索策略
    
    Args:
        alert: 當前警報資料
        
    Returns:
        結合的檢索結果
    """
    from .decision_service import determine_graph_queries, determine_contextual_queries
    from .graph_service import execute_graph_retrieval
    from .metrics import (
        graph_retrieval_fallback_total,
        record_graph_retrieval_fallback
    )
    from embedding_service import GeminiEmbeddingService
    
    logger.info("🔗🔍 HYBRID RETRIEVAL: Combining graph and traditional methods")
    
    # 1. 執行圖形查詢
    graph_queries = await determine_graph_queries(alert, {})
    graph_context = await execute_graph_retrieval(graph_queries, alert)
    
    # 2. 如果圖形查詢結果不足，補充傳統檢索
    total_graph_results = sum(len(results) for results in graph_context.values())
    
    if total_graph_results < 10:  # 設定閾值
        logger.info("📊 Graph results insufficient - supplementing with traditional retrieval")
        
        # Prometheus 監控 - 記錄回退到傳統檢索
        # 使用新的輔助函數而非直接調用 .inc()
        record_graph_retrieval_fallback()
        
        # 生成補充查詢
        traditional_queries = await determine_contextual_queries(alert)
        
        # 向量化警報
        embedding_service = GeminiEmbeddingService()
        try:
            alert_text = _extract_alert_text_for_embedding(alert)
            alert_vector = await embedding_service.embed_text(alert_text)
            traditional_context = await execute_retrieval(traditional_queries, alert_vector)
            
            # 合併結果
            return _merge_retrieval_contexts(graph_context, traditional_context)
        except Exception as e:
            logger.warning(f"Traditional retrieval failed: {str(e)}")
            return graph_context
    
    return graph_context

def _extract_alert_text_for_embedding(alert: Dict[str, Any]) -> str:
    """
    從警報中提取用於嵌入的文本
    
    Args:
        alert: 警報資料
        
    Returns:
        str: 用於嵌入的文本
    """
    parts = []
    
    # 規則描述
    if alert.get('rule', {}).get('description'):
        parts.append(f"Rule: {alert['rule']['description']}")
    
    # 代理名稱
    if alert.get('agent', {}).get('name'):
        parts.append(f"Agent: {alert['agent']['name']}")
    
    # 源 IP
    if alert.get('data', {}).get('srcip'):
        parts.append(f"Source IP: {alert['data']['srcip']}")
    
    # 目標 IP
    if alert.get('data', {}).get('dstip'):
        parts.append(f"Destination IP: {alert['data']['dstip']}")
    
    # 程序
    if alert.get('data', {}).get('process'):
        parts.append(f"Process: {alert['data']['process']}")
    
    # 用戶
    if alert.get('data', {}).get('srcuser'):
        parts.append(f"User: {alert['data']['srcuser']}")
    
    return " | ".join(parts)

def _merge_retrieval_contexts(graph_context: Dict[str, Any], traditional_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    合併圖形檢索和傳統檢索的結果
    
    Args:
        graph_context: 圖形檢索結果
        traditional_context: 傳統檢索結果
        
    Returns:
        Dict: 合併後的上下文
    """
    merged_context = graph_context.copy()
    
    # 添加傳統檢索的結果作為補充上下文
    merged_context['traditional_similar_alerts'] = traditional_context.get('similar_alerts', [])
    merged_context['traditional_metrics'] = traditional_context.get('cpu_metrics', []) + \
                                          traditional_context.get('memory_metrics', [])
    merged_context['traditional_logs'] = traditional_context.get('network_logs', []) + \
                                       traditional_context.get('ssh_logs', [])
    
    return merged_context