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

# --- 新增 Embedding 服務 ---
from embedding_service import GeminiEmbeddingService

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
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY)
    
    elif LLM_PROVIDER == 'anthropic':
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set.")
        return ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=ANTHROPIC_API_KEY)
    
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. Please choose 'gemini' or 'anthropic'.")

# --- 新增: 檢索模組 (Retrieval Module) ---
class AlertRetrievalModule:
    """專門負責相似警報檢索的模組"""
    
    def __init__(self, opensearch_client: AsyncOpenSearch):
        self.client = opensearch_client
        logging.info("AlertRetrievalModule initialized")
    
    async def retrieve_similar_alerts(self, query_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """
        執行 k-NN 搜尋，找出 N 筆最相似的歷史警報
        
        Args:
            query_vector: 查詢向量
            k: 返回相似警報的數量
            
        Returns:
            List of similar alerts with metadata and scores
        """
        try:
            vector_search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "alert_vector": {
                                        "vector": query_vector,
                                        "k": k
                                    }
                                }
                            }
                        ],
                        "filter": [
                            # 只檢索已經有AI分析的歷史警報
                            {"exists": {"field": "ai_analysis"}}
                        ]
                    }
                },
                "_source": {
                    "includes": [
                        "rule.description", "rule.level", "rule.id",
                        "agent.name", "agent.ip", 
                        "timestamp", "ai_analysis.triage_report",
                        "location", "full_log"
                    ]
                }
            }
            
            response = await self.client.search(
                index="wazuh-alerts-*", 
                body=vector_search_body,
                size=k
            )
            
            similar_alerts = response['hits']['hits']
            logging.info(f"✅ 檢索模組找到 {len(similar_alerts)} 筆相似歷史警報")
            
            # 記錄檢索詳情用於除錯
            for i, alert in enumerate(similar_alerts):
                score = alert.get('_score', 0)
                rule_desc = alert['_source'].get('rule', {}).get('description', 'N/A')
                logging.info(f"  相似警報 #{i+1}: 分數={score:.4f}, 規則={rule_desc[:50]}")
                
            return similar_alerts
            
        except Exception as e:
            logging.warning(f"❌ 檢索模組執行失敗: {str(e)}")
            return []
    
    def format_historical_context(self, similar_alerts: List[Dict[str, Any]]) -> str:
        """
        格式化檢索到的歷史警報，準備注入到 prompt 中
        
        Args:
            similar_alerts: 相似警報列表
            
        Returns:
            格式化後的歷史警報上下文字串
        """
        if not similar_alerts:
            return "目前沒有找到相關的歷史警報可供參考。"
        
        context_parts = ["以下是相關的歷史警報分析參考：\n"]
        
        for i, alert in enumerate(similar_alerts, 1):
            source = alert['_source']
            rule = source.get('rule', {})
            agent = source.get('agent', {})
            ai_analysis = source.get('ai_analysis', {})
            score = alert.get('_score', 0)
            
            # 格式化每個歷史警報
            context_parts.append(f"【歷史警報 #{i}】(相似度: {score:.3f})")
            context_parts.append(f"規則: {rule.get('description', 'N/A')} (等級: {rule.get('level', 'N/A')})")
            context_parts.append(f"主機: {agent.get('name', 'N/A')} ({agent.get('ip', 'N/A')})")
            context_parts.append(f"時間: {source.get('timestamp', 'N/A')}")
            
            # 包含之前的AI分析結果
            if ai_analysis.get('triage_report'):
                triage_summary = ai_analysis['triage_report'][:200] + "..." if len(ai_analysis['triage_report']) > 200 else ai_analysis['triage_report']
                context_parts.append(f"之前分析: {triage_summary}")
            
            context_parts.append("---")
        
        formatted_context = "\n".join(context_parts)
        logging.info(f"✅ 格式化了 {len(similar_alerts)} 筆歷史警報上下文，總長度: {len(formatted_context)} 字元")
        
        return formatted_context

# --- LangChain 元件 ---
llm = get_llm()

# --- 修改後的 Prompt Template (包含歷史警報上下文) ---
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst with access to historical alert analysis. Your task is to triage a new Wazuh alert by leveraging both the current alert data and relevant historical context.

    **Relevant Historical Alerts:**
    {historical_context}

    **Current Wazuh Alert to Analyze:**
    {alert_summary}

    **Additional Context from the same host:**
    {context}

    **Your Enhanced Analysis Task:**
    1. **Event Summary**: Briefly describe what happened in this alert.
    2. **Historical Pattern Analysis**: Based on the historical alerts above, identify any patterns, trends, or recurring issues.
    3. **Risk Assessment**: Assess the potential risk level (Critical, High, Medium, Low, Informational) considering both current alert and historical context.
    4. **Contextual Insights**: Provide insights based on historical data (e.g., "This source IP has triggered 3 similar alerts in the past 24 hours").
    5. **Actionable Recommendation**: Provide a clear, specific recommendation for the next step based on the comprehensive analysis.

    **Your Enhanced Triage Report:**
    """
)

output_parser = StrOutputParser()
chain = prompt_template | llm | output_parser

# --- 初始化 Embedding 服務 ---
embedding_service = GeminiEmbeddingService()

# --- 初始化檢索模組 ---
retrieval_module = AlertRetrievalModule(client)

# --- 模組化函式 ---

async def query_new_alerts(max_alerts: int = 10) -> List[Dict[str, Any]]:
    """查詢尚未進行 AI 分析的新警報"""
    try:
        response = await client.search(
            index="wazuh-alerts-*", 
            body={
                "query": {
                    "bool": {
                        "must_not": [{"exists": {"field": "ai_analysis"}}]
                    }
                }
            }, 
            size=max_alerts
        )
        alerts = response['hits']['hits']
        logging.info(f"Found {len(alerts)} new alerts to process")
        return alerts
    except Exception as e:
        logging.error(f"Error querying new alerts: {e}")
        raise

async def vectorize_alert(alert_source: Dict[str, Any]) -> List[float]:
    """將警報內容轉換為向量"""
    try:
        rule = alert_source.get('rule', {})
        agent = alert_source.get('agent', {})
        
        # 構建用於向量化的警報摘要
        alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
        
        # 使用 Gemini Embedding 進行向量化
        alert_vector = await embedding_service.embed_query(alert_summary)
        logging.info(f"Successfully vectorized alert: {alert_summary[:50]}...")
        return alert_vector
    except Exception as e:
        logging.error(f"Error vectorizing alert: {e}")
        raise

async def find_similar_alerts(alert_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
    """使用向量搜尋找出相似的歷史警報 (舊版本，已被檢索模組取代)"""
    try:
        vector_search_body = {
            "query": {
                "knn": {
                    "alert_vector": {
                        "vector": alert_vector,
                        "k": k
                    }
                }
            }
        }
        
        similar_alerts = await client.search(
            index="wazuh-alerts-*", 
            body=vector_search_body,
            size=k
        )
        
        logging.info(f"Found {len(similar_alerts['hits']['hits'])} similar alerts")
        return similar_alerts['hits']['hits']
    except Exception as e:
        logging.warning(f"Vector search failed, using empty context: {str(e)}")
        return []

def build_context_from_similar_alerts(similar_alerts: List[Dict[str, Any]]) -> str:
    """從相似警報構建上下文資訊 (舊版本，已被檢索模組取代)"""
    if not similar_alerts:
        return "No additional context retrieved for this example."
    
    context = "相關歷史警報:\n"
    for similar_alert in similar_alerts:
        similar_rule = similar_alert['_source'].get('rule', {})
        context += f"- {similar_rule.get('description', 'N/A')} (Level: {similar_rule.get('level', 'N/A')})\n"
    
    return context

async def analyze_alert(alert_summary: str, historical_context: str, context: str) -> str:
    """使用 LLM 分析警報 (更新版本，包含歷史上下文)"""
    try:
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary, 
            "historical_context": historical_context,
            "context": context
        })
        logging.info(f"AI Analysis completed: {analysis_result[:100]}...")
        return analysis_result
    except Exception as e:
        logging.error(f"Error analyzing alert: {e}")
        raise

async def update_alert_with_analysis_and_vector(
    alert_index: str, 
    alert_id: str, 
    alert_source: Dict[str, Any],
    analysis_result: str, 
    alert_vector: List[float]
) -> None:
    """更新警報，加入 AI 分析結果和向量"""
    try:
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis_result, 
                    "provider": LLM_PROVIDER, 
                    "timestamp": alert_source.get('timestamp')
                },
                "alert_vector": alert_vector
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logging.info(f"Successfully updated alert {alert_id} with AI analysis and vector")
    except Exception as e:
        logging.error(f"Error updating alert {alert_id}: {e}")
        raise

async def process_single_alert(alert: Dict[str, Any]) -> None:
    """處理單一警報的完整流程 (整合檢索模組)"""
    alert_id = alert['_id']
    alert_index = alert['_index']
    alert_source = alert['_source']
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    
    alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
    
    logging.info(f"🔍 Processing alert: {alert_id} - {alert_summary}")
    
    try:
        # 步驟 1: 向量化警報
        logging.info(f"📊 Step 1: 向量化警報 {alert_id}")
        alert_vector = await vectorize_alert(alert_source)
        
        # 步驟 2: 使用檢索模組搜尋相似警報
        logging.info(f"🔎 Step 2: 使用檢索模組搜尋相似歷史警報")
        similar_alerts = await retrieval_module.retrieve_similar_alerts(alert_vector, k=5)
        
        # 步驟 3: 格式化歷史警報上下文
        logging.info(f"📝 Step 3: 格式化歷史警報上下文")
        historical_context = retrieval_module.format_historical_context(similar_alerts)
        
        # 步驟 4: 構建額外上下文 (同主機相關日誌)
        context = "No additional host context available"  # 可以在未來擴展
        
        # 步驟 5: AI 分析 (包含歷史上下文)
        logging.info(f"🤖 Step 5: AI 分析 (含歷史上下文)")
        analysis_result = await analyze_alert(alert_summary, historical_context, context)
        
        # 步驟 6: 更新警報
        logging.info(f"💾 Step 6: 更新警報到 OpenSearch")
        await update_alert_with_analysis_and_vector(
            alert_index, alert_id, alert_source, analysis_result, alert_vector
        )
        
        logging.info(f"✅ Successfully processed alert {alert_id}")
        
    except Exception as e:
        logging.error(f"❌ Error processing alert {alert_id}: {e}")
        raise

async def triage_new_alerts():
    """主要的 triage 工作流程 (整合檢索模組)"""
    print("--- 🚀 TRIAGE JOB EXECUTING WITH RETRIEVAL MODULE ---")
    logging.info(f"Analyzing alerts with {LLM_PROVIDER} model and Gemini Embedding + Retrieval Module...")
    
    try:
        # 查詢新警報
        alerts = await query_new_alerts()
        
        if not alerts:
            print("--- No new alerts found. ---")
            logging.info("No new alerts found.")
            return
        
        print(f"--- 📊 Found {len(alerts)} new alerts to process with RAG ---")
        
        # 處理每個警報
        for i, alert in enumerate(alerts, 1):
            print(f"--- 🔄 Processing alert {i}/{len(alerts)} ---")
            await process_single_alert(alert)
            
        print(f"--- ✅ Successfully processed {len(alerts)} alerts with enhanced RAG analysis ---")
            
    except Exception as e:
        print(f"!!!!!! A CRITICAL ERROR OCCURRED IN TRIAGE JOB !!!!!!")
        logging.error(f"An error occurred during triage: {e}", exc_info=True)
        traceback.print_exc()

# --- FastAPI 應用與排程 ---
app = FastAPI(title="Wazuh AI Triage Agent with RAG")
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logging.info("🚀 AI Agent with RAG starting up...")
    # 確保 OpenSearch 索引模板存在
    await ensure_index_template()
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logging.info("✅ Scheduler started. Triage job with RAG scheduled.")

async def ensure_index_template():
    """確保 wazuh-alerts 索引模板包含 alert_vector 欄位"""
    try:
        template_name = "wazuh-alerts-template"
        template_body = {
            "index_patterns": ["wazuh-alerts-*"],
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.knn": True  # 啟用 KNN 搜尋
            },
            "mappings": {
                "properties": {
                    "alert_vector": {
                        "type": "knn_vector",
                        "dimension": embedding_service.dimension or 768,  # 使用 embedding service 的維度
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib"
                        }
                    },
                    "ai_analysis": {
                        "properties": {
                            "triage_report": {"type": "text"},
                            "provider": {"type": "keyword"},
                            "timestamp": {"type": "date"}
                        }
                    }
                }
            }
        }
        
        # 檢查模板是否存在
        try:
            await client.indices.get_template(name=template_name)
            logging.info(f"Index template {template_name} already exists")
        except Exception:
            # 模板不存在，建立新模板
            await client.indices.put_template(name=template_name, body=template_body)
            logging.info(f"Created index template: {template_name}")
            
    except Exception as e:
        logging.error(f"Error ensuring index template: {e}")

@app.get("/")
def read_root():
    return {
        "status": "AI Triage Agent with RAG is running", 
        "features": ["Vector Retrieval", "Historical Context", "Enhanced Analysis"],
        "scheduler_status": str(scheduler.get_jobs())
    }

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    try:
        # 檢查 OpenSearch 連接
        await client.info()
        return {
            "status": "healthy",
            "opensearch": "connected",
            "llm_provider": LLM_PROVIDER,
            "embedding_dimension": embedding_service.dimension or 768,
            "retrieval_module": "active"
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