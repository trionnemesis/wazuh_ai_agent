import os
import logging
import traceback
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

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

# 2. 提示模板 - 更新為支援 RAG 的版本
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst. Analyze the new Wazuh alert below, using the provided historical context from similar past alerts to inform your assessment.

    **Relevant Historical Alerts:**
    {historical_context}

    **New Wazuh Alert to Analyze:**
    {alert_summary}

    **Your Analysis Task:**
    1. Briefly summarize the new event.
    2. Assess its risk level (Critical, High, Medium, Low, Informational), considering any patterns from the historical context.
    3. Provide a clear, context-aware recommendation that references similar past incidents when relevant.

    **Guidelines:**
    - If historical alerts show similar patterns, mention them explicitly (e.g., "This is the 3rd SSH failure from this IP in recent hours")
    - Consider the frequency and timing of similar alerts when assessing risk
    - Provide actionable recommendations based on past successful resolutions

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
    
    # 獲取實際的向量維度
    vector_dimension = embedding_service.get_vector_dimension()
    
    template_body = {
        "index_patterns": ["wazuh-alerts-*"],
        "priority": 1,
        "template": {
            "mappings": {
                "properties": {
                    "alert_vector": {
                        "type": "knn_vector",
                        "dimension": vector_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib"
                        }
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
            logging.info(f"成功建立索引範本: {template_name}，向量維度: {vector_dimension}")
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

async def find_similar_alerts(query_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
    """使用 k-NN 搜尋找相似的歷史警報 - Stage 2 RAG 實現"""
    try:
        # 構建 k-NN 搜尋查詢，目標 alert_vector 欄位，使用 cosine similarity
        knn_search_body = {
            "size": k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "exists": {"field": "ai_analysis"}
                        }
                    ]
                }
            },
            "knn": {
                "field": "alert_vector",
                "query_vector": query_vector,
                "k": k,
                "num_candidates": k * 2  # 搜尋更多候選者以提高相關性
            },
            "_source": [
                "rule.description", 
                "rule.level", 
                "rule.id",
                "rule.groups",
                "agent.name", 
                "ai_analysis.triage_report",
                "ai_analysis.risk_level",
                "timestamp",
                "data"
            ]
        }
        
        logging.info(f"執行 k-NN 搜尋查詢，k={k}，向量維度={len(query_vector)}")
        
        similar_alerts_response = await client.search(
            index="wazuh-alerts-*", 
            body=knn_search_body
        )
        
        similar_alerts = similar_alerts_response['hits']['hits']
        
        # 記錄搜尋結果
        logging.info(f"k-NN 搜尋找到 {len(similar_alerts)} 個相似的歷史警報")
        
        if similar_alerts:
            # 記錄相似度分數以便調試
            for i, alert in enumerate(similar_alerts):
                score = alert.get('_score', 'N/A')
                rule_desc = alert['_source'].get('rule', {}).get('description', 'N/A')
                logging.debug(f"相似警報 {i+1}: 分數={score}, 規則={rule_desc[:50]}")
        
        return similar_alerts
        
    except Exception as e:
        logging.warning(f"k-NN 向量搜尋失敗: {str(e)}")
        return []

def format_historical_context(alerts: List[Dict[str, Any]]) -> str:
    """格式化歷史警報上下文 - Stage 2 專用格式化函式"""
    if not alerts:
        return "No similar historical alerts found for reference."
    
    context_parts = [f"Found {len(alerts)} similar historical alerts for context:"]
    context_parts.append("=" * 60)
    
    for i, alert in enumerate(alerts, 1):
        source = alert['_source']
        rule = source.get('rule', {})
        agent = source.get('agent', {})
        ai_analysis = source.get('ai_analysis', {})
        timestamp = source.get('timestamp', 'Unknown')
        score = alert.get('_score', 'N/A')
        
        # 提取重要資訊
        rule_desc = rule.get('description', 'N/A')
        rule_level = rule.get('level', 'N/A')
        rule_groups = ', '.join(rule.get('groups', [])) if rule.get('groups') else 'N/A'
        host_name = agent.get('name', 'N/A')
        previous_analysis = ai_analysis.get('triage_report', 'N/A')
        risk_level = ai_analysis.get('risk_level', 'N/A')
        
        # 截斷過長的分析報告
        if len(previous_analysis) > 200:
            previous_analysis = previous_analysis[:200] + "..."
        
        context_entry = f"""
Alert #{i} (Similarity Score: {score})
├─ Time: {timestamp}
├─ Rule: {rule_desc} (Level: {rule_level})
├─ Groups: {rule_groups}
├─ Host: {host_name}
├─ Previous Risk Assessment: {risk_level}
└─ Previous Analysis: {previous_analysis}
        """.strip()
        
        context_parts.append(context_entry)
        
        if i < len(alerts):
            context_parts.append("-" * 40)
    
    return "\n".join(context_parts)

async def analyze_alert(alert_summary: str, historical_context: str) -> str:
    """使用 LLM 分析警報，包含歷史上下文"""
    try:
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary, 
            "historical_context": historical_context
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
    """處理單個警報的完整流程 - Stage 2 RAG 增強版本"""
    alert_id = alert['_id']
    alert_index = alert['_index']
    alert_source = alert['_source']
    
    try:
        # 1. 構建警報摘要
        rule = alert_source.get('rule', {})
        agent = alert_source.get('agent', {})
        alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
        
        logging.info(f"開始處理警報: {alert_id} - {alert_summary}")
        
        # 2. 向量化新警報
        alert_vector = await vectorize_alert(alert)
        
        # 3. 檢索：使用 k-NN 搜尋相似的歷史警報
        similar_alerts = await find_similar_alerts(alert_vector, k=5)
        
        # 4. 格式化：構建歷史上下文
        historical_context = format_historical_context(similar_alerts)
        
        logging.info(f"為警報 {alert_id} 構建了包含 {len(similar_alerts)} 個相似警報的歷史上下文")
        
        # 5. 分析：將新警報和歷史上下文送至 LLM
        analysis_result = await analyze_alert(alert_summary, historical_context)
        
        # 6. 更新：將結果寫回 OpenSearch
        await update_alert_with_analysis(
            alert_index, 
            alert_id, 
            analysis_result, 
            alert_vector,
            alert_source.get('timestamp')
        )
        
        logging.info(f"警報 {alert_id} RAG 分析完成")
        
    except Exception as e:
        logging.error(f"處理警報 {alert_id} 時發生錯誤: {str(e)}")
        raise

async def triage_new_alerts():
    """主要的警報分流任務 - Stage 2 RAG 版本"""
    print("--- RAG TRIAGE JOB EXECUTING NOW ---")
    logging.info(f"開始使用 {LLM_PROVIDER} 模型和 Gemini Embedding 進行 RAG 分析...")
    
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
        processed_count = 0
        for alert in alerts:
            try:
                await process_single_alert(alert)
                processed_count += 1
                print(f"--- 成功處理警報 {alert['_id']} (包含 RAG 上下文) ---")
            except Exception as e:
                print(f"--- 處理警報 {alert['_id']} 時發生錯誤: {str(e)} ---")
                # 記錄錯誤但繼續處理其他警報
                continue
        
        print(f"--- RAG 批次處理完成，共處理 {processed_count}/{len(alerts)} 個警報 ---")
        logging.info(f"RAG 批次處理完成，共處理 {processed_count}/{len(alerts)} 個警報")
        
    except Exception as e:
        print(f"!!!!!! RAG 分流任務發生嚴重錯誤 !!!!!!")
        logging.error(f"RAG 分流任務發生錯誤: {e}", exc_info=True)
        traceback.print_exc()

# --- FastAPI 應用與排程 (維持不變) ---
app = FastAPI(title="Wazuh AI Triage Agent - Stage 2 RAG")
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logging.info("AI Agent (Stage 2 RAG) starting up...")
    # 啟動時先確保索引範本存在
    try:
        await ensure_index_template()
    except Exception as e:
        logging.error(f"啟動時建立索引範本失敗: {str(e)}")
    
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logging.info("Scheduler started. RAG Triage job scheduled.")

@app.get("/")
def read_root():
    return {
        "status": "AI Triage Agent (Stage 2 RAG) is running", 
        "scheduler_status": str(scheduler.get_jobs()),
        "rag_features": ["k-NN vector search", "historical context", "enhanced prompts"]
    }

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    try:
        # 檢查 OpenSearch 連線
        await client.cluster.health()
        
        # 檢查 embedding 服務
        test_vector = await embedding_service.embed_query("test")
        
        # 測試 k-NN 搜尋功能
        try:
            test_search = await find_similar_alerts(test_vector, k=1)
            knn_status = "working" if isinstance(test_search, list) else "failed"
        except Exception:
            knn_status = "failed"
        
        return {
            "status": "healthy",
            "opensearch": "connected",
            "embedding_service": "working",
            "knn_search": knn_status,
            "vector_dimension": len(test_vector),
            "llm_provider": LLM_PROVIDER,
            "stage": "2 - RAG Implementation"
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