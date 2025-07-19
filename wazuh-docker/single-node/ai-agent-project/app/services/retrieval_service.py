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
        List of similar alert documents
    """
    try:
        k = parameters.get('k', 5)
        include_ai_analysis = parameters.get('include_ai_analysis', True)
        
        # Build k-NN search query
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

async def execute_keyword_time_search(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Enhanced keyword and time-range search for system metrics and logs.
    
    Args:
        parameters: Search parameters including keywords, host, and time window
        
    Returns:
        List of matching documents
    """
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
            search_body["query"]["bool"]["filter"].append({
                "term": {"agent.name.keyword": host}
            })
        
        response = await client.search(
            index="wazuh-alerts-*",
            body=search_body
        )
        
        results = response.get('hits', {}).get('hits', [])
        return results
        
    except Exception as e:
        logger.error(f"Keyword/time search failed: {str(e)}")
        return []

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