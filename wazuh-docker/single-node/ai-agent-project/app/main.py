import os
import logging
import traceback
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# <--- 新增: 匯入新的 LLM 類別 ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# --- 基礎設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 從環境變數讀取配置 ---
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

# <--- 修改: 讀取 LLM 供應商和對應的 Keys ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower() # 預設為 anthropic
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# --- OpenSearch 客戶端 ---
client = AsyncOpenSearch(
    hosts=[OPENSEARCH_URL],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=AsyncHttpConnection
)

# <--- 新增: 根據環境變數選擇 LLM 的函式 ---
def get_llm():
    """根據環境變數 LLM_PROVIDER 選擇並初始化 LLM"""
    logging.info(f"Selected LLM Provider: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == 'gemini':
        if not GEMINI_API_KEY:
            raise ValueError("LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set.")
        # Gemini 1.5 Flash 是速度和成本效益的絕佳選擇
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY)
    
    elif LLM_PROVIDER == 'anthropic':
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set.")
        # Claude 3 Haiku 是最快、最經濟的 Claude 模型，非常適合入門
        return ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=ANTHROPIC_API_KEY)
        # 備選模型:
        # return ChatAnthropic(model="claude-3-sonnet-20240229", anthropic_api_key=ANTHROPIC_API_KEY)
    
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. Please choose 'gemini' or 'anthropic'.")

# --- LangChain 元件 ---
# 1. LLM 模型 (透過新函式動態選擇)
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

# 3. 輸出解析器
output_parser = StrOutputParser()

# 4. 組成 LangChain 鏈
chain = prompt_template | llm | output_parser

# --- 新增 Embedding 服務 ---
from embedding_service import GeminiEmbeddingService

# --- 新增 Embedding 服務 ---
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
            body={"query": {"bool": {"must_not": [{"exists": {"field": "ai_analysis"}}]}}}, 
            size=10
        )
        alerts = response['hits']['hits']
        
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
    scheduler.shutdown()
    logging.info("Scheduler shut down.")