import os
import logging
import traceback
import asyncio
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uuid
import json
import re

# LangChain 相關套件引入
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# OpenSearch 客戶端
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# Neo4j 圖形資料庫客戶端
try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
    NEO4J_AVAILABLE = True
except ImportError:
    logger.warning("Neo4j driver not available. Graph persistence will be disabled.")
    NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None
    AsyncDriver = None

# 引入自定義的嵌入服務模組
from embedding_service import GeminiEmbeddingService

# 配置日誌系統
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 環境變數配置
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

# Neo4j 圖形資料庫配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "wazuh-graph-2024")

# 大型語言模型配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 初始化 OpenSearch 非同步客戶端
client = AsyncOpenSearch(
    hosts=[OPENSEARCH_URL],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=AsyncHttpConnection
)

# 初始化 Neo4j 圖形資料庫客戶端
neo4j_driver = None
if NEO4J_AVAILABLE:
    try:
        neo4j_driver = AsyncGraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        logger.info(f"Neo4j driver initialized: {NEO4J_URI}")
    except Exception as e:
        logger.warning(f"Failed to initialize Neo4j driver: {str(e)}")
        neo4j_driver = None
else:
    logger.warning("Neo4j driver not available - graph persistence disabled")

def get_llm():
    """
    根據環境配置初始化大型語言模型
    
    支援的提供商：
    - gemini: Google Gemini 1.5 Flash 模型
    - anthropic: Anthropic Claude 3 Haiku 模型
    
    Returns:
        ChatModel: 配置完成的語言模型實例
        
    Raises:
        ValueError: 當提供商不支援或 API 金鑰未設定時
    """
    logger.info(f"正在初始化 LLM 提供商: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == 'gemini':
        if not GEMINI_API_KEY:
            raise ValueError("LLM_PROVIDER 設為 'gemini' 但 GEMINI_API_KEY 未設定")
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY)
    
    elif LLM_PROVIDER == 'anthropic':
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER 設為 'anthropic' 但 ANTHROPIC_API_KEY 未設定")
        return ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=ANTHROPIC_API_KEY)
    
    else:
        raise ValueError(f"不支援的 LLM_PROVIDER: {LLM_PROVIDER}。請選擇 'gemini' 或 'anthropic'")

# 初始化 LangChain 組件
llm = get_llm()

# Stage 4: GraphRAG prompt template for graph-native security analysis
graphrag_prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst with expertise in graph-based threat intelligence. Analyze the new Wazuh alert by interpreting the provided threat context graph.

    **Threat Context Graph (Simplified Cypher Path Notation):**
    {graph_context}

    **新 Wazuh 警報分析:**
    {alert_summary}

    **你的分析任務:**
    1.  總結新事件。
    2.  **解讀威脅圖**: 描述攻擊路徑、關聯實體，以及潛在的橫向移動跡象。
    3.  基於圖中揭示的攻擊模式評估風險等級。
    4.  提供基於圖形關聯的、更具體的應對建議。

    **你的深度會診報告:**
    """
)

# Enhanced GraphRAG prompt template with comprehensive graph context
enhanced_graphrag_prompt_template = ChatPromptTemplate.from_template(
    """You are a senior cyber security analyst with expertise in graph-based threat hunting and advanced persistent threat (APT) analysis. Analyze the new Wazuh alert below using the comprehensive graph-native intelligence gathered from the security knowledge graph.

    **🔗 Threat Context Graph (Simplified Cypher Path Notation):**
    {graph_context}

    **🔄 橫向移動檢測 (Lateral Movement Detection):**
    {lateral_movement_analysis}

    **⏰ 時間序列關聯 (Temporal Correlation):**
    {temporal_correlation}

    **🌍 IP 信譽分析 (IP Reputation Analysis):**
    {ip_reputation_analysis}

    **👤 使用者行為分析 (User Behavior Analysis):**
    {user_behavior_analysis}

    **⚙️ 程序執行鏈分析 (Process Chain Analysis):**
    {process_chain_analysis}

    **📁 檔案交互分析 (File Interaction Analysis):**
    {file_interaction_analysis}

    **🌐 網路拓撲分析 (Network Topology Analysis):**
    {network_topology_analysis}

    **⚠️ 威脅全景分析 (Threat Landscape Analysis):**
    {threat_landscape_analysis}

    **📊 傳統檢索補充 (Traditional Retrieval Supplement):**
    {traditional_supplement}

    **🚨 當前分析的新警報：**
    {alert_summary}

    **您的圖形化威脅分析任務：**
    1. **事件摘要與分類：** 簡要總結新事件，並根據圖形上下文進行威脅分類
    2. **攻擊鏈重建：** 基於圖形關聯資料重建完整的攻擊時間線和路徑
    3. **橫向移動評估：** 評估攻擊者的橫向移動能力和已滲透的系統範圍
    4. **威脅行為者畫像：** 基於攻擊模式、IP信譽、時間模式分析威脅行為者特徵
    5. **風險等級評估：** 綜合所有圖形智能，評估風險等級（Critical, High, Medium, Low, Informational）
    6. **影響範圍分析：** 確定受影響的系統、使用者、檔案和網路資源
    7. **緩解建議：** 提供基於圖形分析的精確緩解和應急響應建議
    8. **持續威脅指標：** 識別需要持續監控的威脅指標（IOCs/IOAs）

    **您的 GraphRAG 威脅分析報告：**
    """
)

# Legacy prompt template for fallback scenarios
traditional_prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst with expertise in correlating security events with system performance data. Analyze the new Wazuh alert below using the provided multi-source contextual information.

**Historical Similar Alerts:**
{similar_alerts_context}

**Correlated System Metrics:**
{system_metrics_context}

**Process Information:**
{process_context}

**Network Data:**
{network_context}

**Additional Context:**
{additional_context}

**待分析的新 Wazuh 警報：**
{alert_summary}

**Your Analysis Task:**
1. Briefly summarize the new event.
2. Correlate the alert with system performance data and other contextual information.
3. Assess its risk level (Critical, High, Medium, Low, Informational) considering all available context.
4. Identify any patterns or anomalies by cross-referencing different data sources.
5. Provide actionable recommendations based on the comprehensive analysis.

**Your Comprehensive Triage Report:**
"""
)

def get_analysis_chain(context_data: Dict[str, Any]):
    """
    根據上下文資料類型選擇適當的分析鏈
    """
    # 檢測是否為圖形檢索結果
    graph_indicators = ['attack_paths', 'lateral_movement', 'temporal_sequences']
    has_graph_data = any(context_data.get(indicator) for indicator in graph_indicators)
    
    if has_graph_data:
        logger.info("🔗 Using Enhanced GraphRAG analysis chain with graph context")
        return enhanced_graphrag_prompt_template | llm | StrOutputParser()
    else:
        logger.info("📊 Using traditional analysis chain")
        return traditional_prompt_template | llm | StrOutputParser()

# Remove legacy static chain - now using dynamic chain selection

# 初始化嵌入服務
embedding_service = GeminiEmbeddingService()

# === Stage 3: Enhanced Agentic Context Correlation Implementation ===

def determine_contextual_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Stage 3: Enhanced decision engine that determines what contextual information is needed
    based on the alert type and content using more sophisticated, human-like reasoning.
    
    Args:
        alert: The new alert document from OpenSearch
        
    Returns:
        List of query specifications for different types of contextual data
    """
    queries = []
    alert_source = alert.get('_source', {})
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    data = alert_source.get('data', {})
    timestamp = alert_source.get('timestamp')
    
    rule_description = rule.get('description', '').lower()
    rule_groups = rule.get('groups', [])
    rule_level = rule.get('level', 0)
    host_name = agent.get('name', '')
    
    logger.info(f"🤖 AGENTIC DECISION ENGINE: Analyzing alert for contextual needs")
    logger.info(f"   Alert: {rule_description}")
    logger.info(f"   Level: {rule_level}, Host: {host_name}")
    logger.info(f"   Groups: {', '.join(rule_groups)}")
    
    # Default: Always perform k-NN search for similar historical alerts
    queries.append({
        'type': 'vector_similarity',
        'description': 'Similar historical alerts',
        'priority': 'high',
        'parameters': {
            'k': 7,  # Increased for better context
            'include_ai_analysis': True
        }
    })
    logger.info("✅ DECISION: Adding vector similarity search (always required)")
    
    # Enhanced Resource monitoring correlation rules
    resource_keywords = [
        'high cpu usage', 'excessive ram consumption', 'memory usage', 'memory leak',
        'disk space', 'cpu utilization', 'system overload', 'performance', 
        'resource exhaustion', 'out of memory', 'cpu spike', 'high load'
    ]
    
    if any(keyword in rule_description for keyword in resource_keywords) or 'system' in rule_groups:
        logger.info("🔍 DECISION: Resource-related alert detected - correlating with system data")
        
        # Process information query
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Process information from same host',
            'priority': 'high',
            'parameters': {
                'keywords': ['process list', 'top processes', 'running processes', 'ps aux', 'htop'],
                'host': host_name,
                'time_window_minutes': 10,  # Wider window for resource issues
                'timestamp': timestamp
            }
        })
        
        # Memory usage correlation
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Memory usage metrics',
            'priority': 'medium',
            'parameters': {
                'keywords': ['memory usage', 'ram utilization', 'swap usage', 'free memory'],
                'host': host_name,
                'time_window_minutes': 15,
                'timestamp': timestamp
            }
        })
        
        logger.info("   ✅ Added process and memory correlation queries")
    
    # Enhanced Security event correlation rules
    security_keywords = [
        'ssh brute-force', 'web attack', 'authentication failed', 'login attempt',
        'intrusion', 'malware', 'suspicious activity', 'unauthorized access',
        'privilege escalation', 'command injection', 'sql injection',
        'cross-site scripting', 'buffer overflow', 'trojan', 'backdoor'
    ]
    
    security_groups = ['authentication', 'attack', 'malware', 'intrusion_detection', 'web']
    
    if (any(keyword in rule_description for keyword in security_keywords) or 
        any(group in rule_groups for group in security_groups) or 
        rule_level >= 7):  # High-level alerts likely security-related
        
        logger.info("🛡️ DECISION: Security event detected - adding comprehensive correlation")
        
        # CPU metrics for detecting resource-intensive attacks
        queries.append({
            'type': 'keyword_time_range',
            'description': 'CPU metrics during security event',
            'priority': 'high',
            'parameters': {
                'keywords': ['cpu usage', 'cpu utilization', 'processor load', 'high cpu'],
                'host': host_name,
                'time_window_minutes': 2,  # Tight window for security correlation
                'timestamp': timestamp
            }
        })
        
        # Network activity correlation
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Network activity during security event',
            'priority': 'high',
            'parameters': {
                'keywords': ['network traffic', 'network io', 'bandwidth', 'packets', 'connections'],
                'host': host_name,
                'time_window_minutes': 3,
                'timestamp': timestamp
            }
        })
        
        # User activity correlation
        queries.append({
            'type': 'keyword_time_range',
            'description': 'User activity correlation',
            'priority': 'medium',
            'parameters': {
                'keywords': ['user login', 'user activity', 'session', 'authentication'],
                'host': host_name,
                'time_window_minutes': 5,
                'timestamp': timestamp
            }
        })
        
        logger.info("   ✅ Added security event correlation queries (CPU, Network, User)")
    
    # SSH-specific enhanced correlation
    if 'ssh' in rule_description or 'sshd' in rule_description:
        logger.info("🔑 DECISION: SSH-related alert - adding SSH-specific correlation")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'SSH connection patterns',
            'priority': 'high',
            'parameters': {
                'keywords': ['ssh connection', 'port 22', 'sshd', 'ssh login', 'ssh session'],
                'host': host_name,
                'time_window_minutes': 5,
                'timestamp': timestamp
            }
        })
        
        # Look for brute force patterns
        if 'brute' in rule_description or 'failed' in rule_description:
            queries.append({
                'type': 'keyword_time_range',
                'description': 'SSH failure patterns',
                'priority': 'high',
                'parameters': {
                    'keywords': ['ssh failed', 'authentication failure', 'invalid user', 'connection refused'],
                    'host': host_name,
                    'time_window_minutes': 10,  # Wider window for brute force detection
                    'timestamp': timestamp
                }
            })
            logger.info("   ✅ Added SSH brute force correlation")
    
    # Web-related enhanced correlation
    web_indicators = ['web', 'http', 'apache', 'nginx', 'php', 'sql injection', 'xss']
    if any(indicator in rule_description for indicator in web_indicators):
        logger.info("🌐 DECISION: Web-related alert - adding web server correlation")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Web server performance',
            'priority': 'medium',
            'parameters': {
                'keywords': ['apache', 'nginx', 'web server', 'http requests', 'response time'],
                'host': host_name,
                'time_window_minutes': 3,
                'timestamp': timestamp
            }
        })
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Web access logs',
            'priority': 'high',
            'parameters': {
                'keywords': ['access log', 'http status', 'user agent', 'request uri'],
                'host': host_name,
                'time_window_minutes': 2,
                'timestamp': timestamp
            }
        })
        
        logger.info("   ✅ Added web server correlation queries")
    
    # File system correlation for critical alerts
    if rule_level >= 10 or 'file' in rule_description:
        logger.info("📁 DECISION: High-level/file-related alert - adding filesystem correlation")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'File system activity',
            'priority': 'medium',
            'parameters': {
                'keywords': ['file created', 'file modified', 'file deleted', 'disk usage', 'inode'],
                'host': host_name,
                'time_window_minutes': 5,
                'timestamp': timestamp
            }
        })
        
        logger.info("   ✅ Added filesystem correlation")
    
    # Summary logging
    total_queries = len(queries)
    high_priority = len([q for q in queries if q.get('priority') == 'high'])
    logger.info(f"🎯 AGENTIC DECISION COMPLETE: Generated {total_queries} contextual queries")
    logger.info(f"   High priority: {high_priority}, Total sources: {total_queries}")
    logger.info(f"   Query types: {', '.join(set(q['type'] for q in queries))}")
    
    return queries

async def execute_retrieval(queries: List[Dict[str, Any]], alert_vector: List[float]) -> Dict[str, Any]:
    """
    Stage 3: Enhanced retrieval function that executes multiple types of queries
    and aggregates results into a structured context object.
    
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
    
    logger.info(f"🔄 EXECUTING RETRIEVAL: Processing {len(queries)} contextual queries")
    
    # Sort queries by priority for optimal execution order
    sorted_queries = sorted(queries, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x.get('priority', 'medium'), 1))
    
    for i, query in enumerate(sorted_queries, 1):
        query_type = query['type']
        description = query['description']
        priority = query.get('priority', 'medium')
        parameters = query['parameters']
        
        try:
            logger.info(f"   [{i}/{len(queries)}] 🔍 {priority.upper()}: {description}")
            
            if query_type == 'vector_similarity':
                # K-NN vector search for similar alerts
                results = await execute_vector_search(alert_vector, parameters)
                context_data['similar_alerts'].extend(results)
                logger.info(f"      ✅ Found {len(results)} similar alerts")
                
            elif query_type == 'keyword_time_range':
                # Keyword and time-based search
                results = await execute_keyword_time_search(parameters)
                
                # Enhanced categorization based on description
                if 'cpu' in description.lower():
                    context_data['cpu_metrics'].extend(results)
                elif 'network' in description.lower():
                    context_data['network_logs'].extend(results)
                elif 'process' in description.lower():
                    context_data['process_data'].extend(results)
                elif 'ssh' in description.lower():
                    context_data['ssh_logs'].extend(results)
                elif 'web' in description.lower():
                    context_data['web_metrics'].extend(results)
                elif 'user' in description.lower():
                    context_data['user_activity'].extend(results)
                elif 'memory' in description.lower():
                    context_data['memory_metrics'].extend(results)
                elif 'file' in description.lower():
                    context_data['filesystem_data'].extend(results)
                else:
                    context_data['additional_context'].extend(results)
                
                logger.info(f"      ✅ Found {len(results)} contextual records")
                    
        except Exception as e:
            logger.error(f"      ❌ Query failed: {str(e)}")
            continue
    
    # Enhanced retrieval summary
    total_results = sum(len(results) for results in context_data.values())
    logger.info(f"📊 RETRIEVAL SUMMARY: {total_results} total contextual records")
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

def format_multi_source_context(context_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Stage 3: Enhanced formatting of multi-source context data for LLM consumption.
    
    Args:
        context_data: Aggregated context from execute_retrieval
        
    Returns:
        Dictionary with formatted context strings for each category
    """
    formatted_context = {}
    
    # Format similar alerts with enhanced details
    similar_alerts = context_data.get('similar_alerts', [])
    if similar_alerts:
        context_parts = []
        for i, alert in enumerate(similar_alerts, 1):
            source = alert.get('_source', {})
            rule = source.get('rule', {})
            agent = source.get('agent', {})
            ai_analysis = source.get('ai_analysis', {})
            
            # Extract risk level from previous analysis if available
            prev_analysis = ai_analysis.get('triage_report', '')
            risk_level = "Unknown"
            for level in ['Critical', 'High', 'Medium', 'Low']:
                if level.lower() in prev_analysis.lower():
                    risk_level = level
                    break
            
            context_part = f"""
{i}. **Alert:** {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')})
   **Host:** {agent.get('name', 'Unknown')} | **Time:** {source.get('timestamp', 'Unknown')}
   **Previous Risk Assessment:** {risk_level}
   **Similarity Score:** {alert.get('_score', 'N/A'):.3f}
   **Analysis Preview:** {prev_analysis[:200]}..."""
            context_parts.append(context_part)
        formatted_context['similar_alerts_context'] = "\n".join(context_parts)
    else:
        formatted_context['similar_alerts_context'] = "No similar historical alerts found."
    
    # Format system metrics with enhanced correlation info
    cpu_metrics = context_data.get('cpu_metrics', [])
    memory_metrics = context_data.get('memory_metrics', [])
    all_system_metrics = cpu_metrics + memory_metrics
    
    if all_system_metrics:
        metric_parts = []
        for metric in all_system_metrics[:10]:  # Limit for readability
            source = metric.get('_source', {})
            rule = source.get('rule', {})
            timestamp = source.get('timestamp', 'Unknown')
            metric_parts.append(f"- {timestamp}: {rule.get('description', 'System metric')}")
        formatted_context['system_metrics_context'] = "\n".join(metric_parts)
    else:
        formatted_context['system_metrics_context'] = "No correlated system metrics found."
    
    # Format process data
    process_data = context_data.get('process_data', [])
    if process_data:
        process_parts = []
        for proc in process_data[:8]:
            source = proc.get('_source', {})
            rule = source.get('rule', {})
            timestamp = source.get('timestamp', 'Unknown')
            process_parts.append(f"- {timestamp}: {rule.get('description', 'Process info')}")
        formatted_context['process_context'] = "\n".join(process_parts)
    else:
        formatted_context['process_context'] = "No process information found."
    
    # Format network data with enhanced details
    network_logs = context_data.get('network_logs', [])
    ssh_logs = context_data.get('ssh_logs', [])
    all_network_data = network_logs + ssh_logs
    
    if all_network_data:
        network_parts = []
        for net in all_network_data[:10]:
            source = net.get('_source', {})
            rule = source.get('rule', {})
            timestamp = source.get('timestamp', 'Unknown')
            data = source.get('data', {})
            
            # Extract relevant network details
            details = []
            if data.get('srcip'):
                details.append(f"SRC:{data['srcip']}")
            if data.get('dstip'):
                details.append(f"DST:{data['dstip']}")
            if data.get('srcport'):
                details.append(f"PORT:{data['srcport']}")
            
            detail_str = f" ({', '.join(details)})" if details else ""
            network_parts.append(f"- {timestamp}: {rule.get('description', 'Network activity')}{detail_str}")
        formatted_context['network_context'] = "\n".join(network_parts)
    else:
        formatted_context['network_context'] = "No correlated network data found."
    
    # Format additional context from various sources
    additional_sources = []
    for category in ['web_metrics', 'user_activity', 'filesystem_data', 'additional_context']:
        category_data = context_data.get(category, [])
        if category_data:
            additional_sources.extend(category_data[:5])  # Limit each category
    
    if additional_sources:
        additional_parts = []
        for item in additional_sources:
            source = item.get('_source', {})
            rule = source.get('rule', {})
            timestamp = source.get('timestamp', 'Unknown')
            additional_parts.append(f"- {timestamp}: {rule.get('description', 'Additional context')}")
        formatted_context['additional_context'] = "\n".join(additional_parts)
    else:
        formatted_context['additional_context'] = "No additional contextual data found."
    
    return formatted_context

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

async def process_single_alert(alert: Dict[str, Any]) -> None:
    """
    Stage 3: Enhanced single alert processing with agentic context correlation.
    
    Processing workflow:
    1. Fetch new alert
    2. Vectorize alert
    3. Decide: Call determine_contextual_queries to get required contextual queries
    4. Retrieve: Call execute_retrieval with query list to fetch all required data
    5. Format: Update context formatting to handle multi-source context
    6. Analyze: Send comprehensive context to LLM
    7. Update: Store results
    8. Graph Persistence: Extract entities and build relationships in graph database (NEW)
    """
    alert_id = alert['_id']
    alert_index = alert['_index']
    alert_source = alert['_source']
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    
    # Step 1: Prepare alert summary
    alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
    logger.info(f"Processing alert {alert_id}: {alert_summary}")

    try:
        # Step 2: Vectorize new alert
        logger.info(f"🔮 STEP 2: Vectorizing alert {alert_id}")
        alert_vector = await embedding_service.embed_alert_content(alert_source)
        logger.info(f"   ✅ Alert vectorized (dimension: {len(alert_vector)})")
        
        # Step 3: Decide - Determine graph queries for GraphRAG
        logger.info(f"🔗 STEP 3: GRAPH-NATIVE DECISION - Determining Cypher queries for alert {alert_id}")
        graph_queries = determine_graph_queries(alert)
        
        # Step 4: Execute Graph-Native Retrieval
        logger.info(f"📊 STEP 4: GRAPH-NATIVE RETRIEVAL - Executing {len(graph_queries)} Cypher queries for alert {alert_id}")
        context_data = await execute_hybrid_retrieval(alert)
        
        # Step 5: Format - Prepare graph-native context for LLM
        logger.info(f"📋 STEP 5: GRAPH CONTEXT FORMATTING - Preparing graph-native context for alert {alert_id}")
        formatted_context = format_hybrid_context(context_data)
        
        # Log context summary for verification
        total_context_items = sum(len(ctx.split('\n')) for ctx in formatted_context.values() if ctx and "No " not in ctx)
        logger.info(f"   📊 Context summary: {total_context_items} total contextual items prepared")
        
        # Step 6: Analyze - Send comprehensive context to LLM using appropriate chain
        logger.info(f"🤖 STEP 6: GRAPHRAG ANALYSIS - Generating graph-native AI analysis for alert {alert_id}")
        analysis_chain = get_analysis_chain(context_data)
        analysis_result = await analysis_chain.ainvoke({
            "alert_summary": alert_summary,
            **formatted_context
        })
        
        # Extract risk level for logging
        risk_level = "Unknown"
        for level in ['Critical', 'High', 'Medium', 'Low', 'Informational']:
            if level.lower() in analysis_result.lower():
                risk_level = level
                break
        
        logger.info(f"   ✅ AI Analysis generated (Risk: {risk_level}): {analysis_result[:150]}...")
        
        # Step 7: Update - Store results in OpenSearch
        logger.info(f"💾 STEP 7: STORING RESULTS - Updating alert {alert_id} with GraphRAG analysis")
        
        # Enhanced metadata for Stage 4 GraphRAG
        context_metadata = {
            # Graph-native metrics
            "attack_paths_count": len(context_data.get('attack_paths', [])),
            "lateral_movement_count": len(context_data.get('lateral_movement', [])),
            "temporal_sequences_count": len(context_data.get('temporal_sequences', [])),
            "ip_reputation_count": len(context_data.get('ip_reputation', [])),
            "user_behavior_count": len(context_data.get('user_behavior', [])),
            "process_chains_count": len(context_data.get('process_chains', [])),
            "file_interactions_count": len(context_data.get('file_interactions', [])),
            "network_topology_count": len(context_data.get('network_topology', [])),
            "threat_landscape_count": len(context_data.get('threat_landscape', [])),
            "correlation_graph_count": len(context_data.get('correlation_graph', [])),
            
            # Traditional supplement metrics (when used)
            "traditional_similar_alerts_count": len(context_data.get('traditional_similar_alerts', [])),
            "traditional_metrics_count": len(context_data.get('traditional_metrics', [])),
            "traditional_logs_count": len(context_data.get('traditional_logs', [])),
            
            # Legacy compatibility
            "similar_alerts_count": len(context_data.get('similar_alerts', [])),
            "cpu_metrics_count": len(context_data.get('cpu_metrics', [])),
            "memory_metrics_count": len(context_data.get('memory_metrics', [])),
            "network_logs_count": len(context_data.get('network_logs', [])),
            "ssh_logs_count": len(context_data.get('ssh_logs', [])),
            "process_data_count": len(context_data.get('process_data', [])),
            "web_metrics_count": len(context_data.get('web_metrics', [])),
            "user_activity_count": len(context_data.get('user_activity', [])),
            "filesystem_data_count": len(context_data.get('filesystem_data', [])),
            "additional_context_count": len(context_data.get('additional_context', []))
        }
        
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis_result,
                    "provider": LLM_PROVIDER,
                    "timestamp": alert_source.get('timestamp'),
                    "context_sources": len(graph_queries),
                    "extracted_risk_level": risk_level,
                    "stage": "Stage 4 - GraphRAG Analysis",
                    "analysis_method": "Graph-Native Retrieval" if any(context_data.get(k) for k in ['attack_paths', 'lateral_movement']) else "Hybrid Retrieval",
                    **context_metadata
                },
                "alert_vector": alert_vector
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        
        logger.info(f"🎉 GRAPHRAG PROCESSING COMPLETE: Alert {alert_id} successfully updated")
        logger.info(f"   📈 Graph-native correlation metadata stored for future analysis")
        
        # Step 8: Graph Persistence - Extract entities and build relationships (NEW)
        logger.info(f"🔗 STEP 8: GRAPH PERSISTENCE - Building knowledge graph for alert {alert_id}")
        
        try:
            # Extract graph entities from alert and context
            graph_entities = await extract_graph_entities(alert, context_data, analysis_result)
            logger.info(f"   🔍 Extracted {len(graph_entities)} entities for graph database")
            
            # Build relationships between entities
            graph_relationships = await build_graph_relationships(graph_entities, alert, context_data)
            logger.info(f"   🔗 Built {len(graph_relationships)} relationships for graph database")
            
            # Persist to graph database (Neo4j)
            graph_persistence_result = await persist_to_graph_database(graph_entities, graph_relationships, alert_id)
            
            if graph_persistence_result['success']:
                logger.info(f"   ✅ Graph persistence successful: {graph_persistence_result['nodes_created']} nodes, {graph_persistence_result['relationships_created']} relationships")
                
                # Update alert with graph metadata
                graph_metadata = {
                    "graph_entities_count": len(graph_entities),
                    "graph_relationships_count": len(graph_relationships),
                    "graph_persistence_timestamp": graph_persistence_result['timestamp'],
                    "graph_node_ids": graph_persistence_result.get('node_ids', [])
                }
                
                # Add graph metadata to the alert
                graph_update_body = {
                    "doc": {
                        "ai_analysis.graph_metadata": graph_metadata
                    }
                }
                
                await client.update(index=alert_index, id=alert_id, body=graph_update_body)
                logger.info(f"   📊 Graph metadata added to alert {alert_id}")
                
            else:
                logger.warning(f"   ⚠️ Graph persistence failed: {graph_persistence_result.get('error', 'Unknown error')}")
                
        except Exception as graph_error:
            logger.error(f"   ❌ Graph persistence error for alert {alert_id}: {str(graph_error)}")
            # Graph persistence failure should not break the main pipeline
            logger.info(f"   🔄 Main processing pipeline continues despite graph persistence failure")
        
    except Exception as e:
        logger.error(f"❌ PROCESSING FAILED for alert {alert_id}: {str(e)}")
        logger.error(f"   Stack trace: {traceback.format_exc()}")
        raise

async def triage_new_alerts():
    """Main alert triage task with Stage 3 agentic context correlation"""
    print("🚀 === STAGE 3 AGENTIC CONTEXT CORRELATION TRIAGE JOB EXECUTING ===")
    logger.info(f"🔬 Analyzing alerts with {LLM_PROVIDER} model and enhanced agentic context correlation...")
    
    try:
        # Query new alerts
        alerts = await query_new_alerts(limit=10)
        
        if not alerts:
            print("📭 --- No new alerts found ---")
            logger.info("No new alerts requiring agentic analysis")
            return
            
        logger.info(f"🎯 Found {len(alerts)} new alerts to process with agentic context correlation")
        
        # Process each alert with enhanced agentic workflow
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
                print(f"✅ [{i}/{len(alerts)}] Successfully processed alert {alert_id}")
                logger.info(f"✅ Alert {alert_id} processing completed successfully")
                
            except Exception as e:
                failed_processing += 1
                print(f"❌ [{i}/{len(alerts)}] Failed to process alert {alert_id}: {str(e)}")
                logger.error(f"❌ Alert {alert_id} processing failed: {str(e)}")
                continue
        
        # Summary logging
        print(f"📊 === AGENTIC TRIAGE BATCH SUMMARY ===")
        print(f"   ✅ Successful: {successful_processing}")
        print(f"   ❌ Failed: {failed_processing}")
        print(f"   📈 Success Rate: {(successful_processing/len(alerts)*100):.1f}%")
        
        logger.info(f"🎯 Agentic triage batch completed: {successful_processing}/{len(alerts)} successful")
            
    except Exception as e:
        print(f"💥 !!! CRITICAL ERROR IN AGENTIC TRIAGE JOB !!!")
        logger.error(f"Critical error during agentic triage: {e}", exc_info=True)
        traceback.print_exc()

# === FastAPI 應用程式與排程器 ===

app = FastAPI(title="Wazuh AI Triage Agent - Stage 3 Agentic Context Correlation")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logging.info("AI Agent with Stage 3 Agentic Context Correlation starting up...")
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='agentic_triage_job', misfire_grace_time=30)
    scheduler.start()
    logging.info("Scheduler started. Agentic Context Correlation Triage job scheduled.")

@app.get("/")
def read_root():
    """根端點 - 返回服務狀態資訊"""
    return {
        "status": "AI Triage Agent with Agentic Context Correlation is running", 
        "scheduler_status": str(scheduler.get_jobs()),
        "stage": "Stage 3 - Agentic Context Correlation",
        "features": [
            "Dynamic contextual query generation",
            "Multi-source data retrieval",
            "Cross-referential analysis",
            "Enhanced decision engine"
        ]
    }

@app.get("/health")
async def health_check():
    """
    詳細健康檢查端點
    
    提供完整的系統狀態資訊，包括：
    - OpenSearch 連線狀態
    - 嵌入服務可用性
    - 向量化統計資料
    - 系統配置資訊
    
    Returns:
        Dict: 詳細的健康檢查報告
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.0", # Updated version
        "stage": "Stage 3 - Agentic Context Correlation" # Updated stage
    }
    
    try:
        # 檢查 OpenSearch 連線狀態
        cluster_health = await client.cluster.health()
        health_status["opensearch"] = {
            "status": "connected",
            "cluster_name": cluster_health.get("cluster_name", "unknown"),
            "cluster_status": cluster_health.get("status", "unknown"),
            "number_of_nodes": cluster_health.get("number_of_nodes", 0)
        }
        
        # 檢查嵌入服務狀態
        embedding_test = await embedding_service.test_connection()
        health_status["embedding_service"] = {
            "status": "working" if embedding_test else "failed",
            "model": embedding_service.model_name,
            "dimension": embedding_service.get_vector_dimension()
        }
        
        # 檢查向量化警報統計
        vectorized_count_response = await client.count(
            index="wazuh-alerts-*",
            body={"query": {"exists": {"field": "alert_vector"}}}
        )
        
        # 檢查 Stage 3 分析統計
        stage3_analysis_response = await client.count(
            index="wazuh-alerts-*",
            body={"query": {"bool": {"must": [
                {"exists": {"field": "ai_analysis"}},
                {"term": {"ai_analysis.stage.keyword": "Stage 3 - Agentic Context Correlation"}}
            ]}}}
        )
        
        total_alerts_response = await client.count(index="wazuh-alerts-*")
        
        health_status["processing_stats"] = {
            "vectorized_alerts": vectorized_count_response.get("count", 0),
            "stage3_analyzed_alerts": stage3_analysis_response.get("count", 0),
            "total_alerts": total_alerts_response.get("count", 0),
            "vectorization_rate": round(
                (vectorized_count_response.get("count", 0) / max(total_alerts_response.get("count", 1), 1)) * 100, 2
            ),
            "stage3_analysis_rate": round(
                (stage3_analysis_response.get("count", 0) / max(total_alerts_response.get("count", 1), 1)) * 100, 2
            )
        }
        
        # LLM 配置資訊
        health_status["llm_config"] = {
            "provider": LLM_PROVIDER,
            "model_configured": True
        }
        
        # 排程器狀態
        jobs = scheduler.get_jobs()
        health_status["scheduler"] = {
            "status": "running" if jobs else "no_jobs",
            "active_jobs": len(jobs),
            "next_run": str(jobs[0].next_run_time) if jobs else None
        }
        
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        logger.error(f"健康檢查失敗: {str(e)}")
    
    return health_status

# ==================== 圖形化持久層函數 (GraphRAG Stage 4 準備) ====================

async def extract_graph_entities(alert: Dict[str, Any], context_data: Dict[str, Any], analysis_result: str) -> List[Dict[str, Any]]:
    """
    從警報、上下文資料和分析結果中提取圖形實體
    
    Args:
        alert: 原始警報資料
        context_data: 上下文關聯資料
        analysis_result: LLM 分析結果
    
    Returns:
        提取的圖形實體列表
    """
    entities = []
    alert_source = alert.get('_source', {})
    
    # 1. 警報實體 (Alert Entity)
    alert_entity = {
        'type': 'Alert',
        'id': alert['_id'],
        'properties': {
            'alert_id': alert['_id'],
            'timestamp': alert_source.get('timestamp'),
            'rule_id': alert_source.get('rule', {}).get('id'),
            'rule_description': alert_source.get('rule', {}).get('description'),
            'rule_level': alert_source.get('rule', {}).get('level'),
            'rule_groups': alert_source.get('rule', {}).get('groups', []),
            'risk_level': _extract_risk_level_from_analysis(analysis_result),
            'triage_score': _calculate_triage_score(alert_source, analysis_result)
        }
    }
    entities.append(alert_entity)
    
    # 2. 主機實體 (Host Entity)
    agent = alert_source.get('agent', {})
    if agent.get('id') or agent.get('name'):
        host_entity = {
            'type': 'Host',
            'id': f"host_{agent.get('id', agent.get('name', 'unknown'))}",
            'properties': {
                'agent_id': agent.get('id'),
                'agent_name': agent.get('name'),
                'agent_ip': agent.get('ip'),
                'operating_system': _extract_os_info(alert_source)
            }
        }
        entities.append(host_entity)
    
    # 3. IP 位址實體 (IP Address Entities)
    ip_addresses = _extract_ip_addresses(alert_source)
    for ip_info in ip_addresses:
        ip_entity = {
            'type': 'IPAddress',
            'id': f"ip_{ip_info['address']}",
            'properties': {
                'address': ip_info['address'],
                'type': ip_info['type'],  # source, destination, internal
                'geolocation': ip_info.get('geo'),
                'is_private': _is_private_ip(ip_info['address'])
            }
        }
        entities.append(ip_entity)
    
    # 4. 使用者實體 (User Entities)
    users = _extract_user_info(alert_source)
    for user_info in users:
        user_entity = {
            'type': 'User',
            'id': f"user_{user_info['name']}",
            'properties': {
                'username': user_info['name'],
                'user_type': user_info.get('type', 'unknown'),
                'authentication_method': user_info.get('auth_method')
            }
        }
        entities.append(user_entity)
    
    # 5. 程序實體 (Process Entities)
    processes = _extract_process_info(alert_source, context_data)
    for process_info in processes:
        process_entity = {
            'type': 'Process',
            'id': f"process_{process_info.get('pid', 'unknown')}_{process_info.get('name', 'unknown')}",
            'properties': {
                'process_name': process_info.get('name'),
                'process_id': process_info.get('pid'),
                'command_line': process_info.get('cmdline'),
                'parent_process': process_info.get('ppid'),
                'hash': process_info.get('hash')
            }
        }
        entities.append(process_entity)
    
    # 6. 檔案實體 (File Entities)
    files = _extract_file_info(alert_source)
    for file_info in files:
        file_entity = {
            'type': 'File',
            'id': f"file_{hash(file_info['path'])}",
            'properties': {
                'file_path': file_info['path'],
                'file_name': file_info.get('name'),
                'file_size': file_info.get('size'),
                'file_hash': file_info.get('hash'),
                'file_permissions': file_info.get('permissions')
            }
        }
        entities.append(file_entity)
    
    # 7. 威脅實體 (從分析結果提取)
    threat_indicators = _extract_threat_indicators(analysis_result)
    for threat in threat_indicators:
        threat_entity = {
            'type': 'ThreatIndicator',
            'id': f"threat_{uuid.uuid4().hex[:8]}",
            'properties': {
                'indicator_type': threat['type'],
                'indicator_value': threat['value'],
                'confidence': threat.get('confidence', 0.5),
                'mitre_technique': threat.get('mitre_technique')
            }
        }
        entities.append(threat_entity)
    
    logger.info(f"Extracted {len(entities)} entities: {dict(zip(*zip(*[(e['type'], 1) for e in entities])))}")
    return entities

async def build_graph_relationships(entities: List[Dict[str, Any]], alert: Dict[str, Any], context_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根據實體和上下文資料建立圖形關係
    
    Args:
        entities: 提取的實體列表
        alert: 原始警報資料
        context_data: 上下文關聯資料
    
    Returns:
        實體間的關係列表
    """
    relationships = []
    entity_by_id = {entity['id']: entity for entity in entities}
    entity_by_type = {}
    
    # 按類型組織實體
    for entity in entities:
        entity_type = entity['type']
        if entity_type not in entity_by_type:
            entity_by_type[entity_type] = []
        entity_by_type[entity_type].append(entity)
    
    # 1. 警報觸發關係 (Alert -> Host)
    alert_entities = entity_by_type.get('Alert', [])
    host_entities = entity_by_type.get('Host', [])
    
    for alert_entity in alert_entities:
        for host_entity in host_entities:
            relationship = {
                'type': 'TRIGGERED_ON',
                'source_id': alert_entity['id'],
                'target_id': host_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp'),
                    'severity': alert.get('_source', {}).get('rule', {}).get('level')
                }
            }
            relationships.append(relationship)
    
    # 2. 來源 IP 關係 (Alert -> IPAddress)
    ip_entities = entity_by_type.get('IPAddress', [])
    for alert_entity in alert_entities:
        for ip_entity in ip_entities:
            if ip_entity['properties'].get('type') == 'source':
                relationship = {
                    'type': 'HAS_SOURCE_IP',
                    'source_id': alert_entity['id'],
                    'target_id': ip_entity['id'],
                    'properties': {
                        'timestamp': alert.get('_source', {}).get('timestamp')
                    }
                }
                relationships.append(relationship)
    
    # 3. 使用者參與關係 (Alert -> User)
    user_entities = entity_by_type.get('User', [])
    for alert_entity in alert_entities:
        for user_entity in user_entities:
            relationship = {
                'type': 'INVOLVES_USER',
                'source_id': alert_entity['id'],
                'target_id': user_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp'),
                    'action_type': _determine_user_action_type(alert)
                }
            }
            relationships.append(relationship)
    
    # 4. 程序執行關係 (Alert -> Process)
    process_entities = entity_by_type.get('Process', [])
    for alert_entity in alert_entities:
        for process_entity in process_entities:
            relationship = {
                'type': 'INVOLVES_PROCESS',
                'source_id': alert_entity['id'],
                'target_id': process_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp')
                }
            }
            relationships.append(relationship)
    
    # 5. 檔案存取關係 (Alert -> File)
    file_entities = entity_by_type.get('File', [])
    for alert_entity in alert_entities:
        for file_entity in file_entities:
            relationship = {
                'type': 'ACCESSES_FILE',
                'source_id': alert_entity['id'],
                'target_id': file_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp'),
                    'access_type': _determine_file_access_type(alert)
                }
            }
            relationships.append(relationship)
    
    # 6. 類似警報關係 (基於上下文資料)
    similar_alerts = context_data.get('similar_alerts', [])
    for similar_alert in similar_alerts[:5]:  # 限制關係數量
        similar_alert_id = similar_alert.get('_id')
        if similar_alert_id:
            for alert_entity in alert_entities:
                relationship = {
                    'type': 'SIMILAR_TO',
                    'source_id': alert_entity['id'],
                    'target_id': f"alert_{similar_alert_id}",  # 假設該警報已在圖中
                    'properties': {
                        'similarity_score': similar_alert.get('_score', 0.0),
                        'correlation_type': 'vector_similarity'
                    }
                }
                relationships.append(relationship)
    
    # 7. 時間序列關係 (Temporal Relationships)
    # 根據時間戳建立 PRECEDES 關係
    if len(alert_entities) > 1:
        sorted_alerts = sorted(alert_entities, key=lambda x: x['properties'].get('timestamp', ''))
        for i in range(len(sorted_alerts) - 1):
            relationship = {
                'type': 'PRECEDES',
                'source_id': sorted_alerts[i]['id'],
                'target_id': sorted_alerts[i + 1]['id'],
                'properties': {
                    'time_difference': _calculate_time_difference(
                        sorted_alerts[i]['properties'].get('timestamp'),
                        sorted_alerts[i + 1]['properties'].get('timestamp')
                    )
                }
            }
            relationships.append(relationship)
    
    logger.info(f"Built {len(relationships)} relationships")
    return relationships

async def persist_to_graph_database(entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]], alert_id: str) -> Dict[str, Any]:
    """
    將實體和關係持久化到 Neo4j 圖形資料庫
    
    Args:
        entities: 要存儲的實體列表
        relationships: 要存儲的關係列表
        alert_id: 警報 ID
    
    Returns:
        持久化結果，包含成功狀態和統計資訊
    """
    if not neo4j_driver:
        return {
            'success': False,
            'error': 'Neo4j driver not available',
            'nodes_created': 0,
            'relationships_created': 0
        }
    
    try:
        async with neo4j_driver.session() as session:
            # 存儲節點
            nodes_created = 0
            node_ids = []
            
            for entity in entities:
                # 使用 MERGE 來避免重複節點
                cypher_query = f"""
                MERGE (n:{entity['type']} {{id: $entity_id}})
                SET n += $properties
                RETURN n.id as node_id
                """
                
                result = await session.run(
                    cypher_query,
                    entity_id=entity['id'],
                    properties=entity['properties']
                )
                
                record = await result.single()
                if record:
                    node_ids.append(record['node_id'])
                    nodes_created += 1
            
            # 存儲關係
            relationships_created = 0
            
            for relationship in relationships:
                # 使用 MERGE 來避免重複關係
                cypher_query = f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                MERGE (source)-[r:{relationship['type']}]->(target)
                SET r += $properties
                RETURN r
                """
                
                result = await session.run(
                    cypher_query,
                    source_id=relationship['source_id'],
                    target_id=relationship['target_id'],
                    properties=relationship.get('properties', {})
                )
                
                if await result.peek():
                    relationships_created += 1
            
            # 建立索引 (如果不存在)
            index_queries = [
                "CREATE INDEX alert_timestamp_idx IF NOT EXISTS FOR (a:Alert) ON (a.timestamp)",
                "CREATE INDEX host_agent_id_idx IF NOT EXISTS FOR (h:Host) ON (h.agent_id)",
                "CREATE INDEX ip_address_idx IF NOT EXISTS FOR (i:IPAddress) ON (i.address)",
                "CREATE INDEX user_name_idx IF NOT EXISTS FOR (u:User) ON (u.username)"
            ]
            
            for index_query in index_queries:
                await session.run(index_query)
            
            return {
                'success': True,
                'nodes_created': nodes_created,
                'relationships_created': relationships_created,
                'node_ids': node_ids,
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Graph persistence error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'nodes_created': 0,
            'relationships_created': 0
        }

# ==================== 輔助函數 ====================

def _extract_risk_level_from_analysis(analysis_result: str) -> str:
    """從分析結果中提取風險等級"""
    risk_levels = ['Critical', 'High', 'Medium', 'Low', 'Informational']
    for level in risk_levels:
        if level.lower() in analysis_result.lower():
            return level
    return 'Unknown'

def _calculate_triage_score(alert_source: Dict, analysis_result: str) -> float:
    """計算警報分級分數"""
    base_score = alert_source.get('rule', {}).get('level', 1) * 10
    
    # 根據分析結果調整分數
    if 'critical' in analysis_result.lower():
        return min(base_score * 1.5, 100)
    elif 'high' in analysis_result.lower():
        return min(base_score * 1.2, 100)
    elif 'low' in analysis_result.lower():
        return max(base_score * 0.8, 0)
    
    return base_score

def _extract_os_info(alert_source: Dict) -> str:
    """提取作業系統資訊"""
    agent = alert_source.get('agent', {})
    return agent.get('labels', {}).get('os', 'unknown')

def _extract_ip_addresses(alert_source: Dict) -> List[Dict]:
    """提取 IP 位址資訊"""
    ips = []
    data = alert_source.get('data', {})
    
    # 來源 IP
    if data.get('srcip'):
        ips.append({
            'address': data['srcip'],
            'type': 'source',
            'geo': data.get('srcgeoip', {})
        })
    
    # 目的 IP
    if data.get('dstip'):
        ips.append({
            'address': data['dstip'],
            'type': 'destination',
            'geo': data.get('dstgeoip', {})
        })
    
    # Agent IP
    agent = alert_source.get('agent', {})
    if agent.get('ip'):
        ips.append({
            'address': agent['ip'],
            'type': 'internal'
        })
    
    return ips

def _is_private_ip(ip_address: str) -> bool:
    """檢查是否為私有 IP 位址"""
    import ipaddress
    try:
        ip = ipaddress.ip_address(ip_address)
        return ip.is_private
    except:
        return False

def _extract_user_info(alert_source: Dict) -> List[Dict]:
    """提取使用者資訊"""
    users = []
    data = alert_source.get('data', {})
    
    # 主要使用者
    if data.get('user'):
        users.append({
            'name': data['user'],
            'type': 'primary'
        })
    
    # 來源使用者
    if data.get('srcuser'):
        users.append({
            'name': data['srcuser'],
            'type': 'source'
        })
    
    return users

def _extract_process_info(alert_source: Dict, context_data: Dict) -> List[Dict]:
    """提取程序資訊"""
    processes = []
    data = alert_source.get('data', {})
    
    # 來自警報的程序資訊
    if data.get('process'):
        processes.append({
            'name': data['process'].get('name'),
            'pid': data['process'].get('pid'),
            'cmdline': data['process'].get('cmdline'),
            'ppid': data['process'].get('ppid')
        })
    
    # 來自上下文的程序資訊
    process_data = context_data.get('process_data', [])
    for proc in process_data[:5]:  # 限制數量
        if isinstance(proc, dict) and proc.get('_source'):
            proc_source = proc['_source']
            processes.append({
                'name': proc_source.get('data', {}).get('process', {}).get('name'),
                'pid': proc_source.get('data', {}).get('process', {}).get('pid'),
                'cmdline': proc_source.get('data', {}).get('process', {}).get('cmdline')
            })
    
    return [p for p in processes if p.get('name')]  # 過濾空的程序

def _extract_file_info(alert_source: Dict) -> List[Dict]:
    """提取檔案資訊"""
    files = []
    data = alert_source.get('data', {})
    
    # 檔案路徑
    if data.get('file'):
        files.append({
            'path': data['file'],
            'name': data['file'].split('/')[-1] if '/' in data['file'] else data['file']
        })
    
    # 額外的檔案欄位
    if data.get('path'):
        files.append({
            'path': data['path'],
            'name': data['path'].split('/')[-1] if '/' in data['path'] else data['path']
        })
    
    return files

def _extract_threat_indicators(analysis_result: str) -> List[Dict]:
    """從分析結果中提取威脅指標"""
    indicators = []
    
    # 簡單的正則表達式匹配
    ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    domain_pattern = r'\b[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\b'
    
    # 提取 IP 位址
    ips = re.findall(ip_pattern, analysis_result)
    for ip in ips[:3]:  # 限制數量
        indicators.append({
            'type': 'ip_address',
            'value': ip,
            'confidence': 0.7
        })
    
    # 提取域名（簡化版）
    words = analysis_result.split()
    for word in words:
        if '.' in word and len(word) > 4 and not word.startswith('.'):
            indicators.append({
                'type': 'domain',
                'value': word,
                'confidence': 0.5
            })
            if len(indicators) >= 5:  # 限制數量
                break
    
    return indicators

def _determine_user_action_type(alert: Dict) -> str:
    """確定使用者動作類型"""
    rule_desc = alert.get('_source', {}).get('rule', {}).get('description', '').lower()
    
    if 'login' in rule_desc or 'authentication' in rule_desc:
        return 'authentication'
    elif 'ssh' in rule_desc:
        return 'remote_access'
    elif 'file' in rule_desc:
        return 'file_access'
    else:
        return 'unknown'

def _determine_file_access_type(alert: Dict) -> str:
    """確定檔案存取類型"""
    rule_desc = alert.get('_source', {}).get('rule', {}).get('description', '').lower()
    
    if 'write' in rule_desc or 'modify' in rule_desc:
        return 'write'
    elif 'read' in rule_desc:
        return 'read'
    elif 'delete' in rule_desc:
        return 'delete'
    else:
        return 'access'

def _calculate_time_difference(timestamp1: str, timestamp2: str) -> int:
    """計算兩個時間戳之間的差異（秒）"""
    try:
        from dateutil import parser
        dt1 = parser.parse(timestamp1)
        dt2 = parser.parse(timestamp2)
        return int(abs((dt2 - dt1).total_seconds()))
    except:
        return 0

@app.on_event("shutdown")
def shutdown_event():
    """應用程式關閉事件處理器"""
    scheduler.shutdown()
    if neo4j_driver:
        neo4j_driver.close()
        logger.info("Neo4j 連接已關閉")
    logger.info("排程器已關閉")

# 移除重複的main函數定義

# ==================== Graph-Native 檢索器 (Stage 4 Step 3) ====================

async def execute_graph_retrieval(cypher_queries: List[Dict[str, Any]], alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Graph-Native 檢索器：執行 Cypher 查詢來檢索相關的圖形子網
    這是 GraphRAG 的核心檢索引擎，取代傳統的向量與關鍵字搜尋
    
    Args:
        cypher_queries: 從 Decision Engine 生成的 Cypher 查詢任務列表
        alert: 當前警報資料
        
    Returns:
        Dictionary 包含檢索到的圖形子網和結構化上下文
    """
    logger.info(f"🔗 GRAPH-NATIVE RETRIEVAL: Processing {len(cypher_queries)} Cypher queries")
    
    context_data = {
        'attack_paths': [],           # 攻擊路徑子圖
        'lateral_movement': [],       # 橫向移動模式
        'temporal_sequences': [],     # 時間序列關聯
        'ip_reputation': [],          # IP 信譽圖
        'user_behavior': [],          # 使用者行為圖
        'process_chains': [],         # 程序執行鏈
        'file_interactions': [],      # 檔案交互圖
        'network_topology': [],       # 網路拓撲
        'threat_landscape': [],       # 威脅全景
        'correlation_graph': []       # 相關性圖
    }
    
    if not neo4j_driver:
        logger.warning("Neo4j driver not available - falling back to traditional retrieval")
        # 降級到傳統檢索
        return await _fallback_to_traditional_retrieval(alert)
    
    # 排序查詢以優化執行順序
    sorted_queries = sorted(cypher_queries, key=lambda x: {
        'critical': 0, 'high': 1, 'medium': 2, 'low': 3
    }.get(x.get('priority', 'medium'), 2))
    
    alert_id = alert.get('_id')
    
    async with neo4j_driver.session() as session:
        for i, query_spec in enumerate(sorted_queries, 1):
            query_type = query_spec['type']
            description = query_spec['description']
            priority = query_spec.get('priority', 'medium')
            cypher_query = query_spec['cypher_query']
            parameters = query_spec.get('parameters', {})
            
            # 注入當前警報 ID 到參數中
            parameters['alert_id'] = alert_id
            
            try:
                logger.info(f"   [{i}/{len(sorted_queries)}] 🔍 {priority.upper()}: {description}")
                
                # 執行 Cypher 查詢
                result = await session.run(cypher_query, parameters)
                records = await result.data()
                
                # 根據查詢類型分類結果
                await _categorize_graph_results(query_type, records, context_data)
                
                logger.info(f"      ✅ Graph query returned {len(records)} subgraph components")
                
            except Exception as e:
                logger.error(f"      ❌ Cypher query failed: {str(e)}")
                # 記錄失敗的查詢以便後續分析
                logger.error(f"      Query: {cypher_query[:200]}...")
                continue
    
    # 生成檢索摘要
    total_components = sum(len(results) for results in context_data.values())
    logger.info(f"📊 GRAPH RETRIEVAL SUMMARY: {total_components} total graph components")
    for category, results in context_data.items():
        if results:
            logger.info(f"   {category}: {len(results)} components")
    
    return context_data

async def _categorize_graph_results(query_type: str, records: List[Dict], context_data: Dict[str, Any]):
    """
    根據查詢類型將圖形結果分類到適當的上下文類別中
    
    Args:
        query_type: 查詢類型（攻擊路徑、橫向移動等）
        records: Cypher 查詢返回的記錄
        context_data: 要更新的上下文資料字典
    """
    if query_type == 'attack_path_analysis':
        context_data['attack_paths'].extend(records)
    elif query_type == 'lateral_movement_detection':
        context_data['lateral_movement'].extend(records)
    elif query_type == 'temporal_correlation':
        context_data['temporal_sequences'].extend(records)
    elif query_type == 'ip_reputation_analysis':
        context_data['ip_reputation'].extend(records)
    elif query_type == 'user_behavior_analysis':
        context_data['user_behavior'].extend(records)
    elif query_type == 'process_chain_analysis':
        context_data['process_chains'].extend(records)
    elif query_type == 'file_interaction_analysis':
        context_data['file_interactions'].extend(records)
    elif query_type == 'network_topology_analysis':
        context_data['network_topology'].extend(records)
    elif query_type == 'threat_landscape_analysis':
        context_data['threat_landscape'].extend(records)
    else:
        # 預設分類
        context_data['correlation_graph'].extend(records)

async def _fallback_to_traditional_retrieval(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    當 Neo4j 不可用時，降級到傳統的向量和關鍵字檢索
    
    Args:
        alert: 當前警報資料
        
    Returns:
        傳統檢索的結果
    """
    logger.info("🔄 Falling back to traditional vector + keyword retrieval")
    
    # 生成傳統檢索查詢
    traditional_queries = determine_contextual_queries(alert)
    
    # 向量化警報（如果需要）
    alert_vector = []
    embedding_service = GeminiEmbeddingService()
    try:
        alert_text = _extract_alert_text_for_embedding(alert)
        alert_vector = await embedding_service.embed_text(alert_text)
    except Exception as e:
        logger.warning(f"Alert vectorization failed: {str(e)}")
    
    # 執行傳統檢索
    return await execute_retrieval(traditional_queries, alert_vector)

def _extract_alert_text_for_embedding(alert: Dict[str, Any]) -> str:
    """
    從警報中提取文本用於向量化
    """
    alert_source = alert.get('_source', {})
    rule = alert_source.get('rule', {})
    
    text_parts = [
        rule.get('description', ''),
        ' '.join(rule.get('groups', [])),
        str(alert_source.get('data', {}))
    ]
    
    return ' '.join(filter(None, text_parts))

# ==================== Graph-Native 決策引擎 ====================

def determine_graph_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Graph-Native 決策引擎：根據警報內容決定要執行的 Cypher 查詢
    取代原有的 determine_contextual_queries，專注於圖形查詢策略
    
    Args:
        alert: 新的警報文檔
        
    Returns:
        Cypher 查詢規格列表
    """
    queries = []
    alert_source = alert.get('_source', {})
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    data = alert_source.get('data', {})
    timestamp = alert_source.get('timestamp')
    
    rule_description = rule.get('description', '').lower()
    rule_groups = rule.get('groups', [])
    rule_level = rule.get('level', 0)
    agent_id = agent.get('id', '')
    
    logger.info(f"🔗 GRAPH-NATIVE DECISION ENGINE: Analyzing alert for graph queries")
    logger.info(f"   Alert: {rule_description}")
    logger.info(f"   Level: {rule_level}, Agent: {agent_id}")
    logger.info(f"   Groups: {', '.join(rule_groups)}")
    
    # 1. SSH 暴力破解場景 - 攻擊來源全貌分析
    if 'ssh' in rule_description and ('brute' in rule_description or 'failed' in rule_description):
        logger.info("🔑 DECISION: SSH brute force detected - analyzing attacker profile")
        
        queries.append({
            'type': 'attack_path_analysis',
            'description': 'SSH attacker complete activity profile',
            'priority': 'critical',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})-[:HAS_SOURCE_IP]->(attacker:IPAddress)
                CALL {
                    WITH attacker
                    MATCH (related_alert:Alert)-[:HAS_SOURCE_IP]->(attacker)
                    WHERE related_alert.timestamp > datetime() - duration({hours: 1})
                    MATCH (related_alert)-[r]->(entity)
                    WHERE type(r) <> 'MATCHED_RULE'
                    RETURN related_alert, r, entity
                }
                RETURN *
            ''',
            'parameters': {}
        })
        
        # 橫向移動檢測
        queries.append({
            'type': 'lateral_movement_detection',
            'description': 'Lateral movement patterns from attacker IP',
            'priority': 'high',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})-[:HAS_SOURCE_IP]->(attacker:IPAddress)
                MATCH (attacker)<-[:HAS_SOURCE_IP]-(other_alerts:Alert)-[:TRIGGERED_ON]->(hosts:Host)
                WITH attacker, collect(DISTINCT hosts) as target_hosts
                WHERE size(target_hosts) > 1
                MATCH path = (attacker)-[*1..3]-(hosts:Host)
                RETURN path, target_hosts, attacker
            ''',
            'parameters': {}
        })
    
    # 2. 惡意軟體/程序分析場景
    malware_keywords = ['malware', 'trojan', 'virus', 'suspicious', 'backdoor', 'rootkit']
    if any(keyword in rule_description for keyword in malware_keywords):
        logger.info("🦠 DECISION: Malware detected - analyzing process execution chains")
        
        queries.append({
            'type': 'process_chain_analysis',
            'description': 'Malicious process execution chains',
            'priority': 'critical',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})-[:INVOLVES_PROCESS]->(process:Process)
                MATCH path = (process)-[:SPAWNED_BY*0..5]->(parent:Process)
                MATCH (parent)<-[:INVOLVES_PROCESS]-(related_alerts:Alert)
                WHERE related_alerts.timestamp > datetime() - duration({hours: 2})
                RETURN path, collect(related_alerts) as timeline
            ''',
            'parameters': {}
        })
        
        # 檔案系統影響分析
        queries.append({
            'type': 'file_interaction_analysis',
            'description': 'File system impact analysis',
            'priority': 'high',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})-[:INVOLVES_PROCESS]->(process:Process)
                MATCH (process)-[:ACCESSED_FILE|MODIFIED_FILE|CREATED_FILE]->(files:File)
                MATCH (files)<-[r]-(other_processes:Process)<-[:INVOLVES_PROCESS]-(other_alerts:Alert)
                WHERE other_alerts.timestamp > alert.timestamp - duration({minutes: 30})
                RETURN files, collect(other_processes) as interacting_processes, 
                       collect(other_alerts) as related_alerts
            ''',
            'parameters': {}
        })
    
    # 3. 網路攻擊場景 - Web 攻擊分析
    web_keywords = ['web attack', 'sql injection', 'xss', 'command injection', 'http']
    if any(keyword in rule_description for keyword in web_keywords) or 'web' in rule_groups:
        logger.info("🌐 DECISION: Web attack detected - analyzing network attack patterns")
        
        queries.append({
            'type': 'network_topology_analysis',
            'description': 'Web attack network topology',
            'priority': 'high',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})-[:HAS_SOURCE_IP]->(attacker:IPAddress)
                MATCH (alert)-[:TRIGGERED_ON]->(target:Host)
                MATCH (attacker)-[:CONNECTED_TO*1..3]-(related_ips:IPAddress)
                MATCH (related_ips)<-[:HAS_SOURCE_IP]-(attack_alerts:Alert)
                WHERE attack_alerts.timestamp > datetime() - duration({hours: 6})
                RETURN attacker, target, related_ips, collect(attack_alerts) as attack_sequence
            ''',
            'parameters': {}
        })
    
    # 4. 使用者行為異常分析
    auth_keywords = ['authentication', 'login', 'failed', 'privilege', 'escalation']
    if any(keyword in rule_description for keyword in auth_keywords) or 'authentication' in rule_groups:
        logger.info("👤 DECISION: Authentication anomaly - analyzing user behavior patterns")
        
        queries.append({
            'type': 'user_behavior_analysis',
            'description': 'User behavior anomaly analysis',
            'priority': 'medium',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})-[:INVOLVES_USER]->(user:User)
                MATCH (user)<-[:INVOLVES_USER]-(user_alerts:Alert)
                WHERE user_alerts.timestamp > datetime() - duration({days: 7})
                WITH user, collect(user_alerts) as user_history
                MATCH (user)<-[:INVOLVES_USER]-(recent_alerts:Alert)
                WHERE recent_alerts.timestamp > datetime() - duration({hours: 2})
                RETURN user, user_history, collect(recent_alerts) as recent_activity
            ''',
            'parameters': {}
        })
    
    # 5. 時間序列關聯分析 (總是執行)
    queries.append({
        'type': 'temporal_correlation',
        'description': 'Temporal sequence analysis',
        'priority': 'medium',
        'cypher_query': '''
            MATCH (alert:Alert {id: $alert_id})-[:TRIGGERED_ON]->(host:Host)
            MATCH (host)<-[:TRIGGERED_ON]-(related_alerts:Alert)
            WHERE related_alerts.timestamp > alert.timestamp - duration({minutes: 30})
              AND related_alerts.timestamp < alert.timestamp + duration({minutes: 30})
              AND related_alerts.id <> alert.id
            WITH alert, related_alerts
            ORDER BY related_alerts.timestamp
            RETURN alert, collect(related_alerts) as temporal_sequence
        ''',
        'parameters': {}
    })
    
    # 6. IP 信譽與地理位置分析 (針對外部 IP)
    if _has_external_ip(alert_source):
        logger.info("🌍 DECISION: External IP detected - analyzing IP reputation")
        
        queries.append({
            'type': 'ip_reputation_analysis',
            'description': 'IP reputation and geolocation analysis',
            'priority': 'medium',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})-[:HAS_SOURCE_IP]->(ip:IPAddress)
                WHERE ip.is_private = false
                MATCH (ip)<-[:HAS_SOURCE_IP]-(historical_alerts:Alert)
                WHERE historical_alerts.timestamp > datetime() - duration({days: 30})
                WITH ip, collect(historical_alerts) as ip_history
                MATCH (ip)-[:GEOLOCATED_IN]->(geo:GeoLocation)
                RETURN ip, ip_history, geo
            ''',
            'parameters': {}
        })
    
    # 7. 威脅全景分析 (高級別警報)
    if rule_level >= 8:
        logger.info("⚠️ DECISION: High-severity alert - comprehensive threat landscape analysis")
        
        queries.append({
            'type': 'threat_landscape_analysis',
            'description': 'Comprehensive threat landscape',
            'priority': 'high',
            'cypher_query': '''
                MATCH (alert:Alert {id: $alert_id})
                MATCH (alert)-[r1]->(entity1)
                MATCH (entity1)-[r2]->(entity2)
                MATCH (entity2)<-[r3]-(other_alerts:Alert)
                WHERE other_alerts.timestamp > datetime() - duration({hours: 24})
                  AND other_alerts.rule_level >= 6
                RETURN alert, entity1, entity2, other_alerts, r1, r2, r3
                LIMIT 50
            ''',
            'parameters': {}
        })
    
    logger.info(f"✅ Generated {len(queries)} graph queries for alert analysis")
    return queries

def _has_external_ip(alert_source: Dict[str, Any]) -> bool:
    """
    檢查警報是否包含外部 IP 地址
    """
    data = alert_source.get('data', {})
    
    # 檢查常見的 IP 欄位
    ip_fields = ['srcip', 'dstip', 'src_ip', 'dst_ip', 'remote_ip']
    
    for field in ip_fields:
        ip = data.get(field)
        if ip and not _is_private_ip(ip):
            return True
    
    return False

def _is_private_ip(ip_address: str) -> bool:
    """
    檢查 IP 地址是否為私有地址
    """
    try:
        import ipaddress
        ip = ipaddress.ip_address(ip_address)
        return ip.is_private
    except:
        return False

# ==================== 混合檢索整合 ====================

async def execute_hybrid_retrieval(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    混合檢索系統：結合圖形查詢和傳統檢索方法
    為 GraphRAG 提供最佳的上下文檢索策略
    
    Args:
        alert: 當前警報資料
        
    Returns:
        結合的檢索結果
    """
    logger.info("🔗🔍 HYBRID RETRIEVAL: Combining graph and traditional methods")
    
    # 1. 執行圖形查詢
    graph_queries = determine_graph_queries(alert)
    graph_context = await execute_graph_retrieval(graph_queries, alert)
    
    # 2. 如果圖形查詢結果不足，補充傳統檢索
    total_graph_results = sum(len(results) for results in graph_context.values())
    
    if total_graph_results < 10:  # 設定閾值
        logger.info("📊 Graph results insufficient - supplementing with traditional retrieval")
        
        # 生成補充查詢
        traditional_queries = determine_contextual_queries(alert)
        
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

def _merge_retrieval_contexts(graph_context: Dict[str, Any], traditional_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    合併圖形檢索和傳統檢索的結果
    """
    merged_context = graph_context.copy()
    
    # 添加傳統檢索的結果作為補充上下文
    merged_context['traditional_similar_alerts'] = traditional_context.get('similar_alerts', [])
    merged_context['traditional_metrics'] = traditional_context.get('cpu_metrics', []) + \
                                          traditional_context.get('memory_metrics', [])
    merged_context['traditional_logs'] = traditional_context.get('network_logs', []) + \
                                       traditional_context.get('ssh_logs', [])
    
    return merged_context

def format_graph_context_cypher_notation(context_data: Dict[str, Any]) -> str:
    """
    將圖形上下文轉換為簡化的Cypher路徑記號格式
    
    Args:
        context_data: 圖形檢索的結果數據
        
    Returns:
        Cypher路徑記號格式的字符串
    """
    cypher_paths = []
    
    # 1. 處理攻擊路徑
    attack_paths = context_data.get('attack_paths', [])
    for path_data in attack_paths[:3]:  # 限制數量以避免過長
        attacker = path_data.get('attacker', {})
        related_alerts = path_data.get('related_alert', [])
        
        if attacker.get('address'):
            for alert in related_alerts[:5]:  # 限制每個IP的警報數量
                alert_desc = alert.get('rule', {}).get('description', 'Unknown')
                cypher_paths.append(
                    f"(IP:{attacker['address']}) -[TRIGGERED: {alert_desc[:30]}]-> (Alert:{alert.get('id', 'unknown')[:8]})"
                )
    
    # 2. 處理橫向移動
    lateral_movement = context_data.get('lateral_movement', [])
    for movement_data in lateral_movement[:2]:
        attacker = movement_data.get('attacker', {})
        target_hosts = movement_data.get('target_hosts', [])
        
        if attacker.get('address') and target_hosts:
            for host in target_hosts[:3]:
                host_name = host.get('agent_name', 'unknown')
                cypher_paths.append(
                    f"(IP:{attacker['address']}) -[LATERAL_MOVE]-> (Host:{host_name})"
                )
    
    # 3. 處理程序執行鏈
    process_chains = context_data.get('process_chains', [])
    for process_data in process_chains[:2]:
        timeline = process_data.get('timeline', [])
        if len(timeline) > 1:
            for i in range(len(timeline) - 1):
                current_alert = timeline[i]
                next_alert = timeline[i + 1]
                current_process = current_alert.get('data', {}).get('process', {}).get('name', 'unknown')
                next_process = next_alert.get('data', {}).get('process', {}).get('name', 'unknown')
                cypher_paths.append(
                    f"(Process:{current_process}) -[SPAWNED]-> (Process:{next_process})"
                )
    
    # 4. 處理IP信譽
    ip_reputation = context_data.get('ip_reputation', [])
    for ip_data in ip_reputation[:2]:
        ip = ip_data.get('ip', {})
        ip_history = ip_data.get('ip_history', [])
        
        if ip.get('address') and ip_history:
            alert_count = len(ip_history)
            cypher_paths.append(
                f"(IP:{ip['address']}) -[REPUTATION: {alert_count} alerts in 30 days]-> (ThreatProfile:Suspicious)"
            )
    
    # 5. 處理使用者行為
    user_behavior = context_data.get('user_behavior', [])
    for user_data in user_behavior[:2]:
        user = user_data.get('user', {})
        recent_activity = user_data.get('recent_activity', [])
        
        if user.get('username') and recent_activity:
            activity_count = len(recent_activity)
            cypher_paths.append(
                f"(User:{user['username']}) -[RECENT_ACTIVITY: {activity_count} events]-> (BehaviorPattern:Anomalous)"
            )
    
    # 6. 處理檔案交互
    file_interactions = context_data.get('file_interactions', [])
    for file_data in file_interactions[:2]:
        files = file_data.get('files', {})
        interacting_processes = file_data.get('interacting_processes', [])
        
        if files.get('file_path') and interacting_processes:
            file_path = files['file_path'].split('/')[-1]  # 只顯示檔名
            process_count = len(interacting_processes)
            cypher_paths.append(
                f"(File:{file_path}) -[ACCESSED_BY: {process_count} processes]-> (SecurityEvent:Suspicious)"
            )
    
    # 7. 處理時間序列
    temporal_sequences = context_data.get('temporal_sequences', [])
    for seq_data in temporal_sequences[:1]:  # 只處理一個主要序列
        sequence = seq_data.get('temporal_sequence', [])
        if len(sequence) > 1:
            first_alert = sequence[0]
            last_alert = sequence[-1]
            time_span = len(sequence)
            cypher_paths.append(
                f"(Alert:{first_alert.get('id', 'unknown')[:8]}) -[TEMPORAL_SEQUENCE: {time_span} events in 30min]-> (Alert:{last_alert.get('id', 'unknown')[:8]})"
            )
    
    # 如果沒有足夠的圖形數據，生成基於傳統檢索的路徑格式
    if not cypher_paths:
        cypher_paths = _generate_fallback_cypher_paths(context_data)
    
    return "\n".join(cypher_paths)

def _generate_fallback_cypher_paths(context_data: Dict[str, Any]) -> List[str]:
    """
    當圖形數據不足時，基於傳統檢索結果生成Cypher路徑格式
    
    Args:
        context_data: 上下文數據
        
    Returns:
        Cypher路徑格式的列表
    """
    fallback_paths = []
    
    # 檢查是否有傳統的相似警報
    traditional_alerts = context_data.get('traditional_similar_alerts', [])
    similar_alerts = context_data.get('similar_alerts', [])
    all_similar = traditional_alerts + similar_alerts
    
    if all_similar:
        for i, alert in enumerate(all_similar[:3], 1):
            alert_source = alert.get('_source', {})
            rule = alert_source.get('rule', {})
            agent = alert_source.get('agent', {})
            score = alert.get('_score', 0.0)
            
            fallback_paths.append(
                f"(Alert:Current) -[SIMILAR: {score:.2f}]-> (Alert:{rule.get('description', 'Unknown')[:25]}...)"
            )
            
            if agent.get('name'):
                fallback_paths.append(
                    f"(Host:{agent['name']}) -[EXPERIENCED]-> (Alert:{rule.get('description', 'Unknown')[:25]}...)"
                )
    
    # 檢查系統指標
    cpu_metrics = context_data.get('cpu_metrics', [])
    memory_metrics = context_data.get('memory_metrics', [])
    
    if cpu_metrics or memory_metrics:
        fallback_paths.append(
            f"(Alert:Current) -[CORRELATED_WITH]-> (SystemMetrics:{len(cpu_metrics + memory_metrics)} events)"
        )
    
    # 檢查網路日誌
    network_logs = context_data.get('network_logs', [])
    ssh_logs = context_data.get('ssh_logs', [])
    
    if network_logs or ssh_logs:
        fallback_paths.append(
            f"(Alert:Current) -[NETWORK_CONTEXT]-> (NetworkActivity:{len(network_logs + ssh_logs)} events)"
        )
    
    # 如果還是沒有數據，提供基本說明
    if not fallback_paths:
        fallback_paths = [
            "圖形檢索未發現明顯的威脅關聯模式",
            "當前警報為獨立事件，無顯著的圖形化關聯",
            "建議基於規則等級和內容進行單一事件分析"
        ]
    
    return fallback_paths

def format_graph_context(context_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Graph-Native 上下文格式化：將圖形檢索結果格式化為 LLM 可理解的結構化文本
    
    Args:
        context_data: 從 execute_graph_retrieval 獲得的圖形上下文資料
        
    Returns:
        格式化的上下文字典，準備提供給 LLM 分析
    """
    formatted_context = {}
    
    # 添加Cypher路徑記號格式
    formatted_context['graph_context'] = format_graph_context_cypher_notation(context_data)
    
    # 1. 攻擊路徑分析
    attack_paths = context_data.get('attack_paths', [])
    if attack_paths:
        path_parts = []
        for i, path_data in enumerate(attack_paths[:5], 1):
            # 解析圖形路徑資料
            attacker = path_data.get('attacker', {})
            related_alerts = path_data.get('related_alert', [])
            entities = path_data.get('entity', [])
            
            path_part = f"""
{i}. **攻擊來源:** {attacker.get('address', 'Unknown IP')}
   **相關警報數量:** {len(related_alerts) if isinstance(related_alerts, list) else 1}
   **影響實體:** {len(entities) if isinstance(entities, list) else 1} 個系統組件
   **攻擊時間範圍:** 過去1小時內的持續活動"""
            path_parts.append(path_part)
        formatted_context['attack_path_analysis'] = "\n".join(path_parts)
    else:
        formatted_context['attack_path_analysis'] = "未發現明確的攻擊路徑模式。"
    
    # 2. 橫向移動檢測
    lateral_movement = context_data.get('lateral_movement', [])
    if lateral_movement:
        movement_parts = []
        for i, movement_data in enumerate(lateral_movement[:3], 1):
            attacker = movement_data.get('attacker', {})
            target_hosts = movement_data.get('target_hosts', [])
            
            movement_part = f"""
{i}. **橫向移動來源:** {attacker.get('address', 'Unknown')}
   **目標主機數量:** {len(target_hosts)} 台主機
   **移動模式:** 多主機滲透檢測到"""
            movement_parts.append(movement_part)
        formatted_context['lateral_movement_analysis'] = "\n".join(movement_parts)
    else:
        formatted_context['lateral_movement_analysis'] = "未檢測到橫向移動活動。"
    
    # 3. 時間序列關聯
    temporal_sequences = context_data.get('temporal_sequences', [])
    if temporal_sequences:
        temporal_parts = []
        for seq_data in temporal_sequences[:3]:
            sequence = seq_data.get('temporal_sequence', [])
            if sequence:
                temporal_part = f"**時間序列相關警報:** {len(sequence)} 個相關事件在±30分鐘時間窗口內"
                temporal_parts.append(temporal_part)
        formatted_context['temporal_correlation'] = "\n".join(temporal_parts)
    else:
        formatted_context['temporal_correlation'] = "未發現時間序列相關事件。"
    
    # 4. IP 信譽分析
    ip_reputation = context_data.get('ip_reputation', [])
    if ip_reputation:
        ip_parts = []
        for ip_data in ip_reputation[:3]:
            ip = ip_data.get('ip', {})
            ip_history = ip_data.get('ip_history', [])
            geo = ip_data.get('geo', {})
            
            ip_part = f"""
**IP 地址:** {ip.get('address', 'Unknown')}
**歷史活動:** 過去30天內 {len(ip_history)} 次警報記錄
**地理位置:** {geo.get('country', 'Unknown')} - {geo.get('city', 'Unknown')}
**私有地址:** {'否' if not ip.get('is_private', True) else '是'}"""
            ip_parts.append(ip_part)
        formatted_context['ip_reputation_analysis'] = "\n".join(ip_parts)
    else:
        formatted_context['ip_reputation_analysis'] = "無外部IP信譽資料可供分析。"
    
    # 5. 使用者行為分析
    user_behavior = context_data.get('user_behavior', [])
    if user_behavior:
        user_parts = []
        for user_data in user_behavior[:3]:
            user = user_data.get('user', {})
            user_history = user_data.get('user_history', [])
            recent_activity = user_data.get('recent_activity', [])
            
            user_part = f"""
**使用者:** {user.get('username', 'Unknown')}
**歷史行為:** 過去7天內 {len(user_history)} 次活動記錄
**近期異常:** 過去2小時內 {len(recent_activity)} 次活動"""
            user_parts.append(user_part)
        formatted_context['user_behavior_analysis'] = "\n".join(user_parts)
    else:
        formatted_context['user_behavior_analysis'] = "未發現相關使用者行為異常。"
    
    # 6. 程序執行鏈分析
    process_chains = context_data.get('process_chains', [])
    if process_chains:
        process_parts = []
        for process_data in process_chains[:3]:
            timeline = process_data.get('timeline', [])
            if timeline:
                process_part = f"**程序執行鏈:** 檢測到 {len(timeline)} 個相關程序執行事件"
                process_parts.append(process_part)
        formatted_context['process_chain_analysis'] = "\n".join(process_parts)
    else:
        formatted_context['process_chain_analysis'] = "未發現可疑的程序執行鏈。"
    
    # 7. 檔案交互分析
    file_interactions = context_data.get('file_interactions', [])
    if file_interactions:
        file_parts = []
        for file_data in file_interactions[:3]:
            files = file_data.get('files', {})
            interacting_processes = file_data.get('interacting_processes', [])
            
            file_part = f"""
**檔案路徑:** {files.get('file_path', 'Unknown')}
**交互程序數量:** {len(interacting_processes)}"""
            file_parts.append(file_part)
        formatted_context['file_interaction_analysis'] = "\n".join(file_parts)
    else:
        formatted_context['file_interaction_analysis'] = "未發現異常的檔案系統交互。"
    
    # 8. 網路拓撲分析
    network_topology = context_data.get('network_topology', [])
    if network_topology:
        network_parts = []
        for net_data in network_topology[:3]:
            attacker = net_data.get('attacker', {})
            target = net_data.get('target', {})
            attack_sequence = net_data.get('attack_sequence', [])
            
            network_part = f"""
**攻擊來源:** {attacker.get('address', 'Unknown')}
**目標主機:** {target.get('agent_name', 'Unknown')}
**攻擊序列:** 過去6小時內 {len(attack_sequence)} 次相關攻擊"""
            network_parts.append(network_part)
        formatted_context['network_topology_analysis'] = "\n".join(network_parts)
    else:
        formatted_context['network_topology_analysis'] = "未發現複雜的網路攻擊拓撲。"
    
    # 9. 威脅全景分析
    threat_landscape = context_data.get('threat_landscape', [])
    if threat_landscape:
        threat_parts = []
        threat_count = len(threat_landscape)
        if threat_count > 0:
            threat_part = f"**綜合威脅評估:** 檢測到 {threat_count} 個高級別威脅關聯事件（過去24小時）"
            threat_parts.append(threat_part)
        formatted_context['threat_landscape_analysis'] = "\n".join(threat_parts)
    else:
        formatted_context['threat_landscape_analysis'] = "整體威脅環境相對穩定。"
    
    # 10. 傳統檢索補充（混合模式）
    traditional_alerts = context_data.get('traditional_similar_alerts', [])
    traditional_metrics = context_data.get('traditional_metrics', [])
    traditional_logs = context_data.get('traditional_logs', [])
    
    if traditional_alerts or traditional_metrics or traditional_logs:
        supplement_parts = []
        if traditional_alerts:
            supplement_parts.append(f"**相似警報補充:** {len(traditional_alerts)} 個向量相似警報")
        if traditional_metrics:
            supplement_parts.append(f"**系統指標補充:** {len(traditional_metrics)} 個系統性能記錄")
        if traditional_logs:
            supplement_parts.append(f"**日誌補充:** {len(traditional_logs)} 個網路/SSH日誌")
        formatted_context['traditional_supplement'] = "\n".join(supplement_parts)
    else:
        formatted_context['traditional_supplement'] = "無需傳統檢索補充。"
    
    return formatted_context

# ==================== 混合格式化函數 ====================

def format_hybrid_context(context_data: Dict[str, Any]) -> Dict[str, str]:
    """
    混合上下文格式化：自動檢測並格式化圖形或傳統檢索結果
    
    Args:
        context_data: 檢索結果資料
        
    Returns:
        格式化的上下文字典
    """
    # 檢測是否為圖形檢索結果
    graph_indicators = ['attack_paths', 'lateral_movement', 'temporal_sequences', 
                       'ip_reputation', 'user_behavior', 'process_chains']
    
    has_graph_data = any(context_data.get(indicator) for indicator in graph_indicators)
    
    if has_graph_data:
        logger.info("🔗 Formatting graph-native context for LLM analysis")
        return format_graph_context(context_data)
    else:
        logger.info("📊 Formatting traditional context for LLM analysis")
        return format_multi_source_context(context_data)

# ==================== GraphRAG Context 格式化示例與測試 ====================

def create_example_graph_context() -> str:
    """
    創建一個示例圖形上下文，展示Cypher路徑記號格式
    這個函數展示了GraphRAG prompt template的預期輸入格式
    
    Returns:
        格式化的Cypher路徑記號字符串
    """
    example_cypher_paths = [
        "(IP:192.168.1.100) -[FAILED_LOGIN: 50次]-> (Host:web-01)",
        "(IP:192.168.1.100) -[FAILED_LOGIN: 25次]-> (Host:db-01)", 
        "(IP:192.168.1.100) -[SUCCESSFUL_LOGIN]-> (Host:dev-server)",
        "(Host:dev-server) -[EXECUTED]-> (Process:mimikatz.exe)",
        "(Process:mimikatz.exe) -[ACCESSED]-> (File:sam.db)",
        "(User:admin) -[PRIVILEGE_ESCALATION]-> (Role:SYSTEM)",
        "(Alert:ssh_brute_01) -[TEMPORAL_SEQUENCE: 3 events in 30min]-> (Alert:privilege_esc_02)",
        "(IP:192.168.1.100) -[REPUTATION: 15 alerts in 30 days]-> (ThreatProfile:HighRisk)",
        "(File:malware.exe) -[ACCESSED_BY: 5 processes]-> (SecurityEvent:Suspicious)",
        "(User:alice) -[RECENT_ACTIVITY: 8 events]-> (BehaviorPattern:Anomalous)"
    ]
    
    return "\n".join(example_cypher_paths)

def demonstrate_enhanced_prompt_usage():
    """
    演示增強的GraphRAG prompt template使用方法
    展示完整的圖形上下文如何被注入到prompt中
    """
    
    # 創建示例上下文數據
    example_context = {
        'graph_context': create_example_graph_context(),
        'lateral_movement_analysis': """
        **橫向移動檢測:** 檢測到攻擊者從單一IP滲透多個主機
        - web-01: 初始入侵點，50次失敗登錄
        - db-01: 次要目標，25次失敗登錄  
        - dev-server: 成功滲透，權限提升檢測
        """,
        'temporal_correlation': """
        **時間序列:** 3個關聯事件在30分鐘內發生
        - 18:30 SSH暴力破解開始
        - 18:45 成功登錄dev-server
        - 18:55 權限提升和惡意程序執行
        """,
        'ip_reputation_analysis': """
        **IP信譽:** 192.168.1.100 被標記為高風險
        - 過去30天內觸發15次安全警報
        - 多主機攻擊模式
        """,
        'user_behavior_analysis': """
        **使用者行為:** admin和alice賬戶異常活動
        - admin: 權限提升至SYSTEM等級
        - alice: 2小時內8次異常行為
        """,
        'process_chain_analysis': """
        **程序執行鏈:** 惡意程序執行檢測
        - mimikatz.exe: 憑證竊取工具
        - 存取sam.db: 密碼哈希提取
        """,
        'file_interaction_analysis': """
        **檔案交互:** 系統關鍵檔案被存取
        - sam.db: 密碼資料庫
        - malware.exe: 5個程序存取此可疑檔案
        """,
        'network_topology_analysis': """
        **網路拓撲:** 內網橫向移動模式
        - 單一外部IP攻擊多個內部主機
        - 成功建立內網立足點
        """,
        'threat_landscape_analysis': """
        **威脅全景:** 典型APT攻擊模式
        - 階段1: 偵察和暴力破解
        - 階段2: 權限提升
        - 階段3: 橫向移動
        """,
        'traditional_supplement': """
        **傳統檢索補充:** 5個向量相似警報提供額外上下文
        """
    }
    
    # 創建示例警報摘要
    alert_summary = "SSH Brute Force Attack Detected on dev-server (Level: 7)"
    
    # 展示如何使用enhanced_graphrag_prompt_template
    logger.info("🔗 DEMONSTRATION: Enhanced GraphRAG Prompt Template Usage")
    logger.info("Graph Context Format:")
    logger.info(example_context['graph_context'])
    
    # 這展示了LLM將接收到的完整上下文結構
    full_prompt_context = {
        'alert_summary': alert_summary,
        **example_context
    }
    
    logger.info("✅ Enhanced GraphRAG prompt ready with comprehensive graph context")
    return full_prompt_context

def validate_graph_context_format(graph_context: str) -> bool:
    """
    驗證圖形上下文格式是否符合Cypher路徑記號標準
    
    Args:
        graph_context: 待驗證的圖形上下文字符串
        
    Returns:
        格式是否有效
    """
    lines = graph_context.strip().split('\n')
    valid_lines = 0
    
    for line in lines:
        # 檢查基本的Cypher路徑格式: (Node) -[Relationship]-> (Node)
        if '(' in line and ')' in line and '-[' in line and ']-> (' in line:
            valid_lines += 1
        # 或者是說明性文字
        elif any(keyword in line for keyword in ['未發現', '建議', '獨立事件']):
            valid_lines += 1
    
    validity_ratio = valid_lines / len(lines) if lines else 0
    is_valid = validity_ratio >= 0.8  # 至少80%的行應該是有效格式
    
    logger.info(f"📊 Graph context validation: {valid_lines}/{len(lines)} valid lines ({validity_ratio:.1%})")
    
    return is_valid

# ==================== Stage 4 Step 4 完成確認 ====================

def stage4_step4_completion_summary():
    """
    Stage 4 Step 4 完成總結：增強提示詞模板以容納圖形上下文
    """
    logger.info("🎉 === STAGE 4 STEP 4 COMPLETION SUMMARY ===")
    logger.info("✅ Enhanced prompt template with graph context capability")
    logger.info("✅ Implemented Cypher path notation formatting")
    logger.info("✅ Created fallback formatting for traditional retrieval")
    logger.info("✅ Added validation and demonstration functions")
    logger.info("✅ Integrated graph context into LLM analysis pipeline")
    
    completion_details = {
        "stage": "Stage 4 - GraphRAG Implementation",
        "step": "Step 4 - Enhanced Prompt Template",
        "features_implemented": [
            "enhanced_graphrag_prompt_template: 增強的GraphRAG提示詞模板",
            "format_graph_context_cypher_notation: Cypher路徑記號格式化",
            "_generate_fallback_cypher_paths: 傳統檢索降級格式化",
            "create_example_graph_context: 示例圖形上下文生成",
            "validate_graph_context_format: 格式驗證功能",
            "demonstrate_enhanced_prompt_usage: 使用示例演示"
        ],
        "graph_context_format": "Simplified Cypher Path Notation",
        "example_format": "(IP:192.168.1.100) -[FAILED_LOGIN: 50次]-> (Host:web-01)",
        "integration_points": [
            "get_analysis_chain: 選擇增強的GraphRAG分析鏈",
            "format_graph_context: 整合Cypher路徑格式化",
            "process_single_alert: 圖形上下文注入分析流程"
        ],
        "benefits_achieved": [
            "深度上下文：從相似事件列表變為攻擊路徑圖",
            "高效檢索：利用Neo4j圖形遍歷能力",
            "擺脫版本依賴：現代化資料庫架構", 
            "更強Agentic能力：貼近人類分析師思維模式"
        ]
    }
    
    logger.info("📊 Implementation Details:")
    for feature in completion_details["features_implemented"]:
        logger.info(f"   • {feature}")
    
    logger.info("🔗 Graph Context Format Demonstrated:")
    logger.info(f"   • {completion_details['example_format']}")
    
    logger.info("🎯 Next Steps:")
    logger.info("   • Test enhanced prompt with real alert data")
    logger.info("   • Fine-tune Cypher path formatting based on LLM feedback")
    logger.info("   • Monitor GraphRAG analysis quality improvements")
    
    return completion_details

# 在應用啟動時執行示例演示
if __name__ == "__main__":
    # 演示新的GraphRAG功能
    stage4_step4_completion_summary()
    demonstrate_enhanced_prompt_usage()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)