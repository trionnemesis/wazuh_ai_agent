import os
import logging
import traceback
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# OpenSearch client
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# Import our embedding service
from embedding_service import GeminiEmbeddingService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment configuration
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialize OpenSearch client
client = AsyncOpenSearch(
    hosts=[OPENSEARCH_URL],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=AsyncHttpConnection
)

def get_llm():
    """Initialize LLM based on environment configuration"""
    logger.info(f"Initializing LLM provider: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == 'gemini':
        if not GEMINI_API_KEY:
            raise ValueError("LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set.")
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY)
    
    elif LLM_PROVIDER == 'anthropic':
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set.")
        return ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=ANTHROPIC_API_KEY)
    
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. Please choose 'gemini' or 'anthropic'.")

# Initialize LangChain components
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

**New Wazuh Alert to Analyze:**
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

# Initialize embedding service
embedding_service = GeminiEmbeddingService()

# === Stage 3: Agentic Context Correlation Implementation ===

def determine_contextual_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Stage 3: Decision engine that determines what contextual information is needed
    based on the alert type and content.
    
    Args:
        alert: The new alert document from OpenSearch
        
    Returns:
        List of query specifications for different types of contextual data
    """
    queries = []
    alert_source = alert.get('_source', {})
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    timestamp = alert_source.get('timestamp')
    
    rule_description = rule.get('description', '').lower()
    rule_groups = rule.get('groups', [])
    host_name = agent.get('name', '')
    
    logger.info(f"Determining contextual queries for alert: {rule_description}")
    
    # Default: Always perform k-NN search for similar historical alerts
    queries.append({
        'type': 'vector_similarity',
        'description': 'Similar historical alerts',
        'parameters': {
            'k': 5,
            'include_ai_analysis': True
        }
    })
    
    # Resource monitoring correlation rules
    resource_keywords = ['high cpu usage', 'excessive ram consumption', 'memory usage', 
                         'disk space', 'cpu utilization', 'system overload', 'performance']
    
    if any(keyword in rule_description for keyword in resource_keywords):
        logger.info("Resource-related alert detected - adding process list query")
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Process information from same host',
            'parameters': {
                'keywords': ['process list', 'top processes', 'running processes'],
                'host': host_name,
                'time_window_minutes': 5,
                'timestamp': timestamp
            }
        })
    
    # Security event correlation rules
    security_keywords = ['ssh brute-force', 'web attack', 'authentication failed', 
                         'login attempt', 'intrusion', 'malware', 'suspicious activity']
    
    if any(keyword in rule_description for keyword in security_keywords):
        logger.info("Security event detected - adding system metrics correlation")
        
        # Add CPU metrics query
        queries.append({
            'type': 'keyword_time_range',
            'description': 'CPU metrics from same host',
            'parameters': {
                'keywords': ['cpu usage', 'cpu utilization', 'processor'],
                'host': host_name,
                'time_window_minutes': 1,
                'timestamp': timestamp
            }
        })
        
        # Add network I/O metrics query
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Network I/O metrics from same host',
            'parameters': {
                'keywords': ['network traffic', 'network io', 'bandwidth', 'packets'],
                'host': host_name,
                'time_window_minutes': 1,
                'timestamp': timestamp
            }
        })
    
    # SSH-specific correlation
    if 'ssh' in rule_description:
        logger.info("SSH-related alert detected - adding SSH-specific metrics")
        queries.append({
            'type': 'keyword_time_range',
            'description': 'SSH connection logs',
            'parameters': {
                'keywords': ['ssh connection', 'port 22', 'sshd'],
                'host': host_name,
                'time_window_minutes': 2,
                'timestamp': timestamp
            }
        })
    
    # Web-related correlation
    if any(web_term in rule_description for web_term in ['web', 'http', 'apache', 'nginx']):
        logger.info("Web-related alert detected - adding web server metrics")
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Web server metrics',
            'parameters': {
                'keywords': ['apache', 'nginx', 'web server', 'http requests'],
                'host': host_name,
                'time_window_minutes': 2,
                'timestamp': timestamp
            }
        })
    
    logger.info(f"Generated {len(queries)} contextual queries for correlation analysis")
    return queries

async def execute_retrieval(queries: List[Dict[str, Any]], alert_vector: List[float]) -> Dict[str, Any]:
    """
    Stage 3: Generic retrieval function that executes multiple types of queries
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
        'web_metrics': []
    }
    
    logger.info(f"Executing {len(queries)} retrieval queries")
    
    for query in queries:
        query_type = query['type']
        description = query['description']
        parameters = query['parameters']
        
        try:
            logger.info(f"Executing query: {description}")
            
            if query_type == 'vector_similarity':
                # K-NN vector search for similar alerts
                results = await execute_vector_search(alert_vector, parameters)
                context_data['similar_alerts'].extend(results)
                
            elif query_type == 'keyword_time_range':
                # Keyword and time-based search
                results = await execute_keyword_time_search(parameters)
                
                # Categorize results based on description
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
                    
        except Exception as e:
            logger.error(f"Error executing query '{description}': {str(e)}")
            continue
    
    # Log retrieval summary
    total_results = sum(len(results) for results in context_data.values())
    logger.info(f"Retrieval completed - Total results: {total_results}")
    for category, results in context_data.items():
        if results:
            logger.info(f"  {category}: {len(results)} items")
    
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
                                "alert_vector": { # FIX: Changed from 'alert_embedding' to 'alert_vector' to match template
                                    "vector": alert_vector,
                                    "k": k
                                }
                            }
                        }
                    ]
                }
            },
            "_source": ["rule", "agent", "ai_analysis", "timestamp"]
        }
        
        # Add filter for alerts with AI analysis if requested
        if include_ai_analysis:
            # Ensure filter list exists before appending
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
        logger.debug(f"Vector search returned {len(similar_alerts)} similar alerts")
        return similar_alerts
        
    except Exception as e:
        logger.error(f"Vector search failed: {str(e)}")
        return []

async def execute_keyword_time_search(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Execute keyword and time-range search for system metrics and logs.
    
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
        
        # Build keyword and time-range query
        search_body = {
            "size": 10,
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": " ".join(keywords),
                                "fields": ["rule.description", "data.*", "full_log"],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
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
                    ]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}]
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
        logger.debug(f"Keyword/time search returned {len(results)} results for keywords: {keywords}")
        return results
        
    except Exception as e:
        logger.error(f"Keyword/time search failed: {str(e)}")
        return []

def format_multi_source_context(context_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Stage 3: Format the multi-source context data for LLM consumption.
    
    Args:
        context_data: Aggregated context from execute_retrieval
        
    Returns:
        Dictionary with formatted context strings for each category
    """
    formatted_context = {}
    
    # Format similar alerts
    similar_alerts = context_data.get('similar_alerts', [])
    if similar_alerts:
        context_parts = []
        for i, alert in enumerate(similar_alerts, 1):
            source = alert.get('_source', {})
            rule = source.get('rule', {})
            agent = source.get('agent', {})
            ai_analysis = source.get('ai_analysis', {})
            
            context_part = f"""
{i}. **Timestamp:** {source.get('timestamp', 'Unknown')}
   **Host:** {agent.get('name', 'Unknown')}
   **Rule:** {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')})
   **Previous Analysis:** {ai_analysis.get('triage_report', 'N/A')[:150]}...
   **Similarity Score:** {alert.get('_score', 'N/A')}"""
            context_parts.append(context_part)
        formatted_context['similar_alerts_context'] = "\n".join(context_parts)
    else:
        formatted_context['similar_alerts_context'] = "No similar historical alerts found."
    
    # Format system metrics
    cpu_metrics = context_data.get('cpu_metrics', [])
    if cpu_metrics:
        cpu_parts = []
        for metric in cpu_metrics:
            source = metric.get('_source', {})
            rule = source.get('rule', {})
            cpu_parts.append(f"- {source.get('timestamp', 'Unknown')}: {rule.get('description', 'CPU metric')}")
        formatted_context['system_metrics_context'] = "\n".join(cpu_parts)
    else:
        formatted_context['system_metrics_context'] = "No correlated system metrics found."
    
    # Format process data
    process_data = context_data.get('process_data', [])
    if process_data:
        process_parts = []
        for proc in process_data:
            source = proc.get('_source', {})
            rule = source.get('rule', {})
            process_parts.append(f"- {source.get('timestamp', 'Unknown')}: {rule.get('description', 'Process info')}")
        formatted_context['process_context'] = "\n".join(process_parts)
    else:
        formatted_context['process_context'] = "No process information found."
    
    # Format network data
    network_logs = context_data.get('network_logs', [])
    if network_logs:
        network_parts = []
        for net in network_logs:
            source = net.get('_source', {})
            rule = source.get('rule', {})
            network_parts.append(f"- {source.get('timestamp', 'Unknown')}: {rule.get('description', 'Network activity')}")
        formatted_context['network_context'] = "\n".join(network_parts)
    else:
        formatted_context['network_context'] = "No correlated network data found."
    
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
        logger.info(f"Vectorizing alert {alert_id}")
        # FIX: Changed from embed_query to embed_alert_content for better context
        alert_vector = await embedding_service.embed_alert_content(alert_source)
        
        # Step 3: Decide - Determine contextual queries needed
        logger.info(f"Determining contextual queries for alert {alert_id}")
        contextual_queries = determine_contextual_queries(alert)
        
        # Step 4: Retrieve - Execute all contextual queries
        logger.info(f"Executing {len(contextual_queries)} contextual queries for alert {alert_id}")
        context_data = await execute_retrieval(contextual_queries, alert_vector)
        
        # Step 5: Format - Prepare multi-source context for LLM
        logger.info(f"Formatting multi-source context for alert {alert_id}")
        formatted_context = format_multi_source_context(context_data)
        
        # Step 6: Analyze - Send comprehensive context to LLM
        logger.info(f"Generating comprehensive AI analysis for alert {alert_id}")
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary,
            **formatted_context
        })
        
        logger.info(f"AI Analysis generated for {alert_id}: {analysis_result[:100]}...")
        
        # Step 7: Update - Store results in OpenSearch
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis_result,
                    "provider": LLM_PROVIDER,
                    "timestamp": alert_source.get('timestamp'),
                    "context_sources": len(contextual_queries),
                    "similar_alerts_count": len(context_data.get('similar_alerts', [])),
                    "cpu_metrics_count": len(context_data.get('cpu_metrics', [])),
                    "network_logs_count": len(context_data.get('network_logs', [])),
                    "process_data_count": len(context_data.get('process_data', []))
                },
                "alert_vector": alert_vector # FIX: Changed from 'alert_embedding' to 'alert_vector'
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logger.info(f"Successfully updated alert {alert_id} with agentic context correlation analysis")
        
    except Exception as e:
        logger.error(f"Error processing alert {alert_id}: {str(e)}")
        raise

async def triage_new_alerts():
    """Main alert triage task with Stage 3 agentic context correlation"""
    print("--- STAGE 3 AGENTIC CONTEXT CORRELATION TRIAGE JOB EXECUTING ---")
    logger.info(f"Analyzing alerts with {LLM_PROVIDER} model and agentic context correlation...")
    
    try:
        # Query new alerts
        alerts = await query_new_alerts(limit=10)
        
        if not alerts:
            print("--- No new alerts found. ---")
            logger.info("No new alerts found.")
            return
            
        logger.info(f"Found {len(alerts)} new alerts to process with agentic context correlation")
        
        # Process each alert with enhanced agentic workflow
        for alert in alerts:
            try:
                await process_single_alert(alert)
                print(f"--- Successfully processed alert {alert['_id']} ---")
            except Exception as e:
                print(f"--- Error processing alert {alert['_id']}: {str(e)} ---")
                logger.error(f"Failed to process alert {alert['_id']}: {str(e)}")
                continue
            
    except Exception as e:
        print(f"!!!!!! A CRITICAL ERROR OCCURRED IN AGENTIC TRIAGE JOB !!!!!!")
        logger.error(f"An error occurred during agentic triage: {e}", exc_info=True)
        traceback.print_exc()

# === FastAPI Application and Scheduler ===

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

@app.on_event("shutdown")
def shutdown_event():
    """Application shutdown event handler"""
    scheduler.shutdown()
    logger.info("Scheduler shut down.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)