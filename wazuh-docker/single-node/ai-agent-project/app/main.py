import os
import logging
import traceback
import asyncio
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

# 2. 提示模板 (維持不變)
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst. Your task is to triage a Wazuh alert based on the alert data and relevant log context.

    **Wazuh Alert:**
    {alert_summary}

    **Relevant Log Context from the same host:**
    {context}

    **Your Analysis Task:**
    1. Briefly summarize the event.
    2. Assess the potential risk level (Critical, High, Medium, Low, Informational).
    3. Provide a clear recommendation for the next step (e.g., "Investigate user activity", "Block IP address", "No action needed").

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

# 在 triage_new_alerts 函式中整合語意搜尋
async def triage_new_alerts():
    print("--- TRIAGE JOB EXECUTING NOW ---")
    logging.info(f"Analyzing alerts with {LLM_PROVIDER} model and Gemini Embedding...")
    try:
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
            
        for alert in alerts:
            alert_id = alert['_id']
            alert_index = alert['_index']
            alert_source = alert['_source']
            rule = alert_source.get('rule', {})
            agent = alert_source.get('agent', {})
            
            alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
            print(f"--- Found alert to process: {alert_id} ---")
            logging.info(f"Found new alert to process: {alert_id} - {alert_summary}")

            # 使用 Gemini Embedding 進行語意搜尋
            try:
                alert_embedding = await embedding_service.embed_query(alert_summary)
                
                # 在 OpenSearch 中進行向量搜尋找相關歷史警報
                vector_search_body = {
                    "query": {
                        "knn": {
                            "alert_embedding": {
                                "vector": alert_embedding,
                                "k": 5
                            }
                        }
                    }
                }
                
                similar_alerts = await client.search(
                    index="wazuh-alerts-*", 
                    body=vector_search_body,
                    size=5
                )
                
                # 構建更豐富的上下文
                context = "相關歷史警報:\n"
                for similar_alert in similar_alerts['hits']['hits']:
                    similar_rule = similar_alert['_source'].get('rule', {})
                    context += f"- {similar_rule.get('description', 'N/A')} (Level: {similar_rule.get('level', 'N/A')})\n"
                
            except Exception as e:
                logging.warning(f"向量搜尋失敗，使用預設上下文: {str(e)}")
                context = "No additional context retrieved for this example."
            
            analysis_result = await chain.ainvoke({
                "alert_summary": alert_summary, 
                "context": context
            })
            
            print(f"--- AI Analysis received: {analysis_result[:100]}... ---")
            logging.info(f"AI Analysis for {alert_id}: {analysis_result}")
            
            # 儲存警報向量以供未來搜尋
            update_body = {
                "doc": {
                    "ai_analysis": {
                        "triage_report": analysis_result, 
                        "provider": LLM_PROVIDER, 
                        "timestamp": alert_source.get('timestamp')
                    },
                    "alert_embedding": alert_embedding  # 儲存向量
                }
            }
            
            await client.update(index=alert_index, id=alert_id, body=update_body)
            print(f"--- Successfully updated alert {alert_id} ---")
            logging.info(f"Successfully updated alert {alert_id} with AI analysis.")
            
    except Exception as e:
        print(f"!!!!!! A CRITICAL ERROR OCCURRED IN TRIAGE JOB !!!!!!")
        logging.error(f"An error occurred during triage: {e}", exc_info=True)
        traceback.print_exc()

# --- FastAPI 應用與排程 (維持不變) ---
app = FastAPI(title="Wazuh AI Triage Agent")
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logging.info("AI Agent starting up...")
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logging.info("Scheduler started. Triage job scheduled.")

@app.get("/")
def read_root():
    return {"status": "AI Triage Agent is running", "scheduler_status": str(scheduler.get_jobs())}

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logging.info("Scheduler shut down.")