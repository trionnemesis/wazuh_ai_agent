import os
import logging
import traceback
import asyncio
from typing import List, Dict, Any, Optional
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

# --- 初始化 Embedding 服務 ---
embedding_service = GeminiEmbeddingService()

# === 模組化函式實現 ===

async def ensure_index_template():
    """確保 OpenSearch 索引範本包含向量欄位"""
    template_name = "wazuh-alerts-vector-template"
    template_body = {
        "index_patterns": ["wazuh-alerts-*"],
        "priority": 1,
        "template": {
            "mappings": {
                "properties": {
                    "alert_vector": {
                        "type": "dense_vector",
                        "dims": 768,  # Gemini text-embedding-004 預設維度
                        "index": True,
                        "similarity": "cosine"
                    },
                    "ai_analysis": {
                        "type": "object",
                        "properties": {
                            "triage_report": {"type": "text"},
                            "provider": {"type": "keyword"},
                            "timestamp": {"type": "date"},
                            "risk_level": {"type": "keyword"},
                            "vector_dimension": {"type": "integer"}
                        }
                    }
                }
            }
        }
    }
    
    try:
        # 檢查範本是否已存在
        existing_template = await client.indices.get_index_template(name=template_name)
        logging.info(f"索引範本 {template_name} 已存在，跳過建立")
    except Exception:
        # 範本不存在，建立新範本
        try:
            await client.indices.put_index_template(name=template_name, body=template_body)
            logging.info(f"成功建立索引範本: {template_name}")
        except Exception as e:
            logging.error(f"建立索引範本失敗: {str(e)}")
            raise

async def query_new_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """查詢尚未分析的新警報"""
    try:
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
        logging.info(f"找到 {len(alerts)} 個新警報待處理")
        return alerts
    except Exception as e:
        logging.error(f"查詢新警報失敗: {str(e)}")
        raise

async def vectorize_alert(alert_data: Dict[str, Any]) -> List[float]:
    """將警報內容向量化"""
    try:
        alert_source = alert_data['_source']
        
        # 使用專門的警報內容向量化方法
        alert_vector = await embedding_service.embed_alert_content(alert_source)
        
        logging.debug(f"警報 {alert_data['_id']} 向量化完成，維度: {len(alert_vector)}")
        return alert_vector
        
    except Exception as e:
        logging.error(f"警報向量化失敗: {str(e)}")
        raise

async def find_similar_alerts(alert_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
    """使用向量搜尋找相似的歷史警報"""
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
        logging.debug(f"找到 {len(similar_alerts)} 個相似的歷史警報")
        return similar_alerts
        
    except Exception as e:
        logging.warning(f"向量搜尋失敗: {str(e)}")
        return []

async def build_context(similar_alerts: List[Dict[str, Any]]) -> str:
    """根據相似警報構建分析上下文"""
    if not similar_alerts:
        return "No similar historical alerts found for reference."
    
    context_parts = ["相關歷史警報分析:"]
    
    for i, similar_alert in enumerate(similar_alerts, 1):
        source = similar_alert['_source']
        rule = source.get('rule', {})
        ai_analysis = source.get('ai_analysis', {})
        
        context_parts.append(f"""
{i}. Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')})
   Previous Analysis: {ai_analysis.get('triage_report', 'N/A')[:200]}...
        """.strip())
    
    return "\n".join(context_parts)

async def analyze_alert(alert_summary: str, context: str) -> str:
    """使用 LLM 分析警報"""
    try:
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary, 
            "context": context
        })
        
        logging.debug(f"LLM 分析完成，結果長度: {len(analysis_result)}")
        return analysis_result
        
    except Exception as e:
        logging.error(f"LLM 分析失敗: {str(e)}")
        raise

async def update_alert_with_analysis(
    alert_index: str, 
    alert_id: str, 
    analysis: str, 
    alert_vector: List[float],
    timestamp: str
) -> None:
    """更新警報，加入 AI 分析結果和向量"""
    try:
        # 獲取向量維度
        vector_dimension = len(alert_vector) if alert_vector else 0
        
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis,
                    "provider": LLM_PROVIDER,
                    "timestamp": timestamp,
                    "vector_dimension": vector_dimension
                },
                "alert_vector": alert_vector
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logging.info(f"成功更新警報 {alert_id}，包含 AI 分析和向量")
        
    except Exception as e:
        logging.error(f"更新警報失敗: {str(e)}")
        raise

async def process_single_alert(alert: Dict[str, Any]) -> None:
    """處理單個警報的完整流程"""
    alert_id = alert['_id']
    alert_index = alert['_index']
    alert_source = alert['_source']
    
    try:
        # 1. 構建警報摘要
        rule = alert_source.get('rule', {})
        agent = alert_source.get('agent', {})
        alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
        
        logging.info(f"開始處理警報: {alert_id} - {alert_summary}")
        
        # 2. 向量化警報
        alert_vector = await vectorize_alert(alert)
        
        # 3. 搜尋相似的歷史警報
        similar_alerts = await find_similar_alerts(alert_vector)
        
        # 4. 構建分析上下文
        context = await build_context(similar_alerts)
        
        # 5. LLM 分析
        analysis_result = await analyze_alert(alert_summary, context)
        
        # 6. 更新警報
        await update_alert_with_analysis(
            alert_index, 
            alert_id, 
            analysis_result, 
            alert_vector,
            alert_source.get('timestamp')
        )
        
        logging.info(f"警報 {alert_id} 處理完成")
        
    except Exception as e:
        logging.error(f"處理警報 {alert_id} 時發生錯誤: {str(e)}")
        raise

async def triage_new_alerts():
    """主要的警報分流任務 - 重構後的模組化版本"""
    print("--- TRIAGE JOB EXECUTING NOW ---")
    logging.info(f"開始使用 {LLM_PROVIDER} 模型和 Gemini Embedding 分析警報...")
    
    try:
        # 1. 確保索引範本存在
        await ensure_index_template()
        
        # 2. 查詢新警報
        alerts = await query_new_alerts(limit=10)
        
        if not alerts:
            print("--- 未找到新警報 ---")
            logging.info("未找到新警報")
            return
        
        # 3. 處理每個警報
        for alert in alerts:
            try:
                await process_single_alert(alert)
                print(f"--- 成功處理警報 {alert['_id']} ---")
            except Exception as e:
                print(f"--- 處理警報 {alert['_id']} 時發生錯誤: {str(e)} ---")
                # 記錄錯誤但繼續處理其他警報
                continue
        
        print(f"--- 批次處理完成，共處理 {len(alerts)} 個警報 ---")
        logging.info(f"批次處理完成，共處理 {len(alerts)} 個警報")
        
    except Exception as e:
        print(f"!!!!!! 分流任務發生嚴重錯誤 !!!!!!")
        logging.error(f"分流任務發生錯誤: {e}", exc_info=True)
        traceback.print_exc()

# --- FastAPI 應用與排程 (維持不變) ---
app = FastAPI(title="Wazuh AI Triage Agent")
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logging.info("AI Agent starting up...")
    # 啟動時先確保索引範本存在
    try:
        await ensure_index_template()
    except Exception as e:
        logging.error(f"啟動時建立索引範本失敗: {str(e)}")
    
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logging.info("Scheduler started. Triage job scheduled.")

@app.get("/")
def read_root():
    return {"status": "AI Triage Agent is running", "scheduler_status": str(scheduler.get_jobs())}

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    try:
        # 檢查 OpenSearch 連線
        await client.cluster.health()
        
        # 檢查 embedding 服務
        test_vector = await embedding_service.embed_query("test")
        
        return {
            "status": "healthy",
            "opensearch": "connected",
            "embedding_service": "working",
            "vector_dimension": len(test_vector),
            "llm_provider": LLM_PROVIDER
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logging.info("Scheduler shut down.")