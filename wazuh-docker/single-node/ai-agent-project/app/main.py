import os
import logging
import traceback
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# LangChain 相關套件引入
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# OpenSearch 客戶端
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# 引入自定義的嵌入服務模組
from embedding_service import GeminiEmbeddingService

# 配置日誌系統
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 環境變數配置
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

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

# Stage 3: Enhanced prompt template for multi-source context correlation
prompt_template = ChatPromptTemplate.from_template(
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

output_parser = StrOutputParser()
chain = prompt_template | llm | output_parser

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
        
        # Step 3: Decide - Determine contextual queries needed
        logger.info(f"🧠 STEP 3: AGENTIC DECISION - Determining contextual needs for alert {alert_id}")
        contextual_queries = determine_contextual_queries(alert)
        
        # Step 4: Retrieve - Execute all contextual queries
        logger.info(f"📡 STEP 4: CONTEXTUAL RETRIEVAL - Executing {len(contextual_queries)} queries for alert {alert_id}")
        context_data = await execute_retrieval(contextual_queries, alert_vector)
        
        # Step 5: Format - Prepare multi-source context for LLM
        logger.info(f"📋 STEP 5: CONTEXT FORMATTING - Preparing multi-source context for alert {alert_id}")
        formatted_context = format_multi_source_context(context_data)
        
        # Log context summary for verification
        total_context_items = sum(len(ctx.split('\n')) for ctx in formatted_context.values() if ctx and "No " not in ctx)
        logger.info(f"   📊 Context summary: {total_context_items} total contextual items prepared")
        
        # Step 6: Analyze - Send comprehensive context to LLM
        logger.info(f"🤖 STEP 6: LLM ANALYSIS - Generating comprehensive AI analysis for alert {alert_id}")
        analysis_result = await chain.ainvoke({
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
        logger.info(f"💾 STEP 7: STORING RESULTS - Updating alert {alert_id} with agentic analysis")
        
        # Enhanced metadata for Stage 3
        context_metadata = {
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
                    "context_sources": len(contextual_queries),
                    "extracted_risk_level": risk_level,
                    "stage": "Stage 3 - Agentic Context Correlation",
                    **context_metadata
                },
                "alert_vector": alert_vector
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        
        logger.info(f"🎉 AGENTIC PROCESSING COMPLETE: Alert {alert_id} successfully updated")
        logger.info(f"   📈 Context correlation metadata stored for future analysis")
        
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

@app.on_event("shutdown")
def shutdown_event():
    """應用程式關閉事件處理器"""
    scheduler.shutdown()
    logger.info("排程器已關閉")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)