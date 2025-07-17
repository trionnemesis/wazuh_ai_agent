import os
import logging
import traceback
import asyncio
from datetime import datetime
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

# Stage 2: Updated Prompt Template for RAG with Historical Context
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
                                "alert_vector": {  # 使用一致的字段名稱
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
            },
            "_source": ["rule", "agent", "ai_analysis", "timestamp"]  # 只獲取需要的字段
        }
        
        logger.info(f"Executing k-NN search for {k} similar alerts")
        logger.debug(f"k-NN query: {knn_search_body}")
        
        # 執行搜尋
        response = await client.search(
            index="wazuh-alerts-*",
            body=knn_search_body
        )
        
        similar_alerts = response.get('hits', {}).get('hits', [])
        logger.info(f"Found {len(similar_alerts)} similar historical alerts")
        
        return similar_alerts
        
    except Exception as e:
        logger.error(f"Error in find_similar_alerts: {str(e)}")
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
    logger.info(f"Processing alert {alert_id}: {alert_summary}")

    try:
        # 步驟 2: 向量化新警報
        logger.info(f"Vectorizing alert {alert_id}")
        alert_vector = await embedding_service.embed_alert_content(alert_source)
        
        # 步驟 3: 檢索相似歷史警報
        logger.info(f"Retrieving similar alerts for {alert_id}")
        similar_alerts = await find_similar_alerts(alert_vector, k=5)
        
        # 步驟 4: 格式化歷史上下文
        historical_context = format_historical_context(similar_alerts)
        
        # 步驟 5: 調用 LLM 分析 (包含歷史上下文)
        logger.info(f"Generating AI analysis for {alert_id} with historical context")
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary,
            "historical_context": historical_context
        })
        
        logger.info(f"AI Analysis generated for {alert_id}: {analysis_result[:100]}...")
        
        # 步驟 6: 更新 OpenSearch 文檔
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis_result,
                    "provider": LLM_PROVIDER,
                    "timestamp": datetime.utcnow().isoformat(),
                    "similar_alerts_count": len(similar_alerts)
                },
                "alert_vector": alert_vector  # 儲存向量以供未來檢索
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logger.info(f"Successfully updated alert {alert_id} with RAG-enhanced analysis")
        
    except Exception as e:
        logger.error(f"Error processing alert {alert_id}: {str(e)}")
        raise

async def query_new_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Query OpenSearch for new alerts that haven't been analyzed yet.
    
    Args:
        limit: Maximum number of alerts to retrieve
        
    Returns:
        List of alert documents
    """
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
        
    except Exception as e:
        logger.error(f"Failed to query new alerts: {str(e)}")
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
                            "similar_alerts_count": {"type": "integer"}
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
    Stage 2: 修改主要 triage 函式以使用新的 RAG 流程
    """
    print("--- TRIAGE JOB EXECUTING WITH RAG FUNCTIONALITY ---")
    logger.info(f"Analyzing alerts with {LLM_PROVIDER} model and RAG retrieval...")
    
    try:
        # 1. Ensure index template exists
        await ensure_index_template()
        
        # 2. Query new alerts
        alerts = await query_new_alerts(limit=10)
        
        if not alerts:
            print("--- No new alerts found. ---")
            logger.info("No new alerts found.")
            return
            
        logger.info(f"Found {len(alerts)} new alerts to process with RAG")
        
        # 3. Process each alert using new RAG workflow
        processed_count = 0
        for alert in alerts:
            try:
                await process_single_alert(alert)
                processed_count += 1
                print(f"--- Successfully processed alert {alert['_id']} with RAG ---")
            except Exception as e:
                print(f"--- Error processing alert {alert['_id']}: {str(e)} ---")
                logger.error(f"Failed to process alert {alert['_id']}: {str(e)}")
                continue
        
        print(f"--- RAG batch processing completed: {processed_count}/{len(alerts)} alerts ---")
        logger.info(f"RAG batch processing completed: {processed_count}/{len(alerts)} alerts")
        
    except Exception as e:
        print(f"!!!!!! A CRITICAL ERROR OCCURRED IN RAG TRIAGE JOB !!!!!!")
        logger.error(f"An error occurred during RAG triage: {e}", exc_info=True)
        traceback.print_exc()

# === FastAPI Application and Scheduler ===

app = FastAPI(title="Wazuh AI Triage Agent - Stage 2 RAG")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logger.info("AI Agent with RAG functionality starting up...")
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logger.info("Scheduler started. RAG Triage job scheduled.")

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