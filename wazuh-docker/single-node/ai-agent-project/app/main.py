import os
import logging
import traceback
import asyncio
from typing import List, Dict, Any
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


# 2. 提示模板 (Stage 2: 更新為支援歷史上下文的 RAG 提示)
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst. Analyze the new Wazuh alert below, using the provided historical context from similar past alerts to inform your assessment.


    **Relevant Historical Alerts:**
    {historical_context}


    **New Wazuh Alert to Analyze:**
    {alert_summary}

    **Your Analysis Task:**
    1. Briefly summarize the new event.
    2. Assess its risk level (Critical, High, Medium, Low, Informational), considering any patterns from the historical context.
    3. Provide a clear, context-aware recommendation that references relevant patterns from similar past alerts.


    **Your Triage Report:**
    """
)

output_parser = StrOutputParser()
chain = prompt_template | llm | output_parser

# Initialize embedding service
embedding_service = GeminiEmbeddingService()


# === Stage 2: Core RAG Implementation Functions ===

async def find_similar_alerts(query_vector: List[float], k: int = 5) -> List[Dict[Any, Any]]:
    """
    Stage 2: 實現檢索模組 - 使用 k-NN 搜尋找到相似的歷史警報
    
    Args:
        query_vector: 新警報的向量表示
        k: 要檢索的相似警報數量
        
    Returns:
        List[Dict]: 最相似的k個歷史警報文檔
    """
    try:
        # 構建 OpenSearch k-NN 搜尋查詢，使用餘弦相似度
        knn_search_body = {
            "size": k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "alert_embedding": {  # 針對 alert_embedding 欄位進行搜尋
                                    "vector": query_vector,
                                    "k": k
                                }
                            }
                        }
                    ],
                    "filter": [
                        {
                            "exists": {
                                "field": "ai_analysis"  # 只檢索已經分析過的歷史警報
                            }
                        }
                    ]
                }
            }
        }
        
        logging.info(f"Executing k-NN search for {k} similar alerts")
        logging.debug(f"k-NN query: {knn_search_body}")
        
        # 執行搜尋
        response = await client.search(
            index="wazuh-alerts-*",
            body=knn_search_body
        )
        
        similar_alerts = response.get('hits', {}).get('hits', [])
        logging.info(f"Found {len(similar_alerts)} similar historical alerts")
        
        return similar_alerts
        
    except Exception as e:
        logging.error(f"Error in find_similar_alerts: {str(e)}")
        return []

def format_historical_context(alerts: List[Dict[Any, Any]]) -> str:
    """
    Stage 2: 格式化歷史上下文函式 - 將檢索到的警報格式化為可讀字串
    
    Args:
        alerts: find_similar_alerts 返回的警報文檔列表
        
    Returns:
        str: 格式化的歷史上下文字串
    """
    if not alerts:
        return "No relevant historical alerts found."
    
    context_parts = []
    for i, alert in enumerate(alerts, 1):
        source = alert.get('_source', {})
        rule = source.get('rule', {})
        agent = source.get('agent', {})
        timestamp = source.get('timestamp', 'Unknown time')
        
        # 提取 AI 分析結果
        ai_analysis = source.get('ai_analysis', {})
        previous_analysis = ai_analysis.get('triage_report', 'No previous analysis available')
        
        # 格式化每個歷史警報
        context_part = f"""
{i}. **Timestamp:** {timestamp}
   **Host:** {agent.get('name', 'Unknown')}
   **Rule:** {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')})
   **Previous Analysis:** {previous_analysis[:200]}{'...' if len(previous_analysis) > 200 else ''}
   **Similarity Score:** {alert.get('_score', 'N/A')}
"""
        context_parts.append(context_part)
    
    return "\n".join(context_parts)

async def process_single_alert(alert: Dict[Any, Any]) -> None:
    """
    Stage 2: 修改後的單一警報處理流程 - 整合 RAG 功能
    
    處理順序:
    1. 獲取新警報
    2. 向量化新警報
    3. 檢索相似歷史警報
    4. 格式化歷史上下文
    5. 調用 LLM 分析
    6. 更新結果到 OpenSearch
    """
    alert_id = alert['_id']
    alert_index = alert['_index']
    alert_source = alert['_source']
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    
    # 步驟 1: 準備警報摘要
    alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
    logging.info(f"Processing alert {alert_id}: {alert_summary}")

    try:
        # 步驟 2: 向量化新警報
        logging.info(f"Vectorizing alert {alert_id}")
        alert_vector = await embedding_service.embed_query(alert_summary)
        
        # 步驟 3: 檢索相似歷史警報
        logging.info(f"Retrieving similar alerts for {alert_id}")
        similar_alerts = await find_similar_alerts(alert_vector, k=5)
        
        # 步驟 4: 格式化歷史上下文
        historical_context = format_historical_context(similar_alerts)
        
        # 步驟 5: 調用 LLM 分析 (包含歷史上下文)
        logging.info(f"Generating AI analysis for {alert_id} with historical context")
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary,
            "historical_context": historical_context
        })
        
        logging.info(f"AI Analysis generated for {alert_id}: {analysis_result[:100]}...")
        
        # 步驟 6: 更新 OpenSearch 文檔
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis_result,
                    "provider": LLM_PROVIDER,
                    "timestamp": alert_source.get('timestamp'),
                    "similar_alerts_count": len(similar_alerts)
                },
                "alert_embedding": alert_vector  # 儲存向量以供未來檢索
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logging.info(f"Successfully updated alert {alert_id} with RAG-enhanced analysis")
        
    except Exception as e:
        logging.error(f"Error processing alert {alert_id}: {str(e)}")
        raise

# Stage 2: 修改主要 triage 函式以使用新的 RAG 流程
async def triage_new_alerts():
    """主要的警報分析任務 - 使用 Stage 2 RAG 功能"""
    print("--- TRIAGE JOB EXECUTING WITH RAG FUNCTIONALITY ---")
    logging.info(f"Analyzing alerts with {LLM_PROVIDER} model and RAG retrieval...")
    

    try:
        # 查找未分析的警報
        response = await client.search(
            index="wazuh-alerts-*",
            body={
                "query": {
                    "bool": {
                        "must_not": [{"exists": {"field": "ai_analysis"}}]
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}]
            },
            size=limit
        )
        
        alerts = response['hits']['hits']
        logger.info(f"Found {len(alerts)} new alerts to process")
        return alerts
        if not alerts:
            print("--- No new alerts found. ---")
            logging.info("No new alerts found.")
            return
            
        logging.info(f"Found {len(alerts)} new alerts to process with RAG")
        
        # 使用新的 process_single_alert 函式處理每個警報
        for alert in alerts:
            await process_single_alert(alert)
            
    except Exception as e:
        print(f"!!!!!! A CRITICAL ERROR OCCURRED IN RAG TRIAGE JOB !!!!!!")
        logging.error(f"An error occurred during RAG triage: {e}", exc_info=True)
        traceback.print_exc()

# --- FastAPI 應用與排程 (維持不變) ---
app = FastAPI(title="Wazuh AI Triage Agent - Stage 2 RAG")

    except Exception as e:
        logger.error(f"Failed to query new alerts: {str(e)}")
        raise

async def vectorize_alert(alert_data: Dict[str, Any]) -> List[float]:
    """
    Converts alert content to a vector using the embedding service.
    
    Args:
        alert_data: Alert document from OpenSearch
        
    Returns:
        Vector representation of the alert content
    """
    try:
        alert_source = alert_data['_source']
        alert_vector = await embedding_service.embed_alert_content(alert_source)
        
        logger.debug(f"Alert {alert_data['_id']} vectorized successfully, dimensions: {len(alert_vector)}")
        return alert_vector
        
    except Exception as e:
        logger.error(f"Failed to vectorize alert {alert_data['_id']}: {str(e)}")
        raise

async def find_similar_alerts(alert_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
    """
    Find similar historical alerts using vector search.
    
    Args:
        alert_vector: Vector representation of the current alert
        k: Number of similar alerts to retrieve
        
    Returns:
        List of similar alert documents
    """
    try:
        vector_search_body = {
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
                        },
                        {
                            "exists": {"field": "ai_analysis"}
                        }
                    ]
                }
            },
            "_source": ["rule", "agent", "ai_analysis", "timestamp"]
        }
        
        similar_alerts_response = await client.search(
            index="wazuh-alerts-*",
            body=vector_search_body,
            size=k
        )
        
        similar_alerts = similar_alerts_response['hits']['hits']
        logger.debug(f"Found {len(similar_alerts)} similar historical alerts")
        return similar_alerts
        
    except Exception as e:
        logger.warning(f"Vector search failed: {str(e)}")
        return []

async def build_context(similar_alerts: List[Dict[str, Any]]) -> str:
    """
    Build analysis context from similar alerts.
    
    Args:
        similar_alerts: List of similar alert documents
        
    Returns:
        Formatted context string for LLM analysis
    """
    if not similar_alerts:
        return "No similar historical alerts found for reference."
    
    context_parts = ["Similar Historical Alerts:"]
    
    for i, similar_alert in enumerate(similar_alerts, 1):
        source = similar_alert['_source']
        rule = source.get('rule', {})
        ai_analysis = source.get('ai_analysis', {})
        
        context_parts.append(f"""
{i}. Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')})
   Previous Analysis: {ai_analysis.get('triage_report', 'N/A')[:200]}...
   Risk Assessment: {ai_analysis.get('risk_level', 'N/A')}
        """.strip())
    
    return "\n".join(context_parts)

async def analyze_alert(alert_summary: str, context: str) -> str:
    """
    Invokes the LLM for analysis of the alert.
    
    Args:
        alert_summary: Summary of the alert to analyze
        context: Contextual information from similar alerts
        
    Returns:
        AI analysis report
    """
    try:
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary,
            "context": context
        })
        
        logger.debug(f"LLM analysis completed, result length: {len(analysis_result)}")
        return analysis_result
        
    except Exception as e:
        logger.error(f"LLM analysis failed: {str(e)}")
        raise

async def update_alert_with_analysis(
    alert_index: str,
    alert_id: str,
    analysis: str,
    alert_vector: List[float],
    timestamp: str
) -> None:
    """
    Writes both the analysis and the new vector back to OpenSearch.
    
    Args:
        alert_index: OpenSearch index name
        alert_id: Alert document ID
        analysis: AI analysis report
        alert_vector: Vector representation of the alert
        timestamp: Alert timestamp
    """
    try:
        vector_dimension = len(alert_vector) if alert_vector else 0
        
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis,
                    "provider": LLM_PROVIDER,
                    "timestamp": datetime.utcnow().isoformat(),
                    "vector_dimension": vector_dimension,
                    "processing_time_ms": None  # Could be implemented for performance monitoring
                },
                "alert_vector": alert_vector
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logger.info(f"Successfully updated alert {alert_id} with AI analysis and vector")
        
    except Exception as e:
        logger.error(f"Failed to update alert {alert_id}: {str(e)}")
        raise

async def process_single_alert(alert: Dict[str, Any]) -> None:
    """
    A wrapper for processing one alert through the complete pipeline.
    
    Args:
        alert: Alert document from OpenSearch
    """
    alert_id = alert['_id']
    alert_index = alert['_index']
    alert_source = alert['_source']
    
    try:
        # 1. Build alert summary
        rule = alert_source.get('rule', {})
        agent = alert_source.get('agent', {})
        alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
        
        logger.info(f"Processing alert: {alert_id} - {alert_summary}")
        
        # 2. Vectorize alert
        alert_vector = await vectorize_alert(alert)
        
        # 3. Find similar historical alerts
        similar_alerts = await find_similar_alerts(alert_vector)
        
        # 4. Build analysis context
        context = await build_context(similar_alerts)
        
        # 5. LLM analysis
        analysis_result = await analyze_alert(alert_summary, context)
        
        # 6. Update alert with results
        await update_alert_with_analysis(
            alert_index,
            alert_id,
            analysis_result,
            alert_vector,
            alert_source.get('timestamp')
        )
        
        logger.info(f"Alert {alert_id} processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing alert {alert_id}: {str(e)}")
        raise

async def ensure_index_template() -> None:
    """Ensure OpenSearch index template exists with vector field mapping"""
    template_name = "wazuh-alerts-vector-template"
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
                            "triage_report": {"type": "text"},
                            "provider": {"type": "keyword"},
                            "timestamp": {"type": "date"},
                            "risk_level": {"type": "keyword"},
                            "vector_dimension": {"type": "integer"},
                            "processing_time_ms": {"type": "integer"}
                        }
                    }
                }
            }
        }
    }
    
    try:
        # Check if template already exists
        try:
            await client.indices.get_index_template(name=template_name)
            logger.info(f"Index template {template_name} already exists")
        except Exception:
            # Template doesn't exist, create it
            await client.indices.put_index_template(name=template_name, body=template_body)
            logger.info(f"Successfully created index template: {template_name}")
            
    except Exception as e:
        logger.error(f"Failed to ensure index template: {str(e)}")
        raise

# === Main Processing Function ===

async def triage_new_alerts():
    """
    Main alert triage task - refactored modular version.
    This is the main entry point that orchestrates the entire pipeline.
    """
    print("--- TRIAGE JOB EXECUTING NOW ---")
    logger.info(f"Starting alert analysis using {LLM_PROVIDER} model and Gemini Embedding...")
    
    try:
        # 1. Ensure index template exists
        await ensure_index_template()
        
        # 2. Query new alerts
        alerts = await query_new_alerts(limit=10)
        
        if not alerts:
            print("--- No new alerts found ---")
            logger.info("No new alerts to process")
            return
        
        # 3. Process each alert
        processed_count = 0
        for alert in alerts:
            try:
                await process_single_alert(alert)
                processed_count += 1
                print(f"--- Successfully processed alert {alert['_id']} ---")
            except Exception as e:
                print(f"--- Error processing alert {alert['_id']}: {str(e)} ---")
                logger.error(f"Failed to process alert {alert['_id']}: {str(e)}")
                # Continue processing other alerts even if one fails
                continue
        
        print(f"--- Batch processing completed, processed {processed_count}/{len(alerts)} alerts ---")
        logger.info(f"Batch processing completed, processed {processed_count}/{len(alerts)} alerts")
        
    except Exception as e:
        print(f"!!!!!! Critical error in triage task !!!!!!")
        logger.error(f"Critical error in triage task: {e}", exc_info=True)
        traceback.print_exc()

# === FastAPI Application and Scheduler ===

app = FastAPI(title="Wazuh AI Triage Agent with Vectorization")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():

    logging.info("AI Agent with RAG functionality starting up...")
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logging.info("Scheduler started. RAG Triage job scheduled.")

@app.get("/")
def read_root():
    return {
        "status": "AI Triage Agent with RAG is running", 
        "scheduler_status": str(scheduler.get_jobs()),
        "stage": "Stage 2 - Core RAG Implementation"
    }


@app.on_event("shutdown")
def shutdown_event():
    """Application shutdown event handler"""
    scheduler.shutdown()
    logger.info("Scheduler shut down.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)